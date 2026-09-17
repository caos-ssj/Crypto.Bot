"""Analizador de tokens: 11 filtros ponderados + score + decisión."""

from typing import Any
from loguru import logger


# Score máximo teórico (suma de todos los pesos)
MAX_SCORE = 115


def check_market_cap(token: dict[str, Any], mode_settings: dict[str, Any]) -> tuple[int, str]:
    """Filtro 1: Market Cap en rango (20 pts)."""
    mc = token.get("market_cap", 0)
    mc_min = mode_settings["mc_min"]
    mc_max = mode_settings["mc_max"]
    if mc_min <= mc <= mc_max:
        return 20, f"MC ${mc:,.0f} OK"
    return 0, f"MC ${mc:,.0f} fuera de rango"


def check_global_fees(token: dict[str, Any], mode_settings: dict[str, Any]) -> tuple[int, str]:
    """Filtro 2: Global Fees acumuladas (20 pts)."""
    fees = token.get("global_fees_sol", 0)
    min_fees = mode_settings["global_fees"]
    if fees > min_fees:
        return 20, f"Fees {fees:.3f} SOL OK"
    return 0, f"Fees {fees:.3f} SOL bajo mínimo ({min_fees})"


def check_age(token: dict[str, Any], mode_settings: dict[str, Any]) -> tuple[int, str]:
    """Filtro 3: Edad del token (15 pts)."""
    age = token.get("age_minutes", 999999)
    max_age = mode_settings["max_age_min"]
    if age < max_age:
        return 15, f"Edad {age}min OK"
    return 0, f"Edad {age}min excede {max_age}min"


def check_security(token: dict[str, Any]) -> tuple[int, str]:
    """Filtro 4: Sin bundles y dev no ha vendido (25 pts)."""
    if not token.get("has_bundles", True) and not token.get("dev_has_sold", True):
        return 25, "Seguridad OK"
    return 0, "Falló seguridad (bundles o dev sell)"


def check_liquidity_ratio(token: dict[str, Any]) -> tuple[int, str]:
    """Filtro 5: Ratio liquidez/MC > 3% (5 pts)."""
    mc = token.get("market_cap", 0)
    liq = token.get("liquidity_usd", 0)
    if mc <= 0:
        return 0, "MC inválido"
    ratio = (liq / mc) * 100
    if ratio > 3.0:
        return 5, f"Ratio {ratio:.2f}% OK"
    return 0, f"Ratio {ratio:.2f}% bajo 3%"


def check_top_holders(token: dict[str, Any]) -> tuple[int, str]:
    """Filtro 6: Top-10 holders < 50% (5 pts)."""
    pct = token.get("top_10_holders_pct", 100.0)
    if pct < 50.0:
        return 5, f"Top-10 {pct:.1f}% OK"
    return 0, f"Top-10 {pct:.1f}% concentrado"


def check_volume(token: dict[str, Any]) -> tuple[int, str]:
    """Filtro 7: Volumen 5min > $2K (5 pts)."""
    vol = token.get("volume_5min", 0)
    if vol > 2000:
        return 5, f"Volumen ${vol:,.0f} OK"
    return 0, f"Volumen ${vol:,.0f} bajo"


def check_creator_age(token: dict[str, Any]) -> tuple[int, str]:
    """Filtro 8: Edad del creador > 3 días (5 pts)."""
    age = token.get("creator_age_days", 0)
    if age > 3:
        return 5, f"Creator {age}d OK"
    return 0, f"Creator {age}d muy nuevo"


def check_authorities(token: dict[str, Any]) -> tuple[int, str]:
    """Filtro 9: Mint y Freeze authority deshabilitadas (5 pts)."""
    mint_off = token.get("mint_authority_disabled", False)
    freeze_off = token.get("freeze_authority_disabled", False)
    if mint_off and freeze_off:
        return 5, "Autoridades deshabilitadas"
    return 0, "Autoridades activas"


def check_bundles(token: dict[str, Any]) -> tuple[int, str]:
    """Filtro 10: Sin bundles detectados (5 pts)."""
    if not token.get("has_bundles", True):
        return 5, "Sin bundles"
    return 0, "Bundles detectados"


def check_dev_sell(token: dict[str, Any]) -> tuple[int, str]:
    """Filtro 11: Dev no ha vendido (5 pts)."""
    if not token.get("dev_has_sold", True):
        return 5, "Dev no ha vendido"
    return 0, "Dev vendió tokens"


def calculate_score(
    token: dict[str, Any],
    mode_settings: dict[str, Any],
) -> tuple[int, list[dict[str, Any]]]:
    """Calcula score normalizado (0-100) aplicando los 11 filtros.
    
    Args:
        token: Datos del token.
        mode_settings: Parámetros del modo de operación.
    
    Returns:
        Tupla (score_normalizado, lista de detalles por filtro).
    """
    filters = [
        ("market_cap", check_market_cap(token, mode_settings)),
        ("global_fees", check_global_fees(token, mode_settings)),
        ("age", check_age(token, mode_settings)),
        ("security", check_security(token)),
        ("liquidity_ratio", check_liquidity_ratio(token)),
        ("top_holders", check_top_holders(token)),
        ("volume", check_volume(token)),
        ("creator_age", check_creator_age(token)),
        ("authorities", check_authorities(token)),
        ("bundles", check_bundles(token)),
        ("dev_sell", check_dev_sell(token)),
    ]
    
    details = []
    total = 0
    for name, (points, reason) in filters:
        details.append({"filter": name, "points": points, "reason": reason})
        total += points
    
    normalized = round((total / MAX_SCORE) * 100)
    return normalized, details


def decide(score: int) -> str:
    """Decide la acción según el score.
    
    Args:
        score: Score normalizado (0-100).
    
    Returns:
        "COMPRA" | "OBSERVAR" | "EVITAR"
    """
    if score > 70:
        return "COMPRA"
    if score >= 50:
        return "OBSERVAR"
    return "EVITAR"


def analyze_token(
    token: dict[str, Any],
    mode_settings: dict[str, Any],
) -> dict[str, Any]:
    """Análisis completo: score + decisión + detalles.
    
    Args:
        token: Datos del token.
        mode_settings: Parámetros del modo.
    
    Returns:
        Diccionario con score, decisión y detalles por filtro.
    """
    score, details = calculate_score(token, mode_settings)
    action = decide(score)
    
    logger.info(
        f"Token {token.get('symbol', '?')}: "
        f"score={score} → {action}"
    )
    
    return {
        "token_address": token.get("token_address"),
        "symbol": token.get("symbol"),
        "score": score,
        "action": action,
        "details": details,
    }