"""Datos on-chain de Solana vía Helius RPC."""

from typing import Any
import requests
from loguru import logger


HELIUS_RPC_TEMPLATE = "https://mainnet.helius-rpc.com/?api-key={key}"
LAMPORTS = 1_000_000_000


def _rpc_call(method: str, params: list, api_key: str) -> Any:
    """Ejecuta una llamada JSON-RPC a Helius.
    
    Args:
        method: Nombre del método RPC.
        params: Parámetros del método.
        api_key: API key de Helius.
    
    Returns:
        Campo 'result' de la respuesta, o None si falla.
    """
    url = HELIUS_RPC_TEMPLATE.format(key=api_key)
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
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
    
    Args:
        token_address: Mint address.
        api_key: API key de Helius.
    
    Returns:
        Porcentaje (0-100). Retorna 100.0 si no puede calcular.
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
    """Estima la edad del creador en días (tiempo desde la primera tx).
    
    Args:
        creator_address: Wallet del creador.
        api_key: API key de Helius.
    
    Returns:
        Edad en días. Retorna 0 si no puede determinar.
    """
    import time
    
    result = _rpc_call(
        "getSignaturesForAddress",
        [creator_address, {"limit": 1000}],
        api_key,
    )
    if not result or not isinstance(result, list) or len(result) == 0:
        return 0
    
    # La firma más antigua del lote
    oldest = result[-1]
    block_time = oldest.get("blockTime")
    if not block_time:
        return 0
    
    now = int(time.time())
    age_seconds = now - block_time
    return max(0, age_seconds // 86400)


def enrich_token(token: dict[str, Any], api_key: str) -> dict[str, Any]:
    """Añade datos on-chain al token.
    
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
    
    creator = token.get("creator_address")
    if creator:
        token["creator_age_days"] = get_creator_age_days(creator, api_key)
    else:
        token["creator_age_days"] = 0
    
    # Placeholders para filtros que aún no tenemos
    token.setdefault("global_fees_sol", 0.0)
    token.setdefault("has_bundles", False)
    token.setdefault("dev_has_sold", False)
    token.setdefault("age_minutes", 0)
    
    return token