"""Datos on-chain de Solana vía Helius RPC.

Política de datos:
- Un fallo de RPC NUNCA detiene el bot: se retorna None (dato no verificado).
- None en campos de seguridad hace que el analyzer otorgue 0 pts (conservador).
"""

import time
from functools import lru_cache
from typing import Any

import requests
from loguru import logger

from src.utils import retry_with_backoff

HELIUS_RPC_TEMPLATE = "https://mainnet.helius-rpc.com/?api-key={key}"
LAMPORTS = 1_000_000_000

# Análisis de seguridad on-chain
SECURITY_TOKEN_DEPTH = 10  # transacciones recientes de la mint a escanear
SIGNATURES_PAGE_LIMIT = 100
CREATOR_PAGE_LIMIT = 3  # páginas para hallar la tx más antigua del mint
RPC_BATCH_LIMIT = 10  # firuras por getMultipleParsedTransactions

_CACHE_SIZE = 4096


def _rpc_call(method: str, params: list, api_key: str) -> Any:
    """Ejecuta una llamada JSON-RPC a Helius con reintentos.

    Args:
        method: Nombre del método RPC.
        params: Parámetros del método.
        api_key: API key de Helius.

    Returns:
        Campo 'result' de la respuesta, o None si falla.
    """
    url = HELIUS_RPC_TEMPLATE.format(key=api_key)
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

    def _post() -> requests.Response:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response

    try:
        r = retry_with_backoff(_post, max_retries=3, base_delay=0.5)
        data = r.json()
        if "error" in data:
            logger.warning(f"RPC {method} error: {data['error']}")
            return None
        return data.get("result")
    except Exception as e:
        logger.error(f"RPC {method} falló: {e}")
        return None


def get_mint_info(token_address: str, api_key: str) -> dict[str, Any]:
    """Obtiene mint authority, freeze authority y supply.

    Args:
        token_address: Mint address del token.
        api_key: API key de Helius.

    Returns:
        Dict con authorities y supply.
    """
    default = {
        "mint_authority_disabled": False,
        "freeze_authority_disabled": False,
        "supply": 0,
        "decimals": 0,
    }

    result = _rpc_call(
        "getAccountInfo",
        [token_address, {"encoding": "jsonParsed"}],
        api_key,
    )
    if not result or result.get("value") is None:
        return default

    try:
        info = result["value"]["data"]["parsed"]["info"]
    except (KeyError, TypeError):
        return default

    return {
        "mint_authority_disabled": info.get("mintAuthority") is None,
        "freeze_authority_disabled": info.get("freezeAuthority") is None,
        "supply": int(info.get("supply", 0)),
        "decimals": int(info.get("decimals", 0)),
    }


def get_top_holders_pct(token_address: str, api_key: str) -> float:
    """Calcula el % del supply en los top 10 holders.

    Returns:
        Porcentaje (0-100). Retorna 100.0 si no puede calcular (conservador).
    """
    largest = _rpc_call(
        "getTokenLargestAccounts",
        [token_address],
        api_key,
    )
    if not largest or not largest.get("value"):
        return 100.0

    supply_data = _rpc_call("getTokenSupply", [token_address], api_key)
    if not supply_data or not supply_data.get("value"):
        return 100.0

    try:
        total_supply = float(supply_data["value"]["amount"])
        if total_supply <= 0:
            return 100.0
        top_sum = sum(float(a["amount"]) for a in largest["value"][:10])
        return round((top_sum / total_supply) * 100, 2)
    except (KeyError, TypeError, ValueError):
        return 100.0


