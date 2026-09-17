"""Orquestador principal del bot con UI profesional (rich)."""

import os
import sys
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.align import Align
from rich import box

from src.ai import get_ai_score
from src.analyzer import analyze_token
from src.chain_data import enrich_token
from src.config import get_mode_settings
from src.executor import execute_swap
from src.fetcher import (
    fetch_by_address,
    fetch_by_symbol,
    fetch_recent_memecoins,
)


CYCLE_INTERVAL_SECONDS = 15
AI_WEIGHT = 0.3

console = Console()


# ============ UI HELPERS ============

def clear() -> None:
    """Limpia la pantalla."""
    console.clear()


def show_banner() -> None:
    """Muestra el banner ASCII del bot."""
    banner = Text()
    banner.append("  ██████╗██████╗ ██╗   ██╗██████╗ ████████╗ ██████╗ \n", style="bold cyan")
    banner.append(" ██╔════╝██╔══██╗╚██╗ ██╔╝██╔══██╗╚══██╔══╝██╔═══██╗\n", style="bold cyan")
    banner.append(" ██║     ██████╔╝ ╚████╔╝ ██████╔╝   ██║   ██║   ██║\n", style="bold cyan")
    banner.append(" ██║     ██╔══██╗  ╚██╔╝  ██╔═══╝    ██║   ██║   ██║\n", style="bold cyan")
    banner.append(" ╚██████╗██║  ██║   ██║   ██║        ██║   ╚██████╔╝\n", style="bold cyan")
    banner.append("  ╚═════╝╚═╝  ╚═╝   ╚═╝   ╚═╝        ╚═╝    ╚═════╝ \n", style="bold cyan")
    banner.append("         B  O  T   ·   S O L A N A   ·   2 0 2 6\n", style="bold magenta")
    
    console.print(Align.center(banner))
    console.print()


def show_status_bar(config: dict[str, Any]) -> None:
    """Muestra barra de estado con modo, DRY_RUN e IA."""
    mode = config["mode"].upper()
    dry = "[bold yellow]DRY_RUN[/]" if config["dry_run"] else "[bold red]REAL[/]"
    ai = "[green]ON[/]" if config["use_ai"] else "[dim]OFF[/]"
    
    text = f"  Modo: [bold cyan]{mode}[/]   |   Ejecución: {dry}   |   IA: {ai}  "
    console.print(Panel(text, style="dim", box=box.ROUNDED))


def show_main_menu() -> str:
    """Menú principal con estilo."""
    clear()
    show_banner()
    show_status_bar(CURRENT_CONFIG)
    
    menu = Table(show_header=False, box=box.ROUNDED, border_style="cyan", padding=(0, 2))
    menu.add_column("Opción", style="bold yellow", width=6)
    menu.add_column("Acción", style="white")
    
    menu.add_row("[1]", "🔍 Modo MANUAL — Analizar un token específico")
    menu.add_row("[2]", "🤖 Modo AUTOMÁTICO — Detectar tokens cada 15s")
    menu.add_row("[3]", "⚙️  Cambiar modo de operación")
    menu.add_row("[0]", "🚪 Salir")
    
    console.print(Panel(menu, title="[bold cyan]MENÚ PRINCIPAL[/]", border_style="cyan"))
    
    return Prompt.ask("\n[bold yellow]Opción[/]", choices=["0", "1", "2", "3"], default="0")


def show_token_report(
    token: dict[str, Any],
    analysis: dict[str, Any],
    ai_result: dict[str, Any],
    final_score: int,
    action: str,
) -> None:
    """Reporte visual completo del token."""
    
    # Encabezado del token
    symbol = token.get("symbol", "?")
    name = token.get("name", "?")
    addr = token.get("token_address", "?")
    
    console.print()
    console.print(Panel(
        f"[bold white]{symbol}[/] — {name}\n[dim]{addr}[/]",
        title="[bold cyan]TOKEN[/]",
        border_style="cyan",
    ))
    
    # Tabla de datos
    data = Table(title="📊 Datos de Mercado", box=box.SIMPLE_HEAVY, title_style="bold")
    data.add_column("Métrica", style="cyan")
    data.add_column("Valor", style="white", justify="right")
    
    data.add_row("Precio USD", f"${token.get('price_usd', 0):.8f}")
    data.add_row("Market Cap", f"${token.get('market_cap', 0):,.0f}")
    data.add_row("Liquidez", f"${token.get('liquidity_usd', 0):,.0f}")
    data.add_row("Volumen 5min", f"${token.get('volume_5min', 0):,.0f}")
    data.add_row("Volumen 24h", f"${token.get('volume_24h', 0):,.0f}")
    data.add_row("Cambio 5min", f"{token.get('price_change_5min', 0):+.2f}%")
    data.add_row("DEX", str(token.get("dex_id", "?")))
    console.print(data)
    
    # Tabla de filtros
    filtros = Table(title="🔍 Filtros (11)", box=box.SIMPLE_HEAVY, title_style="bold")
    filtros.add_column("", width=3)
    filtros.add_column("Filtro", style="cyan")
    filtros.add_column("Pts", justify="right", style="yellow")
    filtros.add_column("Razón", style="white")
    
    for d in analysis.get("details", []):
        mark = "[green]✓[/]" if d["points"] > 0 else "[red]✗[/]"
        filtros.add_row(mark, d["filter"], str(d["points"]), d["reason"])
    console.print(filtros)
    
    # IA
    if ai_result.get("fallback"):
        ia_panel = Panel(
            f"[yellow]⚠ IA no disponible:[/] {ai_result.get('reason', '?')}",
            title="🤖 IA Local",
            border_style="yellow",
        )
    else:
        ia_panel = Panel(
            f"[bold]Score:[/] [cyan]{ai_result['score']}/100[/]\n"
            f"[bold]Razón:[/] {ai_result['reason']}",
            title="🤖 IA Local",
            border_style="green",
        )
    console.print(ia_panel)
    
    # Veredicto final
    score_color = {
        "COMPRA": "bold green",
        "OBSERVAR": "bold yellow",
        "EVITAR": "bold red",
    }.get(action, "white")
    
    veredicto = Table(show_header=False, box=box.DOUBLE, border_style=score_color)
    veredicto.add_column("", style="cyan")
    veredicto.add_column("", style=score_color)
    veredicto.add_row("Score reglas", f"{analysis['score']}/100")
    veredicto.add_row("Score IA", f"{ai_result['score']}/100")
    veredicto.add_row("Score final", f"{final_score}/100")
    veredicto.add_row("Acción", f"[{score_color}]{action}[/]")
    
    console.print(Panel(veredicto, title="🎯 VEREDICTO", border_style=score_color))


