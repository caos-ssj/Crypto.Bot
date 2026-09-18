"""Orquestador principal del bot con UI profesional (rich)."""

import os
import sys
from typing import Any

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from loguru import logger
from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from src.ai import get_ai_score
from src.analyzer import analyze_token, decide
from src.chain_data import enrich_token
from src.config import get_mode_settings
from src.executor import (
    LAMPORTS_PER_SOL,
    execute_sell,
    execute_swap,
    load_wallet,
    wallet_public_key,
)
from src.fetcher import (
    fetch_by_address,
    fetch_by_symbol,
    fetch_recent_memecoins,
)
from src.risk import (
    Position,
    calculate_tp_sl,
    can_open_position,
    check_daily_limit,
    check_stop_loss,
    check_take_profit,
    update_trailing_stop,
)
from src.storage import (
    close_position,
    get_open_positions,
    get_seen_tokens,
    get_today_realized_loss,
    init_db,
    mark_seen,
    save_analysis,
    save_position,
    update_position_state,
)

# ============ CONSTANTES ============
CYCLE_INTERVAL_SECONDS = 15
AI_WEIGHT = 0.3

console = Console()
CURRENT_CONFIG: dict[str, Any] = {}
_WALLET_KEYPAIR: Any = None


# ============ WALLET ============


def get_wallet_keypair(config: dict[str, Any]) -> Any:
    """Construye (y cachea) el Keypair de la wallet desde .env."""
    global _WALLET_KEYPAIR
    if _WALLET_KEYPAIR is not None:
        return _WALLET_KEYPAIR

    _WALLET_KEYPAIR = load_wallet(config.get("wallet_private_key", ""))
    if _WALLET_KEYPAIR is not None:
        console.print(f"[green]Wallet: {wallet_public_key(_WALLET_KEYPAIR)}[/]")
    elif not config.get("dry_run", True):
        console.print(
            "[red]⚠ Sin WALLET_PRIVATE_KEY válida: no se podrá operar en real.[/]"
        )
    return _WALLET_KEYPAIR


# ============ UI HELPERS ============


def clear() -> None:
    """Limpia la pantalla."""
    console.clear()


def show_banner() -> None:
    """Muestra el banner ASCII del bot."""
    banner = Text()
    banner.append(
        "  ██████╗██████╗ ██╗   ██╗██████╗ ████████╗ ██████╗ \n", style="bold cyan"
    )
    banner.append(
        " ██╔════╝██╔══██╗╚██╗ ██╔╝██╔══██╗╚══██╔══╝██╔═══██╗\n", style="bold cyan"
    )
    banner.append(
        " ██║     ██████╔╝ ╚████╔╝ ██████╔╝   ██║   ██║   ██║\n", style="bold cyan"
    )
    banner.append(
        " ██║     ██╔══██╗  ╚██╔╝  ██╔═══╝    ██║   ██║   ██║\n", style="bold cyan"
    )
    banner.append(
        " ╚██████╗██║  ██║   ██║   ██║        ██║   ╚██████╔╝\n", style="bold cyan"
    )
    banner.append(
        "  ╚═════╝╚═╝  ╚═╝   ╚═╝   ╚═╝        ╚═╝    ╚═════╝ \n", style="bold cyan"
    )
    banner.append(
        "         B  O  T   ·   S O L A N A   ·   2 0 2 6\n", style="bold magenta"
    )

    console.print(Align.center(banner))
    console.print()


def show_status_bar(config: dict[str, Any]) -> None:
    """Muestra barra de estado con modo, DRY_RUN e IA."""
    mode = config.get("mode", "?").upper()
    dry = "[bold yellow]DRY_RUN[/]" if config.get("dry_run") else "[bold red]REAL[/]"
    ai = "[green]ON[/]" if config.get("use_ai") else "[dim]OFF[/]"

    text = f"  Modo: [bold cyan]{mode}[/]   |   Ejecución: {dry}   |   IA: {ai}  "
    console.print(Panel(text, style="dim", box=box.ROUNDED))


