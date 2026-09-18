# Base de Conocimiento — Crypto Bot v2.0

> Documento de estado y referencia del proyecto para asistentes IA (Bionic Studio).
> Última actualización: 2026-09-18. Versión: **v2.0** (tag `v2.0` en GitHub).
> Fuente canónica de código: repositorio local. Este documento es la versión
> autocontenida del estado.

---

## 1. Qué es

Bot autónomo de trading de memecoins en Solana, con fines educativos y riesgo de
pérdida total **muy alto**. Pipeline completo:

```
Detección (DexScreener) → Análisis (11 filtros) → IA local (Qwen3)
→ Decisión → Ejecución (Jupiter) → Gestión de riesgo (TP/SL/trailing)
```

## 2. Estado actual

- **Versión:** v2.1 (sobre el tag v2.0). Commiteado en `git` y subido a GitHub
  (`caos-ssj/Crypto.Bot`).
- **Tests:** 130 de 130 pasando. Lint: solo 15 avisos pre-existentes. Black: limpio.
- **Verificado en vivo (smoke test)**: modo automático y manual PASS sin excepciones;
  la IA puntúa con Qwen3/Bionic cuando el servidor `:1234` está abierto y cae a
  fallback seguro (score 0) si no — el bot nunca se rompe por eso.
- **Persistencia:** SQLite en `logs/bot.db` (tablas `analyses`, `positions`,
  `seen_tokens`).

## 3. Stack

- Python 3.11/3.12 (venv local `venv/`; sin Poetry/uv).
- `requests`, `loguru`, `rich`, `streamlit`, `pandas`, `apscheduler`, `python-dotenv`.
- IA local: `openai` (cliente OpenAI-compatible) apuntando a Bionic/LM Studio
  (`http://localhost:1234/v1`, modelo `qwen/qwen3-4b-2507`, embeddings
  `text-embedding-nomic-embed-text-v1.5`).
- Wallet/firma (Fase A): `solders` 0.26.0, `solana` 0.36.6.
- DB: SQLite, sin ORM.

## 4. Arquitectura por módulo (`src/`)

| Módulo | Rol |
|---|---|
| `main.py` | Orquestador: menú rich, modos manual/automático, `process_token`, `monitor_positions` |
| `fetcher.py` | Datos DexScreener (`fetch_by_address`, `fetch_by_symbol`, `fetch_recent_memecoins`); única fuente de normalización (`_normalize_pair`) |
| `chain_data.py` | On-chain vía Helius RPC: mint info, top holders, dev address, seguridad (bundles/dev-sell). Dato no verificado → `None` (conservador) |
| `analyzer.py` | 11 filtros ponderados, score 0-100, `decide()`, campo `status` por filtro |
| `ai.py` | `get_ai_score` con Qwen3 local (peso 30%), fallback robusto |
| `executor.py` | Quotes + swap vía Jupiter (`/v6/quote`, `/v6/swap`); firma con `solders` y `sendTransaction` (real) |
| `risk.py` | `Position`, TP/SL/trailing, límite diario |
| `storage.py` | SQLite: `analyses`, `positions`, `seen_tokens` |
| `utils.py` | `retry_with_backoff` (3 intentos, backoff 0.5→1.0→2.0 s), `format_sol`, `safe_float` |

`config.py`: 3 modos (`conservador`, `equilibrado`, `agresivo`) con parámetros
(mc_min/max, max_age_min, global_fees, base_buy). La configuración real viene de
`.env` (el `config/config.yaml` no se usa).

## 5. Configuración (`.env`)

| Variable | Propósito |
|---|---|
| `SOLANA_RPC_URL` | Endpoint RPC de Solana (mainnet) |
| `HELIUS_API_KEY` | API key de Helius para análisis on-chain |
| `WALLET_PRIVATE_KEY` | Clave privada de la wallet en base58 (ejecución real; Fase A) |
| `JUPITER_API_URL` | Endpoint API de Jupiter |
| `LM_STUDIO_URL` / `LM_STUDIO_MODEL` | Servidor y modelo local de IA |
| `MODE` | `conservador` · `equilibrado` · `agresivo` |
| `DRY_RUN` | `true` simulación / `false` operaciones reales |
| `LOG_LEVEL` | Nivel de log |

## 6. Flujo del bot (`process_token` en `main.py`)

1. Enriquecer con on-chain (`enrich_token`) si hay `HELIUS_API_KEY`.
2. Reglas: `analyze_token` → 11 filtros, score normalizado `(total/115)*100`.
3. IA local `get_ai_score` (30% peso). `final_score = 70%·reglas + 30%·IA`.
4. Decisión unificada `decide(score)`: **>70 COMPRA · >=50 OBSERVAR · else EVITAR**.
5. Si COMPRA → `execute_swap(...)`. Con `DRY_RUN=true` se simula.
6. `save_analysis` en SQLite + output rich.

Modo automático: bucle cada 15 s, consulta `fetch_recent_memecoins`, salta tokens en
`seen_tokens` (persistente entre reinicios), los marca con `mark_seen` tras procesar.

### Ejecución y riesgo

- Compra SOL→token: quote → validación de price impact (**máx 5%**, Jupiter devuelve %)
  → `POST /v6/swap` (`prioritizationFeeLamports: "auto"`, `dynamicComputeUnitLimit: true`)
  → firma con `solders.VersionedTransaction` → `sendTransaction` (`processed`, base64).
