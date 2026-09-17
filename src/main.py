"""Orquestador principal con menú manual/automático."""

import os
import sys
from typing import Any
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from loguru import logger

from src.ai import get_ai_score
from src.analyzer import analyze_token
from src.config import get_mode_settings
from src.executor import execute_swap
from src.fetcher import (
    fetch_by_address,
    fetch_by_symbol,
    fetch_recent_memecoins,
)


CYCLE_INTERVAL_SECONDS = 15
AI_WEIGHT = 0.3


def load_env_config() -> dict[str, Any]:
    """Carga configuración desde .env."""
    load_dotenv()
    rpc_url = os.getenv("SOLANA_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("Falta SOLANA_RPC_URL en .env")
    return {
        "rpc_url": rpc_url,
        "mode": os.getenv("MODE", "equilibrado"),
        "dry_run": os.getenv("DRY_RUN", "true").lower() == "true",
        "lm_studio_url": os.getenv("LM_STUDIO_URL", "http://localhost:1234"),
        "lm_studio_model": os.getenv("LM_STUDIO_MODEL", "qwen/qwen3-4b-2507"),
        "use_ai": os.getenv("USE_AI", "true").lower() == "true",
    }


def print_header(title: str) -> None:
    """Imprime encabezado con formato."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_token_report(
    token: dict[str, Any],
    analysis: dict[str, Any],
    ai_result: dict[str, Any],
    final_score: int,
    action: str,
) -> None:
    """Imprime reporte completo del token."""
    print(f"\n📊 DATOS DEL TOKEN")
    print(f"  Símbolo:       {token.get('symbol', '?')}")
    print(f"  Nombre:        {token.get('name', '?')}")
    print(f"  Address:       {token.get('token_address')}")
    print(f"  Precio USD:    ${token.get('price_usd', 0):.8f}")
    print(f"  Market Cap:    ${token.get('market_cap', 0):,.0f}")
    print(f"  Liquidez:      ${token.get('liquidity_usd', 0):,.0f}")
    print(f"  Volumen 5min:  ${token.get('volume_5min', 0):,.0f}")
    print(f"  Volumen 24h:   ${token.get('volume_24h', 0):,.0f}")
    print(f"  Cambio 5min:   {token.get('price_change_5min', 0):+.2f}%")
    print(f"  DEX:           {token.get('dex_id', '?')}")
    
    print(f"\n🔍 FILTROS APLICADOS (11)")
    for d in analysis.get("details", []):
        mark = "✅" if d["points"] > 0 else "❌"
        print(f"  {mark} {d['filter']:<18} {d['points']:>2} pts — {d['reason']}")
    
    print(f"\n🤖 ANÁLISIS IA")
    if ai_result.get("fallback"):
        print(f"  ⚠️  IA no disponible: {ai_result.get('reason', '?')}")
    else:
        print(f"  Score IA:  {ai_result['score']}/100")
        print(f"  Razón:     {ai_result['reason']}")
    
    print(f"\n🎯 VEREDICTO FINAL")
    print(f"  Score reglas:  {analysis['score']}/100")
    print(f"  Score IA:      {ai_result['score']}/100")
    print(f"  Score final:   {final_score}/100  (70% reglas + 30% IA)")
    print(f"  Acción:        {action}")
    print()


def process_token(
    token: dict[str, Any],
    mode_settings: dict[str, Any],
    dry_run: bool = True,
    use_ai: bool = True,
    lm_studio_url: str = "http://localhost:1234",
    lm_studio_model: str = "qwen/qwen3-4b-2507",
    verbose: bool = False,
) -> dict[str, Any]:
    """Analiza un token (reglas + IA) y decide."""
    analysis = analyze_token(token, mode_settings)
    rule_score = analysis["score"]
    
    ai_result = {"score": 0, "reason": "IA desactivada", "fallback": True}
    if use_ai:
        ai_result = get_ai_score(token, base_url=lm_studio_url, model=lm_studio_model)
    
    final_score = round((1 - AI_WEIGHT) * rule_score + AI_WEIGHT * ai_result["score"])
    
    if final_score > 70:
        action = "COMPRA"
    elif final_score >= 50:
        action = "OBSERVAR"
    else:
        action = "EVITAR"
    
    if verbose:
        print_token_report(token, analysis, ai_result, final_score, action)
    else:
        logger.info(
            f"{token.get('symbol', '?'):<8} | Reglas={rule_score:>3} "
            f"| IA={ai_result['score']:>3} | Final={final_score:>3} | {action}"
        )
    
    result = {
        "token": token,
        "analysis": analysis,
        "ai": ai_result,
        "final_score": final_score,
        "action": action,
        "executed": False,
    }
    
    if action == "COMPRA":
        swap = execute_swap(
            token_address=token["token_address"],
            amount_sol=mode_settings.get("base_buy", 0.01),
            dry_run=dry_run,
        )
        result["executed"] = swap.get("status") in ("dry_run", "success")
        result["swap_result"] = swap
    
    return result


# ============ MODO MANUAL ============

def run_manual_mode(config: dict[str, Any], mode_settings: dict[str, Any]) -> None:
    """Modo manual: análisis de un token específico."""
    print_header("MODO MANUAL")
    print("\n¿Cómo quieres buscar el token?")
    print("  [1] Por dirección (address)")
    print("  [2] Por símbolo (ej. BONK, WIF)")
    
    choice = input("\nOpción [1/2]: ").strip()
    
    if choice == "1":
        address = input("Address del token: ").strip()
        if not address:
            print("❌ Address vacío.")
            return
        print(f"\n🔍 Buscando {address}...")
        token = fetch_by_address(address)
        if token is None:
            print("❌ Token no encontrado.")
            return
        process_token(
            token, mode_settings,
            dry_run=config["dry_run"],
            use_ai=config["use_ai"],
            lm_studio_url=config["lm_studio_url"],
            lm_studio_model=config["lm_studio_model"],
            verbose=True,
        )
    
    elif choice == "2":
        symbol = input("Símbolo del token: ").strip().upper()
        if not symbol:
            print("❌ Símbolo vacío.")
            return
        print(f"\n🔍 Buscando '{symbol}'...")
        tokens = fetch_by_symbol(symbol)
        if not tokens:
            print(f"❌ No se encontraron tokens con símbolo '{symbol}'.")
            return
        
        if len(tokens) > 1:
            print(f"\nSe encontraron {len(tokens)} resultados:")
            for i, t in enumerate(tokens, 1):
                print(f"  [{i}] {t['symbol']:<10} | "
                      f"MC=${t['market_cap']:,.0f} | "
                      f"Liq=${t['liquidity_usd']:,.0f} | "
                      f"{t['token_address'][:12]}...")
            try:
                idx = int(input(f"\nSelecciona [1-{len(tokens)}]: ").strip()) - 1
                token = tokens[idx]
            except (ValueError, IndexError):
                print("❌ Selección inválida.")
                return
        else:
            token = tokens[0]
        
        process_token(
            token, mode_settings,
            dry_run=config["dry_run"],
            use_ai=config["use_ai"],
            lm_studio_url=config["lm_studio_url"],
            lm_studio_model=config["lm_studio_model"],
            verbose=True,
        )
    
    else:
        print("❌ Opción inválida.")


# ============ MODO AUTOMÁTICO ============

def run_automatic_mode(config: dict[str, Any], mode_settings: dict[str, Any]) -> None:
    """Modo automático: scheduler continuo."""
    print_header("MODO AUTOMÁTICO")
    print(f"\nCiclo cada {CYCLE_INTERVAL_SECONDS}s. Ctrl+C para detener.\n")
    
    seen_tokens: set[str] = set()
    
    def cycle_job() -> None:
        tokens = fetch_recent_memecoins()
        new = [t for t in tokens if t["token_address"] not in seen_tokens]
        if not new:
            logger.debug("Sin tokens nuevos.")
            return
        logger.info(f"🔍 {len(new)} tokens nuevos detectados")
        for token in new:
            try:
                process_token(
                    token, mode_settings,
                    dry_run=config["dry_run"],
                    use_ai=config["use_ai"],
                    lm_studio_url=config["lm_studio_url"],
                    lm_studio_model=config["lm_studio_model"],
                    verbose=False,
                )
                seen_tokens.add(token["token_address"])
            except Exception as e:
                logger.error(f"Error en {token.get('symbol')}: {e}")
    
    cycle_job()
    scheduler = BlockingScheduler()
    scheduler.add_job(cycle_job, "interval", seconds=CYCLE_INTERVAL_SECONDS)
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n\nBot detenido.")
        scheduler.shutdown(wait=False)


# ============ MENÚ PRINCIPAL ============

def show_main_menu() -> str:
    """Muestra menú principal y retorna la opción elegida."""
    print_header("CRYPTO BOT — Solana Memecoins")
    print("\n  [1] Modo MANUAL   — Analizar un token específico")
    print("  [2] Modo AUTOMÁTICO — Detectar y analizar tokens cada 15s")
    print("  [0] Salir")
    return input("\nOpción: ").strip()


def main() -> int:
    """Punto de entrada con menú."""
    try:
        config = load_env_config()
    except EnvironmentError as e:
        logger.error(str(e))
        return 1
    
    mode_settings = get_mode_settings(config["mode"])
    
    while True:
        choice = show_main_menu()
        
        if choice == "0":
            print("\n👋 Hasta luego.")
            return 0
        elif choice == "1":
            run_manual_mode(config, mode_settings)
            input("\nPresiona Enter para volver al menú...")
        elif choice == "2":
            run_automatic_mode(config, mode_settings)
            return 0
        else:
            print("❌ Opción inválida.")


if __name__ == "__main__":
    sys.exit(main())