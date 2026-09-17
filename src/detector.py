"""Módulo de detección de tokens nuevos en Solana."""

from typing import Any, Callable
from loguru import logger
from src.utils import safe_float


# Campos obligatorios para que un token sea válido
REQUIRED_FIELDS = ("baseToken", "marketCap", "liquidity", "volume")


def parse_token_data(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convierte el JSON crudo de DexScreener en estructura limpia.
    
    Args:
        raw: Diccionario crudo de la API.
    
    Returns:
        Token normalizado, o None si faltan campos críticos.
    """
    # Validar campos obligatorios
    for field in REQUIRED_FIELDS:
        if field not in raw or raw[field] is None:
            return None
    
    try:
        base_token = raw.get("baseToken", {})
        token_address = base_token.get("address")
        symbol = base_token.get("symbol", "UNKNOWN")
        
        if not token_address:
            return None
        
        return {
            "token_address": token_address,
            "symbol": symbol,
            "pair_address": raw.get("pairAddress", ""),
            "price_usd": safe_float(raw.get("priceUsd")),
            "market_cap": safe_float(raw.get("marketCap")),
            "liquidity_usd": safe_float(raw.get("liquidity", {}).get("usd")),
            "volume_5min": safe_float(raw.get("volume", {}).get("h5")),
            "pair_created_at": raw.get("pairCreatedAt"),
            "raw": raw,  # guardar para análisis posteriores
        }
    except (AttributeError, TypeError) as e:
        logger.warning(f"Error parseando token: {e}")
        return None


def filter_new_tokens(
    tokens: list[dict[str, Any]],
    seen_tokens: set[str],
) -> list[dict[str, Any]]:
    """Filtra tokens que ya fueron procesados.
    
    Args:
        tokens: Lista de tokens normalizados.
        seen_tokens: Set de token_address ya procesados.
    
    Returns:
        Lista filtrada con solo tokens nuevos.
    """
    return [
        token for token in tokens
        if token.get("token_address") not in seen_tokens
    ]


def detect_new_tokens(
    fetch_func: Callable[[], list[dict[str, Any]]],
    seen_tokens: set[str],
) -> list[dict[str, Any]]:
    """Detecta tokens nuevos aplicando fetch → parse → filter.
    
    Args:
        fetch_func: Función que retorna la lista cruda de la API.
        seen_tokens: Set de token_address ya procesados.
    
    Returns:
        Lista de tokens nuevos listos para análisis.
    """
    try:
        raw_tokens = fetch_func()
    except Exception as e:
        logger.error(f"Error obteniendo tokens: {e}")
        return []
    
    if not raw_tokens:
        return []
    
    parsed = []
    for raw in raw_tokens:
        token = parse_token_data(raw)
        if token is not None:
            parsed.append(token)
    
    new_tokens = filter_new_tokens(parsed, seen_tokens)
    logger.info(f"Detectados {len(new_tokens)} tokens nuevos de {len(raw_tokens)} recibidos")
    
    return new_tokens