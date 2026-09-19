# Changelog

## [v2.2.5] QA hardening: cobertura 67→83 %, bug-023 y bug-024 (pendiente de tag tras merge del PR)

- **Bug #023 corregido** (`src/fetcher.py`): un par malformado de DexScreener
  (`baseToken: null`, `liquidity` no-dict) rompía **toda** la búsqueda
  (`fetch_by_symbol`/`fetch_recent_memecoins` → `[]`, `fetch_by_address` → `None`).
  `_normalize_pair` ahora valida tipos y descarta solo el par sucio; nuevo helper
  `_liquidity_usd` como `key` del `max()`. Regresión cubierta en `tests/test_fetcher.py`.
- **Bug #024 corregido** (`src/ai.py`): la IA local caía siempre a fallback con
  la config documentada (`LM_STUDIO_URL` con `/v1`) porque el cliente duplicaba el
  sufijo (`/v1/v1`) → 404 de LM Studio → `choices=None` → `score 0` silencioso en
  cada token. Se normaliza `base_url` con `removesuffix("/v1")` (admite ambas
  convenciones); regresión en `tests/test_ai.py` (+2). Detectado **en vivo** al
  activar Bionic/LM Studio en `:1234`.
- **Cobertura +16 puntos** (67→**83 %**): suite de **176 tests** (eran 130).
  - `fetcher.py` 20→**94 %** (19 tests: normalización, edad, retry HTTP, búsquedas).
  - `main.py` 35→**70 %** (36 tests: wallet, enrich/IA-fallback, apertura con re-fetch,
    monitor TP/SL/venta fallida/pnl dry-run, modos manual/automático, `main()`).
- **Nuevo `Makefile`**: `make check` = ruff + black `--check` + cobertura (gate 60 %),
  el mismo pipeline del CI en un comando.
- **Docs:** `docs/QA-CASE-STUDY.md` (case study de portafolio), `docs/bug-reports/bug-023-*`
  y `bug-024-*`, estado "resuelto" en `bug-022`, `README.md`/`README.EN.md`
  (176 tests · 83 %), `CLAUDE.md` y `CHANGELOG` actualizados.

---

## [v2.2.4] Fix de CI: pytest no arrancaba (plugin roto de anchorpy) — 2026-09-18

- **`requirements.txt`**: eliminado `anchorpy>=0.20.0` (sin uso en `src/` ni `tests/`).
  Su plugin pytest11 ejecuta `from pytest_xprocess import getrootdir`, que falla con
  pytest-xprocess ≥1.0 (el módulo pasó a ser `xprocess.pytest_xprocess`) → **pytest
  moría al arrancar en GitHub Actions** con output vacío (`0/2` checks en `main`).
  El error reproducido en CI: `ModuleNotFoundError: No module named 'pytest_xprocess'`.
- Limpieza: línea duplicada de `rich` en `requirements.txt`.
- Verificado localmente con el mismo pipeline del CI: `ruff` limpio, `black` limpio,
  **130 tests pasando**, cobertura **67 %** (gate 60 %).

---

## [v2.2.3] Badge de versión dinámico — 2026-09-18

- Badge `versión` del README (ES/EN) pasa a dinámico
  (`img.shields.io/github/v/release/...`), que se alimenta de la Release v2.2.

---

## [v2.2.2] Licencia GPL-3.0 (copyleft) — 2026-09-18

- `LICENSE` cambiada de MIT a **GNU GPL v3** (copyleft): los derivados deben
  seguir siendo open-source; no se puede reutilizar en closed-source.
- README (ES/EN): badge y sección de licencia actualizados.
- `social-preview.png` regenerado (pie "copyleft GPL-3.0").

> El 2026-09-18 el historial fue reescrito (purga de artefactos personales y
> email → `caosssj@users.noreply.github.com`); los tags v2.0/v2.1/v2.2 apuntan a
> commits equivalentes reescritos.

---

## [v2.2.1] Preparación para lanzamiento público (GitHub) — 2026-09-18

