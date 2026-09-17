"""Orquestador principal del bot."""

import os
import sys
from typing import Any
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from loguru import logger

from src.analyzer import analyze_token
from src.config import get_mode_settings
from src.detector import detect_new_tokens, fetch_recent_solana_tokens
from src.executor import execute_swap


CYCLE_INTERVAL_SECONDS = 15


def load_env_config() -> dict[str, Any]:
    """Carga la configuración desde variables de entorno.
    
    Returns:
        Dict con la configuración del entorno.
    
    Raises:
        EnvironmentError: Si falta alguna variable obligatoria.
    """
    load_dotenv()
    
    rpc_url = os.getenv("SOLANA_RPC_URL")
    if not rpc_url:
        raise EnvironmentError(
            "Falta SOLANA_RPC_URL en .env. "
            "Copia .env.example a .env y configura las variables."
        )
    
    return {
        "rpc_url": rpc_url,
        "mode": os.getenv("MODE", "equilibrado"),
        "dry_run": os.getenv("DRY_RUN", "true").lower() == "true",
        "lm_studio_url": os.getenv("LM_STUDIO_URL", "http://localhost:1234"),
        "lm_studio_model": os.getenv("LM_STUDIO_MODEL", "qwen/qwen3-4b-2507"),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }


def process_token(
    token: dict[str, Any],
    mode_settings: dict[str, Any],
    dry_run: bool = True,
) -> dict[str, Any]:
    """Analiza un token y decide si ejecutar compra.
    
    Args:
        token: Datos del token.
        mode_settings: Parámetros del modo.
        dry_run: Si True, no ejecuta swap real.
    
    Returns:
        Dict con acción y estado de ejecución.
    """
    analysis = analyze_token(token, mode_settings)
    score = analysis["score"]
    action = analysis["action"]
    
    if action != "COMPRA":
        return {"action": action, "score": score, "executed": False}
    
    base_buy = mode_settings.get("base_buy", 0.01)
    result = execute_swap(
        token_address=token["token_address"],
        amount_sol=base_buy,
        dry_run=dry_run,
    )
    
    return {
        "action": action,
        "score": score,
        "executed": result.get("status") in ("dry_run", "success"),
        "swap_result": result,
    }


def run_cycle(
    seen_tokens: set[str],
    mode_settings: dict[str, Any],
    dry_run: bool = True,
) -> dict[str, int]:
    """Ejecuta un ciclo completo: detectar → analizar → ejecutar.
    
    Args:
        seen_tokens: Set de tokens ya procesados (modificado in-place).
        mode_settings: Parámetros del modo.
        dry_run: Si True, no ejecuta swaps reales.
    
    Returns:
        Dict con estadísticas del ciclo.
    """
    try:
        new_tokens = detect_new_tokens(
            fetch_func=lambda: fetch_recent_solana_tokens(query="pump"),
            seen_tokens=seen_tokens,
        )
    except Exception as e:
        logger.error(f"Error en detección: {e}")
        return {"processed": 0, "executed": 0}
    
    processed = 0
    executed = 0
    
    for token in new_tokens:
        try:
            result = process_token(token, mode_settings, dry_run=dry_run)
            processed += 1
            if result.get("executed"):
                executed += 1
            seen_tokens.add(token["token_address"])
        except Exception as e:
            logger.error(f"Error procesando {token.get('symbol', '?')}: {e}")
    
    logger.info(f"Ciclo: {processed} procesados, {executed} ejecutados, {len(seen_tokens)} vistos total")
    
    return {"processed": processed, "executed": executed}


def main() -> int:
    """Punto de entrada del bot con scheduler continuo.
    
    Returns:
        Código de salida (0 = éxito, 1 = error).
    """
    try:
        config = load_env_config()
    except EnvironmentError as e:
        logger.error(str(e))
        return 1
    
    logger.info(f"Bot iniciado en modo {config['mode']} (DRY_RUN={config['dry_run']})")
    logger.info(f"Ciclo cada {CYCLE_INTERVAL_SECONDS}s. Ctrl+C para detener.")
    
    mode_settings = get_mode_settings(config["mode"])
    seen_tokens: set[str] = set()
    
    # Ejecutar un ciclo inmediatamente al arrancar
    run_cycle(seen_tokens, mode_settings, dry_run=config["dry_run"])
    
    # Programar ciclos periódicos
    scheduler = BlockingScheduler()
    scheduler.add_job(
        lambda: run_cycle(seen_tokens, mode_settings, dry_run=config["dry_run"]),
        "interval",
        seconds=CYCLE_INTERVAL_SECONDS,
        id="cycle",
        max_instances=1,
    )
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot detenido por el usuario.")
        scheduler.shutdown(wait=False)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())