def show_main_menu() -> str:
    """Menú principal con estilo."""
    clear()
    show_banner()
    show_status_bar(CURRENT_CONFIG)

    menu = Table(
        show_header=False,
        box=box.ROUNDED,
        border_style="cyan",
        padding=(0, 2),
    )
    menu.add_column("Opción", style="bold yellow", width=6)
    menu.add_column("Acción", style="white")

    menu.add_row("[1]", "🔍 Modo MANUAL — Analizar un token específico")
    menu.add_row("[2]", "🤖 Modo AUTOMÁTICO — Detectar tokens cada 15s")
    menu.add_row("[3]", "⚙️  Cambiar modo de operación")
    menu.add_row("[0]", "🚪 Salir")

    console.print(
        Panel(menu, title="[bold cyan]MENÚ PRINCIPAL[/]", border_style="cyan")
    )

    return Prompt.ask(
        "\n[bold yellow]Opción[/]",
        choices=["0", "1", "2", "3"],
        default="0",
    )


def show_token_report(
    token: dict[str, Any],
    analysis: dict[str, Any],
    ai_result: dict[str, Any],
    final_score: int,
    action: str,
) -> None:
    """Reporte visual completo del token."""

    symbol = token.get("symbol", "?")
    name = token.get("name", "?")
    addr = token.get("token_address", "?")

    console.print()
    console.print(
        Panel(
            f"[bold white]{symbol}[/] — {name}\n[dim]{addr}[/]",
            title="[bold cyan]TOKEN[/]",
            border_style="cyan",
        )
    )

    # Tabla de datos de mercado
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

    if "supply" in token:
        data.add_row("Supply", f"{token.get('supply', 0):,.0f}")
    if "top_10_holders_pct" in token:
        data.add_row("Top-10 holders", f"{token.get('top_10_holders_pct', 0):.2f}%")
    if "creator_age_days" in token:
        data.add_row("Edad creador", f"{token.get('creator_age_days', 0)} días")

    console.print(data)

    # Tabla de filtros
    filtros = Table(title="🔍 Filtros (11)", box=box.SIMPLE_HEAVY, title_style="bold")
    filtros.add_column("", width=3)
    filtros.add_column("Filtro", style="cyan")
    filtros.add_column("Pts", justify="right", style="yellow")
    filtros.add_column("Razón", style="white")

    for d in analysis.get("details", []):
        if d.get("status") == "missing":
            mark = "[yellow]⚠[/]"
        elif d["points"] > 0:
            mark = "[green]✓[/]"
        else:
            mark = "[red]✗[/]"
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
    console.print()


# ============ CONFIG ============


