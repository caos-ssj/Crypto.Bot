# Revisión Crítica — Crypto Bot v2.1 (Sistema de trading autónomo en Solana)

**Fecha:** 2026-09-18
**Alcance:** 10 módulos de `src/` + `dashboard.py` + suite de tests (130 casos)
**Metodología:** Auditoría estática del código (~2.9k LOC) + validación en vivo
con token real (reporte CLI con `WIF`, dry-run, Helius/DexScreener en operación)
+ análisis de cobertura por módulo (`pytest --cov`).
**Tipo de sistema:** Bot de trading de memecoins en Solana con ejecución real
de swaps (Jupiter/solders), scoring mixto (reglas + IA local) y gestión de
riesgo TP/SL/trailing.

---

## Resumen ejecutivo

La arquitectura del bot es sólida en su diseño defensivo (política de fallos
externos conservadora, persistencia SQLite, límites de riesgo) y está bien
documentada. Sin embargo, la revisión encontró **12 hallazgos** con una
característica común y crítica: **los defectos de mayor severidad se concentran
en las rutas de ejecución real (modo dinero), que además son las de menor
cobertura de tests.**

La conclusión principal: el bot está listo para **simulación y análisis** (su
uso predominante actual), pero **no es prudente operarlo en modo real** hasta
resolver los hallazgos de alta severidad #014 (confianza en el fill) y #015
(calibración del entry). Ningún hallazgo compromete la integridad del
repositorio o del scoring offline.

---

## Métricas

| Métrica | Valor |
|---|---|
| Hallazgos totales | **12** |
| ⚫ Alta severidad | 2 |
| 🟠 Media severidad | 4 |
| 🟡 Baja severidad | 5 |
| ℹ️ Informativa (testing) | 1 |
| Código auditado | ~2.9k LOC (10 módulos + dashboard) |
| Tests | 130 pass · cobertura total 67 % |
| Cobertura crítica | `fetcher` 20 % · `main` 35 % · `executor` 76 % |
| Verificación | Estática (9/9 reportes) + smoke live en dry-run real |

---

## Matriz de riesgo (probabilidad × impacto, modo real)

| ## | Hallazgo | Prob. | Impacto | Riesgo |
|---|---|---|---|---|
| 014 | Position ghost sin confirmación de fill | Alta | Crítico | 🔴 |
| 015 | Entry = snapshot, no fill (TP/SL descalibrados) | Alta | Alto | 🔴 |
| 016 | DRY_RUN ignora límites y miente métricas | Casi seguro | Medio | 🟠 |
| 017 | Centinelas colisionan con datos reales | Alta (bajo fallo Helius) | Medio | 🟠 |
| 018 | Sin precio → SL nunca se ejecuta | Media | Alto | 🟠 |
| 019 | Edad = pairing, no mint | Media | Medio | 🟠 |
| 020 | Límite diario UTC vs dashboard local | Media | Bajo | 🟡 |
| 021 | TP vs SL: doc contradice código | Baja | Bajo (latente) | 🟡 |
| 022 | Cobertura baja en rutas del dinero | Casi seguro | Medio | 🟠 (habilitador) |

*Fuera de reporte individual (severidad baja, agrupadas en las recomendaciones):*
`mint/freeze authority` sin estado `missing` (status incierto en pantalla cuando
Helius no responde), fallback `marketCap → fdv` en el gate de MC y comparador
estricto `>` en `global_fees`.

---

## Tabla consolidada de hallazgos

| ID | Severidad | Módulo | Efecto | Acción recomendada |
|---|---|---|---|---|
| **bug-014** | ⚫ Alta | main/executor | Posición abierta sin tokens si la compra revierte; nunca se cierra | `getSignatureStatuses` + validación de balance + estado `pending` |
| **bug-015** | ⚫ Alta | main/risk | TP/SL anclados al snapshot, no al fill (desvío hasta ±5 %) | Entry price derivado del quote ejecutado |
| **bug-016** | 🟠 Media | main/storage | Simulacro ignora límites; dashboard cuenta dry-run como ejecutado | Mismo path de riesgo en dry-run + campo `simulated` |
| **bug-017** | 🟠 Media | chain_data | RPC caído = "Top-10 100 %/creador 0d" real en pantalla | Retornar `None` y mapear a `missing` |
| **bug-018** | 🟠 Media | main/fetcher | SL desarmado cuando DexScreener cae; sin tope | Precio de respaldo (Jupiter) + staleness timeout |
| **bug-019** | 🟠 Media | fetcher/analyzer | Tokens con mint vieja pasan filtro de novedad | `mint_age_minutes` desde la tx de creación |
| **bug-020** | 🟡 Baja | storage/dashboard | Día del límite en UTC vs pantalla local | TZ de negocio única y configurable |
| **bug-021** | 🟡 Baja | main/docs | Código prioriza TP; docs dicen SL | Fijar prioridad (recomendado SL) + test + doc |
| **bug-022** | ℹ️ Info | tests | Rutas del dinero sin cobertura e2e | Tests mockeando RPC/Jupiter + umbral por módulo |

