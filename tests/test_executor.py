"""Tests para el ejecutor de swaps (Jupiter)."""

from unittest.mock import MagicMock, patch
import pytest
from src.executor import (
    build_swap_request,
    parse_quote_response,
    execute_swap,
    get_quote,
)


def test_build_swap_request_basic():
    """Construye el request de swap con los campos necesarios."""
    request = build_swap_request(
        quote_response={"data": "fake_quote"},
        user_public_key="PUBKEY123",
        slippage_bps=100,
    )
    assert request["userPublicKey"] == "PUBKEY123"
    assert request["slippageBps"] == 100
    assert "quoteResponse" in request


def test_parse_quote_response_valid():
    """Parsea quote válida."""
    raw = {
        "inputMint": "SOL",
        "outputMint": "TOKEN",
        "inAmount": "1000000000",
        "outAmount": "50000000000",
        "priceImpactPct": "0.005",
        "routePlan": [{"swapInfo": {}}],
    }
    result = parse_quote_response(raw)
    assert result is not None
    assert result["input_mint"] == "SOL"
    assert result["out_amount"] == 50000000000
    assert result["price_impact_pct"] == 0.005


def test_parse_quote_response_missing_fields():
    """Retorna None si faltan campos obligatorios."""
    raw = {"inputMint": "SOL"}
    result = parse_quote_response(raw)
    assert result is None


def test_parse_quote_response_invalid_price_impact():
    """Maneja priceImpactPct no numérico sin crashear."""
    raw = {
        "inputMint": "SOL",
        "outputMint": "T",
        "inAmount": "1000",
        "outAmount": "2000",
        "priceImpactPct": "invalid",
    }
    result = parse_quote_response(raw)
    assert result is not None
    assert result["price_impact_pct"] == 0.0


def test_get_quote_success():
    """Quote obtenida correctamente."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "inputMint": "SOL",
        "outputMint": "T",
        "inAmount": "1000",
        "outAmount": "2000",
        "priceImpactPct": "0.01",
    }
    with patch("src.executor._http_get", return_value=mock_response):
        result = get_quote("SOL", "T", amount_lamports=1000)
    assert result is not None
    assert result["out_amount"] == 2000


def test_get_quote_failure():
    """Retorna None si la API falla."""
    with patch("src.executor._http_get", side_effect=ConnectionError("no net")):
        result = get_quote("SOL", "T", amount_lamports=1000)
    assert result is None


def test_execute_swap_dry_run():
    """En modo DRY_RUN no envía transacción real."""
    with patch("src.executor.get_quote") as mock_quote:
        mock_quote.return_value = {
            "input_mint": "SOL",
            "output_mint": "T",
            "in_amount": 1000,
            "out_amount": 2000,
            "price_impact_pct": 0.01,
        }
        result = execute_swap(
            token_address="T",
            amount_sol=0.01,
            wallet_keypair=None,
            dry_run=True,
        )
    assert result["status"] == "dry_run"
    assert result["amount_sol"] == 0.01


def test_execute_swap_high_price_impact_aborts():
    """Si priceImpactPct > 5%, aborta."""
    with patch("src.executor.get_quote") as mock_quote:
        mock_quote.return_value = {
            "input_mint": "SOL",
            "output_mint": "T",
            "in_amount": 1000,
            "out_amount": 2000,
            "price_impact_pct": 0.10,  # 10%
        }
        result = execute_swap(
            token_address="T",
            amount_sol=0.01,
            wallet_keypair=None,
            dry_run=False,
        )
    assert result["status"] == "aborted"
    assert "price impact" in result["reason"].lower()


def test_execute_swap_no_quote():
    """Si no hay quote, retorna failed."""
    with patch("src.executor.get_quote", return_value=None):
        result = execute_swap(
            token_address="T",
            amount_sol=0.01,
            wallet_keypair=None,
            dry_run=False,
        )
    assert result["status"] == "failed"