# Bug #011: Métodos RPC inexistentes rompen el análisis de seguridad on-chain

**Severidad:** Alta
**Módulo:** Análisis on-chain (src/chain_data.py)
**Entorno:** Helius RPC, Python 3.12
**Fecha:** 2026-09-18
**Estado:** ✅ Corregido y verificado

## Descripción

El análisis de seguridad (bundles / ventas del dev) fallaba silenciosamente en
vivo: `analyze_security` devolvía `None` y todos los filtros de seguridad quedaban
marcados como `missing`. El problema no era el tipo de dato sino que **los métodos
RPC usados no existen** en Helius/RPC estándar de Solana.

## Pasos para reproducir

1. Ejecutar el flujo con `HELIUS_API_KEY` válida
2. Observar en logs:
```
RPC getParsedTransaction error: {'code': -32601, 'message': 'Method not found'}
RPC getMultipleParsedTransactions error: {'code': -32601, 'message': 'Method not found'}
```

## Resultado esperado

Obtener `has_bundles`, `dev_has_sold` y `dev_address` reales para alimentar los
filtros security/bundles/dev_sell/creator_age.

## Resultado obtenido

- `_rpc_call("getParsedTransaction", ...)` → error 32601 "Method not found"
- `_rpc_call("getMultipleParsedTransactions", ...)` → error 32601 "Method not found"
- `_security_analysis` acababa en `None` → `status: "missing"` en 3 filtros y la
  wallet del dev nunca se detectaba (creator_age también "missing")

## Causa raíz

`getParsedTransaction` y `getMultipleParsedTransactions` **no existen** en el RPC
JSON-RPC de Solana. Los métodos correctos son:

- `getTransaction` (estándar, con `encoding: "jsonParsed"` y
  `maxSupportedTransactionVersion: 0`)
- `getMultipleTransactions` (extensión de Helius para batching)

Como Helius ya era el proveedor objetivo, el batching debía usar su extensión —
con **fallback** al método estándar por si se apunta a otro RPC.

> Nota: la versión anterior (Fase B) marcaba estos datos como `None` de forma
> conservadora **por diseño**, así que el bot nunca pinchaba — pero tampoco
> operaba la funcionalidad de seguridad real.

## Solución aplicada

- `_fetch_parsed_transaction`: ahora usa `getTransaction`.
- `_fetch_parsed_transactions`: usa `getMultipleTransactions` (extensión Helius);
  si el RPC la rechaza (resultado no-list), hace **fallback secuencial** a
  `getTransaction` por firma.

## Verificación

Dry-run real sobre el token JUP:
```
[enrich] has_bundles=False dev_has_sold=False dev_address=<dir> creator_age=0
[security] dev_address=HYe4vSaEG... bundles=False dev_sell=False
[analyze] score=39 | filtros con datos: 10/11
```
10 de 11 filtros con datos reales (el único sin fuente sigue siendo `global_fees`,
por diseño — no existe fuente fiable).

## Lección aprendida

- Los métodos RPC de Solana tienen nombres exactos; las "extensiones" (Helius Ion:
  `getMultipleTransactions`, `getAsset`…) dependen del tier del proveedor.
- Ante métodos opcionales, implementar **probe + fallback** en vez de asumir.
- Coste a tener en cuenta: el fallback secuencial cuesta 1 llamada RPC por firma
  (profiling: un batch de 30 → 30 llamadas). Optimizable subiendo tier de Helius
  (Ion) o reduciendo `SECURITY_TOKEN_DEPTH`.