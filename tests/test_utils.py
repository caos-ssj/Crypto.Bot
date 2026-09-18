"""Tests para utilidades."""

from unittest.mock import MagicMock

import pytest

from src.utils import format_sol, retry_with_backoff, safe_float


def test_retry_with_backoff_success_first_try():
    """Si la función funciona a la primera, no reintenta."""
    mock = MagicMock(return_value="ok")
    result = retry_with_backoff(mock, max_retries=3, base_delay=0.01)
    assert result == "ok"
    assert mock.call_count == 1


def test_retry_with_backoff_success_after_failures():
    """Reintenta hasta 3 veces antes de fallar."""
    mock = MagicMock(side_effect=[Exception("fail"), Exception("fail"), "ok"])
    result = retry_with_backoff(mock, max_retries=3, base_delay=0.01)
    assert result == "ok"
    assert mock.call_count == 3


def test_retry_with_backoff_all_fail():
    """Si falla todas las veces, lanza excepción."""
    mock = MagicMock(side_effect=Exception("fail"))
    with pytest.raises(Exception, match="fail"):
        retry_with_backoff(mock, max_retries=2, base_delay=0.01)
    assert mock.call_count == 2


def test_format_sol():
    """Formatea SOL con 4 decimales."""
    assert format_sol(0.123456) == "0.1235 SOL"
    assert format_sol(1.0) == "1.0000 SOL"


def test_safe_float_valid():
    """Convierte string numérico a float."""
    assert safe_float("3.14") == 3.14
    assert safe_float(42) == 42.0


def test_safe_float_invalid():
    """Retorna default si no se puede convertir."""
    assert safe_float("abc", default=0.0) == 0.0
    assert safe_float(None, default=-1.0) == -1.0
