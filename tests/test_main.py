"""Tests para main."""

from unittest.mock import patch

import pytest

from src.executor import LAMPORTS_PER_SOL
from src.main import (
    _open_position_from_swap,
    load_env_config,
    monitor_positions,
    process_token,
)

# ============ load_env_config ============


def test_load_env_config_missing_rpc(monkeypatch):
    """Falla si falta SOLANA_RPC_URL."""
    monkeypatch.delenv("SOLANA_RPC_URL", raising=False)
    with patch("src.main.load_dotenv"), pytest.raises(EnvironmentError):
        load_env_config()


def test_load_env_config_ok(monkeypatch):
    """Carga configuración con todas las variables."""
    monkeypatch.setenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    monkeypatch.setenv("MODE", "equilibrado")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("USE_AI", "false")
    monkeypatch.setenv("HELIUS_API_KEY", "test-key")

    with patch("src.main.load_dotenv"):
        config = load_env_config()

    assert config["mode"] == "equilibrado"
    assert config["dry_run"] is True
    assert config["use_ai"] is False
    assert config["helius_api_key"] == "test-key"


def test_load_env_config_defaults(monkeypatch):
    """Valores por defecto cuando faltan vars opcionales."""
    monkeypatch.setenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    for var in ["MODE", "DRY_RUN", "USE_AI", "HELIUS_API_KEY", "BIRDEYE_API_KEY"]:
        monkeypatch.delenv(var, raising=False)

    with patch("src.main.load_dotenv"):
        config = load_env_config()

    assert config["mode"] == "equilibrado"
    assert config["dry_run"] is True
    assert config["use_ai"] is True
    assert config["helius_api_key"] == ""


# ============ process_token ============


@pytest.fixture
def base_config():
    """Config mínima para tests."""
    return {
        "rpc_url": "https://api.mainnet-beta.solana.com",
        "helius_api_key": "",
        "birdeye_api_key": "",
        "wallet_private_key": "",
        "mode": "equilibrado",
        "dry_run": True,
        "lm_studio_url": "http://localhost:1234",
        "lm_studio_model": "qwen/qwen3-4b-2507",
        "use_ai": False,  # desactivar IA para tests (evita llamadas)
    }


@pytest.fixture
def mode_settings():
    return {
        "mc_min": 20000,
        "mc_max": 800000,
        "max_age_min": 1440,
        "global_fees": 0.15,
        "base_buy": 0.03,
    }


def test_process_token_evitar(base_config, mode_settings):
    """Token con score bajo → EVITAR, no ejecuta."""
    token = {
        "symbol": "TEST",
        "token_address": "TOK1",
        "market_cap": 1,
        "liquidity_usd": 0,
        "volume_5min": 0,
    }
    with patch("src.main.save_analysis"):
        result = process_token(token, mode_settings, base_config, verbose=False)

    assert result["action"] == "EVITAR"
    assert result["executed"] is False
    assert result["final_score"] < 50


def test_process_token_saves_to_db(base_config, mode_settings):
    """save_analysis es llamado después del análisis."""
    token = {
        "symbol": "TEST",
        "token_address": "TOK1",
        "market_cap": 50000,
        "liquidity_usd": 5000,
        "volume_5min": 5000,
    }
    with patch("src.main.save_analysis") as mock_save:
        process_token(token, mode_settings, base_config, verbose=False)

    assert mock_save.call_count == 1
    saved_result = mock_save.call_args[0][0]
    assert "final_score" in saved_result
    assert "action" in saved_result


def test_process_token_handles_db_error(base_config, mode_settings):
    """Si save_analysis falla, el bot no crashea."""
    token = {
        "symbol": "TEST",
        "token_address": "TOK1",
        "market_cap": 1,
        "liquidity_usd": 0,
        "volume_5min": 0,
    }
    with patch("src.main.save_analysis", side_effect=Exception("DB error")):
        result = process_token(token, mode_settings, base_config, verbose=False)

    # No crashea, retorna el resultado igual
    assert "action" in result
    assert "final_score" in result


# ============ COMPRA (dry run) ============


def _high_score_token():
    """Token que pasa todos los filtros (score 100)."""
    return {
        "symbol": "LAMBRO",
        "token_address": "TOK_LAMBRO",
        "price_usd": 0.001,
        "market_cap": 50000,
        "global_fees_sol": 0.5,
        "age_minutes": 10,
        "has_bundles": False,
        "dev_has_sold": False,
        "liquidity_usd": 5000,
        "top_10_holders_pct": 20.0,
        "volume_5min": 5000,
        "creator_age_days": 30,
        "mint_authority_disabled": True,
        "freeze_authority_disabled": True,
    }


