"""World Cup Predictor Pro — app Streamlit.

Día 1: esqueleto visual del dashboard. Usa datos de ejemplo (app/sample_data.py)
y, si existe data/raw/elo_ratings.csv (generado por scripts/download_elo.py),
muestra además el Elo real para validar que el pipeline arranca.

Ejecutar localmente:
    streamlit run app/main.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from sample_data import get_sample_ranking

# --- Rutas -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
ELO_CSV = ROOT / "data" / "raw" / "elo_ratings.csv"
MAPPING_CSV = ROOT / "data" / "country_name_mapping.csv"

# --- Configuración de página -------------------------------------------------
st.set_page_config(
    page_title="World Cup Predictor Pro",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=3600)
def load_real_elo() -> pd.DataFrame | None:
    """Lee el Elo real si download_elo.py ya generó el CSV. None si no existe."""
    if not ELO_CSV.exists():
        return None
    try:
        return pd.read_csv(ELO_CSV)
    except Exception:  # noqa: BLE001 - el dato real es opcional en el Día 1
        return None


@st.cache_data(ttl=3600)
def load_wc_teams() -> pd.DataFrame | None:
    if not MAPPING_CSV.exists():
        return None
    try:
        return pd.read_csv(MAPPING_CSV)
    except Exception:  # noqa: BLE001
        return None


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## 🏆 WC Predictor Pro")
        st.caption("Probabilidades del Mundial en tiempo real")
        st.divider()
        st.radio(
            "Navegación",
            [
                "🏠 Dashboard",
                "🔎 Selección",
                "🗂️ Bracket",
                "🎮 Simulador",
                "⚡ Upset Detector",
            ],
            index=0,
            help="Día 1: solo el Dashboard está activo. El resto llega días 5–7.",
        )
        st.divider()
        st.caption(
            "⚠️ Día 1 — datos de ejemplo. El ranking se basará en datos reales "
            "(Elo + FIFA + mercado) y simulación Monte Carlo a partir del Día 4."
        )


def render_hero(ranking: pd.DataFrame) -> None:
    st.title("World Cup Predictor Pro")
    st.markdown(
        "#### Probabilidades del Mundial en tiempo real, con un índice propio (WPI) "
        "y simulación Monte Carlo."
    )

    fav = ranking.iloc[0]
    biggest_upset = ranking.sort_values("elo").iloc[0]  # placeholder simple
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Favorito actual", f"{fav['flag']} {fav['team']}", f"{fav['prob_campeon']:.1f}% campeón")
    c2.metric("Selecciones", "48", "Mundial 2026")
    c3.metric("Simulaciones / día", "50.000", "Monte Carlo")
    c4.metric("Tapado a vigilar", f"{biggest_upset['flag']} {biggest_upset['team']}", "outsider")


def render_ranking(ranking: pd.DataFrame) -> None:
    st.subheader("Ranking de campeones")
    st.caption("Probabilidad estimada de ganar el Mundial (datos de ejemplo en el Día 1).")

    table = ranking.copy()
    table["Selección"] = table["flag"] + " " + table["team"]
    table["Tendencia"] = table["trend_icon"]
    table = table.rename(
        columns={
            "confederation": "Conf.",
            "wpi": "WPI",
            "elo": "Elo",
            "prob_campeon": "% Campeón",
            "prob_semis": "% Semis",
        }
    )
    cols = ["Selección", "Conf.", "WPI", "Elo", "% Campeón", "% Semis", "Tendencia"]
    st.dataframe(
        table[cols],
        hide_index=True,
        use_container_width=True,
        column_config={
            "WPI": st.column_config.ProgressColumn(
                "WPI", min_value=0.0, max_value=1.0, format="%.2f"
            ),
            "% Campeón": st.column_config.NumberColumn("% Campeón", format="%.1f%%"),
            "% Semis": st.column_config.NumberColumn("% Semis", format="%.1f%%"),
        },
    )


def render_bar_chart(ranking: pd.DataFrame) -> None:
    st.subheader("Top 10 — probabilidad de campeón")
    top = ranking.head(10).copy()
    top["label"] = top["flag"] + " " + top["team"]
    fig = px.bar(
        top.sort_values("prob_campeon"),
        x="prob_campeon",
        y="label",
        orientation="h",
        text="prob_campeon",
        labels={"prob_campeon": "% Campeón", "label": ""},
        color="prob_campeon",
        color_continuous_scale="Tealgrn",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        coloraxis_showscale=False,
        margin=dict(l=10, r=30, t=10, b=10),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_data_status(elo: pd.DataFrame | None, wc: pd.DataFrame | None) -> None:
    with st.expander("🔧 Estado del pipeline de datos (debug Día 1)", expanded=False):
        if wc is not None:
            st.success(f"country_name_mapping.csv cargado · {len(wc)} selecciones del Mundial.")
        else:
            st.warning("country_name_mapping.csv no encontrado.")

        if elo is not None:
            st.success(f"data/raw/elo_ratings.csv cargado · {len(elo)} selecciones con Elo real.")
            st.caption("Top 10 por Elo real (eloratings.net):")
            st.dataframe(elo.head(10), hide_index=True, use_container_width=True)
        else:
            st.info(
                "Aún no hay Elo real. Genera el CSV con:\n\n"
                "```bash\npython scripts/download_elo.py\n```"
            )


def main() -> None:
    render_sidebar()
    ranking = get_sample_ranking()
    elo = load_real_elo()
    wc = load_wc_teams()

    render_hero(ranking)
    st.divider()
    render_ranking(ranking)
    st.divider()
    render_bar_chart(ranking)
    st.divider()
    render_data_status(elo, wc)


if __name__ == "__main__":
    main()
