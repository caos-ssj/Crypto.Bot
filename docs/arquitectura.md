# Arquitectura del Bot

## Visión General

Bot autónomo de trading de memecoins en Solana. Detecta tokens nuevos, los analiza con 11 filtros ponderados, usa IA local para scoring, y ejecuta operaciones con gestión de riesgo.

## Diagrama de Flujo
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Detección │ → │ Análisis │ → │ IA │
│ (DexScreener)│ │(11 filtros) │ │ (Qwen3 4B) │
└─────────────┘ └─────────────┘ └─────────────┘
↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Riesgo │ ← │ Ejecución │ ← │ Decisión │
│ (TP/SL) │ │ (Jupiter) │ │ (Score) │
└─────────────┘ └─────────────┘ └─────────────┘

## Módulos

### 1. Detección (`src/detector.py`)
- **Fuente:** DexScreener API (polling cada 15s)
- **Función:** Detectar tokens nuevos y extraer datos on-chain
- **Salida:** Lista de tokens candidatos con metadata

### 2. Análisis (`src/analyzer.py`)
- **Función:** Aplicar 11 filtros ponderados
- **Salida:** Score numérico (0-100)
- **Umbral:** COMPRA > 70, OBSERVAR 50-70, EVITAR < 50

### 3. IA Local (`src/ai.py`)
- **Modelo:** Qwen3 4B 2507 (Q4_K_M) vía LM Studio
- **Función:** Scoring cualitativo y análisis de contexto
- **Salida:** Score complementario y razonamiento

### 4. Ejecución (`src/executor.py`)
- **Fuente:** Jupiter API
- **Función:** Construir y enviar transacciones de swap
- **Parámetros:** Slippage, priority fee, compute units

### 5. Gestión de Riesgo (`src/risk.py`)
- **TP:** 20%
- **SL:** 10%
- **Trailing Stop:** Activado
- **Límite diario:** 0.5 SOL
- **Máximo posiciones:** 3

### 6. Configuración (`src/config.py`)
- **Fuente:** Variables de entorno (.env) + YAML (config/config.yaml)
- **Modos:** Conservador, Equilibrado, Agresivo

## Stack Tecnológico

| Capa | Herramienta |
|------|-------------|
| Lenguaje | Python 3.11+ |
| Blockchain | solana-py, solders, anchorpy |
| Ejecución | Jupiter API |
| IA Local | LM Studio + Qwen3 4B |
| RPC | Helius / Solana público |
| Datos | DexScreener API |
| Testing | pytest |
| CI/CD | GitHub Actions |

## Modos de Operación

| Modo | MC mínimo | MC máximo | Edad máx | Global Fees | Compra base |
|------|-----------|-----------|----------|-------------|-------------|
| Conservador | $50K | $500K | 720 min | 0.3 SOL | 0.05 SOL |
| Equilibrado | $20K | $800K | 1440 min | 0.15 SOL | 0.03 SOL |
| Agresivo | $5K | $1M | 2880 min | 0.05 SOL | 0.01 SOL |

## Flujo de Datos

1. Fetcher consulta DexScreener cada 15s
2. Filtra tokens nuevos usando el histórico persistido (`seen_tokens` en SQLite)
3. Extrae datos on-chain vía Helius: mint/freeze authority, top holders, wallet
   del dev (fee payer de la tx de creación), bundles y ventas del dev
   (escanear transacciones de la mint). Todo con caché y fallo conservador (`None`)
4. Analyzer aplica 11 filtros y calcula score (datos no verificados → 0 pts)
5. IA local evalúa contexto y ajusta score
6. Decisión unificada (`analyzer.decide`): COMPRA / OBSERVAR / EVITAR
7. Si COMPRA → Executor construye y envía swap vía Jupiter
8. Risk registra posición y monitorea TP/SL
9. Cada token procesado se marca como visto en `seen_tokens`

## Persistencia

- Análisis e histórico de tokens procesados: SQLite (`logs/bot.db`)
  - Tabla `analyses`: reportes por token.
  - Tabla `seen_tokens`: evita reprocesar tokens entre reinicios.
  - Tabla `positions`: posiciones abiertas/cerradas (pendiente de conexión con Risk).
- Estado de posiciones: JSON (`logs/positions.json`) — pendiente de migrar a SQLite
- Logs: `logs/bot.log` (rotación diaria)
## Resiliencia ante Fallos Externos

El bot consulta múltiples APIs externas (DexScreener, Helius, LM Studio). Cada una puede fallar de forma independiente.

### Estrategia de manejo de fallos

| Fuente | Fallo típico | Manejo |
|--------|--------------|--------|
| DexScreener | Timeout / rate limit | Retry con backoff → lista vacía |
| Helius RPC | 500 server error | Filtro devuelve valor conservador (falla el filtro, no el bot) |
| LM Studio | Offline / timeout | Fallback a score 0, decisión basada solo en reglas |
| Jupiter | Sin quote | Aborta swap, registra en log |

### Principio de diseño

**Un fallo de API externa nunca debe detener el ciclo completo del bot.**

- Cada módulo captura sus excepciones
- El scoring continúa con datos parciales (conservador)
- El bot sigue corriendo aunque Helius, LM Studio o DexScreener fallen

Esto se probó en producción: durante un ciclo real, Helius devolvió `500 Server Error` en `getTokenSupply` y el bot continuó analizando tokens sin interrupción.
