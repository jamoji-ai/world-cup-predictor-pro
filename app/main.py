"""World Cup Predictor Pro — app Streamlit.

Día 3: el dashboard lee data/processed/teams_master.csv + wpi_scores.csv (Elo +
FIFA + forma + MERCADO de las 48 selecciones) y ordena por el WPI completo
(World Predictor Index). Aún NO hay probabilidades de Monte Carlo (Día 4). Si no
existe el CSV, usa datos de ejemplo.

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
WPI_CSV = ROOT / "data" / "processed" / "wpi_scores.csv"
MAPPING_CSV = ROOT / "data" / "country_name_mapping.csv"

# --- Configuración de página -------------------------------------------------
st.set_page_config(
    page_title="World Cup Predictor Pro",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=1800)
def load_master() -> pd.DataFrame | None:
    """Lee teams_master + wpi_scores y los une. None si falta teams_master."""
    if not MASTER_CSV.exists():
        return None
    try:
        df = pd.read_csv(MASTER_CSV)
    except Exception:  # noqa: BLE001
        return None
    if WPI_CSV.exists():
        wpi = pd.read_csv(WPI_CSV)[["canonical_name", "wpi", "wpi_rank"]]
        df = df.merge(wpi, on="canonical_name", how="left")
        df = df.sort_values("wpi", ascending=False).reset_index(drop=True)
    else:
        df["wpi"] = float("nan")
        df["wpi_rank"] = range(1, len(df) + 1)
    return df


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
                "📊 **Día 3** — ranking por **WPI** completo (Elo + FIFA + forma + "
                "valor de mercado, edad y ligas top-5). Las probabilidades por fase "
                "(Monte Carlo) llegan el Día 4."
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
    richest = df.sort_values("market_value_total", ascending=False).iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Favorito (WPI)", fav["canonical_name"], f"WPI {fav['wpi']:.3f}")
    c2.metric("Plantilla más cara", richest["canonical_name"],
              f"€{richest['market_value_total']/1e6:.0f}M")
    c3.metric("Mejor forma reciente", best_form["canonical_name"], f"{best_form['form_n']:.2f}")
    c4.metric("Selecciones", "48", "Mundial 2026")


def render_ranking_real(df: pd.DataFrame) -> None:
    st.subheader("Ranking por WPI")
    st.caption(
        "World Predictor Index = Elo 30% · FIFA 20% · forma 15% · valor 15% · "
        "valor medio 5% · ligas top-5 10% · edad 5%. "
        "⚠️ Aún sin probabilidades por fase (Monte Carlo, Día 4)."
    )
    table = df.copy()
    table["Pos"] = range(1, len(table) + 1)
    table["Valor (€M)"] = (table["market_value_total"] / 1e6).round(0)
    table = table.rename(
        columns={
            "canonical_name": "Selección",
            "confederation": "Conf.",
            "wpi": "WPI",
            "elo_rating": "Elo",
            "fifa_rank": "FIFA #",
            "form_n": "Forma",
            "top_player": "Jugador top",
        }
    )
    table["FIFA #"] = table["FIFA #"].astype("Int64")
    cols = ["Pos", "Selección", "Conf.", "WPI", "Elo", "FIFA #", "Valor (€M)", "Forma", "Jugador top"]
    st.dataframe(
        table[cols],
        hide_index=True,
        use_container_width=True,
        height=560,
        column_config={
            "WPI": st.column_config.ProgressColumn(
                "WPI", min_value=0.0, max_value=1.0, format="%.3f"
            ),
            "Forma": st.column_config.ProgressColumn(
                "Forma", min_value=0.0, max_value=1.0, format="%.2f"
            ),
            "Valor (€M)": st.column_config.NumberColumn("Valor (€M)", format="%d"),
        },
    )


def render_bar_real(df: pd.DataFrame) -> None:
    st.subheader("Top 12 — WPI")
    top = df.head(12)
    fig = px.bar(
        top.sort_values("wpi"),
        x="wpi",
        y="canonical_name",
        orientation="h",
        text="wpi",
        labels={"wpi": "WPI (0–1)", "canonical_name": ""},
        color="wpi",
        color_continuous_scale="Tealgrn",
    )
    fig.update_traces(texttemplate="%{text:.3f}", textposition="outside")
    fig.update_layout(coloraxis_showscale=False, margin=dict(l=10, r=30, t=10, b=10), height=460)
    st.plotly_chart(fig, use_container_width=True)


def render_scatter_real(df: pd.DataFrame) -> None:
    st.subheader("WPI vs. valor de mercado")
    st.caption(
        "Por encima de la tendencia: rinden más de lo que su valor sugiere "
        "(infravalorados). Por debajo: sobrevalorados. (Análisis completo, Día 7.)"
    )
    d = df.copy()
    d["Valor (€M)"] = d["market_value_total"] / 1e6
    fig = px.scatter(
        d, x="Valor (€M)", y="wpi", text="canonical_name", color="confederation",
        labels={"wpi": "WPI", "confederation": "Confederación"},
        log_x=True,
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
            ("data/raw/transfermarkt_squads.csv", ROOT / "data" / "raw" / "transfermarkt_squads.csv"),
            ("data/processed/teams_master.csv", MASTER_CSV),
            ("data/processed/wpi_scores.csv", WPI_CSV),
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
            "python scripts/download_transfermarkt.py\n"
            "python scripts/build_teams_master.py\n"
            "python scripts/wpi.py\n```"
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
