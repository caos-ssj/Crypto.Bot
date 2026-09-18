# Bug #020: El límite de pérdida diaria se agrupa por día UTC mientras el dashboard muestra hora local

**Severidad:** Baja
**Módulo:** Persistencia / Dashboard (`src/storage.py:347-361` → `dashboard.py:128`)
**Entorno:** v2.1, cualquier horizonte de inversión con operaciones a caballo de la medianoche
**Fecha:** 2026-09-18

## Descripción

`get_today_realized_loss` agrupa las pérdidas del día con `date('now')` de
SQLite (**UTC**). En cambio, el dashboard convierte las marcas a la **hora
local** del observador. Para zonas distintas de UTC (típico en LatAm/Europa), el
"día" del límite de 0.5 SOL no coincide con el "día" que el operador ve en
pantalla: una pérdida a las 21:00 UTC−3 (18:00) pertenece al día de mañana en
UTC, y el límite se reinicia a las 00:00 UTC = 21:00 del día local anterior.

## Pasos para reproducir

1. TZ distinta a UTC (ej. America/Argentina/Buenos_Aires, UTC−3).
2. Cerrar una posición perdedora a las 23:00 hora local (02:00 UTC del día
   siguiente).
3. Abrir dashboard: la columna "CERRADA" muestra 23:00 de hoy, pero
   `get_today_realized_loss` ya no la cuenta hoy; cuenta desde las 21:00 local
   del día anterior.

## Resultado esperado

Un único concepto de "día" consistente entre el límite de riesgo, la
persistencia y el dashboard — preferentemente **configurable y explícito**.

## Resultado obtenido

- El límite y la UI viven en calendarios distintos (UTC vs local).
- El tope de 0.5 SOL puede "recargarse" a las 21:00 local que el usuario aún
  considera ayer, o al revés, solaparse dos días a la vez.

## Causa raíz

```sql
-- src/storage.py:353-358
WHERE status = 'closed' AND pnl_sol < 0
AND date(substr(closed_at, 1, 10)) = date('now')   -- UTC explícito
```

mientras `dashboard.py:128-133` convierte a `local_tz` cualquier marca para
mostrarla. Las marcas (`datetime.now(UTC)`) son coherentes en UTC; la incoherente
es la "frontera del día" y su despliegue.

## Impacto en la decisión

- Inconsistencia de auditoría: el operador que supervise "pérdida diaria" contra
  sus movimientos locales recibe un número que no corresponde a su día.
- Riesgo menor para el capital: el límite en sí funciona (honesto en UTC), pero
  su semántica es confusa y rompe la trazabilidad diaria del usuario.

## Evidencia de código

```python
# dashboard.py:128-133 — muestra hora local
local_tz = datetime.now().astimezone().tzinfo
display_df["timestamp"] = (
    pd.to_datetime(display_df["timestamp"], utc=True)
    .dt.tz_convert(local_tz)
    .dt.strftime("%H:%M:%S")
)
```

## Recomendación

1. Inyectar TZ local al `date()` de SQLite: `datetime(closed_at) in local_time` o
   calcular en Python el inicio del día local y filtrar por instantes.
2. Unificar: un módulo/config `RISK_DAY_TZ` (por defecto local) usado por
   storage y dashboard.
3. Test de frontera: pérdida a N-1 23:30 local → pertenece a hoy; a N 00:30 →
   ayer.

## Lección aprendida

Las fronteras de tiempo de negocio (límites, streaks, KPIs) son una decisión de
producto tanto como de código: fijar TZ y que la capa de datos y la de
presentación compartan la misma definición evita que el dashboard mienta por
espejo.