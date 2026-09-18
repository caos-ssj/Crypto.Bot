"""Utilidades generales: retry, logging, formateo."""

import time
from collections.abc import Callable
from typing import Any, TypeVar

from loguru import logger

T = TypeVar("T")


def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Ejecuta una función con reintentos exponenciales.

    Args:
        func: Función a ejecutar.
        max_retries: Número máximo de intentos.
        base_delay: Delay base en segundos (se duplica cada intento).
        exceptions: Tipos de excepción que activan retry.

    Returns:
        El resultado de la función.

    Raises:
        La última excepción si todos los intentos fallan.
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)
                logger.warning(
                    f"Intento {attempt + 1}/{max_retries} falló: {e}. "
                    f"Reintentando en {delay:.2f}s..."
                )
                time.sleep(delay)

    assert last_exception is not None
    raise last_exception


def format_sol(amount: float) -> str:
    """Formatea una cantidad de SOL con 4 decimales.

    Args:
        amount: Cantidad en SOL.

    Returns:
        String formateado (ej. "0.1235 SOL").
    """
    return f"{amount:.4f} SOL"


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convierte un valor a float de forma segura.

    Args:
        value: Valor a convertir.
        default: Valor por defecto si la conversión falla.

    Returns:
        El valor convertido o el default.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
