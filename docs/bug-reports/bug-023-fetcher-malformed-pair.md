# Bug #023: Par malformado de DexScreener rompe toda la búsqueda

**Severidad:** Alta (robustez del primer eslabón del pipeline)
**Módulo:** `src/fetcher.py` (`_normalize_pair`, `fetch_by_address`, `fetch_by_symbol`, `fetch_recent_memecoins`)
**Entorno:** v2.2.4, encontrado al ampliar la suite sobre la brecha reportada en Bug #022
**Fecha:** 2026-09-18
**Estado:** ✅ Corregido y cubierto por tests

## Descripción

`_normalize_pair(raw)` asumía que `baseToken` era siempre un diccionario y usaba
`(raw.get("liquidity") or {}).get("usd")` sin validar el tipo: si DexScreener
devuelve un par con `baseToken: null` (o `liquidity` como string/valor sucio),
`_normalize_pair` lanzaba `AttributeError: 'NoneType' object has no attribute 'get'`.

Ese error, al estar envuelto por el `try/except` de alto nivel, **derribaba la
búsqueda entera**:

- `fetch_by_symbol` → devuelve `[]` aunque haya 50 pares válidos.
- `fetch_recent_memecoins` → devuelve `[]` (ciclo automático pierde el batch completo).
- `fetch_by_address` → devuelve `None` aunque el par con más liquidez fuera válido.

Un solo par malformado (caso frecuente en memecoins recién creadas) anulaba el
resto de datos buenos.

## Pasos para reproducir

```python
from src.fetcher import fetch_by_symbol
pairs = {
    "pairs": [
        {"chainId": "solana", "baseToken": None, "liquidity": None},  # malformado
        {"chainId": "solana", "baseToken": {"address": "OK", "symbol": "OK"},
         "liquidity": {"usd": 100}},
    ]
}
# Antes del fix: la normalización crashea en el primer par → []
```

## Resultado esperado

`_normalize_pair` **nunca** debe lanzar por datos sucios: los pares malformados
se descartan individualmente (`None`) y la búsqueda continúa con los válidos.

## Resultado obtenido (antes del fix)

```
________________ test_fetch_by_symbol_skips_malformed_pair ________________
>       assert [t["token_address"] for t in result] == ["OK"]
E       AssertionError: assert [] == ['OK']
ERROR | src.fetcher:fetch_by_symbol:113 - Error buscando por símbolo: 'NoneType' object has no attribute 'get'
```

## Causa raíz

Normalización sin validación defensiva de tipos en la frontera de datos externos:
`raw.get("baseToken", {})` no protege frente a `baseToken: null` (la clave existe
pero su valor no es dict), y el patrón `X or {}` no protege frente a valores
truthy no-dict (string).

## Fix aplicado (src/fetcher.py)

- `base = raw.get("baseToken") or {}` + `isinstance(base, dict)` → `None` si no
  es dict (el par se descarta, no la búsqueda).
- `liquidity`/`volume`/`priceChange` con guard `isinstance(..., dict)`.
- Helper `_liquidity_usd(pair)` usado como `key` del `max()` en `fetch_by_address`
  (immune a `liquidity` corrupta sin romper la selección del mejor par).

## Tests añadidos (tests/test_fetcher.py)

`test_fetch_by_symbol_skips_malformed_pair` y
`test_fetch_recent_memecoins_skips_malformed_pair` (regresión). Ambos fallaban
antes del fix y pasan después. Suite de fetcher: **19 tests · 94 % cobertura**.

## Lección aprendida

En fronteras de datos externos, el contrato no es "el proveedor es consistente",
sino "un dato inválido se degrada a nivel de registro, nunca a nivel de lote".
El patrón `try/except` amplio transformó un error de datos en una caída de
disponibilidad silenciosa (búsquedas vacías sin stacktrace útil).