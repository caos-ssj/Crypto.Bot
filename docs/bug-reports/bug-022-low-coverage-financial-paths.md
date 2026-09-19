# Bug #022: Brecha de cobertura de tests en las rutas financieras reales

**Severidad:** Informativa (riesgo de QA / deuda técnica de testeo)
**Módulo:** Testing — `src/fetcher.py`, `src/main.py`, `src/executor.py`
**Entorno:** v2.1, cobertura medida por `pytest --cov=src`
**Fecha:** 2026-09-18
**Estado:** ✅ Resuelto — ampliación de cobertura ejecutada el 2026-09-18 (ver sección al final)

## Descripción

La suite (130 tests) cubre razonablemente analyzer (96 %), storage (98 %),
risk (100 %), config (100 %) y utils (100 %), pero los módulos que tocan el
**camino del dinero** tienen los huecos más grandes:

| Módulo | Cobertura | Comentario crítico |
|---|---|---|
| `fetcher.py` | **20 %** | Normalización DexScreener: primer eslabón del pipeline casi sin tests |
| `main.py` | **35 %** | Orquestador: `process_token`, límites, monitoreo, decisión |
| `executor.py` | 76 % | El 24 % restante son justo los paths **reales** (firma/envío) |

## Pasos para reproducir

1. `venv/bin/python -m pytest tests/ -q --cov=src --cov-fail-under=60`.
2. Observar cobertura por módulo (fetcher 20 %, main 35 %).
3. Revisar en `tests/` la ausencia de casos que ejerciten `_send_transaction` de
   venta real, confirmación de fill y monitoreo con precio obsoleto.

## Resultado esperado

Los mecanismos que mueven dinero (compra real, venta real, confirmación,
monitor con fill revertido) deberían tener tests con mocks de Jupiter/RPC que
cubran: éxito, revert, timeout, no_balance, price impact excedido, tope de
reintentos y "stale price".

## Resultado obtenido

- Los tests de `executor` validan quotes, dry-run y parsers; los de `main`, el
  flujo de decisión con mocks **parciales**. No existe ningún test que:
  - encole un `sendTransaction` que revierte y verifique la ausencia de
    posición fantasma (Bug #014);
  - fuerce divergencia precio-snapshot/fill y valide TP/SL del fill (Bug #015);
  - valide stops con precio obsoleto/inexistente (Bug #018);
  - verifique límites de riesgo dentro del propio dry-run (Bug #016).
- Combinado con los Bug #014/#015/#016/#018: **los defectos de mayor impacto
  financiero viven exactamente en las rutas sin cobertura**.

## Causa raíz

Priorización histórica de la Fase A: primero se implementaron swaps reales y
después se reorganizó el testeo; los casos de borde de red (fallos de inclusión,
fill divergente, disponibilidad de precios) no se tabularon como obligatorios
antes de dar el flujo por cerrado.

## Impacto en la decisión

- El umbral `--cov-fail-under=60` da falsa sensación de robustez: el promedio
  es 67 % pero **el área que decide el capital es la menos cubierta**.
- Todo defecto e2e financiero probablemente solo se descubrirá en producción
  real, donde el costo se paga en SOL y no en CPU de CI.

## Evidencia

```bash
$ venv/bin/python -m pytest tests/ -q --cov=src --cov-fail-under=60
fetcher.py     65     52    20%
main.py       347    227    35%
executor.py   178     42    76%
TOTAL        1109    366    67%
130 passed
```

## Recomendación

1. Tests e2e con RPC mockeado para: compra exitosa, revertida, timeout, sin
   confirmación; venta completa; impact > 5 %; salida sin precio; aparición de
   precio tras N ciclos.
2. Tests de analyzer/risk para `hit_tp and hit_sl` (Bug #021) y para centinelas
   `None` (Bug #017).
3. Sustituir el promedio global por un requisito **por módulo crítico**
   (fetcher/main/executor ≥ 60-70 %) para que la cobertura deje de ser una
   colección de promedios engañosos.
4. Añadir checklist de QA "modo real" en `docs/qa-plan.md` con los escenarios de
   red del punto 1.

## Lección aprendida

La cobertura agregada oculta las islas de riesgo. En bots financieros, la
política de testeo debe exigir cobertura **alta en los módulos que firman y
envían transacciones** (confirmación, fallos, reintentos) antes que subir el
promedio de módulos triviales. El test que no existe para un caso de pérdida
real es un huérfano en el presupuesto de QA.
---

## ✅ Resolución (2026-09-18)

Ampliación de la suite sobre los dos huecos críticos identificados:

| Módulo | Antes | Después |
|---|---|---|
| `fetcher.py` | 20 % | **94 %** (19 tests) |
| `main.py` | 35 % | **70 %** (36 tests) |
| `executor.py` | 76 % | 76 % |
| `risk.py` | 100 % | 100 % |
| **TOTAL** | **67 %** (130 tests) | **83 %** (174 tests) |

Cobertura de `--cov-fail-under=60` → gate local `make check` con mismo umbral.
Durante la ampliación se detectó y corrigió un defecto nuevo (Bug #023: par
malformado de DexScreener que anulaba la búsqueda completa), cubierto con tests
de regresión.

Quedan pendientes como deuda de QA, menores:
- `main.py` (~70 %): UI rich (`show_token_report` en mayor detalle) y escenarios
  e2e completos con scheduler (TP/SL real vía mock de Jupiter).
- `executor.py` (76 %): paths reales de firma/envío con RPC mockeado siguen
  siendo los menos cubiertos (recomendación 1 del informe).
