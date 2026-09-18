# Changelog

## [Fase A] Wallet operativa: swaps reales y gestión de riesgo — 2026-09-18

### Ejecución real (executor)
- Carga de `WALLET_PRIVATE_KEY` (`load_wallet`) y construcción del keypair con solders.
- **Compra SOL→token**: quote → validación de price impact (máx 5%) → `POST /v6/swap`
  (fee prioritario automático + `dynamicComputeUnitLimit`) → firma con
  `VersionedTransaction` → `sendTransaction` (commitment `processed`, base64).
- **Venta token→SOL** (`execute_sell`): vende toda la posición leyendo la ATA de la
  wallet (`getTokenAccountsByOwner`). En `dry_run` no toca RPC.
- Cada etapa devuelve `status`/`reason` determinista (no_quote, aborted por impact,
  swap_request_failed, signing_failed, send_failed, success+signature).

### Gestión de riesgo conectada (risk + main + storage)
- Al comprar real exitoso se abre una `Position` en SQLite (entrada = precio real,
  TP +20% / SL -10%).
- `monitor_positions`: por cada ciclo revisa posiciones abiertas, actualiza trailing
  (activa al +5%, distancia 10%) y **vende automáticamente** al tocar TP/SL.
- Límites en modo real: máx 3 posiciones y pérdida diaria máx 0.5 SOL
  (`get_today_realized_loss`).
- Storage: `save_position`, `get_open_positions`, `close_position`,
  `update_position_state` y migración idempotente de columnas vía PRAGMA/ALTER.

### Tests
- Suite ampliada a **126** (eran 101): firma real de solders, swap/venta real con
  mocks, límites de riesgo, apertura/cierre/trailing de posiciones y reporte de pérdida
  diaria. `ruff`: sin errores nuevos; `black`: limpio.

## [Fase B] Scoring honesto y filtros con datos reales — 2026-09-18

### Scoring (analyzer)
- Política de "dato no verificado": los datos on-chain que no pueden confirmarse
  se representan con `None` y otorgan **0 pts** (antes se asumían seguros).
- Nuevo campo `status` (`ok` / `fail` / `missing`) en cada detalle de filtro.
- Manejo defensivo de `None` en todos los filtros numéricos (evita crashes).

### Análisis on-chain de seguridad (chain_data)
- `get_dev_address()`: wallet del dev derivada del fee payer de la tx más antigua
  de la mint (corrige el campo `creator_address` que apuntaba al address del token).
- `detect_bundles()` + `detect_dev_sold()`: detección por heurísticas sobre
  transacciones de la mint (compras simultáneas en una firma / saldo del dev
  decreciente), con caché por mint y fallo conservador (`None`).

### Persistencia y flujo (storage / main)
- Nueva tabla `seen_tokens`: los tokens ya procesados persisten entre reinicios
  (antes solo en memoria), reduciendo reprocesos y gasto RPC.
- Decisión unificada: `main` usa `analyzer.decide()` (se eliminó la duplicación).

### Ejecución (executor)
- Corrección de unidades de `MAX_PRICE_IMPACT_PCT`: ahora 5% real (Jupiter
  devuelve `priceImpactPct` en %; antes el límite efectivo era 0.05%).

### Limpieza
- Eliminado `src/detector.py` (código muerto, duplicaba `fetcher`) y sus tests.
- Retry con backoff aplicado a llamadas DexScreener (fetcher) y Helius (chain_data).
- El dashboard muestra el estado de cada filtro (ok / fail / sin datos).

### Tests
- Suite ampliada a 101 tests (eran 89): casos de datos no verificados,
  paginación de firmas, detección de bundles/dev-sell, `seen_tokens`.