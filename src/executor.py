"""Ejecutor de swaps vía Jupiter API (soporta DRY_RUN y ejecución real)."""

import base64
from typing import Any

import requests
from loguru import logger
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

JUPITER_QUOTE_URL = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL = "https://quote-api.jup.ag/v6/swap"
SOL_MINT = "So11111111111111111111111111111111111111112"
# Jupiter devuelve priceImpactPct en porcentaje (ej. "0.5" = 0.5%).
MAX_PRICE_IMPACT_PCT = 5.0  # límite absoluto de price impact (5%)
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
    rpc_url: str = "",
) -> dict[str, Any]:
    """Ejecuta un swap SOL → token.

    Args:
        token_address: Dirección del token a comprar.
        amount_sol: Cantidad en SOL.
        wallet_keypair: Keypair de la wallet (None en dry_run).
        dry_run: Si True, no envía transacción real.
        slippage_bps: Slippage permitido.
        rpc_url: URL del RPC de Solana (requerida para ejecución real).

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
    impact = quote["price_impact_pct"]
    if impact > MAX_PRICE_IMPACT_PCT:
        logger.warning(
            f"Price impact {impact:.2f}% excede " f"límite {MAX_PRICE_IMPACT_PCT:.0f}%"
        )
        return {
            "status": "aborted",
            "reason": f"price impact {impact:.2f}%",
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

    # 4. Ejecución real (requiere wallet, keypair y RPC)
    if wallet_keypair is None:
        return {"status": "failed", "reason": "no_wallet", "amount_sol": amount_sol}
    if not wallet_public_key(wallet_keypair):
        return {
            "status": "failed",
            "reason": "invalid_wallet",
            "amount_sol": amount_sol,
        }

    result = _execute_real_swap(
        quote=quote,
        wallet_keypair=wallet_keypair,
        slippage_bps=slippage_bps,
        rpc_url=rpc_url,
    )
    if result is None:
        return {
            "status": "failed",
            "reason": "no_rpc_url",
            "amount_sol": amount_sol,
        }
    result["amount_sol"] = amount_sol
    return result


def load_wallet(private_key: str) -> Keypair | None:
    """Construye el Keypair desde una private key base58.

    Args:
        private_key: Clave privada en base58.

    Returns:
        Keypair válido o None si la clave es inválida.
    """
    if not private_key:
        return None
    try:
        keypair = Keypair.from_base58_string(private_key)
    except ValueError as e:
        logger.error(
            f"Private key inválida: {e}. Debe ser base58 de 32 o 64 bytes "
            f"(típicamente 43-88 caracteres), no un JSON ni una frase semilla."
        )
        return None
    return keypair


def wallet_public_key(keypair: Keypair) -> str | None:
    """Public key base58 de un Keypair (None si es inválido)."""
    try:
        return str(keypair.pubkey())
    except (AttributeError, ValueError, TypeError):
        return None


def _request_swap_transaction(
    quote: dict[str, Any],
    user_public_key: str,
    slippage_bps: int,
) -> str | None:
    """Pide la transacción firmable a Jupiter (/v6/swap).

    Returns:
        swapTransaction en base64 o None si falla.
    """
    payload = build_swap_request(quote, user_public_key, slippage_bps)
    payload["prioritizationFeeLamports"] = "auto"
    payload["dynamicComputeUnitLimit"] = True

    try:
        response = _http_post(JUPITER_SWAP_URL, payload)
        raw = response.json()
    except (requests.RequestException, ValueError, TypeError) as e:
        logger.error(f"Error pidiendo swap a Jupiter: {e}")
        return None

    swap_tx = raw.get("swapTransaction") if isinstance(raw, dict) else None
    if not swap_tx:
        logger.error(f"Jupiter no devolvió swapTransaction: {raw}")
        return None
    return swap_tx


def _sign_swap_transaction(swap_tx_b64: str, keypair: Keypair) -> str | None:
    """Firma la transacción de Jupiter con el keypair de la wallet.

    Returns:
        Transacción firmada en base64 o None.
    """
    try:
        tx = VersionedTransaction.from_bytes(base64.b64decode(swap_tx_b64))
        signed = VersionedTransaction(tx.message, [keypair])
        return base64.b64encode(bytes(signed)).decode()
    except (ValueError, TypeError) as e:
        logger.error(f"Error firmando transacción: {e}")
        return None


def _send_transaction(signed_tx_b64: str, rpc_url: str) -> str | None:
    """Envía la transacción firmada al RPC de Solana.

    Returns:
        Signature (base58) de la tx o None.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "sendTransaction",
        "params": [
            signed_tx_b64,
            {
                "encoding": "base64",
                "preflightCommitment": "processed",
                "maxRetries": 3,
            },
        ],
    }
    try:
        response = _http_post(rpc_url, payload)
        raw = response.json()
    except (requests.RequestException, ValueError, TypeError) as e:
        logger.error(f"RPC rechazó sendTransaction: {e}")
        return None

    if not isinstance(raw, dict) or "result" not in raw:
        error = raw.get("error", raw) if isinstance(raw, dict) else raw
        logger.error(f"RPC rechazó sendTransaction: {error}")
        return None
    return str(raw["result"])


