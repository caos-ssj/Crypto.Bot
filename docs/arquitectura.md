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

1. Detector consulta DexScreener cada 15s
2. Filtra tokens nuevos (no procesados previamente)
3. Extrae datos on-chain vía Helius
4. Analyzer aplica 11 filtros y calcula score
5. IA local evalúa contexto y ajusta score
6. Decisión: COMPRA / OBSERVAR / EVITAR
7. Si COMPRA → Executor construye y envía swap vía Jupiter
8. Risk registra posición y monitorea TP/SL

## Persistencia

- Estado de posiciones: archivo JSON (`logs/positions.json`)
- Historial de operaciones: PostgreSQL (pendiente)
- Logs: `logs/bot.log` (rotación diaria)
