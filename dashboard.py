"""Dashboard web con Streamlit para el bot.

Tono visual: dossier técnico "terminal dark" (misma identidad que la página de
presentación). Paleta + tipografía auto-hospedada desde `dashboard_theme.css`.
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.fetcher import fetch_by_address
from src.storage import (
    get_closed_positions,
    get_open_positions,
    get_recent_analyses,
    get_stats,
    get_today_realized_loss,
    init_db,
)

# ============ CONFIG ============
st.set_page_config(
    page_title="Crypto Bot Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

theme_file = Path(__file__).parent / "dashboard_theme.css"
if theme_file.exists():
    st.markdown(
        f"<style>{theme_file.read_text()}</style>",
        unsafe_allow_html=True,
    )


def _stat(label: str, value: str, tone: str = "ok", caption: str = "") -> str:
    """Célula de cifra verificada (hairline + mono label + numeral serif con glow)."""
    num_style = {"ok": "ok", "cy": "cy", "ink": ""}.get(tone, "")
    cap = f'<div class="st-cap">{caption}</div>' if caption else ""
    return (
        f"""<div class="stat"><div class="st-hd">{label}</div>"""
        f"""<div class="st-num {num_style}">{value}</div>{cap}</div>"""
    )


def _stat_row(cells: list[str]) -> str:
    """Fila de células separadas por hairlines (grid dossier)."""
    return f'<div class="proof">{"".join(cells)}</div>'


# ============ HEADER ============
st.markdown("""
    <h1 class="dsh-title"><span class="r">CRYPTO&nbsp;BOT</span></h1>
    <p class="dsh-sub">DASHBOARD · ANÁLISIS DE MEMECOINS EN SOLANA</p>
    <div class="dsh-rule"></div>
