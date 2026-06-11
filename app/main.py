"""World Cup Predictor Pro — app Streamlit.

Día 2: el dashboard lee data/processed/teams_master.csv (Elo + FIFA + forma
reales de las 48 selecciones) y ordena por un ÍNDICE DEPORTIVO PROVISIONAL
(combinación de las 3 variables deportivas con los pesos del WPI, reescalados).
Aún NO es el WPI completo (falta el componente de mercado, Día 3) ni hay
probabilidades de Monte Carlo (Día 4). Si no existe el CSV, usa datos de ejemplo.

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
MASTER_CSV = ROOT / "data" / "processed" / "teams_master.csv"
MAPPING_CSV = ROOT / "data" / "country_name_mapping.csv"

# Pesos DEPORTIVOS del WPI (doc 03), reescalados a 1.0 para el índice provisional.
W_ELO, W_FIFA, W_FORM = 0.30, 0.20, 0.15
_W_SUM = W_ELO + W_FIFA + W_FORM

# --- Configuración de página -------------------------------------------------
st.set_page_config(
    page_title="World Cup Predictor Pro",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=1800)
def load_master() -> pd.DataFrame | None:
    """Lee teams_master.csv y añade el índice deportivo provisional. None si no existe."""
    if not MASTER_CSV.exists():
        return None
    try:
        df = pd.read_csv(MASTER_CSV)
    except Exception:  # noqa: BLE001
        return None
    df["sport_index"] = (
        W_ELO * df["elo_n"] + W_FIFA * df["fifa_n"] + W_FORM * df["form_n"]
    ) / _W_SUM
    return df.sort_values("sport_index", ascending=False).reset_index(drop=True)


def render_sidebar(using_real: bool) -> None:
    with st.sidebar:
        st.markdown("## 🏆 WC Predictor Pro")
        st.caption("Probabilidades del Mundial en tiempo real")
        st.divider()
        st.radio(
            "Navegación",
            ["🏠 Dashboard", "🔎 Selección", "🗂️ Bracket", "🎮 Simulador", "⚡ Upset Detector"],
            index=0,
            help="Día 2: solo el Dashboard está activo. El resto llega días 5–7.",
        )
        st.divider()
        if using_real:
            st.caption(
                "📊 **Día 2** — ranking con datos REALES (Elo + FIFA + forma de los "
                "últimos 20 partidos). Orden = índice deportivo provisional. "
                "El WPI completo (con mercado) llega el Día 3; las probabilidades "
                "Monte Carlo, el Día 4."
            )
        else:
            st.caption("⚠️ Datos de ejemplo (aún no se ha generado teams_master.csv).")


# --- Render con DATOS REALES (Día 2) ----------------------------------------

def render_hero_real(df: pd.DataFrame) -> None:
    st.title("World Cup Predictor Pro")
    st.markdown(
        "#### Probabilidades del Mundial 2026 en tiempo real, con un índice propio "
        "(WPI) y simulación Monte Carlo."
    )
    fav = df.iloc[0]
    best_form = df.sort_values("form_n", ascending=False).iloc[0]
    top_elo = df.sort_values("elo_rating", ascending=False).iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Favorito (índice deportivo)", fav["canonical_name"], f"{fav['sport_index']:.2f}")
    c2.metric("Mejor Elo", top_elo["canonical_name"], f"{int(top_elo['elo_rating'])}")
    c3.metric("Mejor forma reciente", best_form["canonical_name"], f"{best_form['form_n']:.2f}")
    c4.metric("Selecciones", "48", "Mundial 2026")


def render_ranking_real(df: pd.DataFrame) -> None:
    st.subheader("Ranking deportivo provisional")
    st.caption(
        "Orden por índice deportivo (Elo 30% · FIFA 20% · forma 15%, reescalado). "
        "⚠️ Provisional: sin el componente de mercado del WPI ni probabilidades Monte Carlo."
    )
    table = df.copy()
    table["Pos"] = range(1, len(table) + 1)
    table = table.rename(
        columns={
            "canonical_name": "Selección",
            "confederation": "Conf.",
            "elo_rating": "Elo",
            "fifa_rank": "FIFA #",
            "form_n": "Forma",
            "sport_index": "Índice dep.",
        }
    )
    table["FIFA #"] = table["FIFA #"].astype("Int64")
    cols = ["Pos", "Selección", "Conf.", "Elo", "FIFA #", "Forma", "Índice dep."]
    st.dataframe(
        table[cols],
        hide_index=True,
        use_container_width=True,
        height=560,
        column_config={
            "Índice dep.": st.column_config.ProgressColumn(
                "Índice dep.", min_value=0.0, max_value=1.0, format="%.2f"
            ),
            "Forma": st.column_config.ProgressColumn(
                "Forma", min_value=0.0, max_value=1.0, format="%.2f"
            ),
        },
    )


def render_bar_real(df: pd.DataFrame) -> None:
    st.subheader("Top 12 — índice deportivo provisional")
    top = df.head(12)
    fig = px.bar(
        top.sort_values("sport_index"),
        x="sport_index",
        y="canonical_name",
        orientation="h",
        text="sport_index",
        labels={"sport_index": "Índice deportivo (0–1)", "canonical_name": ""},
        color="sport_index",
        color_continuous_scale="Tealgrn",
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(coloraxis_showscale=False, margin=dict(l=10, r=30, t=10, b=10), height=460)
    st.plotly_chart(fig, use_container_width=True)


def render_scatter_real(df: pd.DataFrame) -> None:
    st.subheader("Elo vs. forma reciente")
    st.caption("Selecciones arriba-derecha: fuertes históricamente y en buen momento.")
    fig = px.scatter(
        df, x="form_n", y="elo_rating", text="canonical_name", color="confederation",
        labels={"form_n": "Forma (0–1)", "elo_rating": "Elo", "confederation": "Confederación"},
    )
    fig.update_traces(textposition="top center", textfont_size=9, marker_size=10)
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=520, legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)


# --- Render con DATOS DE EJEMPLO (fallback Día 1) ---------------------------

def render_sample(ranking: pd.DataFrame) -> None:
    st.title("World Cup Predictor Pro")
    st.warning("Mostrando datos de ejemplo. Genera los datos reales con los scripts de ETL.")
    fav = ranking.iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Favorito (ejemplo)", f"{fav['flag']} {fav['team']}", f"{fav['prob_campeon']:.1f}%")
    c2.metric("Selecciones", "48", "Mundial 2026")
    c3.metric("Estado", "Día 1", "placeholder")
    st.dataframe(ranking, hide_index=True, use_container_width=True)


def render_pipeline_status(df: pd.DataFrame | None) -> None:
    with st.expander("🔧 Estado del pipeline de datos", expanded=False):
        steps = [
            ("data/raw/elo_ratings.csv", ROOT / "data" / "raw" / "elo_ratings.csv"),
            ("data/raw/fifa_ranking.csv", ROOT / "data" / "raw" / "fifa_ranking.csv"),
            ("data/raw/matches_history.csv", ROOT / "data" / "raw" / "matches_history.csv"),
            ("data/processed/teams_master.csv", MASTER_CSV),
        ]
        for label, path in steps:
            if path.exists():
                st.success(f"✓ {label}")
            else:
                st.warning(f"✗ {label} — no generado")
        st.caption(
            "Regenerar datos:\n\n"
            "```bash\npython scripts/download_elo.py\n"
            "python scripts/download_fifa_ranking.py\n"
            "python scripts/download_matches_history.py\n"
            "python scripts/build_teams_master.py\n```"
        )
        if df is not None:
            st.caption("teams_master.csv (primeras filas):")
            st.dataframe(df.head(8), hide_index=True, use_container_width=True)


def main() -> None:
    df = load_master()
    render_sidebar(using_real=df is not None)

    if df is not None:
        render_hero_real(df)
        st.divider()
        col_a, col_b = st.columns([3, 2])
        with col_a:
            render_ranking_real(df)
        with col_b:
            render_bar_real(df)
        st.divider()
        render_scatter_real(df)
    else:
        render_sample(get_sample_ranking())

    st.divider()
    render_pipeline_status(df)


if __name__ == "__main__":
    main()
