"""Tests para fetch_recent_solana_tokens."""

from unittest.mock import MagicMock, patch
from src.detector import fetch_recent_solana_tokens


def test_fetch_filters_solana_only():
    """Solo retorna pares de Solana."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "pairs": [
            {"chainId": "solana", "pairAddress": "A"},
            {"chainId": "ethereum", "pairAddress": "B"},
            {"chainId": "solana", "pairAddress": "C"},
        ]
    }
    with patch("src.detector.requests.get", return_value=mock_response):
        result = fetch_recent_solana_tokens(query="test")
    assert len(result) == 2
    assert all(p["chainId"] == "solana" for p in result)


def test_fetch_handles_empty_response():
    """Maneja respuesta sin pares."""
    mock_response = MagicMock()
    mock_response.json.return_value = {}
    with patch("src.detector.requests.get", return_value=mock_response):
        result = fetch_recent_solana_tokens()
    assert result == []


def test_fetch_handles_network_error():
    """Retorna lista vacía si hay error de red."""
    with patch("src.detector.requests.get", side_effect=ConnectionError("no net")):
        result = fetch_recent_solana_tokens()
    assert result == []