def load_env_config() -> dict[str, Any]:
    """Carga configuración desde .env."""
    load_dotenv()

    rpc_url = os.getenv("SOLANA_RPC_URL")
    if not rpc_url:
        raise OSError(
            "Falta SOLANA_RPC_URL en .env. "
            "Copia .env.example a .env y configura las variables."
        )

    return {
        "rpc_url": rpc_url,
        "helius_api_key": os.getenv("HELIUS_API_KEY", ""),
        "birdeye_api_key": os.getenv("BIRDEYE_API_KEY", ""),
        "wallet_private_key": os.getenv("WALLET_PRIVATE_KEY", ""),
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
        try:
            token = enrich_token(token, config["helius_api_key"])
        except Exception as e:
            logger.warning(f"Error enriqueciendo {token.get('symbol')}: {e}")

    # 2. Análisis por reglas (11 filtros)
    analysis = analyze_token(token, mode_settings)
    rule_score = analysis["score"]

    # 3. Análisis por IA
    ai_result = {"score": 0, "reason": "IA desactivada", "fallback": True}
    if config["use_ai"]:
        try:
            ai_result = get_ai_score(
                token,
                base_url=config["lm_studio_url"],
                model=config["lm_studio_model"],
            )
        except Exception as e:
            logger.warning(f"Error en IA para {token.get('symbol')}: {e}")

    # 4. Score combinado (70% reglas + 30% IA)
    final_score = round((1 - AI_WEIGHT) * rule_score + AI_WEIGHT * ai_result["score"])

    # 5. Decisión unificada (analyzer.decide)
    action = decide(final_score)

    # 6. Ejecución (con límites de riesgo en modo real)
    executed = False
    swap_result = None
    if action == "COMPRA":
        open_positions = get_open_positions()
        daily_loss = get_today_realized_loss()
        risk_ok = config["dry_run"] or (
            can_open_position(open_positions) and check_daily_limit(daily_loss)
        )
        if not risk_ok:
            logger.warning(
                f"Riesgo bloquea compra de {token.get('symbol')}: "
                f"{len(open_positions)} posiciones, "
                f"pérdida diaria {daily_loss:.3f} SOL"
            )
        else:
            wallet_keypair = get_wallet_keypair(config)
            try:
                swap_result = execute_swap(
                    token_address=token["token_address"],
                    amount_sol=mode_settings.get("base_buy", 0.01),
                    wallet_keypair=wallet_keypair,
                    dry_run=config["dry_run"],
                    rpc_url=config["rpc_url"],
                )
                executed = swap_result.get("status") in ("dry_run", "success")
                if swap_result.get("status") == "success":
                    _open_position_from_swap(token, swap_result, config, mode_settings)
            except Exception as e:
                logger.warning(f"Error en swap para {token.get('symbol')}: {e}")

    # 7. Resultado
    result = {
        "token": token,
        "analysis": analysis,
        "ai": ai_result,
        "final_score": final_score,
        "action": action,
        "executed": executed,
        "swap_result": swap_result,
    }

    # 8. Guardar en SQLite
    try:
        save_analysis(result)
    except Exception as e:
        logger.warning(f"No se pudo guardar en DB: {e}")

    # 9. Output
    if verbose:
        show_token_report(token, analysis, ai_result, final_score, action)
    else:
        score_style = (
            "green" if final_score > 70 else ("yellow" if final_score >= 50 else "red")
        )
        console.print(
            f"  [cyan]{token.get('symbol', '?'):<8}[/] "
            f"| Reglas=[yellow]{rule_score:>3}[/] "
            f"| IA=[cyan]{ai_result['score']:>3}[/] "
            f"| Final=[{score_style}]{final_score:>3}[/] "
            f"| [{score_style}]{action}[/]"
        )

    return result


def _open_position_from_swap(
    token: dict[str, Any],
    swap_result: dict[str, Any],
    config: dict[str, Any],
    mode_settings: dict[str, Any],
) -> None:
    """Abre una posición en la DB tras una compra real exitosa."""
    symbol = token.get("symbol", "?")
    price = token.get("price_usd")
    if not price:
        try:
            fresh = fetch_by_address(token["token_address"])
            price = fresh.get("price_usd") if fresh else None
        except Exception as e:  # BLE001 ignorado (ruff.toml): frontera de red
            logger.warning(f"No se pudo obtener precio de {symbol}: {e}")
            price = None
    if not price:
        logger.warning(f"Comprado pero sin entry price; no se abre posición: {symbol}")
        return

    amount_sol = swap_result.get("amount_sol", mode_settings.get("base_buy", 0.01))
    tp, sl = calculate_tp_sl(price)
    position = Position(
        token_address=token["token_address"],
        symbol=symbol,
        entry_price=price,
        amount_sol=amount_sol,
        tp_price=tp,
        sl_price=sl,
    )
    save_position(position.__dict__)
    logger.info(
        f"Posición abierta: {symbol} @ ${price:.8f} (TP ${tp:.8f}/SL ${sl:.8f})"
    )


def monitor_positions(config: dict[str, Any]) -> None:
    """Monitorea posiciones abiertas: TP/SL/trailing + venta real."""
    positions = get_open_positions()
    if not positions:
        return

    keypair = get_wallet_keypair(config)
    console.print(f"[cyan]📊 Monitoreo: {len(positions)} posición(es) abierta(s)[/]")

    for row in positions:
        symbol = row.get("symbol", "?")
        address = row["token_address"]
        try:
            fresh = fetch_by_address(address)
            price = fresh.get("price_usd") if fresh else None
            if not price:
                console.print(f"[dim]Sin precio para {symbol}, se omite.[/]")
                continue

            position = Position(
                token_address=address,
                symbol=symbol,
                entry_price=row.get("entry_price") or 0.0,
                amount_sol=row.get("amount_sol") or 0.0,
                tp_price=row.get("tp_price") or 0.0,
                sl_price=row.get("sl_price") or 0.0,
                trailing_active=bool(row.get("trailing_active")),
                max_price_reached=row.get("max_price_reached") or 0.0,
                opened_at=row.get("opened_at") or "",
            )
            before_sl = position.sl_price
            update_trailing_stop(position, price)
            if position.sl_price != before_sl or position.trailing_active:
                update_position_state(
                    address,
                    position.sl_price,
                    position.trailing_active,
                    position.max_price_reached,
                )
                console.print(
                    f"[yellow]↗ Trailing {symbol}: SL a ${position.sl_price:.8f}[/]"
                )

            hit_tp = check_take_profit(position, price)
            hit_sl = check_stop_loss(position, price)
            if hit_tp or hit_sl:
                reason = "TP" if hit_tp else "SL"
                console.print(
                    f"[yellow]🎯 {reason} en {symbol} @ ${price:.8f} — vendiendo...[/]"
                )
                sell = execute_sell(
                    address,
                    keypair,
                    config["rpc_url"],
                    dry_run=config["dry_run"],
                )
                if sell.get("status") == "success":
                    received_sol = sell.get("out_amount_sol", 0) / LAMPORTS_PER_SOL
                    pnl = received_sol - position.amount_sol
                elif sell.get("status") == "dry_run":
                    pnl = (
                        position.amount_sol * (price / position.entry_price - 1)
                        if position.entry_price
                        else 0.0
                    )
                else:
                    console.print(
                        f"[red]Venta falló ({sell.get('reason')}) en {symbol} — se mantiene la posición.[/]"
                    )
                    continue
                close_position(address, price, pnl)
                console.print(
                    f"[green]↩ {symbol} cerrado: pnl {pnl:+.4f} SOL (${price:.8f})[/]"
                )
        except Exception as e:  # BLE001 ignorado (ruff.toml): no cortar el ciclo
            console.print(f"[red]Error monitoreando {symbol}: {e}[/]")


# ============ MODOS ============


def run_manual_mode(config: dict[str, Any], mode_settings: dict[str, Any]) -> None:
    """Modo manual: analizar un token específico."""
    clear()
    console.print(Panel("[bold]MODO MANUAL[/]", border_style="cyan"))

    console.print("\n[cyan]¿Cómo quieres buscar el token?[/]")
    console.print("  [yellow][1][/] Por dirección (address)")
    console.print("  [yellow][2][/] Por símbolo (ej. BONK, WIF)")

    choice = Prompt.ask("\n[cyan]Opción[/]", choices=["1", "2"], default="2")

    token: dict[str, Any] | None = None

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

    if token is None:
        return

    with console.status("[cyan]Enriqueciendo con datos on-chain...[/]"):
        process_token(token, mode_settings, config, verbose=True)


def run_automatic_mode(config: dict[str, Any], mode_settings: dict[str, Any]) -> None:
    """Modo automático: scheduler continuo."""
    clear()
    console.print(
        Panel(
            f"[bold]MODO AUTOMÁTICO[/]\n"
            f"[dim]Ciclo cada {CYCLE_INTERVAL_SECONDS}s. Ctrl+C para detener.[/]",
            border_style="cyan",
        )
    )
    console.print()

    # Cargar histórico de tokens ya procesados (persistido en SQLite).
    seen_tokens: set[str] = get_seen_tokens()
    console.print(f"[dim]Historial: {len(seen_tokens)} tokens ya procesados.[/]")
    console.print()

    cycle_num = 0

    def cycle_job() -> None:
        nonlocal cycle_num
        cycle_num += 1
        console.rule(f"[bold cyan]Ciclo #{cycle_num}[/]")

        try:
            monitor_positions(config)
        except Exception as e:  # BLE001 ignorado (ruff.toml): frontera de red
            console.print(f"[red]Error en monitoreo: {e}[/]")

        try:
            tokens = fetch_recent_memecoins()
        except Exception as e:
            console.print(f"[red]Error obteniendo tokens: {e}[/]")
            return

        new = [t for t in tokens if t["token_address"] not in seen_tokens]

        if not new:
            console.print("[dim]Sin tokens nuevos.[/]")
            return

        console.print(f"[yellow]🔍 {len(new)} tokens nuevos[/]")
        for token in new:
            address = token["token_address"]
            try:
                process_token(token, mode_settings, config, verbose=False)
                seen_tokens.add(address)
                mark_seen(address)
            except Exception as e:
                console.print(f"[red]Error en {token.get('symbol')}: {e}[/]")

    try:
        cycle_job()
        scheduler = BlockingScheduler()
        scheduler.add_job(cycle_job, "interval", seconds=CYCLE_INTERVAL_SECONDS)
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[yellow]Bot detenido.[/]")
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass


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


def main() -> int:
    """Punto de entrada del bot."""
    global CURRENT_CONFIG

    try:
        config = load_env_config()
    except OSError as e:
        console.print(f"[red]Error: {e}[/]")
        return 1

    CURRENT_CONFIG = config

    # Inicializar base de datos
    try:
        init_db()
    except Exception as e:
        console.print(f"[red]Error inicializando DB: {e}[/]")
        return 1

    # Logger solo para warnings (la UI ya muestra todo)
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
