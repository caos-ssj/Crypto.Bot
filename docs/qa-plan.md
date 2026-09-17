# Plan de QA — Crypto Bot

## Objetivo

Asegurar que el bot funciona correctamente bajo condiciones normales y de fallo, minimizando el riesgo de pérdidas por bugs no detectados.

## Estrategia de Testing

| Nivel | Herramienta | Frecuencia |
|-------|-------------|------------|
| Unitario | pytest | Cada commit |
| Integración | pytest + mocks | Cada PR |
| End-to-end | Manual + DRY_RUN | Semanal |
| Regresión | pytest | Antes de release |

## Áreas Críticas a Probar

### 1. Detección
- Filtrado correcto de tokens ya procesados
- Manejo de errores de API (timeout, rate limit)
- Validación de datos de entrada

### 2. Análisis (11 filtros)
- Cada filtro suma los puntos correctos
- Umbrales inclusivos/exclusivos bien definidos
- Score final normalizado (115 → 100)
- Datos faltantes = 0 pts (conservador)

### 3. IA Local
- Conexión a LM Studio (timeout, retry)
- Parseo de respuesta JSON
- Manejo de respuesta inválida
- Fallback si la IA no responde

### 4. Ejecución
- Construcción correcta de transacción Jupiter
- Manejo de slippage y priority fees
- Reintentos con backoff exponencial
- Confirmación de transacción

### 5. Gestión de Riesgo
- TP/SL se ejecutan al precio exacto
- Trailing stop ajusta correctamente
- Límite diario se respeta
- Máximo de posiciones se respeta

## Casos de Prueba por Módulo

### `test_detector.py`

| ID | Test | Entrada | Esperado |
|----|------|---------|----------|
| D-01 | Token nuevo detectado | API responde con token nuevo | Token en lista |
| D-02 | Token duplicado ignorado | Mismo token ya procesado | No se añade |
| D-03 | API timeout | Sin respuesta en 5s | Reintento, luego error |
| D-04 | API retorna vacío | Lista vacía | Lista vacía, sin crash |
| D-05 | Datos malformados | JSON inválido | Log de error, skip |

### `test_analyzer.py`

| ID | Test | Entrada | Esperado |
|----|------|---------|----------|
| A-01 | Score perfecto | Todos los filtros OK | Score = 100 |
| A-02 | Score cero | Todos los filtros fallan | Score = 0 |
| A-03 | Umbral inclusivo | MC = $20,000 | 20 pts |
| A-04 | Umbral exclusivo | MC = $19,999 | 0 pts |
| A-05 | Dato faltante | MC = None | 0 pts, sin crash |
| A-06 | Normalización | Suma = 115 | Score = 100 |

### `test_ai.py`

| ID | Test | Entrada | Esperado |
|----|------|---------|----------|
| I-01 | Respuesta válida | JSON bien formado | Score parseado |
| I-02 | Respuesta inválida | Texto plano | Fallback a 0 |
| I-03 | Timeout LM Studio | > 30s sin respuesta | Reintento 3x |
| I-04 | LM Studio offline | Connection refused | Log de error, pausa |
| I-05 | Response truncada | JSON incompleto | Fallback a filtros solo |

### `test_executor.py`

| ID | Test | Entrada | Esperado |
|----|------|---------|----------|
| E-01 | Swap exitoso | Quote válido | Transacción enviada |
| E-02 | Slippage alto | > 5% | Abortar swap |
| E-03 | Saldo insuficiente | Balance < monto | Error claro |
| E-04 | RPC caído | Timeout de red | Reintento con backoff |
| E-05 | Confirmación | Tx enviada | Verificar en 30s |

### `test_risk.py`

| ID | Test | Entrada | Esperado |
|----|------|---------|----------|
| R-01 | TP activado | Precio = entry × 1.20 | Cerrar posición |
| R-02 | SL activado | Precio = entry × 0.90 | Cerrar posición |
| R-03 | Trailing ajusta | Precio sube +5% | SL = max × 0.90 |
| R-04 | Límite diario | Pérdida = 0.5 SOL | Detener bot |
| R-05 | Máx posiciones | 3 abiertas | Ignorar nueva señal |
| R-06 | Reset medianoche | 00:00 UTC | Pérdida diaria = 0 |

## Reporte de Bugs (Formato)

Cada bug encontrado se documenta en `docs/bug-reports/` con este formato:

```markdown
# Bug #XXX: Título corto

**Severidad:** Crítica / Alta / Media / Baja
**Módulo:** detector / analyzer / ai / executor / risk
**Entorno:** Linux Mint, Python 3.12, venv

## Descripción
Qué pasó, en una frase.

## Pasos para reproducir
1. ...
2. ...
3. ...

## Resultado esperado
Qué debería haber pasado.

## Resultado obtenido
Qué pasó realmente (con logs si aplica).

## Causa raíz
Por qué ocurrió el bug.

## Solución aplicada
Cómo se resolvió.

## Lección aprendida
Qué se puede mejorar para evitar bugs similares.
Cobertura Objetivo
Módulo	Cobertura mínima
detector.py	80%
analyzer.py	90%
ai.py	70%
executor.py	80%
risk.py	90%
Comando para medir:

bash
pytest tests/ --cov=src --cov-report=html
CI/CD
GitHub Actions ejecuta en cada push:

Instalar dependencias

Correr pytest con cobertura

Fallar si cobertura < 70%

Lint con ruff y black

Datos de Prueba
Nunca usar datos reales. Los tests usan:

Mocks de APIs (DexScreener, Jupiter)

Tokens ficticios con valores conocidos

Respuestas simuladas de LM Studio

Wallet de prueba (sin fondos)

Herramientas
Herramienta	Uso
pytest	Framework de testing
pytest-cov	Cobertura de código
pytest-asyncio	Tests asíncronos
black	Formateo automático
ruff	Linting
mypy	Verificación de tipos
