# Bug #019: El filtro de edad usa el "pairing" de DexScreener, no la creación de la mint

**Severidad:** Media
**Módulo:** Análisis / Detección (`src/fetcher.py:40-43` → `src/analyzer.py:59-67`)
**Entorno:** v2.1, los tres modos
**Fecha:** 2026-09-18

## Descripción

`age_minutes` se calcula desde `pairCreatedAt` de DexScreener —el momento en que
se creó el **par de trading**, no cuando se acuñó el **token**. Un token con la
mint creada hace semanas/días puede listarse recién hoy (pair nuevo) y pasará el
filtro "token nuevo" (`age < max_age`) como si fuera un lanzamiento fresco.
Los filtros de novedad son exactamente la puerta de entrada para tokens con
historia previa oculta (rug con ciclo retrasado, re-listings, honeypots con mint
vieja) y el resto del pipeline asume novedad real.

## Pasos para reproducir

1. Tomar un token cuya mint existe desde hace días (> `max_age_min`) y que
   recién crea un pair en un DEX.
2. Analizarlo en modo manual.
3. Observar `age_minutes` bajo (`pairCreatedAt` reciente) → filtro `check_age`
   da 15 pts, aunque la mint sea antigua.

## Resultado esperado

La "novedad" de un token debería derivarse de la **fecha de creación de la
mint** (on-chain, `getAccountInfo`/`getTransaction` de la tx de creación), o
como mínimo complementar el `pairCreatedAt` con un chequeo de edad de mint.

## Resultado obtenido

- Filtro `check_age` puntúa como nuevo lo que es "par nuevo".
- Los 15 pts de `age` son alcanzables por tokens con historial previo, con la
  misma ponderación que si fueran lanzamientos genuinos.

## Causa raíz

`fetcher.py` solo consume datos DexScreener en el momento de normalizar:

```python
# src/fetcher.py:43
"age_minutes": _calc_age_minutes(raw.get("pairCreatedAt")),

# src/analyzer.py:61-67
age = token.get("age_minutes")
max_age = mode_settings["max_age_min"]
if age is None:
    return 0, "Edad sin datos (pairCreatedAt ausente)"
if age < max_age:
    return 15, f"Edad {age}min OK"
```

El `enrich_token` on-chain no introduce una "mint age" propia; la edad del
creador es una métrica distinta (wallet del dev).

## Impacto en la decisión

- **Riesgo operativo**: la segunda fuente de riesgos clásica de pump.fun
  (rug retardado/relisting) entra sin fricción al gate de novedad.
- Los 15/115 pts se otorgan con una métrica que no mide lo que declara su
  nombre, sesgando el score hacia COMPRA en tokens con antifaz.

## Evidencia de código

```python
# src/fetcher.py:47-54
def _calc_age_minutes(pair_created_at: Any) -> int | None:
    if not pair_created_at:
        return None
    try:
        return max(0, int((time.time() * 1000 - pair_created_at) / 60000))
```

## Recomendación

1. En `enrich_token`, derivar la fecha de creación de la mint desde la tx más
   antigua del mint (reusar `get_earliest_signature` +
   `getTransaction.blockTime`) y exponer `mint_age_minutes`.
2. `check_age` debe usar `min(pair_age, mint_age)` o directamente
   `mint_age_minutes` cuando exista; si no hay dato on-chain, seguir la política
   conservadora de `missing`.
3. Documentar + test: token con pair nuevo pero mint antigua → filtro edad 0 o
   `missing`, no 15 pts.

## Lección aprendida

Al validar "es un token recién nacido", midí la edad del **activo** (la mint),
no la del **mostrador donde lo venden** (el pair). Toda métrica de seguridad
debe definirse sobre la entidad que se quiere proteger.