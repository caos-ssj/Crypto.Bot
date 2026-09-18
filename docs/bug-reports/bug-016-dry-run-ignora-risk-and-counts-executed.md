# Bug #016: DRY_RUN ignora los límites de riesgo y el dashboard cuenta las simulaciones como ejecuciones

**Severidad:** Media
**Módulo:** Orquestador / Dashboard (`src/main.py:327-333` → `src/storage.py:134`)
**Entorno:** v2.1, modo simulación (`DRY_RUN=true`, el valor por defecto)
**Fecha:** 2026-09-18

## Descripción

En modo simulación los dos límites de riesgo clave —máximo 3 posiciones abiertas
y pérdida diaria máxima 0.5 SOL— **no se evalúan**: `risk_ok` es
incondicionalmente `true` cuando `dry_run`. Además, todo swap simulado se
persiste con `executed = 1`, por lo que la métrica "Ejecutadas" del dashboard
mezcla operaciones ficticias con reales.

## Pasos para reproducir

1. `DRY_RUN=true` (defecto). Modo automático.
2. Provocar (mock o datos reales) más de 3 señales `COMPRA` en ciclos seguidos.
3. Observar: se "ejecutan" las 4, 5… sin aviso de límite (`main.py:334-338`).
4. Abrir dashboard: "💸 Ejecutadas" crece aunque no haya habido ninguna tx real.
5. Histórico del `analyses`: filas con `executed = 1` para swaps dry-run.

## Resultado esperado

- La simulación debería **reproducir fielmente las restricciones del modo real**
  (si el bot real no compraría con 4 posiciones, la sim tampoco).
- El contador "Ejecutadas" debería etiquetar las simulaciones como tales
  (`executed=1` solo para txs reales, o una columna `simulated`).

## Resultado obtenido

- La simulación dibuja un mundo donde no hay límites: muestra "éxitos" que el
  modo real jamás permitiría.
- El dashboard reporta N ejecutadas que no existieron → baraja el KPI del
  usuario.

## Causa raíz

`src/main.py:330`: `risk_ok = config["dry_run"] or (can_open... and check_daily...)`.
La evaluación de riesgo se condiciona al modo real, en vez de simular el mismo
criterio. Y `src/storage.py:134`: `1 if result.get("executed") else 0` donde
`executed` ya es `true` para `status == "dry_run"` (`main.py:349`).

## Impacto en la decisión

- Quien use el dry-run como prueba del comportamiento real recibe una **imagen
  optimista** del sistema (sin límites de riesgo). Es la fuente de expectativas
  falsas al pasar a real.
- Las "Ejecutadas" (KPI del dashboard) son engañosas; imposible comparar
  simuladas vs reales sin consultar SQL a mano.

## Evidencia de código

```python
# src/main.py:327-333
if action == "COMPRA":
    open_positions = get_open_positions()
    daily_loss = get_today_realized_loss()
    risk_ok = config["dry_run"] or (
        can_open_position(open_positions) and check_daily_limit(daily_loss)
    )

# src/storage.py:134
1 if result.get("executed") else 0,
```

## Recomendación

1. Evaluar `can_open_position`/`check_daily_limit` **también en dry_run** para
   que la simulación replique las restricciones reales (single code path).
2. Diferenciar `executed` (real) de `simulated` (dry_run) en `analyses`, o
   guardar `dry_run` explícito y restar de la métrica del dashboard.
3. Añadir en el dashboard un indicador "Modo: DRY_RUN" junto a "Ejecutadas".
4. Test: en dry_run con 3 posiciones ficticias, la 4.ª señal debe quedar en
   `OBSERVAR`/bloqueada igual que en real.

## Lección aprendida

Una simulación que no impone las mismas restricciones que el modo productivo no
es un entorno de pruebas válido: contamina métricas y expectativas. Los KPIs
deben llevar su semántica ("simulado" vs "real") explícita desde la capa de
persistencia.