# CLAUDE.md — Crypto Bot (memecoin trading en Solana)

Contexto de memoria del proyecto para agentes de IA. Mantener actualizado conforme
evoluciona el código. Última revisión: 2026-09-18 (Fase A en curso).

## 1. Resumen del proyecto

Bot autónomo de trading de memecoins en Solana (fines educativos, riesgo de pérdida
total **muy alto**). Pipeline:

```
Detección (DexScreener) → Análisis (11 filtros) → IA local (Qwen3/LM Studio)
→ Decisión → Ejecución (Jupiter) → Gestión de riesgo (TP/SL/trailing)
```

El token/creador nunca deben ser quemados; siempre obedecer los límites de riesgo.

## 2. Stack

- Python 3.11/3.12 (venv local: `venv/`). Sin Poetry/uv.
- `requests`, `loguru`, `rich`, `streamlit`, `pandas`, `apscheduler`, `python-dotenv`.
- IA local vía LM Studio (cliente OpenAI-compatible): `openai`.
- Para wallet/firma en la Fase A: `solders` 0.26.0 y `solana` 0.36.6 **ya instalados**.
- DB: SQLite (`logs/bot.db`), sin ORM.

## 3. Arquitectura por módulo (`src/`)

| Módulo | Rol | Estado |
|---|---|---|
| `main.py` | Orquestador: menú rich, modos manual/automático, `process_token` | ✅ activo |
| `fetcher.py` | Datos DexScreener (`fetch_by_address`, `fetch_by_symbol`, `fetch_recent_memecoins`). **Única** fuente de normalización (`_normalize_pair`); el antiguo `detector.py` fue eliminado | ✅ activo |
| `chain_data.py` | On-chain vía Helius RPC: mint info, top holders, dev address, seguridad (bundles/dev-sell). Caché con `lru_cache`. Política: dato no verificado → `None` (conservador) | ✅ activo |
| `analyzer.py` | 11 filtros ponderados, score 0-100, `decide()`, campo `status` por filtro | ✅ activo |
| `ai.py` | `get_ai_score` con Qwen3 local (peso 30%), fallback robusto | ✅ activo |
| `executor.py` | Quotes + swap vía Jupiter (`/v6/quote`, `/v6/swap`); firma con solders y `sendTransaction` (real) | ✅ real (buy SOL→token y sell token→SOL) |
| `risk.py` | `Position`, TP/SL/trailing, límite diario | ✅ conectado a `main` |
| `storage.py` | SQLite: `analyses`, `positions`, `seen_tokens` | ✅ activo |
| `utils.py` | `retry_with_backoff` (3 intentos, backoff 0.5 → 1.0 → 2.0s), `format_sol`, `safe_float` | ✅ activo |

`config.py`: 3 modos (`conservador` / `equilibrado` / `agresivo`) con parámetros
(mc_min/max, max_age_min, global_fees, base_buy). `config/config.yaml` existe pero
**no se usa**; la configuración real viene de `.env`.

Variables `.env` (ver `.env.example`):
`SOLANA_RPC_URL`, `HELIUS_API_KEY`, `WALLET_PRIVATE_KEY` (aún sin usar — Fase A),
`JUPITER_API_URL`, `LM_STUDIO_URL`, `LM_STUDIO_MODEL`, `MODE`, `DRY_RUN`, `LOG_LEVEL`.

## 4. Flujo del bot (`process_token` en `main.py:247`)

1. Enriquecer con on-chain (`enrich_token`) si hay `HELIUS_API_KEY` (Helius RPC).
2. Reglas: `analyze_token` → 11 filtros, score normalizado `(total/115)*100`.
3. IA local `get_ai_score` (30% peso). `final_score = 70%·reglas + 30%·IA`.
4. Decisión unificada `decide(score)`: **>70 COMPRA · >=50 OBSERVAR · else EVITAR**.
5. Si COMPRA → `execute_swap(...)`; hoy termina en `dry_run` (Fase B usa dry_run).
6. `save_analysis` en SQLite + output rich.

Modo automático (`run_automatic_mode`): bucle c/15s, consulta `fetch_recent_memecoins`,
salta tokens en `seen_tokens` (persistente a través de reinicios), los marca con
`mark_seen` tras procesar.

