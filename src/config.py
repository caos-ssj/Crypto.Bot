"""Módulo de configuración del bot."""

from typing import Any


MODES: dict[str, dict[str, Any]] = {
    "conservador": {
        "mc_min": 50000,
        "mc_max": 500000,
        "max_age_min": 720,
        "global_fees": 0.3,
        "base_buy": 0.05,
    },
    "equilibrado": {
        "mc_min": 20000,
        "mc_max": 800000,
        "max_age_min": 1440,
        "global_fees": 0.15,
        "base_buy": 0.03,
    },
    "agresivo": {
        "mc_min": 5000,
        "mc_max": 1000000,
        "max_age_min": 2880,
        "global_fees": 0.05,
        "base_buy": 0.01,
    },
}


def get_mode_settings(mode: str) -> dict[str, Any]:
    """Retorna la configuración para un modo específico.
    
    Args:
        mode: Nombre del modo (conservador, equilibrado, agresivo).
    
    Returns:
        Diccionario con los parámetros del modo.
    
    Raises:
        ValueError: Si el modo no existe.
    """
    if mode not in MODES:
        raise ValueError(
            f"Modo inválido: {mode}. "
            f"Opciones válidas: {list(MODES.keys())}"
        )
    return MODES[mode]