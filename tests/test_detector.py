"""Tests para el módulo de detección."""

from unittest.mock import MagicMock
from src.detector import (
    parse_token_data,
    filter_new_tokens,
    detect_new_tokens,
)


def test_parse_token_data_valid():
    """Parsea un token válido de la API."""
    raw = {
        "chainId": "solana",
        "dexId": "raydium",
        "pairAddress": "ABC123",
        "baseToken": {"address": "TOKEN1", "name": "Test", "symbol": "TST"},
        "quoteToken": {"address": "SOL"},
        "priceUsd": "0.00123",
        "marketCap": 50000,
        "fdv": 50000,
        "liquidity": {"usd": 3000},
        "volume": {"h5": 2500},
        "pairCreatedAt": 1234567890000,
    }
    result = parse_token_data(raw)
    assert result is not None
    assert result["token_address"] == "TOKEN1"
    assert result["symbol"] == "TST"
    assert result["market_cap"] == 50000
    assert result["liquidity_usd"] == 3000
    assert result["volume_5min"] == 2500
    assert result["price_usd"] == 0.00123


def test_parse_token_data_missing_fields():
    """Retorna None si faltan campos críticos."""
    raw = {"chainId": "solana"}  # falta todo lo demás
    result = parse_token_data(raw)
    assert result is None


def test_parse_token_data_invalid_types():
    """No crashea con tipos inválidos, retorna valores seguros."""
    raw = {
        "chainId": "solana",
        "pairAddress": "ABC123",
        "baseToken": {"address": "TOKEN1", "symbol": "TST"},
        "priceUsd": "not_a_number",
        "marketCap": "invalid",
        "liquidity": {"usd": None},
        "volume": {"h5": "abc"},
    }
    result = parse_token_data(raw)
    assert result is not None
    assert result["price_usd"] == 0.0
    assert result["market_cap"] == 0.0
    assert result["liquidity_usd"] == 0.0
    assert result["volume_5min"] == 0.0


def test_filter_new_tokens_removes_seen():
    """Filtra tokens que ya fueron procesados."""
    tokens = [
        {"token_address": "A", "symbol": "AAA"},
        {"token_address": "B", "symbol": "BBB"},
        {"token_address": "C", "symbol": "CCC"},
    ]
    seen = {"A", "C"}
    result = filter_new_tokens(tokens, seen)
    assert len(result) == 1
    assert result[0]["token_address"] == "B"


def test_filter_new_tokens_empty_seen():
    """Si no hay tokens vistos, devuelve todos."""
    tokens = [{"token_address": "A"}, {"token_address": "B"}]
    result = filter_new_tokens(tokens, set())
    assert len(result) == 2


def test_detect_new_tokens_full_flow():
    """Flujo completo: fetch → parse → filter."""
    mock_fetch = MagicMock(return_value=[
        {
            "chainId": "solana",
            "pairAddress": "PAIR1",
            "baseToken": {"address": "TOK1", "symbol": "T1"},
            "priceUsd": "0.001",
            "marketCap": 50000,
            "liquidity": {"usd": 3000},
            "volume": {"h5": 2500},
        },
        {
            "chainId": "solana",
            "pairAddress": "PAIR2",
            "baseToken": {"address": "TOK2", "symbol": "T2"},
            "priceUsd": "0.002",
            "marketCap": 30000,
            "liquidity": {"usd": 2000},
            "volume": {"h5": 1500},
        },
    ])
    seen = {"TOK1"}  # TOK1 ya fue visto
    result = detect_new_tokens(fetch_func=mock_fetch, seen_tokens=seen)
    assert len(result) == 1
    assert result[0]["token_address"] == "TOK2"


def test_detect_new_tokens_empty_response():
    """Maneja respuesta vacía de la API."""
    mock_fetch = MagicMock(return_value=[])
    result = detect_new_tokens(fetch_func=mock_fetch, seen_tokens=set())
    assert result == []