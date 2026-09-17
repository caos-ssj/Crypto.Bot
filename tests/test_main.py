"""Tests para el orquestador principal."""

from unittest.mock import MagicMock, patch
import pytest
from src.main import (
    load_env_config,
    process_token,
    run_cycle,
)


def test_load_env_config_missing_vars(monkeypatch):
    """Falla si faltan variables obligatorias."""
    monkeypatch.delenv("SOLANA_RPC_URL", raising=False)
    with pytest.raises(EnvironmentError):
        load_env_config()


def test_load_env_config_ok(monkeypatch):
    """Carga configuración cuando todas las vars están presentes."""
    monkeypatch.setenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    monkeypatch.setenv("MODE", "equilibrado")
    monkeypatch.setenv("DRY_RUN", "true")
    config = load_env_config()
    assert config["mode"] == "equilibrado"
    assert config["dry_run"] is True


def test_process_token_score_bajo_no_compra():
    """Score bajo → no se compra."""
    token = {"symbol": "T", "token_address": "TOK1"}
    mode_settings = {"mc_min": 20000, "mc_max": 800000,
                     "max_age_min": 1440, "global_fees": 0.15, "base_buy": 0.03}
    
    with patch("src.main.analyze_token") as mock_analyze:
        mock_analyze.return_value = {"score": 30, "action": "EVITAR"}
        result = process_token(token, mode_settings, dry_run=True)
    
    assert result["action"] == "EVITAR"
    assert result["executed"] is False


def test_process_token_score_alto_compra():
    """Score alto + DRY_RUN → simula compra."""
    token = {"symbol": "T", "token_address": "TOK1"}
    mode_settings = {"mc_min": 20000, "mc_max": 800000,
                     "max_age_min": 1440, "global_fees": 0.15, "base_buy": 0.03}
    
    with patch("src.main.analyze_token") as mock_analyze, \
         patch("src.main.execute_swap") as mock_swap:
        mock_analyze.return_value = {"score": 85, "action": "COMPRA"}
        mock_swap.return_value = {"status": "dry_run", "amount_sol": 0.03}
        result = process_token(token, mode_settings, dry_run=True)
    
    assert result["action"] == "COMPRA"
    assert result["executed"] is True


def test_process_token_score_medio_observa():
    """Score medio → OBSERVAR, no ejecuta."""
    token = {"symbol": "T", "token_address": "TOK1"}
    mode_settings = {"mc_min": 20000, "mc_max": 800000,
                     "max_age_min": 1440, "global_fees": 0.15, "base_buy": 0.03}
    
    with patch("src.main.analyze_token") as mock_analyze:
        mock_analyze.return_value = {"score": 60, "action": "OBSERVAR"}
        result = process_token(token, mode_settings, dry_run=True)
    
    assert result["action"] == "OBSERVAR"
    assert result["executed"] is False


def test_run_cycle_empty_tokens():
    """Sin tokens nuevos, no hace nada."""
    with patch("src.main.detect_new_tokens", return_value=[]):
        result = run_cycle(
            seen_tokens=set(),
            mode_settings={"base_buy": 0.03},
            dry_run=True,
        )
    assert result["processed"] == 0
    assert result["executed"] == 0


def test_run_cycle_multiple_tokens():
    """Procesa varios tokens en un ciclo."""
    tokens = [
        {"symbol": "A", "token_address": "TOK1"},
        {"symbol": "B", "token_address": "TOK2"},
    ]
    
    with patch("src.main.detect_new_tokens", return_value=tokens), \
         patch("src.main.process_token") as mock_process:
        mock_process.side_effect = [
            {"executed": True},
            {"executed": False},
        ]
        result = run_cycle(
            seen_tokens=set(),
            mode_settings={"base_buy": 0.03},
            dry_run=True,
        )
    
    assert result["processed"] == 2
    assert result["executed"] == 1