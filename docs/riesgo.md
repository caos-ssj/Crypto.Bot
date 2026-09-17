# Gestión de Riesgo

## Parámetros Principales

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| Take Profit (TP) | 20% | Vender al alcanzar +20% |
| Stop Loss (SL) | 10% | Vender al caer -10% |
| Trailing Stop | Activado | Ajusta SL dinámicamente |
| Límite diario pérdida | 0.5 SOL | Detiene operaciones si se alcanza |
| Máximo posiciones | 3 | No abre más si ya hay 3 abiertas |

## Take Profit (TP)

- **Objetivo:** Asegurar ganancias al +20%
- **Ejecución:** Venta a mercado cuando el precio alcanza el umbral
- **Venta escalonada:** Opcional, vender 50% al +20% y dejar el resto correr
- **Caso de prueba:** Precio entra a +20.1% → ejecutar venta

## Stop Loss (SL)

- **Objetivo:** Limitar pérdidas al -10%
- **Ejecución:** Venta a mercado cuando el precio cae al umbral
- **Prioridad:** SL siempre tiene prioridad sobre TP si ambos se disparan
- **Caso de prueba:** Precio cae a -10.1% → ejecutar venta

## Trailing Stop

- **Funcionamiento:** El SL se mueve hacia arriba conforme el precio sube
- **Activación:** Cuando el precio sube +5% desde la entrada
- **Distancia:** 10% por debajo del precio máximo alcanzado
- **Ejemplo:**
  - Entrada: $100
  - Precio sube a $120 → SL sube a $108 (10% por debajo)
  - Precio sube a $150 → SL sube a $135
  - Precio cae a $135 → se ejecuta venta
- **Caso de prueba:** Precio máximo $150, cae a $134.9 → ejecutar venta

## Límite Diario de Pérdida

- **Umbral:** 0.5 SOL de pérdida acumulada en 24h
- **Reset:** A medianoche UTC
- **Acción al alcanzar:** Detiene todas las operaciones hasta el próximo día
- **Persistencia:** Se guarda en `logs/daily_loss.json`
- **Caso de prueba:** Pérdida acumulada = 0.51 SOL → detener bot

## Máximo de Posiciones

- **Límite:** 3 posiciones abiertas simultáneamente
- **Acción al alcanzar:** No abre nuevas hasta cerrar una
- **Prioridad:** Se cierra la posición con peor rendimiento si hay empate
- **Caso de prueba:** 3 posiciones abiertas + nueva señal → ignorar señal

## Modos de Operación

### Conservador
- Compra base: 0.05 SOL
- Máximo exposición: 0.15 SOL (3 × 0.05)
- Perfil: Bajo riesgo, pocas operaciones

### Equilibrado
- Compra base: 0.03 SOL
- Máximo exposición: 0.09 SOL
- Perfil: Balance entre riesgo y oportunidad

### Agresivo
- Compra base: 0.01 SOL
- Máximo exposición: 0.03 SOL
- Perfil: Más operaciones, menor tamaño

## Flujo de Evaluación de Riesgo
Detectar token nuevo

Calcular score

¿Score > 70?

NO → ignorar

SÍ → continuar

¿Posiciones abiertas < 3?

NO → ignorar

SÍ → continuar

¿Pérdida diaria < 0.5 SOL?

NO → detener bot

SÍ → continuar

Ejecutar compra con tamaño según modo

Registrar posición y monitorear TP/SL

text

## Casos de Prueba (QA)

| ID | Caso | Escenario | Resultado esperado |
|----|------|-----------|-------------------|
| R-01 | TP alcanzado | Precio +20% | Vender, cerrar posición |
| R-02 | SL alcanzado | Precio -10% | Vender, cerrar posición |
| R-03 | Trailing activo | Precio +5%, luego cae 10% | Vender con ganancia |
| R-04 | Límite diario | Pérdida acumulada 0.5 SOL | Detener bot 24h |
| R-05 | Máximo posiciones | 3 abiertas + señal | Ignorar señal |
| R-06 | Modo conservador | Señal con score 75 | Compra 0.05 SOL |
| R-07 | Reset diario | Medianoche UTC | Pérdida diaria = 0 |

## Registro de Posiciones

Cada posición abierta se registra en `logs/positions.json`:

```json
{
  "id": "pos-001",
  "token": "TOKEN_ADDRESS",
  "entry_price": 0.000123,
  "amount_sol": 0.05,
  "tp_price": 0.0001476,
  "sl_price": 0.0001107,
  "trailing_active": false,
  "max_price_reached": 0.000123,
  "opened_at": "2026-09-17T14:30:00Z"
}
Advertencias
El trailing stop solo se activa después de +5% de ganancia

El límite diario se resetea a medianoche UTC, no hora local

Si la API de precios falla, el bot pausa las operaciones (no vende a ciegas)

Las ventas siempre son a mercado (no hay órdenes límite en memecoins)
