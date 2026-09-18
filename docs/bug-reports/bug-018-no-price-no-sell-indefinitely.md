# Bug #018: Sin precio de DexScreener, el SL nunca se ejecuta (venta "a oscuras" sin tope temporal)

**Severidad:** Media
**Módulo:** Monitoreo de riesgo (`src/main.py:441-443`)
**Entorno:** v2.1, modo real, cualquier posición abierta
**Fecha:** 2026-09-18

## Descripción

`monitor_positions` toma la decisión de TP/SL **exclusivamente** del precio
reportado por DexScreener (`fetch_by_address`). Si esa fuente falla o no devuelve
precio, el ciclo hace `continue` y **no evalúa el stop loss** ningún ciclo hasta
que vuelva el precio. No hay límite de reintentos consecutivos, ni ventana de
vigencia, ni Plan B (RPC/Jupiter como precio de respaldo). Una caída prolongada
de DexScreener deja un SL real sin ejecutar durante todo el incidente.

## Pasos para reproducir

1. Abrir una posición arbitraria (dry-run o real).
2. Mockear `fetch_by_address` para que devuelva `None` (o timeouts) durante
   N+ ciclos.
3. Ejecutar `monitor_positions` repetidamente.
4. El stop loss no se evalúa ninguna vez: siempre "Sin precio, se omite".

## Resultado esperado

- Un precio ausente **no debe cancelar el SL**: o se usa una fuente de respaldo
  (RPC pool price, Jupiter quote inversa), o se mantiene la última marca válida
  con un tiempo de caducidad, o se dispara un mecanismo de emergencia.
- Debe haber un tope de ciclos consecutivos sin precio (state de staleness).

## Resultado obtenido

- Sin precio → `continue` sin contador. La sentencia de pérdida queda
  efectivamente desarmada por la indisponibilidad de una única API.
- La política "nunca vender a ciegas" (correcta como principio) se implementa
  como **asimetría absoluta**: se vende a mercado sin verificar nada cuando el
  precio vuelve, pero no se ejecuta nada durante la ausencia.

## Causa raíz

```python
# src/main.py:438-444
fresh = fetch_by_address(address)
price = fresh.get("price_usd") if fresh else None
if not price:
    console.print(f"[dim]Sin precio para {symbol}, se omite.[/]")
    continue
```

No existe: (a) fuente de respaldo, (b) `last_price`/`last_seen` persistido,
(c) timeout de staleness, (d) salida de emergencia.

## Impacto en el capital

- En memecoins de alta volatilidad, 15-30 min de oscuridad de precios pueden
  convertir un SL −10 % en una salida a −40 %/−60 % (rug en progreso) una vez
  que el precio retorna.
- El bot puede **vigorizar** la pérdida sin darse cuenta: no registra P&L
  durante el apagón, el límite diario nunca se entera, y la posición llega viva
  al final del túnel ya en pérdida profunda.

## Evidencia de código

```python
# src/fetcher.py:84-91 — un fallo total devuelve None (aceptable)
except Exception as e:
    logger.error(f"Error buscando por address: {e}")
    return None
```

## Recomendación

1. Persistir `last_price` y `last_seen` por posición y usar la última marca
   válida con caducidad configurable (p. ej. expira en 60 s).
2. Fuente de respaldo: quote inversa de Jupiter (token→SOL) como precio de
   monitoreo cuando DexScreener falla.
3. Contador de staleness: si N ciclos consecutivos sin precio real, disparar
   alerta (y en modo real, decisión explícita: vender a mercado o hold informado).
4. Test: simular N ciclos sin precio + aparición → verificar que el SL se
   evalúa con la marca expirada y se cierra con P&L correcto.

## Lección aprendida

La tolerancia a fallos en la entrada de datos no puede vaciar la lógica de
salida del riesgo: un sistema de stop-loss cuyo gatillo depende de una sola
fuente de precios hereda el 100 % de su disponibilidad. El riesgo necesita
fuentes redundantes y política explícita de datos obsoletos.