def test_process_token_compra_dry_run_executes(base_config, mode_settings):
    """COMPRA en dry_run ejecuta execute_swap pero no abre posición real."""
    token = _high_score_token()
    config = {**base_config, "use_ai": True}
    with patch("src.main.get_ai_score", return_value={"score": 100}), patch(
        "src.main.get_open_positions", return_value=[]
    ), patch("src.main.get_today_realized_loss", return_value=0.0), patch(
        "src.main.execute_swap", return_value={"status": "dry_run", "amount_sol": 0.03}
    ) as mock_swap, patch(
        "src.main.save_analysis"
    ), patch(
        "src.main.save_position"
    ) as mock_save_pos:
        result = process_token(token, mode_settings, config, verbose=False)

    assert result["action"] == "COMPRA"
    assert result["executed"] is True
    assert mock_swap.call_args.kwargs["dry_run"] is True
    assert mock_swap.call_args.kwargs["rpc_url"] == base_config["rpc_url"]
    mock_save_pos.assert_not_called()


def test_process_token_compra_blocked_by_risk(base_config, mode_settings):
    """Riesgo bloquea la compra sin ejecutar swap."""
    token = _high_score_token()
    with patch("src.main.get_ai_score", return_value={"score": 100}), patch(
        "src.main.get_open_positions", return_value=[{}, {}, {}]
    ), patch("src.main.get_today_realized_loss", return_value=0.6), patch(
        "src.main.execute_swap"
    ) as mock_swap, patch(
        "src.main.save_analysis"
    ):
        config = {**base_config, "use_ai": True, "dry_run": False}
        result = process_token(token, mode_settings, config, verbose=False)

    assert result["action"] == "COMPRA"
    assert result["executed"] is False
    mock_swap.assert_not_called()


# ============ posiciones ============


def test_open_position_from_swap_saves(base_config, mode_settings):
    """Una compra real exitosa abre la posición en la DB."""
    token = _high_score_token()  # incluye price_usd
    swap_result = {"status": "success", "amount_sol": 0.03}
    with patch("src.main.save_position") as mock_save:
        _open_position_from_swap(token, swap_result, base_config, mode_settings)

    assert mock_save.call_count == 1
    saved = mock_save.call_args[0][0]
    assert saved["token_address"] == "TOK_LAMBRO"
    assert saved["entry_price"] == 0.001
    assert saved["tp_price"] == pytest.approx(0.0012)
    assert saved["sl_price"] == pytest.approx(0.0009)


def test_monitor_positions_sells_at_tp(base_config):
    """Al llegar al TP: vende y cierra la posición con pnl correcto."""
    row = {
        "token_address": "TOK_LAMBRO",
        "symbol": "LAMBRO",
        "entry_price": 0.001,
        "amount_sol": 0.03,
        "tp_price": 0.0012,
        "sl_price": 0.0009,
        "trailing_active": 0,
        "max_price_reached": 0.001,
        "opened_at": "2026-09-18T00:00:00+00:00",
    }
    out_sol_lamports = int(0.04 * LAMPORTS_PER_SOL)
    config = {**base_config, "dry_run": False}
    with patch("src.main.get_open_positions", return_value=[row]), patch(
        "src.main.fetch_by_address", return_value={"price_usd": 0.0015}
    ), patch(
        "src.main.execute_sell",
        return_value={"status": "success", "out_amount_sol": out_sol_lamports},
    ) as mock_sell, patch(
        "src.main.update_position_state"
    ), patch(
        "src.main.close_position"
    ) as mock_close:
        monitor_positions(config)

    mock_sell.assert_called_once()
    _, exit_price, pnl = mock_close.call_args[0]
    assert exit_price == 0.0015
    assert pnl == pytest.approx(0.01)  # 0.04 recibidos - 0.03 invertidos


def test_monitor_positions_updates_trailing(base_config):
    """Precio subiendo activa trailing y persiste el nuevo SL."""
    row = {
        "token_address": "TOK_LAMBRO",
        "symbol": "LAMBRO",
        "entry_price": 0.001,
        "amount_sol": 0.03,
        "tp_price": 0.002,
        "sl_price": 0.0009,
        "trailing_active": 0,
        "max_price_reached": 0.001,
        "opened_at": "2026-09-18T00:00:00+00:00",
    }
    with patch("src.main.get_open_positions", return_value=[row]), patch(
        "src.main.fetch_by_address", return_value={"price_usd": 0.0011}
    ), patch("src.main.execute_sell"), patch(
        "src.main.update_position_state"
    ) as mock_update, patch(
        "src.main.close_position"
    ):
        monitor_positions(base_config)  # dry_run=True: no vende de verdad

    assert mock_update.call_count == 1
    kwargs = mock_update.call_args
    assert kwargs.args[0] == "TOK_LAMBRO"
    assert kwargs.args[1] == pytest.approx(0.00099)  # SL subido con trailing (+10%)
    assert kwargs.args[2] is True  # trailing activado
    assert kwargs.args[3] == pytest.approx(0.0011)  # máximo alcanzado
