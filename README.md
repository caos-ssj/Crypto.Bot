# Crypto Bot — Self-Driven Memecoin Trading on Solana

![Version](https://img.shields.io/badge/version-2.0-blue)
![Status](https://img.shields.io/badge/status-in_development-yellow)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![Tests](https://img.shields.io/badge/tests-130-green)
![CI](https://github.com/caos-ssj/Crypto-Bot/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)

> Bot autónomo de trading de memecoins en Solana con análisis on-chain (Helius),
> scoring honesto de 11 filtros, IA local (Qwen3/LM Studio), ejecución real vía
> Jupiter y gestión de riesgo (TP/SL/trailing).

## Arquitectura

```
Detección (DexScreener) → Análisis (11 filtros) → IA local (Qwen3)
→ Decisión → Ejecución (Jupiter, wallet real) → Riesgo (TP/SL/trailing)
```

Detalle completo en [docs/arquitectura.md](docs/arquitectura.md).

## Características (v2.0)

- **Detección en tiempo real** vía DexScreener con persistencia de tokens vistos
  (`seen_tokens`, evita reprocesos entre reinicios).
- **Análisis on-chain honesto** (Helius): authorities, top-10 holders, wallet del dev,
  bundles y ventas del dev. Dato no verificado = 0 pts + `status: missing` (jamás
  inflar el score con datos inventados).
- **11 filtros ponderados** → score 0-100 + decisión (`>70 COMPRA · >=50 OBSERVAR`).
- **IA local** (LM Studio + Qwen3 4B, peso 30%) sin dependencia de APIs externas.
- **Ejecución real + dry-run**: swaps SOL→token y token→SOL firmados con el keypair de
  la wallet (`WALLET_PRIVATE_KEY`, base58) vía Jupiter `/v6/swap` + `sendTransaction`.
  Price-impact máximo 5%.
- **Gestión de riesgo activa**: máx 3 posiciones, pérdida diaria máx 0.5 SOL, TP +20%,
  SL -10%, trailing (+5% activa, distancia 10%), venta automática al tocar niveles.
- **Dashboard** Streamlit (`dashboard.py`) sobre SQLite, con sección de **riesgo/
  posiciones** en vivo (TP/SL/trailing, P&L y pérdida diaria).

## Instalación

```bash
git clone git@github.com:caosssj/crypto-bot.git
cd crypto-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuración

```bash
cp .env.example .env
nano .env
```

Variables requeridas:

| Variable | Descripción |
|---|---|
| `SOLANA_RPC_URL` | Endpoint RPC de Solana |
| `HELIUS_API_KEY` | API key de Helius (análisis on-chain) |
| `WALLET_PRIVATE_KEY` | Clave privada de la wallet en base58 (ejecución real) |
| `LM_STUDIO_URL` | URL del servidor local de LM Studio |
| `MODE` | `conservador` · `equilibrado` · `agresivo` |
| `DRY_RUN` | `true` simulación / `false` operaciones reales |

## Uso

```bash
python -m src.main          # menú interactivo (modos manual / automático)
streamlit run dashboard.py  # dashboard web
```

## Testing

```bash
venv/bin/python -m pytest tests/ -q
venv/bin/ruff check src/ tests/
venv/bin/black --check src/ tests/
```

## Documentación

- [docs/arquitectura.md](docs/arquitectura.md) — estructura y flujo
- [docs/filtros.md](docs/filtros.md) — los 11 filtros y su ponderación
- [docs/riesgo.md](docs/riesgo.md) — gestión de riesgo
- [docs/qa-plan.md](docs/qa-plan.md) — plan de QA
- [docs/bug-reports/](docs/bug-reports/) — bugs y lecciones aprendidas
- [CHANGELOG.md](CHANGELOG.md) — historial de versiones

## Roadmap

- [ ] Detección Pump.fun WebSocket
- [ ] Monitoreo de wallets rentables
- [ ] Filtros dinámicos
- [ ] Backtesting
- [ ] Dashboard web
- [ ] TP/SL dinámicos (ATR)
- [ ] Soporte multi-wallet
- [ ] Fine-tuning del modelo
- [ ] Integración con Telegram

## Licencia

MIT — ver `LICENSE`.

## Disclaimer

Este software es con fines educativos y de investigación. El trading de
criptomonedas conlleva riesgo de pérdida total del capital. El autor no se hace
responsable del uso indebido.