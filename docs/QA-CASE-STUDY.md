# QA Case Study — Crypto.Bot (Solana memecoin trading bot)

> **Autor:** QA Automation Engineer · **Fecha:** 2026-09-18 · **Repo:** [gitlab.com/braynerssj26/crypto-bot](https://gitlab.com/braynerssj26/crypto-bot)
>
> **Summary (EN):** End-to-end QA hardening of a Python 3.11/3.12 trading bot
> (requests, rich, apscheduler, Jupiter API, DexScreener, Helius RPC). In one day
> the test suite went from **130 to 176 tests** and coverage from **67 % to 83 %**
> (`pytest --cov` gate at 60 %), raising `fetcher.py` from **20 % to 94 %** and
> `main.py` from **35 % to 70 %**. Testing revealed a real defect (Bug #023): a
> single malformed DexScreener pair crashed the whole search — fixed with an
> immunity-at-record-level design and covered by regression tests. A second live
> defect (Bug #024) was caught while validating the pipeline with the local LLM
> server on: the OpenAI-style client built a duplicated `/v1/v1` endpoint, so the
> AI silently fell back to 0 on every token — fixed and regression-tested. All
> checks run locally with `make check` (ruff + black + coverage), mirroring CI.

---

## 1. Contexto

Bot autónomo de trading de memecoins en Solana (fin de trading automatizado
persona). Pipeline en 6 etapas: detección (DexScreener) → análisis on-chain
(Helius RPC) → 11 filtros ponderados → IA local (Qwen3) → decisión → ejecución
(Jupiter) y gestión de riesgo TP/SL/trailing en SQLite.

Como bot financiero, el área de mayor valor QA es el **camino del dinero**:
fetch de precios, decisión, límites de riesgo y ejecución. El informe previo
(Bug #022) ya documentaba que cobertura global 67 % escondía islas de riesgo:
`fetcher.py` **20 %** y `main.py` **35 %** eran el primer eslabón del pipeline y
el orquestador, los módulos menos cubiertos.

## 2. Objetivos

1. Cerrar la brecha de cobertura crítica (Bug #022): fetcher y main.
2. Encontrar defectos reales durante la escritura de tests (no solo "subir el
   porcentaje").
3. Dejar un gate de QA replicable y documentable: `make check`.
4. Documentar hallazgos y evidencia para auditoría y mejora continua.

## 3. Estrategia de testing

- **Pirámide pragmática:** tests unitarios con mocks en las fronteras de red
  (`requests`, Jupiter, RPC), sin llamadas reales que dependan de una wallet o
  de internet (determinismo y CI-friendly).
- **Congelado de reloj:** `time.time()` se congela en `fetcher` para que las
  edades de pares sean reproducibles.
- **Regresión primero:** cada defecto se captura con un test que falla antes del
  fix y pasa después (test-driven en la corrección).
- **Diseño de casos pelo del dato sucio:** proveedores externos no cumplen
  contratos → cada campo puede ser `null`, string malformado o de otro tipo.
- **Gate local idéntico al CI:** ruff, black `--check` y
  `pytest --cov=src --cov-fail-under=60` (bloqueante desde v2.1).

### Matriz de casos cubiertos en esta iteración

| Categoría | Casos | Módulo |
|---|---|---|
| Normalización DexScreener | par completo, `baseToken` nulo/ausente, marketCap→fdv, defaults, valores inválidos | `fetcher` |
| Edad del par | válida, futura (clamp 0), ausente, inválida | `fetcher` |
| HTTP + retry | éxito, fallo→reintento exitoso | `fetcher` |
| Búsquedas | mejor par por liquidez, filtro por chain, sin resultados, error de red | `fetcher` |
| Par malformado (Bug #023) | se descarta a nivel de registro, el lote sobrevive | `fetcher` |
| Wallet | cacheo del keypair, ausencia sin crash | `main` |
| `process_token` | enrich on-chain, error de enrich, error de IA (fallback), verbose | `main` |
| Apertura de posición | price re-fetch, sin precio (no abre), error de red (no abre) | `main` |
| `monitor_positions` | sin posiciones, sin precio (omite), venta fallida (mantiene), pnl dry-run, error de red | `main` |
| Modos | manual (address/símbolo/select multi/vacíos), automático (1 ciclo), `change_mode` | `main` |
| Entrada | `main()` sin RPC → 1, menú "0" → salida limpia | `main` |

## 4. Hallazgo principal — Bug #023

La nueva suite de fetcher expuso un defecto real (confirmado con test que
fallaba): un **par malformado** (`baseToken: null` o `liquidity` no-dict) lanzaba
`AttributeError` dentro de `_normalize_pair`, y el `try/except` de alto nivel
**anulaba la búsqueda completa**:

```
ERROR | src.fetcher:fetch_by_symbol:113 - Error buscando por símbolo: 'NoneType' object has no attribute 'get'
```

> Un solo par con datos sucios hacía que `fetch_by_symbol` devolviera `[]` pese a
> haber 50 pares válidos → el ciclo automático perdía el batch entero.

**Fix (principio: el error de datos se degrada a nivel de registro, nunca a nivel
de lote):**
- `_normalize_pair` valida `isinstance(base, dict)` → descarta solo ese par.
- `liquidity`/`volume`/`priceChange` blindados con `isinstance`.
- Helper `_liquidity_usd()` como `key` del `max()` en `fetch_by_address`.

Detalle completo, con causa raíz, reproducibilidad y evidencia de los tests
failing/passing en `docs/bug-reports/bug-023-fetcher-malformed-pair.md`.

### Hallazgo concurrente — Bug #024 (IA local)

La validación en vivo de la sección IA del dashboard (con LM Studio/Bionic
sirviendo en `:1234`) expuso que `_call_lm_studio` duplicaba el sufijo `/v1`:
`LM_STUDIO_URL=http://localhost:1234/v1` (documentado en `.env.example`) + el
cliente añadiendo `/v1` = `.../v1/v1/chat/completions` → 404 de LM Studio →
`ChatCompletion.choices = None` → fallback silencioso a `score 0` en **cada**
token. El bug solo se ve en vivo con el servidor de IA encendido; con él apagado
el fallback enmascara todo.

**Fix (`src/ai.py`):** normar `base_url` con `removesuffix("/v1")` antes de
construir la URL → admite ambas convenciones. Regresión en `tests/test_ai.py`
(+2). Detalle en `docs/bug-reports/bug-024-ai-lmstudio-doble-v1.md`.

## 5. Resultados

| Métrica | Antes (v2.1) | Después (v2.2.5) |
|---|---|---|
| Tests | 130 | **176** (+46, +35 %) |
| Cobertura total | 67 % | **83 %** (82.87) |
| `fetcher.py` | 20 % | **94 %** |
| `main.py` | 35 % | **70 %** |
| `risk.py` | 100 % | 100 % |
| `analyzer.py` | 96 % | 96 % |
| Suite completa | 2.8 s | 3.5 s (sin pérdida de determinismo) |

Ejecución real:

```bash
$ make check
# ruff: 0 errores nuevos (solo BLE001 pre-existentes documentados en fronteras)
# black: limpio src/ y tests/
# coverage: TOTAL 1127 stmts → 82.87 %; gate --cov-fail-under=60 ✅
# 176 passed in 3.51s
```

## 6. Proceso y metodología

1. **Medir antes de tocar:** línea base con `pytest --cov=src --cov-report=term-missing`.
2. **Priorizar por riesgo (no por esfuerzo):** atacar `fetcher` y `main` (los
   huecos que tocan dinero), dejando última la UI pura.
3. **Escribir el test que demuestre el defecto** antes del fix (red-first).
4. **Aplicar el fix con el contrato más pequeño** que cumpla el test.
5. **Verificar con gate completo** (`make check`) y no solo con la suite nueva.
6. **Documentar** en `docs/bug-reports/` (causa raíz, evidencia, lección) y en
   este case study.

## 7. Herramientas

| Herramienta | Uso |
|---|---|
| `pytest` + `pytest-cov` | suite y cobertura con umbral bloqueante |
| `unittest.mock` / `monkeypatch` | mocks de `requests`, Jupiter, RPC, rich, scheduler |
| `ruff` | lint estricto (import sorting, excepciones BLE001 documentadas) |
| `black` | formato (con exclusión explícita de `dashboard.py`) |
| `Makefile` | `make check` → gate QA reproducible en una línea |
| GitHub Actions | CI v2: lint + format-check + cobertura (bloqueante) |

## 8. Cómo verificarlo

```bash
$ make test         # 176 passed
$ make lint         # ruff sin errores nuevos
$ make coverage     # 82.87 % sobre src/
$ make check        # los tres + gate bloqueante
```

Evidencia en vivo y screenshots del portafolio: `tests/`, `docs/qa-plan.md`,
`docs/bug-reports/`, CI `.github/workflows/ci.yml`.

## 9. Lecciones

1. **El promedio engaña:** 67 % global con fetcher al 20 % y main al 35 % era una
   colección de promedios. La política de QA de un bot financiero exige cobertura
   alta en los módulos que deciden y mueven capital.
2. **Los contratos de proveedores externos no existen:** la normalización debe
   degradarse a nivel de registro, no de lote (`try/except` amplio convierte un
   dato sucio en una caída de disponibilidad silenciosa).
3. **Los tests son cobertura de bugs, no solo de líneas:** los 44 tests nuevos
   sirvieron para cazar Bug #023 y fijar comportamientos de borde (incluso
   errores de la propia IA sin servidor).
4. **La documentación cierra el ciclo:** cada defecto con causa raíz y lección
   (Bug #011…#024) convierte el QA en know-how reutilizable y en evidencia
   auditable para hiring managers de QA.