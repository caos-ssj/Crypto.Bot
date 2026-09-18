"""Fuente de datos: DexScreener para manual, perfiles recientes para auto."""

import time
from typing import Any

import requests
from loguru import logger

from src.utils import retry_with_backoff, safe_float

DEXSCREENER_BASE = "https://api.dexscreener.com"
MEMECOIN_QUERIES = ["pump", "bonk", "wif", "popcat", "mew", "jup", "ray"]


def _normalize_pair(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Normaliza un par de DexScreener al formato interno.

    Args:
        raw: Par de DexScreener.

    Returns:
        Token normalizado o None si faltan datos.
    """
    base = raw.get("baseToken", {})
    address = base.get("address")
    if not address:
        return None

    return {
        "token_address": address,
        "symbol": base.get("symbol", "?"),
        "name": base.get("name", "?"),
        "pair_address": raw.get("pairAddress", ""),
        "price_usd": safe_float(raw.get("priceUsd")),
        "market_cap": safe_float(raw.get("marketCap") or raw.get("fdv")),
        "liquidity_usd": safe_float((raw.get("liquidity") or {}).get("usd")),
        "volume_5min": safe_float((raw.get("volume") or {}).get("m5")),
        "volume_24h": safe_float((raw.get("volume") or {}).get("h24")),
        "price_change_5min": safe_float((raw.get("priceChange") or {}).get("m5")),
        "pair_created_at": raw.get("pairCreatedAt"),
        "dex_id": raw.get("dexId", "?"),
        "raw": raw,
        "age_minutes": _calc_age_minutes(raw.get("pairCreatedAt")),
    }


def _calc_age_minutes(pair_created_at: Any) -> int | None:
    """Calcula la edad del par en minutos (None si falta la fecha)."""
    if not pair_created_at:
        return None
    try:
        return max(0, int((time.time() * 1000 - pair_created_at) / 60000))
    except (TypeError, ValueError):
        return None


def _get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    """GET con retry/backoff y validación de status HTTP."""

    def _do_get() -> requests.Response:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response

    return retry_with_backoff(_do_get, max_retries=3, base_delay=0.5).json()


def fetch_by_address(address: str) -> dict[str, Any] | None:
    """Busca un token por su dirección (manual mode).

    Args:
        address: Dirección del token en Solana.

    Returns:
        Token normalizado o None.
    """
    try:
        url = f"{DEXSCREENER_BASE}/latest/dex/tokens/{address}"
        data = _get_json(url)
        pairs = data.get("pairs") or []
        solana = [p for p in pairs if p.get("chainId") == "solana"]
        if not solana:
            return None
        # Tomar el par con más liquidez
        best = max(
            solana, key=lambda p: safe_float((p.get("liquidity") or {}).get("usd"))
        )
        return _normalize_pair(best)
    except Exception as e:
        logger.error(f"Error buscando por address: {e}")
        return None


def fetch_by_symbol(symbol: str) -> list[dict[str, Any]]:
    """Busca tokens por símbolo (manual mode).

    Args:
        symbol: Símbolo del token (ej. "BONK").

    Returns:
        Lista de tokens normalizados ordenados por liquidez.
    """
    try:
        url = f"{DEXSCREENER_BASE}/latest/dex/search"
        data = _get_json(url, {"q": symbol})
        pairs = data.get("pairs") or []
        solana = [p for p in pairs if p.get("chainId") == "solana"]
        normalized = [_normalize_pair(p) for p in solana]
        result = [t for t in normalized if t is not None]
        result.sort(key=lambda t: t["liquidity_usd"], reverse=True)
        return result[:5]  # top 5
    except Exception as e:
        logger.error(f"Error buscando por símbolo: {e}")
        return []


def fetch_recent_memecoins() -> list[dict[str, Any]]:
    """Obtiene memecoins recientes (automatic mode).

    Usa rotación de queries para descubrir tokens distintos entre ciclos.

    Returns:
        Lista de tokens normalizados.
    """
    import random

    query = random.choice(MEMECOIN_QUERIES)
    try:
        url = f"{DEXSCREENER_BASE}/latest/dex/search"
        data = _get_json(url, {"q": query})
        pairs = data.get("pairs") or []
        solana = [p for p in pairs if p.get("chainId") == "solana"]
        normalized = [_normalize_pair(p) for p in solana]
        return [t for t in normalized if t is not None]
    except Exception as e:
        logger.error(f"Error fetch recientes (query={query}): {e}")
        return []
