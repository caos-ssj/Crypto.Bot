"""Tests para el módulo de configuración."""

import pytest

from src.config import get_mode_settings


def test_get_mode_settings_equilibrado():
    """Verifica los valores del modo equilibrado."""
    settings = get_mode_settings("equilibrado")
    assert settings["mc_min"] == 20000
    assert settings["mc_max"] == 800000
    assert settings["base_buy"] == 0.03


def test_get_mode_settings_conservador():
    """Verifica los valores del modo conservador."""
    settings = get_mode_settings("conservador")
    assert settings["mc_min"] == 50000
    assert settings["base_buy"] == 0.05


def test_get_mode_settings_agresivo():
    """Verifica los valores del modo agresivo."""
    settings = get_mode_settings("agresivo")
    assert settings["mc_min"] == 5000
    assert settings["base_buy"] == 0.01


def test_get_mode_settings_invalid():
    """Verifica que falla con modo inválido."""
    with pytest.raises(ValueError, match="Modo inválido"):
        get_mode_settings("inexistente")