""", unsafe_allow_html=True)


# ============ SIDEBAR ============
with st.sidebar:
    st.markdown(
        "<div class='st-hd'>CONFIGURACIÓN</div>",
        unsafe_allow_html=True,
    )
    limit = st.slider("Análisis a mostrar", 10, 500, 50, step=10)
    action_filter = st.multiselect(
        "Filtrar por acción",
        ["COMPRA", "OBSERVAR", "EVITAR"],
        default=["COMPRA", "OBSERVAR", "EVITAR"],
    )
    min_score = st.slider("Score final mínimo", 0, 100, 0)

    if st.button("🔄 Refrescar"):
        st.rerun()

    st.divider()
    st.caption("Ejecuta el bot en otra terminal:")
    st.code("python -m src.main", language="bash")


# ============ MÉTRICAS ============
stats = get_stats()

st.markdown(
    _stat_row(
        [
            _stat("Total analizados", str(stats["total"])),
            _stat("Compra", str(stats["compra"]), "ok"),
            _stat("Observar", str(stats["observar"]), "cy"),
            _stat("Evitar", str(stats["evitar"]), "ink"),
            _stat("Ejecutadas", str(stats["executed"]), "ok"),
        ]
    ),
    unsafe_allow_html=True,
)

st.markdown('<div style="height:1.2rem"></div>', unsafe_allow_html=True)


# ============ CARGA DE DATOS ============
analyses = get_recent_analyses(limit=limit)

if not analyses:
    st.info("📭 No hay análisis todavía. Ejecuta el bot para generar datos.")
    st.stop()

df = pd.DataFrame(analyses)

# Parsear details_json
df["details"] = df["details_json"].apply(
    lambda x: json.loads(x) if x else []
)

# Filtros
df = df[df["action"].isin(action_filter)]
df = df[df["final_score"] >= min_score]

if df.empty:
    st.warning("⚠️ No hay análisis que coincidan con los filtros.")
    st.stop()


# ============ GRÁFICO DE SCORES ============
st.markdown('<div class="dsh-hd">Evolución de scores</div>', unsafe_allow_html=True)

chart_df = df[["timestamp", "rule_score", "ai_score", "final_score"]].copy()
chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"])
chart_df = chart_df.sort_values("timestamp").set_index("timestamp")

st.line_chart(
    chart_df,
    color=["#aeb8c4", "#22d3ee", "#3ddc97"],
    height=250,
)

st.divider()


# ============ TABLA PRINCIPAL ============
st.markdown(
    f'<div class="dsh-hd">Análisis recientes · {len(df)}</div>',
    unsafe_allow_html=True,
)

display_df = df[[
    "timestamp", "symbol", "price_usd", "market_cap",
    "liquidity_usd", "rule_score", "ai_score", "final_score", "action"
]].copy()

local_tz = datetime.now().astimezone().tzinfo
display_df["timestamp"] = (
    pd.to_datetime(display_df["timestamp"], utc=True)
    .dt.tz_convert(local_tz)
    .dt.strftime("%H:%M:%S")
)
display_df["price_usd"] = display_df["price_usd"].apply(lambda x: f"${x:.8f}")
display_df["market_cap"] = display_df["market_cap"].apply(lambda x: f"${x:,.0f}")
display_df["liquidity_usd"] = display_df["liquidity_usd"].apply(lambda x: f"${x:,.0f}")

display_df.columns = [
    "Hora", "Símbolo", "Precio", "MC", "Liq",
    "Reglas", "IA", "Final", "Acción"
]

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    height=400,
)

st.divider()


# ============ RIESGO / POSICIONES ============
st.markdown('<div class="dsh-hd">Riesgo / Posiciones</div>', unsafe_allow_html=True)

open_positions = get_open_positions()
closed = get_closed_positions(limit=100)
today_loss = get_today_realized_loss()
realized_total = sum(p.get("pnl_sol") or 0.0 for p in closed)
trailing_active = sum(1 for p in open_positions if p.get("trailing_active"))

st.markdown(
    _stat_row(
        [
            _stat("Posiciones abiertas", str(len(open_positions)), "ok", "máx 3"),
            _stat("Pérdida diaria", f"{today_loss:.4f} SOL", "cy", "límite 0.5"),
            _stat("P&L realizado", f"{realized_total:.4f} SOL", "ok", "histórico"),
            _stat("SL/Trailing activos", str(trailing_active), "ink", "posiciones"),
        ]
    ),
    unsafe_allow_html=True,
)

st.markdown('<div style="height:1.2rem"></div>', unsafe_allow_html=True)

if not open_positions and not closed:
    st.info("📭 Sin posiciones todavía. El modo DRY_RUN no abre posiciones; se llenará al operar en real.")
else:
    if open_positions:
        st.markdown("**Posiciones abiertas**")
        risk_rows = []
        for p in open_positions:
            live_price = None
            try:
                t = fetch_by_address(p["token_address"])
                live_price = (t or {}).get("price_usd")
            except Exception:  # noqa: BLE001 - frontera de red (precio en vivo)
                live_price = None
            entry = p.get("entry_price") or 0.0
            amount = p.get("amount_sol") or 0.0
            if live_price and entry:
                pnl_pct = (live_price / entry - 1) * 100
                pnl_sol = pnl_pct / 100 * amount
            else:
                pnl_pct = pnl_sol = None
            risk_rows.append({
                "Símbolo": p.get("symbol") or "?",
                "Entrada": f"${entry:.10f}",
                "Actual": f"${live_price:.10f}" if live_price else "n/d",
                "TP": f"${(p.get('tp_price') or 0):.10f}",
                "SL": f"${(p.get('sl_price') or 0):.10f}",
                "Trailing": "✅" if p.get("trailing_active") else "—",
                "P&L %": f"{pnl_pct:+.1f}%" if pnl_pct is not None else "n/d",
                "P&L SOL": f"{pnl_sol:+.4f}" if pnl_sol is not None else "n/d",
                "SOL usados": f"{amount:.3f} SOL",
            })
        st.dataframe(pd.DataFrame(risk_rows), use_container_width=True, hide_index=True)

    if closed:
        st.markdown("**Historial de posiciones cerradas**")
        hist = pd.DataFrame([{
            "Símbolo": p.get("symbol") or "?",
            "Entrada": f"${(p.get('entry_price') or 0):.10f}",
            "Salida": f"${(p.get('exit_price') or 0):.10f}",
            "P&L SOL": f"{(p.get('pnl_sol') or 0):+.4f}",
            "ABIERTA": (p.get("opened_at") or "")[0:10],
            "CERRADA": (p.get("closed_at") or "")[0:10],
        } for p in closed])
        st.dataframe(hist, use_container_width=True, hide_index=True)

st.divider()


# ============ DETALLE POR TOKEN ============
st.markdown('<div class="dsh-hd">Detalle de un token</div>', unsafe_allow_html=True)

symbols = df["symbol"].unique().tolist()
if symbols:
    selected = st.selectbox("Selecciona símbolo", symbols)
    token_rows = df[df["symbol"] == selected]

    if not token_rows.empty:
        latest = token_rows.iloc[0]

        st.markdown(
            _stat_row(
                [
                    _stat("Score reglas", str(latest["rule_score"])),
                    _stat("Score IA", str(latest["ai_score"]), "cy"),
                    _stat(latest["action"], str(latest["final_score"]), "ok"),
                ]
            ),
            unsafe_allow_html=True,
        )

        st.markdown('<div style="height:1.2rem"></div>', unsafe_allow_html=True)

        st.markdown("**🤖 Análisis de la IA:**")
        st.info(latest["ai_reason"] or "Sin razón proporcionada")

        st.markdown("**🔍 Filtros aplicados:**")
        details = latest["details"]
        if details:
            for d in details:
                status = d.get("status")
                if status == "missing":
                    mark = "⚠️"
                    style = ":gray[sin datos]"
                elif d.get("points", 0) > 0:
                    mark = "✅"
                    style = ":green[ok]"
                else:
                    mark = "❌"
                    style = ":red[fail]"
                st.write(
                    f"{mark} **{d.get('filter', '?')}** — "
                    f"{d.get('points', 0)} pts ({style}) — {d.get('reason', '')}"
                )
        else:
            st.write("Sin detalles disponibles")


# ============ FOOTER ============
st.divider()
st.caption(
    f"Última actualización: "
    f"{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')}"
)