### Ejecución y riesgo (Fase A)

- `execute_swap` (compra SOL→token): quote → validación de price impact (máx 5%) →
  `POST /v6/swap` (`prioritizationFeeLamports: "auto"`, `dynamicComputeUnitLimit: true`)
  → firma con `solders.VersionedTransaction` → `sendTransaction` (`processed`, base64).
- `execute_sell` (venta token→SOL): vende **toda** la posición; lee el balance de la
  ATA de la wallet via `getTokenAccountsByOwner`. En `dry_run` no consulta balance.
- Límites de riesgo en `process_token` (modo real): máx 3 posiciones
  (`can_open_position`) y pérdida diaria máx 0.5 SOL (`check_daily_limit`,
  `get_today_realized_loss`).
- Al comprar real exitoso, se abre `Position` (entrada = precio DexScreener, TP +20%,
  SL -10%).
- `monitor_positions` se corre al inicio de cada ciclo: actualiza trailing (activa al
  +5%, distancia 10%), y al tocar TP/SL **vende** (real) o simula (dry_run) y cierra.

### Filtros del analyzer (pesos / decisión)

market_cap 20 | global_fees 20 | age 15 | security 25 | liquidity_ratio 5 |
top_holders 5 | volume 5 | creator_age 5 | authorities 5 | bundles 5 | dev_sell 5
(`MAX_SCORE = 115`, normalizado a 100).

**Regla crítica:** los campos on-chain no verificados se guardan como `None`
(`has_bundles`, `dev_has_sold`, `global_fees_sol`, `creator_age_days`,
`top_10_holders_pct`). El analyzer les da **0 pts + `status: "missing"`** — jamás
inflar el score asumiendo que un token es seguro por falta de datos. Mapeo en
`MISSING_INDICATORS` (analyzer.py:13).

## 5. Puntos clave de on-chain (`chain_data.py`)

- `get_mint_info`: `mint_authority_disabled`, `freeze_authority_disabled`,
  top-10 holders %.
- `get_dev_address`: fee payer de la **tx más antigua** de la mint (paginando
  hasta el bloque de creación con `getSignaturesForAddress`).
- `analyze_security` (caché por mint, profundidad `SECURITY_TOKEN_DEPTH=10`):
  - **Bundles**: firma única con >1 comprador nuevo (heurística; sin datos → `None`).
  - **Dev-sell**: saldo del dev decreciente («sold the bag»).
  - Si falla el RPC → devuelve `None` (nunca `False`).
- Llamadas RPC con `retry_with_backoff` y batching (`getMultipleTransactions`
  — extensión Helius — con **fallback** secuencial a `getTransaction`, método RPC
  estándar; `RPC_BATCH_LIMIT=10`, `maxSupportedTransactionVersion: 0`).
- ⚠️ No usar `getParsedTransaction`/`getMultipleParsedTransactions`: NO existen
  (error → "Method not found"). Corregido en bug-011.

## 6. Convenciones y verificación

- Comentarios y docstrings en **español**; código simple y autocontenido.
- Ejecutar siempre estos chequeos:
  - Tests: `venv/bin/python -m pytest tests/ -q`
  - Lint: `venv/bin/ruff check src/ tests/`
  - Formato: `venv/bin/black --check src/ tests/`
- Notas de lint: existen `BLE001` (cachés de excepción abiertos) pre-existentes en
  fronteras de API (`fetcher`, `executor`, `main`, `ai`, `_rpc_call`) — se aceptan
  para no romper el ciclo del bot; **no añadir más sin necesidad** (si se añade,
  justificar con `# noqa: BLE001` en boundary público).
- `dashboard.py` no está black-limpio (no tocarlo con black automático).
- CI (`/.github/workflows/ci.yml`): ruff/black/pytest con `|| true` (no bloquea).

## 7. Estado actual (Fase B completada — 2026-09-18)

- **Scoring honesto:** datos on-chain no verificados = 0 pts + `status: missing`
  (antes `has_bundles=False`/`dev_has_sold=False` inflaban 35 pts sin verificar nada).
