"""Tests para main."""

from unittest.mock import patch
import pytest

from src.main import load_env_config, process_token


# ============ load_env_config ============

def test_load_env_config_missing_rpc(monkeypatch):
    """Falla si falta SOLANA_RPC_URL."""
    monkeypatch.delenv("SOLANA_RPC_URL", raising=False)
    with patch("src.main.load_dotenv"):
        with pytest.raises(EnvironmentError):
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
        "helius_api_key": "",
        "birdeye_api_key": "",
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