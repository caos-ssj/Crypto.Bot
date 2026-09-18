"""Tests para chain_data (Helius)."""

from unittest.mock import patch
from src.chain_data import (
    get_mint_info,
    get_top_holders_pct,
    get_creator_age_days,
    enrich_token,
)


def test_get_mint_info_disabled():
    """Authorities deshabilitadas correctamente."""
    fake_result = {
        "value": {
            "data": {
                "parsed": {
                    "info": {
                        "mintAuthority": None,
                        "freezeAuthority": None,
                        "supply": "1000000000",
                        "decimals": 9,
                    }
                }
            }
        }
    }
    with patch("src.chain_data._rpc_call", return_value=fake_result):
        info = get_mint_info("MINT", "key")
    assert info["mint_authority_disabled"] is True
    assert info["freeze_authority_disabled"] is True
    assert info["supply"] == 1000000000


def test_get_mint_info_enabled():
    """Authorities activas → disabled=False."""
    fake_result = {
        "value": {
            "data": {
                "parsed": {
                    "info": {
                        "mintAuthority": "WALLET123",
                        "freezeAuthority": "WALLET123",
                        "supply": "1000",
                        "decimals": 6,
                    }
                }
            }
        }
    }
    with patch("src.chain_data._rpc_call", return_value=fake_result):
        info = get_mint_info("MINT", "key")
    assert info["mint_authority_disabled"] is False
    assert info["freeze_authority_disabled"] is False


def test_get_mint_info_null_response():
    """Si el RPC no devuelve nada, defaults seguros."""
    with patch("src.chain_data._rpc_call", return_value=None):
        info = get_mint_info("MINT", "key")
    assert info["mint_authority_disabled"] is False
    assert info["supply"] == 0


def test_get_top_holders_pct_valid():
    """Calcula bien el porcentaje."""
    largest = {"value": [{"amount": "100"}, {"amount": "100"}]}
    supply = {"value": {"amount": "1000"}}
    
    with patch("src.chain_data._rpc_call", side_effect=[largest, supply]):
        pct = get_top_holders_pct("MINT", "key")
    assert pct == 20.0


def test_get_top_holders_pct_empty():
    """Si no hay holders, retorna 100 (conservador)."""
    with patch("src.chain_data._rpc_call", return_value=None):
        pct = get_top_holders_pct("MINT", "key")
    assert pct == 100.0


def test_get_creator_age_days_valid():
    """Calcula edad a partir de la firma más antigua."""
    import time
    now = int(time.time())
    signatures = [{"blockTime": now - 86400 * 5}]  # 5 días atrás
    
    with patch("src.chain_data._rpc_call", return_value=signatures):
        age = get_creator_age_days("WALLET", "key")
    assert 4 <= age <= 6  # tolerancia por tiempo entre llamadas


def test_get_creator_age_days_empty():
    """Sin firmas → 0 días."""
    with patch("src.chain_data._rpc_call", return_value=[]):
        age = get_creator_age_days("WALLET", "key")
    assert age is None


def test_enrich_token_adds_fields():
    """enrich_token añade los campos on-chain."""
    token = {"token_address": "MINT", "symbol": "T", "creator_address": "CREATOR123"}
    fake_mint = {
        "mint_authority_disabled": True,
        "freeze_authority_disabled": True,
        "supply": 1_000_000,
        "decimals": 6,
    }
    
    with patch("src.chain_data.get_mint_info", return_value=fake_mint), \
         patch("src.chain_data.get_top_holders_pct", return_value=25.0), \
         patch("src.chain_data.get_creator_age_days", return_value=30):
        result = enrich_token(token, "key")
    
    assert result["mint_authority_disabled"] is True
    assert result["top_10_holders_pct"] == 25.0
    assert result["creator_age_days"] == 30
    assert "age_minutes" in result
    assert "global_fees_sol" in result

def test_enrich_token_preserves_unknown_security_data():
    token = {"token_address": "MINT"}
    with patch("src.chain_data.get_mint_info", return_value={
        "mint_authority_disabled": None,
        "freeze_authority_disabled": None,
        "supply": None,
        "decimals": None,
    }), patch("src.chain_data.get_top_holders_pct", return_value=None):
        result = enrich_token(token, "key")

    assert result["has_bundles"] is None
    assert result["dev_has_sold"] is None
    assert result["global_fees_sol"] is None
    assert result["top_10_holders_pct"] is None