- Venta token→SOL: `execute_sell` vende **toda** la posición; lee el balance de la ATA
  vía `getTokenAccountsByOwner`. En `dry_run` no consulta balance.
- Límites en `process_token` (modo real): máx **3 posiciones** (`can_open_position`),
  pérdida diaria máx **0.5 SOL** (`check_daily_limit`, `get_today_realized_loss`).
- Al comprar real exitoso: se abre `Position` (entrada = precio DexScreener).
- `monitor_positions` (inicio de cada ciclo): actualiza trailing y al tocar TP/SL vende
  (real) o simula (dry_run) y cierra.

**Parámetros de riesgo (`risk.py`):**
- TP: +20 %, SL: −10 %, trailing activa al +5 %, distancia 10 %.
- Decisión: >70 COMPRA / ≥50 OBSERVAR / resto EVITAR.

## 7. Filtros del analyzer (pesos / decisión)

```
market_cap 20 · global_fees 20 · age 15 · security 25 · liquidity_ratio 5
top_holders 5 · volume 5 · creator_age 5 · authorities 5 · bundles 5 · dev_sell 5
MAX_SCORE = 115 → normalizado a 100
```

**Regla crítica (scoring honesto):** los campos on-chain no verificados se guardan
como `None` (`has_bundles`, `dev_has_sold`, `global_fees_sol`, `creator_age_days`,
`top_10_holders_pct`). El analyzer les da **0 pts + `status: "missing"`** — jamás se
asume que un token es seguro por falta de datos. `MISSING_INDICATORS` en
`analyzer.py`.

## 8. On-chain: puntos clave (`chain_data.py`)

- `get_mint_info`: `mint_authority_disabled`, `freeze_authority_disabled`, top-10 holders %.
- `get_dev_address`: fee payer de la tx más antigua de la mint (paginando hasta el
  bloque de creación con `getSignaturesForAddress`).
- `analyze_security` (caché por mint, `SECURITY_TOKEN_DEPTH=10`):
  - **Bundles:** firma única con >1 comprador nuevo (heurística; sin datos → `None`).
  - **Dev-sell:** saldo del dev decreciente.
  - Si falla el RPC → `None` (nunca `False`).
- Métodos RPC **correctos**: `getTransaction` + `getMultipleTransactions` (extensión
  Helius) con **fallback** secuencial a `getTransaction`; `RPC_BATCH_LIMIT=10`,
  `maxSupportedTransactionVersion: 0`.
- ⚠️ `getParsedTransaction` / `getMultipleParsedTransactions` **NO existen** en el
  RPC (corregido: bug-011).

## 9. Fuentes de datos

| Fuente | Uso |
|---|---|
| DexScreener API | Precios/liquidez, detección de tokens |
| Helius RPC | Datos on-chain (authorities, holders, dev, bundles) |
| Jupiter API v6 | Quotes y swaps |
| Bionic Studio / LM Studio (`localhost:1234`) | IA local Qwen3 (scoring) |

## 10. Bugs documentados (resumen)

- **bug-011 (corregido):** métodos RPC inexistentes rompían la seguridad on-chain.
  Fix: `getTransaction`/`getMultipleTransactions` con fallback. Verificado en vivo.
- **bug-012 (pendiente de usuario):** `WALLET_PRIVATE_KEY` del `.env` es inválida
  (22 chars, no base58). El código la rechaza con seguridad; pide reemplazo antes del
  modo real.
- **bug-013 (entorno):** `quote-api.jup.ag` no resuelve DNS en el sandbox de pruebas
  (DexScreener/Helius sí). Verificar conectividad desde la máquina final.

## 11. Cómo correr

```bash
venv/bin/python -m src.main           # menú interactivo (manual/automático)
venv/bin/python -m pytest tests/ -q   # 130 tests
streamlit run dashboard.py            # dashboard web (con posiciones en vivo)
```

| Chequeo | Comando |
|---|---|
| Tests | `venv/bin/python -m pytest tests/ -q` |
| Lint | `venv/bin/ruff check src/ tests/` |
| Formato | `venv/bin/black --check src/ tests/` |

**Dashboard** (v2): además del análisis histórico muestra **Riesgo/Posiciones** —
posiciones abiertas con precio en vivo (entrada/actual/TP/SL/trailing/P&L), pérdida
diaria realizada, P&L acumulado e historial de cerradas. La hora se muestra en la zona
local del sistema.

`dashboard.py` no es black-limpio (intencional; no tocarlo con black automático).
CI (`.github/workflows/ci.yml`): ruff/black/pytest con `|| true`.

## 12. Pendientes y aristas (Fase A)

- Confirmación de transacción recibida (`getSignatureStatuses`) en `sendTransaction`.
- Priority fee parametrizable (hoy "auto").
- Venta parcial (% de la posición) opcional.
- `DRY_RUN=true` por defecto; pasar a `false` solo con wallet válida.
- Componente de "caja" para monitorizar el saldo SOL de la wallet tras ventas.
- Roadmap a futuro: Pump.fun WebSocket, monitoreo de wallets, backtesting, filtros
  dinámicos, TP/SL dinámicos (ATR), multi-wallet, Telegram.