- **Seguridad real on-chain:** `get_dev_address`, `analyze_security` (bundles/dev-sell)
  con caché y profundidad 10; corregido `creator_address` que apuntaba al address del token.
- **Persistencia:** tabla `seen_tokens` (evita reprocesar entre reinicios, ahorra RPC).
- **Decisión unificada:** `main` usa `analyzer.decide()` (eliminada duplicación).
- **Fix price impact:** `MAX_PRICE_IMPACT_PCT = 5.0` (Jupiter devuelve %; antes el límite
  efectivo era 0.05%).
- **Limpieza:** eliminado `detector.py` y sus tests (código muerto); retries con backoff
  en fetcher/chain_data; docs y CHANGELOG actualizados.
- **Tests:** 129 (eran 89). `ruff`: solo 15 pre-existentes (14 BLE001 + 1 S110), cero nuevos.

## 8. Fase A — estado (wallet operativa en curso)

### Hecho (mismo día 2026-09-18)
1. `load_env_config` expone `wallet_private_key`; `get_wallet_keypair` (main.py) crea
   el `Keypair` con `solders.Keypair.from_base58_string` (cacheado).
2. `executor.py` implementa swaps **reales**: compra (SOL→token) y venta (token→SOL):
   - `_request_swap_transaction`: POST `/v6/swap` con fee prioritario automático.
   - `_sign_swap_transaction`: firma con `VersionedTransaction`.
   - `_send_transaction`: `sendTransaction` al RPC (`preflightCommitment: processed`).
   - `execute_sell` vende toda la posición (lee ATA con `getTokenAccountsByOwner`);
     en `dry_run` no toca RPC.
3. `storage.py`: `save_position`, `get_open_positions`, `close_position`,
   `update_position_state` (trailing), `get_today_realized_loss` + migración de
   columnas vía `ALTER` (PRAGMA) en `_connect`.
4. `main.py`: apertura de posición tras compra real, límites (max 3 posiciones /
   0.5 SOL día) y `monitor_positions` (TP/SL/trailing + venta) al inicio de cada ciclo.

### Dry-run de humo (validado en vivo el 2026-09-18)
- Flujo completo OK: DexScreener → enrich (Helius) → 11 filtros → decisión → guardado.
- **bug-011 corregido**: `getParsedTransaction`/`getMultipleParsedTransactions` no
  existen; ahora `getTransaction` + `getMultipleTransactions` con fallback. Tras el
  fix, el enrich devuelve datasets on-chain reales (10/11 filtros con datos; solo
  `global_fees` sigue "missing" por falta de fuente fiable).
- **bug-012**: `WALLET_PRIVATE_KEY` del `.env` actual es **inválida** (22 chars, `l`
  fuera del alfabeto base58). El código la rechaza con seguridad; el usuario debe
  poner un keypair real antes de `DRY_RUN=false`.
- **bug-013**: `quote-api.jup.ag` no resuelve DNS en este sandbox (DexScreener/Helius
  sí). No es bug de código; verificar conectividad desde la máquina final.

### Pendiente / aristas
- No se confirma la transacción recibida (`getSignatureStatuses`); el swap se considera
  "enviado". Añadir confirmación + reintentos.
- Priority fee fijo en "auto"; opcional parametrizarlo por momento (SLA nitro/sniper).
- Venta siempre de la posición completa; opcional venta parcial (%).
- `DRY_RUN=true` por defecto: pasar a `false` SOLO cuando se quiera operar real (con
  `WALLET_PRIVATE_KEY` cargada en `.env`).
- Al vender en real, el SOL vuelve a la wallet pero no se monitoriza el balance SOL
  (falta componente de "caja" para reusar el saldo).

## 9. Roadmap (de README) y docs

- `docs/arquitectura.md`, `docs/filtros.md`, `docs/riesgo.md`, `docs/qa-plan.md`,
  `docs/bug-reports/`, `CHANGELOG.md`.
- Fuentes de datos: **DexScreener** (precios/liquidez), **Helius RPC** (on-chain),
  **Jupiter API v6** (quotes/swaps), **LM Studio** (IA local).