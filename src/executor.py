"""Ejecutor de swaps vía Jupiter API (soporta DRY_RUN)."""

from typing import Any

import requests
from loguru import logger


JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"
SOL_MINT = "So11111111111111111111111111111111111111112"
MAX_PRICE_IMPACT_PCT = 0.05  # 5%
LAMPORTS_PER_SOL = 1_000_000_000


def _http_get(url: str, params: dict[str, Any]) -> Any:
    """Wrapper de requests.get (facilita mocking en tests)."""
    return requests.get(url, params=params, timeout=10)


def _http_post(url: str, payload: dict[str, Any]) -> Any:
    """Wrapper de requests.post (facilita mocking en tests)."""
    return requests.post(url, json=payload, timeout=10)


def parse_quote_response(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Normaliza la respuesta de Jupiter.
    
    Args:
        raw: Respuesta cruda de Jupiter.
    
    Returns:
        Quote normalizada o None si faltan campos.
    """
    required = ("inputMint", "outputMint", "inAmount", "outAmount")
    for field in required:
        if field not in raw:
            return None
    
    # priceImpactPct puede venir como string o número
    try:
        impact = float(raw.get("priceImpactPct", 0))
    except (ValueError, TypeError):
        impact = 0.0
    
    return {
        "input_mint": raw["inputMint"],
        "output_mint": raw["outputMint"],
        "in_amount": int(raw["inAmount"]),
        "out_amount": int(raw["outAmount"]),
        "price_impact_pct": impact,
        "raw": raw,
    }


def get_quote(
    input_mint: str,
    output_mint: str,
    amount_lamports: int,
    slippage_bps: int = 100,
) -> dict[str, Any] | None:
    """Obtiene quote de Jupiter para un swap.
    
    Args:
        input_mint: Mint de entrada (SOL).
        output_mint: Mint de salida (token).
        amount_lamports: Cantidad en lamports.
        slippage_bps: Slippage en puntos base (100 = 1%).
    
    Returns:
        Quote normalizada o None si falla.
    """
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": str(amount_lamports),
        "slippageBps": str(slippage_bps),
    }
    
    try:
        response = _http_get(JUPITER_QUOTE_URL, params)
        raw = response.json()
    except Exception as e:
        logger.error(f"Error obteniendo quote: {e}")
        return None
    
    return parse_quote_response(raw)


def build_swap_request(
    quote_response: dict[str, Any],
    user_public_key: str,
    slippage_bps: int = 100,
) -> dict[str, Any]:
    """Construye el payload para el endpoint de swap.
    
    Args:
        quote_response: Respuesta de get_quote.
        user_public_key: Public key de la wallet.
        slippage_bps: Slippage en bps.
    
    Returns:
        Payload listo para POST.
    """
    return {
        "quoteResponse": quote_response.get("raw", quote_response),
        "userPublicKey": user_public_key,
        "slippageBps": slippage_bps,
        "wrapAndUnwrapSol": True,
    }


def execute_swap(
    token_address: str,
    amount_sol: float,
    wallet_keypair: Any = None,
    dry_run: bool = True,
    slippage_bps: int = 100,
) -> dict[str, Any]:
    """Ejecuta un swap SOL → token.
    
    Args:
        token_address: Dirección del token a comprar.
        amount_sol: Cantidad en SOL.
        wallet_keypair: Keypair de la wallet (None en dry_run).
        dry_run: Si True, no envía transacción real.
        slippage_bps: Slippage permitido.
    
    Returns:
        Dict con status, amount_sol y demás detalles.
    """
    amount_lamports = int(amount_sol * LAMPORTS_PER_SOL)
    
    # 1. Obtener quote
    quote = get_quote(SOL_MINT, token_address, amount_lamports, slippage_bps)
    if quote is None:
        logger.error(f"No se pudo obtener quote para {token_address}")
        return {"status": "failed", "reason": "no_quote", "amount_sol": amount_sol}
    
    # 2. Validar price impact
    if quote["price_impact_pct"] > MAX_PRICE_IMPACT_PCT:
        logger.warning(
            f"Price impact {quote['price_impact_pct']*100:.2f}% excede "
            f"límite {MAX_PRICE_IMPACT_PCT*100:.0f}%"
        )
        return {
            "status": "aborted",
            "reason": f"price impact {quote['price_impact_pct']*100:.2f}%",
            "amount_sol": amount_sol,
        }
    
    # 3. Modo DRY_RUN: no enviar transacción
    if dry_run:
        logger.info(
            f"[DRY_RUN] Swap simulado: {amount_sol} SOL → {token_address[:8]}... "
            f"(out: {quote['out_amount']})"
        )
        return {
            "status": "dry_run",
            "amount_sol": amount_sol,
            "quote": quote,
        }
    
    # 4. Ejecución real (requiere wallet)
    if wallet_keypair is None:
        return {"status": "failed", "reason": "no_wallet", "amount_sol": amount_sol}
    
    logger.warning("Ejecución real no implementada aún (requiere firma de tx)")
    return {"status": "not_implemented", "amount_sol": amount_sol}