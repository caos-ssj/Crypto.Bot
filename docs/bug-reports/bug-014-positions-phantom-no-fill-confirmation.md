# Bug #014: Posición fantasma si la compra no se confirma en cadena

**Severidad:** Alta
**Módulo:** Ejecución / Riesgo (`src/main.py` → `src/executor.py`)
**Entorno:** v2.1, modo real (`DRY_RUN=false`)
**Fecha:** 2026-09-18

## Descripción

Tras una compra real, el bot abre la posición en SQLite en cuanto Jupiter
devuelve la firma (`status: "success"`), **sin confirmar que la transacción fue
incluida en cadena** (`getSignatureStatuses`). Si la tx de compra revierte o no
se incluye (red congestionada, RPC deshonesto, fallo del proveedor de quotes),
la posición queda registrada como `open` **sin que exista saldo del token en la
wallet**. La posición "fantasma" se mantiene abierta para siempre: el flujo de
venta la rechaza con `no_balance` y el ciclo la preserva.

## Pasos para reproducir

1. Configurar `DRY_RUN=false` con una wallet real.
2. Interceptar/mockear `_send_transaction` (`src/executor.py:268`) para que
   devuelva una firma no válida (simula un swap que acabará revirtiéndose), o
   simular un RPC que acepta la tx pero la descarta después.
3. Provocar una señal `COMPRA` (score > 70).
4. `process_token` abre posición (`main.py:350-351`) como si la compra fuera
   exitosa.
5. Ejecutar ciclos siguientes: `monitor_positions` pide el saldo real de la ATA
   (`_get_token_balance`, `executor.py:339`) → `amount_lamports <= 0` →
   `{"status": "failed", "reason": "no_balance"}` → `continue` (`main.py:491-495`).
6. Confirmar que la posición nunca se cierra ni se concilia.

## Resultado esperado

- La posición solo se abre si la compra queda confirmada en cadena.
- Si la compra falla/revierte, el capital SOL usado se devuelve y la posición
  no existe.
- Si hay ambigüedad de estado, la posición se marca como `pending` y el bot la
  reintenta o la anula conforme a un criterio explícito.

## Resultado obtenido

- Se abre una posición `open` al instante de obtener la firma (`status=success`
  en `executor._send_transaction` no significa incluida).
- La venta de esa posición fantasma devuelve `no_balance` y el monitoreo
  continúa (`continue`), así que **nunca se auto-corrige**.
- La posición fantasmal es computada por `can_open_position` (máx. 3), de modo
  que puede **bloquear compras legítimas posteriores**.

## Causa raíz

Flujo de compra incompleto de la Fase A (limitación conocida y declarada en
CLAUDE.md §8, pero no mitigada):

1. `_send_transaction` devuelve la firma tras `sendTransaction`
   (`preflightCommitment: "processed"`), es decir, la tx pudo salir del
   preflight sin estar confirmada — o revertirse después.
2. No existe lectura de `getSignatureStatuses` ni reintentos de confirmación.
3. `_open_position_from_swap` (`main.py:390`) depende únicamente del
   `status` del dict de retorno; no consulta balances.

## Impacto en el capital

- **Posición fantasma = hueco de control**: el sistema cree tener exposición que
  no tiene (o un costo SOL pagado que sí tuvo). Cualquier decisión derivada
  (límites de posiciones, pérdida diaria, P&L del dashboard) parte de un estado
  falso.
- En el peor caso una compra que revierte **sí debita SOL** en la quema de
  lamports de la tx y la posición fantasma lo oculta durante horas/días.
- Bloquea operar cuando el timbre dice "3 posiciones" sin que existan.

## Evidencia de código

```python
# src/main.py:349-351
executed = swap_result.get("status") in ("dry_run", "success")
if swap_result.get("status") == "success":
    _open_position_from_swap(token, swap_result, config, mode_settings)

# src/executor.py:322-324 — "success" == firma emitida, no incluida
signature = _send_transaction(signed_tx, rpc_url)
if signature is None:
    return {"status": "failed", "reason": "send_failed"}
```

```python
# src/main.py:491-495 — venta de la fantasma → no_balance → continue (perenne)
else:
    console.print(... "se mantiene la posición.")
    continue
```

## Recomendación

1. Tras `sendTransaction`, confirmar con `getSignatureStatuses`
   (`confirmed`/`finalized`), con reintentos y timeout (p. ej. 30-60 s).
2. Validar el balance de la ATA del token después de la compra antes de dar por
   abierta la posición (`_get_token_balance`).
3. Si no hay confirmación: reintentar; si el intento falla tras N ciclos,
   marcar la posición como `stale`/`reverted`, cerrarla y devolver la SOL.
4. Añadir una ventana de "pending" que **no cuente** para el límite de 3
   posiciones hasta confirmarse.

## Lección aprendida

En bots de trading, `"enviado" ≠ "ejecutado"`. Toda decisión de estado
financiero debe anclarse a la **confirmación en cadena**, no a la firma del
preflight. Las transacciones que fallan deben tener un ciclo de vida cerrado
(dead-letter), nunca quedar huérfanas abiertas.