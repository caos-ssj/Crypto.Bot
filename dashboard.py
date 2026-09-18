"""Dashboard web con Streamlit para el bot."""

import json
from datetime import datetime
import pandas as pd
import streamlit as st

from src.storage import get_recent_analyses, get_stats, init_db


# ============ CONFIG ============
st.set_page_config(
    page_title="Crypto Bot Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()


# ============ HEADER ============
st.markdown("""
    <h1 style='text-align: center; color: #00d4ff; margin-bottom: 0;'>
        🤖 CRYPTO BOT
    </h1>
    <p style='text-align: center; color: #888; margin-top: 0;'>
        Dashboard de análisis de memecoins en Solana
    </p>
""", unsafe_allow_html=True)

st.divider()


# ============ SIDEBAR ============
with st.sidebar:
    st.header("⚙️ Configuración")
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

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("📊 Total analizados", stats["total"])
with col2:
    st.metric("🟢 COMPRA", stats["compra"], delta_color="normal")
with col3:
    st.metric("🟡 OBSERVAR", stats["observar"])
with col4:
    st.metric("🔴 EVITAR", stats["evitar"])
with col5:
    st.metric("💸 Ejecutadas", stats["executed"])

st.divider()


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
st.subheader("📈 Evolución de Scores")

chart_df = df[["timestamp", "rule_score", "ai_score", "final_score"]].copy()
chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"])
chart_df = chart_df.sort_values("timestamp").set_index("timestamp")

st.line_chart(
    chart_df,
    color=["#888888", "#00d4ff", "#00ff88"],
    height=250,
)

st.divider()


# ============ TABLA PRINCIPAL ============
st.subheader(f"📋 Análisis recientes ({len(df)})")

display_df = df[[
    "timestamp", "symbol", "price_usd", "market_cap",
    "liquidity_usd", "rule_score", "ai_score", "final_score", "action"
]].copy()

display_df["timestamp"] = pd.to_datetime(display_df["timestamp"]).dt.strftime("%H:%M:%S")
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


# ============ DETALLE POR TOKEN ============
st.subheader("🔍 Detalle de un token")

symbols = df["symbol"].unique().tolist()
if symbols:
    selected = st.selectbox("Selecciona símbolo", symbols)
    token_rows = df[df["symbol"] == selected]
    
    if not token_rows.empty:
        latest = token_rows.iloc[0]
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Score reglas", latest["rule_score"])
        with c2:
            st.metric("Score IA", latest["ai_score"])
        with c3:
            action_color = {"COMPRA": "🟢", "OBSERVAR": "🟡", "EVITAR": "🔴"}
            st.metric(
                f"{action_color.get(latest['action'], '')} {latest['action']}",
                latest["final_score"],
            )
        
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
st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")