### Community-ready
- README bilingüe: switcher ES/EN, `README.EN.md` (traducción completa).
- `CONTRIBUTING.md`, `SECURITY.md` y `CODE_OF_CONDUCT.md`.
- Templates de GitHub: Issue Forms (bug/feature), PR template, `dependabot.yml`.
- Social preview `.github/social-preview.png` (1280×640) para el About/OG del repo.

### Limpieza
- Eliminados del repo los artefactos personales (`bug-001…008`, `BOT_KNOWLEDGE.md`)
  y `config/config.yaml` (vacío, sin uso). Copia de seguridad local conservada.

### Docs
- `docs/PUBLIC-LAUNCH-CHECKLIST.md`: pasos manuales en github.com (description,
  topics, branch protection, releases, Discussions) antes de hacer público.

### Tests / lint
- Sin cambios de código: 130 tests, 67 %, ruff y black limpios.

---

## [v2.2] Hardening de CI, documentación profesional y revisión crítica de QA — 2026-09-18

### CI endurecido (ahora bloqueante)
- Eliminado `|| true` de ruff/black: el pipeline solo pasa si lint y formato OK.
- Tests con cobertura obligatoria: `pytest --cov=src --cov-fail-under=60`
  (130 tests, 67 % actual).
- Nuevo `ruff.toml`: `BLE001`/`S110` permitidos solo en fronteras de API.

### Documentación profesional
- README reescrito: badges corregidos, Mermaid del pipeline y la decisión, scoring
  visual, modos/riesgo reales, roadmap honesto.
- `docs/arquitectura.md`: solo `.env`, SQLite, diagramas de componentes y secuencia.
- `docs/filtros.md`: escalera de decisión, barras de peso, T-05 corregido.
- `docs/riesgo.md`: alineado al código real (sin artefactos de v1).
- Capturas reales del dashboard y del reporte CLI (`docs/assets`).

### Revisión crítica de QA
- 9 bug-reports (`bug-014` → `bug-022`) + `REVISION-CRITICA-2026-09-18.md`.
- Hallazgos de alta severidad (014/015) quedan documentados para la siguiente
  iteración; este commit es solo documentación.

### Tests
- 130 tests, cobertura 67 %. `ruff` y `black` limpios.

---

## [v2.1] Dashboard de riesgo, verificación en vivo y RPC robusto — 2026-09-18

### Verificación en vivo (smoke test runtime)
- **Modo automático PASS** (~12 min): `monitor_positions` por ciclo sin errores, fetch
  de tokens, procesado y `seen_tokens` persistidos, cero excepciones en todo el log.
- **Modo manual PASS**: búsqueda por símbolo (POPCAT), enrich Helius con fallback RPC,
  reporte completo y salida limpia.
- **Hallazgo operacional**: si Bionic Studio/LM Studio no está sirviendo, la IA cae a
  fallback (score 0) sin tumbar el bot — comportamiento correcto y verificado. Al
  abrir el servidor, `get_ai_score` puntúa con normalidad (IA=10-30 en vivo).
- El ciclo puede durar más de 15 s con muchos tokens nuevos (pipeline secuencial +
  Helius sin batch); el scheduler salta intervalos que no caben (comportamiento
  esperado, no bloquea ni encola).

### Dashboard v2 — sección Riesgo/Posiciones
- Métricas: posiciones abiertas (máx 3), pérdida diaria realizada (0.5 SOL), P&L
  realizado acumulado y SL/trailing activos.
- Tabla de posiciones abiertas con **precio en vivo** (DexScreener): entrada, actual,
  TP +20%, SL −10%, trailing y P&L no realizado (% y SOL).
- Historial de posiciones cerradas (`get_closed_positions`).
- Hora local en la tabla (la DB guarda UTC; se convierte a la zona del sistema).

### Fix y limpieza
- Dashboard: conversión de timestamps robusta (`utc=True`) para zonas ya aware.
- Storage: nuevo `get_closed_positions(limit)`.

### Tests
- Suite a **130** (eran 129): historial de posiciones cerradas. `ruff`: 15
  pre-existentes sin nuevos; `black`: limpio.

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