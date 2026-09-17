# Crypto Bot — Autonomous Memecoin Trading on Solana

![Status](https://img.shields.io/badge/status-in_development-yellow)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> Bot autónomo de trading de memecoins en Solana con análisis on-chain, IA local y gestión de riesgo.

## Descripción

Este bot detecta tokens nuevos en Solana, los analiza mediante 11 filtros ponderados, usa un modelo de lenguaje local (Qwen3 4B) para scoring cualitativo, y ejecuta operaciones vía Jupiter API con gestión de riesgo configurable.

**Características principales:**
- Detección en tiempo real vía DexScreener
- Análisis on-chain con 11 filtros ponderados
- Scoring con IA local (sin dependencia de APIs externas)
- Ejecución vía Jupiter API
- Gestión de riesgo: TP, SL, trailing stop, límite diario
- Tres modos de operación: Conservador, Equilibrado, Agresivo

## Arquitectura
Detección → Análisis → IA → Decisión → Ejecución → Riesgo

text

Ver [docs/arquitectura.md](docs/arquitectura.md) para el detalle completo.

## Instalación

```bash
git clone git@github.com:caosssj/crypto-bot.git
cd crypto-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Configuración
Copia el archivo de ejemplo y edita tus credenciales:

bash
cp .env.example .env
nano .env
Variables requeridas:

SOLANA_RPC_URL — Endpoint RPC de Solana

HELIUS_API_KEY — API key de Helius (opcional)

WALLET_PRIVATE_KEY — Clave privada de la wallet (base58)

LM_STUDIO_URL — URL del servidor local de LM Studio

MODE — Modo de operación (conservador, equilibrado, agresivo)

DRY_RUN — true para simulación, false para operaciones reales

Testing
bash
pytest tests/ -v
pytest tests/ --cov=src --cov-report=html
Documentación
Arquitectura

Filtros

Gestión de riesgo

Plan de QA

Roadmap
□ Detección Pump.fun WebSocket
□ Monitoreo de wallets rentables
□ Filtros dinámicos
□ Backtesting
□ Dashboard web
□ TP/SL dinámicos (ATR)
□ Soporte multi-wallet
□ Fine-tuning del modelo
□ Integración con Telegram
Licencia
MIT — ver LICENSE

Disclaimer
Este software es con fines educativos y de investigación. El trading de criptomonedas conlleva riesgo de pérdida total del capital. El autor no se hace responsable del uso indebido.

text

**3. Guarda y sal:**
- Presiona `Ctrl + O` (guardar)
- Presiona `Enter` (confirma el nombre)
- Presiona `Ctrl + X` (salir)

---

### 🎯 Opción 2: Un solo comando (si prefieres terminal)

Copia y pega **todo esto** de una sola vez:

```bash
cat > ~/proyectos/crypto-bot/README.md << 'ENDOFREADME'
# Crypto Bot — Autonomous Memecoin Trading on Solana

![Status](https://img.shields.io/badge/status-in_development-yellow)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> Bot autónomo de trading de memecoins en Solana con análisis on-chain, IA local y gestión de riesgo.

## Descripción

Este bot detecta tokens nuevos en Solana, los analiza mediante 11 filtros ponderados, usa un modelo de lenguaje local (Qwen3 4B) para scoring cualitativo, y ejecuta operaciones vía Jupiter API con gestión de riesgo configurable.

## Arquitectura
Detección → Análisis → IA → Decisión → Ejecución → Riesgo

text

Ver [docs/arquitectura.md](docs/arquitectura.md) para el detalle completo.

## Instalación

```bash
git clone git@github.com:caosssj/crypto-bot.git
cd crypto-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Configuración
bash
cp .env.example .env
nano .env
Testing
bash
pytest tests/ -v
Documentación
Arquitectura

Filtros

Gestión de riesgo

Plan de QA

Roadmap
□ Detección Pump.fun WebSocket
□ Monitoreo de wallets rentables
□ Filtros dinámicos
□ Backtesting
□ Dashboard web
□ TP/SL dinámicos (ATR)
□ Soporte multi-wallet
□ Fine-tuning del modelo
□ Integración con Telegram
Licencia
MIT

Disclaimer
Software con fines educativos. El trading de criptomonedas conlleva riesgo de pérdida total.
ENDOFREADME