def _execute_real_swap(
    quote: dict[str, Any],
    wallet_keypair: Keypair,
    slippage_bps: int,
    rpc_url: str,
) -> dict[str, Any] | None:
    """Firma y envía un swap real (flujo completo Jupiter → RPC)."""
    if not rpc_url:
        return None

    user_public_key = wallet_public_key(wallet_keypair)
    assert user_public_key is not None

    swap_tx = _request_swap_transaction(quote, user_public_key, slippage_bps)
    if swap_tx is None:
        return {"status": "failed", "reason": "swap_request_failed"}

    signed_tx = _sign_swap_transaction(swap_tx, wallet_keypair)
    if signed_tx is None:
        return {"status": "failed", "reason": "signing_failed"}

    signature = _send_transaction(signed_tx, rpc_url)
    if signature is None:
        return {"status": "failed", "reason": "send_failed"}

    logger.info(
        f"[REAL] Swap enviado: {signature} "
        f"(impact {quote['price_impact_pct']:.2f}%)"
    )
    return {
        "status": "success",
        "public_key": user_public_key,
        "signature": signature,
        "out_amount": quote["out_amount"],
        "quote": quote,
    }


def _get_token_balance(
    token_address: str,
    public_key: str,
    rpc_url: str,
) -> int | None:
    """Saldo del token (lamports) en la ATA de la wallet.

    Returns:
        Cantidad de lamports del token o None si no hay cuenta/no se puede leer.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "getTokenAccountsByOwner",
        "params": [
            public_key,
            {"mint": token_address},
            {"encoding": "jsonParsed"},
        ],
    }
    try:
        response = _http_post(rpc_url, payload)
        raw = response.json()
    except (requests.RequestException, ValueError, TypeError) as e:
        logger.error(f"Error leyendo balance de {token_address[:8]}...: {e}")
        return None

    if not isinstance(raw, dict):
        return None
    result = raw.get("result")
    if not result or not result.get("value"):
        return None

    try:
        account = result["value"][0]["account"]["data"]["parsed"]["info"]["tokenAmount"]
        return int(account["amount"])
    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"Balance parse falló para {token_address[:8]}...: {e}")
        return None


def execute_sell(
    token_address: str,
    wallet_keypair: Keypair,
    rpc_url: str,
    dry_run: bool = True,
    slippage_bps: int = 100,
) -> dict[str, Any]:
    """Vende TODA la posición del token → SOL (token→SOL).

    Args:
        token_address: Mint del token a vender.
        wallet_keypair: Keypair de la wallet.
        rpc_url: URL del RPC de Solana.
        dry_run: Si True, no envía transacción real.
        slippage_bps: Slippage permitido.

    Returns:
        Dict con status y detalles.
    """
    if wallet_keypair is None:
        return {"status": "failed", "reason": "no_wallet"}

    public_key = wallet_public_key(wallet_keypair)
    if public_key is None:
        return {"status": "failed", "reason": "invalid_wallet"}

    if dry_run:
        logger.info(f"[DRY_RUN] Venta simulada: {token_address[:8]}... → SOL")
        return {"status": "dry_run", "amount_tokens": None, "quote": None}

    amount_lamports = _get_token_balance(token_address, public_key, rpc_url)
    if amount_lamports is None:
        amount_lamports = 0
    if amount_lamports <= 0:
        logger.warning(f"No hay saldo de {token_address[:8]}... para vender")
        return {"status": "failed", "reason": "no_balance"}

    quote = get_quote(token_address, SOL_MINT, amount_lamports, slippage_bps)
    if quote is None:
        return {"status": "failed", "reason": "no_quote"}

    impact = quote["price_impact_pct"]
    if impact > MAX_PRICE_IMPACT_PCT:
        logger.warning(
            f"Sell price impact {impact:.2f}% excede "
            f"límite {MAX_PRICE_IMPACT_PCT:.0f}%"
        )
        return {
            "status": "aborted",
            "reason": f"price impact {impact:.2f}%",
        }

    if not rpc_url:
        return {"status": "failed", "reason": "no_rpc_url"}

    swap_tx = _request_swap_transaction(quote, public_key, slippage_bps)
    if swap_tx is None:
        return {"status": "failed", "reason": "swap_request_failed"}

    signed_tx = _sign_swap_transaction(swap_tx, wallet_keypair)
    if signed_tx is None:
        return {"status": "failed", "reason": "signing_failed"}

    signature = _send_transaction(signed_tx, rpc_url)
    if signature is None:
        return {"status": "failed", "reason": "send_failed"}

    logger.info(f"[REAL] Venta enviada: {signature}")
    return {
        "status": "success",
        "public_key": public_key,
        "signature": signature,
        "amount_tokens": amount_lamports,
        "out_amount_sol": quote["out_amount"],
        "quote": quote,
    }
