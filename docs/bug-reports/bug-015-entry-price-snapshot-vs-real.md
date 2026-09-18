# Bug #015: El precio de entrada (TP/SL) usa el snapshot de DexScreener, no el fill real

**Severidad:** Alta
**Módulo:** Riesgo / Ejecución (`src/main.py:390-423`)
**Entorno:** v2.1, modo real (`DRY_RUN=false`)
**Fecha:** 2026-09-18

## Descripción

El precio de entrada del `Position` —y por tanto el TP (+20 %) y el SL (−10 %)—
se calcula con el `price_usd` **del snapshot de DexScreener capturado en el
análisis**, no con el precio real al que Jupiter ejecutó el swap. Entre el
análisis y el fill real hay un gap temporal (15 s+ de latencia) y el slippage
permitido llega al **1 %** con un **price impact admitido hasta el 5 %**
(`executor.py:15`). El resultado: los niveles de protección no están calibrados
sobre el costo real de la posición.

## Pasos para reproducir

1. Modo real, señal `COMPRA`.
2. Provocar divergencia precio-snapshot vs fill: tokens volátiles o con slippage
   alto (quote con impacto 3-5 %).
3. Comparar el `entry_price` guardado en `positions` (`main.py:420`) con el
   `out_amount`/precio implícito del quote ejecutado.
4. Observar que TP/SL derivados pueden dispararse antes o después de lo
   calibrado respecto al fill real.

## Resultado esperado

El `entry_price` debe ser el **precio de ejecución real** (derivado de
`out_amount`/`in_amount` del quote confirmado), y el TP/SL de ese precio.

## Resultado obtenido

- `entry_price = token["price_usd"]` del snapshot (o un refetch adicional,
  `main.py:401-402`, que tampoco es el fill).
- Un fill un 3 % peor que el snapshot implica:
  - El SL "−10 %" efectivo se alcanza con una caída real de solo **−7 %** desde
    el costo real.
  - El TP "+20 %" real se dispara con una suba de **+17 %** desde el fill.
- Con el fill un 5 % mejor, el TP/SL se recorre en la dirección inversa y el
  bot deja ganancia sobre la mesa o aguanta pérdida de más.

## Causa raíz

`_open_position_from_swap` (`main.py:390`) ignora el resultado del quote:

```python
price = token.get("price_usd")          # snapshot del análisis
if not price:
    fresh = fetch_by_address(...)        # otro snapshot, no el fill
    ...
tp, sl = calculate_tp_sl(price)         # risk.py:33-44
position = Position(entry_price=price, tp_price=tp, sl_price=sl, ...)
```

El dict de `execute_swap` sí porta `quote["out_amount"]` y
`quote["price_impact_pct"]` (`executor.py:163-167`, `330-336`), disponibles
para derivar el precio real, pero no se usan.

## Impacto en el capital

- La **calibración del riesgo es inexacta por diseño**: TP/SL se anclan a una
  referencia que puede diferir del costo real en hasta ~5 % en tokens de baja
  liquidez (los que el propio bot favorece).
- SL que se dispara "antes de lo previsto": destruye posiciones que estaban
  dentro del perfil de riesgo calculado.
- TP que se dispara "tarde": deja P&L positivo sin materializar.

## Evidencia de código

```python
# src/main.py:398-420 (versión real)
price = token.get("price_usd")
if not price:
    fresh = fetch_by_address(token["token_address"])
    price = fresh.get("price_usd") if fresh else None
...
tp, sl = calculate_tp_sl(price)
position = Position(token_address=..., entry_price=price, tp_price=tp, sl_price=sl, ...)

# src/executor.py:330-334 — el dato real existe pero no llega a la posición
return {
    "status": "success",
    "out_amount": quote["out_amount"],
    "quote": quote,
}
```

## Recomendación

1. Derivar `entry_price` del **quote ejecutado**: `price_usd = SOL_in / (out_amount / 10^decimals)` — o usar el precio implícito de Jupiter si lo reporta.
2. Persistir `executed_price`, `expected_out`, `slippage_real` en `positions`
   para auditoría.
3. Recalcular TP/SL sobre ese precio ejecutado, no sobre el snapshot.
4. Añadir test de integración que fuerce divergencia snapshot/fill y valide los
   niveles resultantes.

## Lección aprendida

El riesgo debe calibrarse sobre **datos de ejecución**, nunca sobre la última
observación de mercado previa. En sistemas de trading, el "entry" es un dato de
transacción, no de tarjeta de cotización.