def get_creator_age_days(creator_address: str, api_key: str) -> int:
    """Estima la edad del creador en días (tiempo desde su primera tx).

    Heurística: la firma más antigua del último lote consultado se usa como
    aproximación del nacimiento de la wallet. Solo es fiable para wallets con
    menos de mil transacciones.

    Returns:
        Edad en días. Retorna 0 si no puede determinar.
    """
    result = _rpc_call(
        "getSignaturesForAddress",
        [creator_address, {"limit": 1000}],
        api_key,
    )
    if not result or not isinstance(result, list) or len(result) == 0:
        return 0

    oldest = result[-1]
    block_time = oldest.get("blockTime")
    if not block_time:
        return 0

    now = int(time.time())
    age_seconds = now - block_time
    return max(0, age_seconds // 86400)


# ============ ANÁLISIS DE SEGURIDAD ON-CHAIN ============


def get_earliest_signature(address: str, api_key: str) -> str | None:
    """Retorna la firma más antigua de una cuenta.

    Se pagina hacia atrás en el historial de firmas hasta agotar las páginas
    configuradas o la historia completa de la cuenta.

    Args:
        address: Cuenta (mint, wallet o pool) a inspeccionar.
        api_key: API key de Helius.

    Returns:
        Firma más antigua encontrada, o None si no hay transacciones.
    """
    before: str | None = None
    oldest: str | None = None

    for _ in range(CREATOR_PAGE_LIMIT):
        params: list[Any] = [address, {"limit": SIGNATURES_PAGE_LIMIT}]
        if before:
            params[1]["beforeSignature"] = before

        result = _rpc_call("getSignaturesForAddress", params, api_key)
        if not isinstance(result, list) or not result:
            break

        oldest = result[-1].get("signature") or oldest
        if len(result) < SIGNATURES_PAGE_LIMIT:
            break  # se alcanzó el inicio de la historia de la cuenta

        before = result[-1].get("signature")

    return oldest


def _tx_encoding() -> dict[str, Any]:
    """Configuración de encoding para transacciones parseadas (v0 + legacy)."""
    return {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}


def _fetch_parsed_transaction(signature: str, api_key: str) -> dict[str, Any] | None:
    """Obtiene una transacción parseada (getTransaction, RPC estándar)."""
    result = _rpc_call("getTransaction", [signature, _tx_encoding()], api_key)
    return result if isinstance(result, dict) else None


def get_dev_address(token_address: str, api_key: str) -> str | None:
    """Deriva la wallet del creador desde la tx más antigua de la mint.

    Heurística: el fee payer de la transacción de creación de la mint suele ser
    la wallet del desarrollador (así funciona pump.fun). Se usa la transacción
    más antigua de la historia del mint.

    Returns:
        Address del dev, o None si no se puede determinar.
    """
    signature = get_earliest_signature(token_address, api_key)
    if not signature:
        return None

    tx = _fetch_parsed_transaction(signature, api_key)
    if not tx:
        return None

    keys = tx.get("transaction", {}).get("message", {}).get("accountKeys", [])
    if not keys:
        return None
    first = keys[0]
    return first.get("pubkey", first) if isinstance(first, dict) else first


def _recent_signatures(address: str, api_key: str, limit: int) -> list[str]:
    """Obtiene las firmas más recientes de una cuenta (solo strings válidas)."""
    result = _rpc_call("getSignaturesForAddress", [address, {"limit": limit}], api_key)
    if not isinstance(result, list):
        return []
    return [
        entry.get("signature")
        for entry in result
        if isinstance(entry, dict) and entry.get("signature")
    ]


def _fetch_parsed_transactions(
    signatures: list[str],
    api_key: str,
) -> list[dict[str, Any]]:
    """Bach de getMultipleTransactions (extensión Helius).

    Si el RPC no soporta el método (getMultipleTransactions devuelve None),
    hace fallback secuencial con getTransaction (RPC estándar).
    """
    transactions: list[dict[str, Any]] = []
    for i in range(0, len(signatures), RPC_BATCH_LIMIT):
        batch = signatures[i : i + RPC_BATCH_LIMIT]
        result = _rpc_call(
            "getMultipleTransactions",
            [batch, _tx_encoding()],
            api_key,
        )
        if isinstance(result, list):
            transactions.extend(t for t in result if isinstance(t, dict))
        else:
            logger.warning(
                "getMultipleTransactions no soportado; fallback a getTransaction"
            )
            for signature in batch:
                tx = _fetch_parsed_transaction(signature, api_key)
                if tx:
                    transactions.append(tx)
    return transactions


def _balances_by_owner(
    tx: dict[str, Any],
    mint: str,
) -> tuple[dict[str, int], dict[str, int]]:
    """Mapea owner -> saldo (lamports) de la mint antes y después de una tx."""
    pre: dict[str, int] = {}
    post: dict[str, int] = {}
    meta = tx.get("meta") or {}

    for entry in meta.get("preTokenBalances", []) or []:
        amount = (entry.get("uiTokenAmount") or {}).get("amount")
        if entry.get("mint") == mint and entry.get("owner") and amount is not None:
            pre[entry["owner"]] = int(amount)

    for entry in meta.get("postTokenBalances", []) or []:
        amount = (entry.get("uiTokenAmount") or {}).get("amount")
        if entry.get("mint") == mint and entry.get("owner") and amount is not None:
            post[entry["owner"]] = int(amount)

    return pre, post


def _analyze_security_txs(
    transactions: list[dict[str, Any]],
    mint: str,
    dev: str | None,
) -> tuple[Any, Any]:
    """Analiza transacciones en busca de bundles y ventas del dev.

    Heurísticas:
    - Bundle: una sola firma donde >1 wallet distinta recibió el token por
      primera vez (compras simultáneas en una misma transacción).
    - Dev sell: el saldo del dev disminuye entre el antes y después de una tx.

    Returns:
        Tupla (has_bundles, dev_has_sold). Cada valor es True/False o None
        si no hubo transacciones que escanear.
    """
    has_bundles = False
    dev_sold = False
    scanned = False

    for tx in transactions:
        pre, post = _balances_by_owner(tx, mint)
        if not pre and not post:
            continue
        scanned = True

        buyers = {
            owner
            for owner, after in post.items()
            if after > 0 and pre.get(owner, 0) == 0
        }
        if len(buyers) > 1:
            has_bundles = True

        if dev and dev in pre and dev in post and post[dev] < pre[dev]:
            dev_sold = True

    if not scanned:
        return None, None
    return has_bundles, dev_sold


@lru_cache(maxsize=_CACHE_SIZE)
def _security_analysis(
    token_address: str,
    api_key: str,
    depth: int,
) -> tuple[str | None, Any, Any]:
    """Análisis de seguridad cacheado: (dev, has_bundles, dev_has_sold)."""
    dev = get_dev_address(token_address, api_key)
    signatures = _recent_signatures(token_address, api_key, depth)
    transactions = _fetch_parsed_transactions(signatures, api_key)
    has_bundles, dev_sold = _analyze_security_txs(transactions, token_address, dev)
    return dev, has_bundles, dev_sold


def analyze_security(token_address: str, api_key: str) -> dict[str, Any]:
    """Análisis on-chain de seguridad para un token (con caché).

    Returns:
        Dict con dev_address, has_bundles y dev_has_sold.
        Cada campo puede ser None = dato no verificable (el analyzer da 0 pts).
    """
    try:
        dev, has_bundles, dev_sold = _security_analysis(
            token_address,
            api_key,
            SECURITY_TOKEN_DEPTH,
        )
    except Exception as e:  # noqa: BLE001 - frontera: nunca detener el ciclo
        logger.warning(f"Análisis de seguridad falló para {token_address}: {e}")
        return {"dev_address": None, "has_bundles": None, "dev_has_sold": None}

    return {
        "dev_address": dev,
        "has_bundles": has_bundles,
        "dev_has_sold": dev_sold,
    }


def enrich_token(token: dict[str, Any], api_key: str) -> dict[str, Any]:
    """Añade datos on-chain al token (authorities, holders y seguridad).

    Cualquier dato no disponible se deja como None para que el analyzer lo
    puntúe con 0 (conservador) y NUNCA infle el score.

    Args:
        token: Token normalizado por fetcher.
        api_key: API key de Helius.

    Returns:
        El mismo dict con campos añadidos.
    """
    address = token["token_address"]

    mint_info = get_mint_info(address, api_key)
    token.update(mint_info)

    token["top_10_holders_pct"] = get_top_holders_pct(address, api_key)

    # Seguridad on-chain (bundles + dev-sell), con caché por mint.
    security = analyze_security(address, api_key)
    token["dev_address"] = security["dev_address"]
    token["has_bundles"] = security["has_bundles"]
    token["dev_has_sold"] = security["dev_has_sold"]

    # Edad del creador: solo con la wallet real del dev.
    dev = security["dev_address"]
    if dev:
        token["creator_age_days"] = get_creator_age_days(dev, api_key)
    else:
        token["creator_age_days"] = None

    # Global fees: sin fuente fiable disponible hoy → no verificado (0 pts).
    token["global_fees_sol"] = None

    return token