def show_progress(msg: str) -> None:
    """Muestra spinner mientras se procesa algo."""
    console.print(f"[dim]⏳ {msg}...[/]")


# ============ CONFIG ============

def load_env_config() -> dict[str, Any]:
    """Carga configuración desde .env."""
    load_dotenv()
    rpc_url = os.getenv("SOLANA_RPC_URL")
    if not rpc_url:
        raise EnvironmentError("Falta SOLANA_RPC_URL en .env")
    return {
        "rpc_url": rpc_url,
        "helius_api_key": os.getenv("HELIUS_API_KEY", ""),
        "birdeye_api_key": os.getenv("BIRDEYE_API_KEY", ""),
        "mode": os.getenv("MODE", "equilibrado"),
        "dry_run": os.getenv("DRY_RUN", "true").lower() == "true",
        "lm_studio_url": os.getenv("LM_STUDIO_URL", "http://localhost:1234"),
        "lm_studio_model": os.getenv("LM_STUDIO_MODEL", "qwen/qwen3-4b-2507"),
        "use_ai": os.getenv("USE_AI", "true").lower() == "true",
    }


# ============ CORE LOGIC ============

def process_token(
    token: dict[str, Any],
    mode_settings: dict[str, Any],
    config: dict[str, Any],
    verbose: bool = False,
) -> dict[str, Any]:
    """Analiza un token (on-chain + reglas + IA) y decide."""
    # 1. Enriquecer con datos on-chain (Helius)
    if config["helius_api_key"]:
        token = enrich_token(token, config["helius_api_key"])
    
    # 2. Análisis por reglas
    analysis = analyze_token(token, mode_settings)
    rule_score = analysis["score"]
    
    # 3. Análisis por IA
    ai_result = {"score": 0, "reason": "IA desactivada", "fallback": True}
    if config["use_ai"]:
        ai_result = get_ai_score(
            token,
            base_url=config["lm_studio_url"],
            model=config["lm_studio_model"],
        )
    
    # 4. Score combinado
    final_score = round((1 - AI_WEIGHT) * rule_score + AI_WEIGHT * ai_result["score"])
    
    # 5. Decisión
    if final_score > 70:
        action = "COMPRA"
    elif final_score >= 50:
        action = "OBSERVAR"
    else:
        action = "EVITAR"
    
    # 6. Ejecución
    executed = False
    swap_result = None
    if action == "COMPRA":
        swap_result = execute_swap(
            token_address=token["token_address"],
            amount_sol=mode_settings.get("base_buy", 0.01),
            dry_run=config["dry_run"],
        )
        executed = swap_result.get("status") in ("dry_run", "success")
    
    if verbose:
        show_token_report(token, analysis, ai_result, final_score, action)
    else:
        score_style = "green" if final_score > 70 else ("yellow" if final_score >= 50 else "red")
        console.print(
            f"  [cyan]{token.get('symbol', '?'):<8}[/] "
            f"| Reglas=[yellow]{rule_score:>3}[/] "
            f"| IA=[cyan]{ai_result['score']:>3}[/] "
            f"| Final=[{score_style}]{final_score:>3}[/] "
            f"| [{score_style}]{action}[/]"
        )
    
    return {
        "token": token,
        "analysis": analysis,
        "ai": ai_result,
        "final_score": final_score,
        "action": action,
        "executed": executed,
        "swap_result": swap_result,
    }


# ============ MODOS ============

