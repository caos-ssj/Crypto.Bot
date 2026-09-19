"""Tests para el módulo de IA local (LM Studio)."""

from unittest.mock import MagicMock, patch

from src.ai import (
    _call_lm_studio,
    build_prompt,
    get_ai_score,
    parse_ai_response,
)


def test_build_prompt_contains_token_info():
    """El prompt incluye datos clave del token."""
    token = {
        "symbol": "TEST",
        "market_cap": 50000,
        "liquidity_usd": 5000,
        "volume_5min": 3000,
        "top_10_holders_pct": 25.0,
        "age_minutes": 100,
    }
    prompt = build_prompt(token)
    assert "TEST" in prompt
    assert "50000" in prompt or "50,000" in prompt
    assert "JSON" in prompt


def test_parse_ai_response_valid_json():
    """Parsea respuesta JSON válida."""
    response = '{"score": 75, "reason": "Token con buena liquidez"}'
    result = parse_ai_response(response)
    assert result is not None
    assert result["score"] == 75
    assert "liquidez" in result["reason"].lower()


def test_parse_ai_response_json_with_text_around():
    """Extrae JSON aunque venga con texto alrededor."""
    response = 'Aquí está mi análisis:\n{"score": 80, "reason": "OK"}\nFin.'
    result = parse_ai_response(response)
    assert result is not None
    assert result["score"] == 80


def test_parse_ai_response_invalid():
    """Retorna None si no hay JSON válido."""
    response = "No puedo responder eso."
    result = parse_ai_response(response)
    assert result is None


def test_parse_ai_response_missing_keys():
    """Retorna None si faltan claves obligatorias."""
    response = '{"foo": "bar"}'
    result = parse_ai_response(response)
    assert result is None


def test_get_ai_score_success():
    """Retorna score parseado cuando la API responde bien."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"score": 85, "reason": "Buen token"}'

    with patch("src.ai._call_lm_studio", return_value=mock_response):
        result = get_ai_score({"symbol": "T"}, base_url="http://localhost:1234")

    assert result["score"] == 85
    assert result["fallback"] is False


def test_get_ai_score_api_error():
    """Retorna fallback si la API falla."""
    with patch("src.ai._call_lm_studio", side_effect=ConnectionError("no server")):
        result = get_ai_score({"symbol": "T"}, base_url="http://localhost:1234")

    assert result["score"] == 0
    assert result["fallback"] is True


def test_get_ai_score_invalid_response():
    """Retorna fallback si la respuesta no es parseable."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "texto sin json"

    with patch("src.ai._call_lm_studio", return_value=mock_response):
        result = get_ai_score({"symbol": "T"}, base_url="http://localhost:1234")

    assert result["score"] == 0
    assert result["fallback"] is True


def test_call_lm_studio_normaliza_v1_duplicado():
    """No duplica el sufijo /v1 del base_url (evita .../v1/v1)."""
    with patch("src.ai.OpenAI") as mock_cls:
        mock_cls.return_value.completions.create = MagicMock()
        _call_lm_studio("hola", "http://localhost:1234/v1", model="qwen/qwen3-4b-2507")

    assert mock_cls.call_args.kwargs["base_url"] == "http://localhost:1234/v1"


def test_call_lm_studio_sin_v1_le_añade():
    """Si el base_url no trae /v1, se añade una sola vez."""
    with patch("src.ai.OpenAI") as mock_cls:
        mock_cls.return_value.completions.create = MagicMock()
        _call_lm_studio("hola", "http://localhost:1234", model="qwen/qwen3-4b-2507")

    assert mock_cls.call_args.kwargs["base_url"] == "http://localhost:1234/v1"
