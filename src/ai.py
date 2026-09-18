"""Integración con IA local (LM Studio + Qwen3 4B)."""

import json
from typing import Any

from loguru import logger
from openai import OpenAI

DEFAULT_MODEL = "qwen/qwen3-4b-2507"
DEFAULT_TIMEOUT = 30.0


def build_prompt(token: dict[str, Any]) -> str:
    """Construye el prompt para el modelo.

    Args:
        token: Datos del token normalizados.

    Returns:
        Prompt en formato string.
    """
    return f"""Analiza este token de Solana y responde SOLO con JSON válido.

Datos del token:
- Símbolo: {token.get("symbol", "?")}
- Market Cap: ${token.get("market_cap", 0):,.0f}
- Liquidez: ${token.get("liquidity_usd", 0):,.0f}
- Volumen 5min: ${token.get("volume_5min", 0):,.0f}
- Top-10 holders: {token.get("top_10_holders_pct", 0):.1f}%
- Edad: {token.get("age_minutes", 0)} min

Responde con este formato exacto:
{{"score": <número 0-100>, "reason": "<explicación breve>"}}

Sé estricto: score alto solo si el token parece seguro y con potencial."""


def parse_ai_response(response_text: str) -> dict[str, Any] | None:
    """Extrae y parsea JSON de la respuesta del modelo.

    Args:
        response_text: Texto crudo del modelo.

    Returns:
        Diccionario con score y reason, o None si no es parseable.
    """
    if not response_text:
        return None

    # Buscar el primer bloque {...} en la respuesta
    start = response_text.find("{")
    end = response_text.rfind("}") + 1
    if start == -1 or end <= start:
        return None

    json_str = response_text[start:end]
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    if "score" not in data or "reason" not in data:
        return None

    # Validar rango del score
    try:
        score = int(data["score"])
    except (ValueError, TypeError):
        return None

    if not 0 <= score <= 100:
        return None

    return {"score": score, "reason": str(data["reason"])}


def _call_lm_studio(
    prompt: str,
    base_url: str,
    model: str = DEFAULT_MODEL,
) -> Any:
    """Llama a LM Studio (API compatible con OpenAI)."""
    client = OpenAI(base_url=f"{base_url}/v1", api_key="not-needed")
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,  # ← subir de 200 a 1000
        temperature=0.3,
    )


def get_ai_score(
    token: dict[str, Any],
    base_url: str = "http://localhost:1234",
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """Obtiene el score de IA para un token."""
    prompt = build_prompt(token)

    try:
        response = _call_lm_studio(prompt, base_url, model)
        message = response.choices[0].message
        content = message.content
        # Qwen3 puede dejar content=None si todo se fue en thinking
        if not content:
            logger.warning("Respuesta vacía de IA (posible thinking mode)")
            return {"score": 0, "reason": "Respuesta vacía", "fallback": True}
    except Exception as e:
        logger.warning(f"IA no disponible: {e}. Usando fallback.")
        return {"score": 0, "reason": "IA no disponible", "fallback": True}

    parsed = parse_ai_response(content)
    if parsed is None:
        logger.warning("Respuesta de IA no parseable. Usando fallback.")
        return {"score": 0, "reason": "Respuesta inválida", "fallback": True}

    logger.info(f"IA evaluó {token.get('symbol', '?')}: score={parsed['score']}")
    return {**parsed, "fallback": False}
