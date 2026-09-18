# Bug #013: quote-api.jup.ag sin resolución DNS en el entorno de pruebas

**Severidad:** Baja (nota de entorno)
**Módulo:** Ejecución (src/executor.py, Jupiter)
**Entorno:** Sandbox de pruebas (Linux sin salida a dominios arbitrarios)
**Fecha:** 2026-09-18
**Estado:** ℹ️ No es bug de código — limitación de red del entorno de pruebas

## Descripción

Durante el dry-run de humo, la obtención de quote de Jupiter falla por resolución
DNS, mientras que DexScreener y Helius funcionan:

```
ERROR src.executor:get_quote:87 - Error obteniendo quote:
HTTPSConnectionPool(host='quote-api.jup.ag', port=443): Max retries exceeded
(Caused by NameResolutionError("Failed to resolve 'quote-api.jup.ag'
([Errno -2] Name or service not known)"))
```

## Resultado esperado

`get_quote` devuelve la cotización de Jupiter para el max 5% de price impact.

## Resultado obtenido

`get_quote` → `None` (`no_quote`) de forma segura; el bot continúa sin crashear
comportamiento: los fallos de red ya están acotados en `get_quote`/`_request_swap_transaction`).

## Causa raíz

- `quote-api.jup.ag` **no resuelve** en este entorno de pruebas; `api.dexscreener.com`
  y `mainnet.helius-rpc.com` sí.
- Los servicios de Jupiter (y casi todos) tienen DDoS protección; en la red del
  usuario (máquina doméstica) el dominio debería resolver sin problema.

## Solución aplicada

No aplicable al código (es limitación del entorno de red del sandbox).

## Acciones recomendadas antes de operar en real

1. Verificar conectividad con Jupiter desde la máquina del usuario:
   ```bash
   curl -s "https://quote-api.jup.ag/v6/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263&amount=100000&slippageBps=100" | head
   ```
2. Si el sandbox/CI debe probar Jupiter, permitir el tráfico hacia `quote-api.jup.ag`
   o usar un mock en los tests (ya cubierto por los unit tests con `patch`).
3. Mantener `DRY_RUN=true` hasta confirmar quotes reales desde la máquina final.

## Lección aprendida

- Los fallos de DNS/red externa no deben tumbar al bot: los wrappers de red
  (`get_quote`, `_request_swap_transaction`, `_send_transaction`) ya devuelven
  `None`/`status` determinista en vez de propagar la excepción.
- Distinguir entre bugs de código y limitaciones del entorno antes de "arreglar" un
  error que desaparecerá en producción.