---

## Análisis crítico por área

### 1. Ejecución y confirmación (el dinero real) — 🔴 prioridad 0

- La transacción se considera exitosa con la **firma del preflight**
  (`preflightCommitment: processed`). Sin `getSignatureStatuses` no hay forma de
  saber si el swap se incluyó o revirtió. El sistema construye su estado
  financiero (posición abierta, límites, P&L) sobre esa premisa frágil.
- **Riesgo concreto:** una compra revertida deja un hueco de hasta 0.05 SOL (por
  posición) en capital y una posición fantasma que bloquea el límite de 3.
  Aunque el tamaño por posición es pequeño, es exactamente el tipo de fallo que
  se amplifica en escala y erosiona la confianza en los KPIs del dashboard.

### 2. Calibración del riesgo — 🔴 prioridad 0

- TP/SL se anclan al snapshot de DexScreener con hasta ~5 % de desalineación
  posible con el fill real. En instrumentos de volatilidad extrema (memecoins),
  un SL "−10 %" que en la práctica es "−7 %" convierte a pérdidas ciertas
  posiciones que el diseño quisiera mantener. **El control más importante del
  sistema está calibrado contra un punto de referencia que no es el real.**

### 3. Honestidad de datos y de la simulación — 🟠

- Dos fallas distintas (RPC caído vs dato real extremo) se representan igual
  (Bug #017). El principio rector "nunca inflar el score" se cumple, pero la
  **veracidad del diagnóstico** no.
- El dry-run no replica las restricciones del modo real (Bug #016), que es la
  fuente de la falsa confianza típica al pasar de simulación a producción.

### 4. Disponibilidad del mecanismo de salida — 🟠

- Un SL que depende de una única fuente de precios (DexScreener) hereda su
  disponibilidad. Diseño: no vender a ciegas. Correcto como principio; peligroso
  como política única sin redundancia ni caducidad (Bug #018).

### 5. Calidad de validación y tests — 🟠 (habilitador)

- La cobertura es engañosa por agregación: 67 % global con 20 % en `fetcher` y
  35 % en `main`. Los hallazgos de mayor impacto viven en las rutas sin testear.
- El nuevo `--cov-fail-under=60` bloquea caídas, pero no exige solidez donde
  importa.

---

## Recomendaciones priorizadas

1. **Confirmación de transacciones** (`getSignatureStatuses` + reintentos) y
   **validación de balance post-compra** antes de abrir posición. → resuelve #014.
2. **Entry price del fill real** (derivado de `out_amount`/inverso del quote) y
   recálculo de TP/SL sobre ese precio; persistir `executed_price`. → #015.
3. **Redundancia de precios** para el monitoreo: Jupiter quote inversa como
   respaldo, caducidad de la última marca y alerta de staleness. → #018.
4. **Mismo camino de riesgo en dry-run** + campo `simulated` en `analyses` y KPI
   separado en dashboard. → #016.
5. **Eliminar centinelas ambiguos**: `None` + `missing` en holders/creador;
   añadir `mint_age_minutes`. → #017 y #019.
6. **Tests e2e con RPC mockeado** que cubran exactamente los 4 escenarios de red
   críticos (revert, timeout, no_balance, precio perdido) y umbral de cobertura
   **por módulo** para fetcher/main/executor. → #022.
7. **Hardening menor**: corregir la prioridad TP/SL y su doc (#021), uniformar la
   TZ del límite diario (#020), aclarar el `>` estricto de fees y el fallback
   `marketCap → fdv`.

---

## Limitaciones de la auditoría

- Revisión **estática + smoke live** (dry-run real con `WIF`); no se ejecutaron
  transacciones reales ni incidentes destructivos en producción.
- No se auditaron dependencias de terceros ni la seguridad de la wallet
  (almacenamiento de la clave privada).
- Los hallazgos de probabilidad son estimaciones del revisor basadas en el
  diseño y en la operación observada, no en estadística de producción.

---

## Veredicto

| Uso | Decisión |
|---|---|
| **Investigación / simulación / análisis histórico** | ✅ Aprobado |
| **Modo real con pequeñas cantidades** | ⚠️ Solo tras resolver #014 y #015 |
| **Modo real con capital no prescindible** | ❌ No recomendado |

Cerrar los 2 hallazgos de severidad alta reduce el riesgo operativo del sistema
a nivel medio sin necesidad de rediseño; los hallazgos de severidad baja/media
se pueden agendar como iteración de hardening sin bloquear el desarrollo.