def run_manual_mode(config: dict[str, Any], mode_settings: dict[str, Any]) -> None:
    """Modo manual."""
    clear()
    console.print(Panel("[bold]MODO MANUAL[/]", border_style="cyan"))
    
    choice = Prompt.ask(
        "\n[cyan]Buscar por[/]",
        choices=["1", "2"],
        default="2",
    )
    
    if choice == "1":
        address = Prompt.ask("Address del token").strip()
        if not address:
            console.print("[red]❌ Address vacío.[/]")
            return
        with console.status("[cyan]Buscando en DexScreener...[/]"):
            token = fetch_by_address(address)
        if token is None:
            console.print("[red]❌ Token no encontrado.[/]")
            return
        with console.status("[cyan]Enriqueciendo con datos on-chain...[/]"):
            process_token(token, mode_settings, config, verbose=True)
    
    elif choice == "2":
        symbol = Prompt.ask("Símbolo del token").strip().upper()
        if not symbol:
            console.print("[red]❌ Símbolo vacío.[/]")
            return
        
        with console.status(f"[cyan]Buscando '{symbol}'...[/]"):
            tokens = fetch_by_symbol(symbol)
        
        if not tokens:
            console.print(f"[red]❌ No se encontraron tokens '{symbol}'.[/]")
            return
        
        if len(tokens) == 1:
            token = tokens[0]
        else:
            table = Table(title=f"Resultados para '{symbol}'", box=box.SIMPLE_HEAVY)
            table.add_column("#", style="yellow")
            table.add_column("Símbolo", style="cyan")
            table.add_column("MC", justify="right")
            table.add_column("Liquidez", justify="right")
            table.add_column("Address", style="dim")
            
            for i, t in enumerate(tokens, 1):
                table.add_row(
                    str(i),
                    t["symbol"],
                    f"${t['market_cap']:,.0f}",
                    f"${t['liquidity_usd']:,.0f}",
                    t["token_address"][:16] + "...",
                )
            console.print(table)
            
            idx = Prompt.ask(
                "[cyan]Selecciona[/]",
                choices=[str(i) for i in range(1, len(tokens) + 1)],
                default="1",
            )
            token = tokens[int(idx) - 1]
        
        with console.status("[cyan]Enriqueciendo con datos on-chain...[/]"):
            process_token(token, mode_settings, config, verbose=True)


def run_automatic_mode(config: dict[str, Any], mode_settings: dict[str, Any]) -> None:
    """Modo automático."""
    clear()
    console.print(Panel(
        f"[bold]MODO AUTOMÁTICO[/]\n"
        f"[dim]Ciclo cada {CYCLE_INTERVAL_SECONDS}s. Ctrl+C para detener.[/]",
        border_style="cyan",
    ))
    console.print()
    
    seen_tokens: set[str] = set()
    cycle_num = 0
    
    def cycle_job() -> None:
        nonlocal cycle_num
        cycle_num += 1
        console.rule(f"[bold cyan]Ciclo #{cycle_num}[/]")
        
        tokens = fetch_recent_memecoins()
        new = [t for t in tokens if t["token_address"] not in seen_tokens]
        
        if not new:
            console.print("[dim]Sin tokens nuevos.[/]")
            return
        
        console.print(f"[yellow]🔍 {len(new)} tokens nuevos[/]")
        for token in new:
            try:
                process_token(token, mode_settings, config, verbose=False)
                seen_tokens.add(token["token_address"])
            except Exception as e:
                console.print(f"[red]Error en {token.get('symbol')}: {e}[/]")
    
    try:
        cycle_job()
        scheduler = BlockingScheduler()
        scheduler.add_job(cycle_job, "interval", seconds=CYCLE_INTERVAL_SECONDS)
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[yellow]Bot detenido.[/]")
        scheduler.shutdown(wait=False)


def change_mode(config: dict[str, Any]) -> None:
    """Cambia el modo de operación en runtime."""
    current = config["mode"]
    new_mode = Prompt.ask(
        "[cyan]Nuevo modo[/]",
        choices=["conservador", "equilibrado", "agresivo"],
        default=current,
    )
    config["mode"] = new_mode
    console.print(f"[green]✓ Modo cambiado a {new_mode}[/]")
    Prompt.ask("\n[dim]Enter para continuar[/]", default="")


# ============ MAIN ============

CURRENT_CONFIG: dict[str, Any] = {}


def main() -> int:
    """Punto de entrada."""
    global CURRENT_CONFIG
    
    try:
        config = load_env_config()
    except EnvironmentError as e:
        console.print(f"[red]Error: {e}[/]")
        return 1
    
    CURRENT_CONFIG = config
    
    # Configurar logger para que no inunde la UI
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    
    mode_settings = get_mode_settings(config["mode"])
    
    while True:
        choice = show_main_menu()
        
        if choice == "0":
            console.print("\n[cyan]👋 Hasta luego.[/]\n")
            return 0
        elif choice == "1":
            run_manual_mode(config, mode_settings)
            Prompt.ask("\n[dim]Enter para volver al menú[/]", default="")
        elif choice == "2":
            run_automatic_mode(config, mode_settings)
            return 0
        elif choice == "3":
            change_mode(config)
            mode_settings = get_mode_settings(config["mode"])


if __name__ == "__main__":
    sys.exit(main())