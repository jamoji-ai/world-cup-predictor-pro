"""World Cup Predictor Pro — app Streamlit.

Día 4 (MVP): el dashboard muestra las PROBABILIDADES reales de la simulación
Monte Carlo (data/results/simulation_results.csv), en lenguaje llano para
cualquier aficionado (sin jerga ni siglas). El detalle técnico (cómo se calcula)
vive en una sección aparte "Cómo funciona".

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
SIM_CSV = ROOT / "data" / "results" / "simulation_results.csv"
META_CSV = ROOT / "data" / "results" / "sim_meta.csv"
MASTER_CSV = ROOT / "data" / "processed" / "teams_master.csv"

st.set_page_config(
    page_title="World Cup Predictor Pro",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=1800)
def load_data() -> pd.DataFrame | None:
    """Une probabilidades de la simulación con datos de equipo. None si falta la sim."""
    if not SIM_CSV.exists():
        return None
    try:
        sim = pd.read_csv(SIM_CSV)
    except Exception:  # noqa: BLE001
        return None
    if MASTER_CSV.exists():
        extra = pd.read_csv(MASTER_CSV)[
            ["canonical_name", "confederation", "top_player", "market_value_total"]
        ]
        sim = sim.merge(extra, on="canonical_name", how="left")
    # "Fuerza del equipo" 0-100 a partir del WPI (0-1), para lectura humana.
    sim["fuerza"] = (sim["wpi"] * 100).round().astype(int)
    return sim


@st.cache_data(ttl=1800)
def load_meta() -> dict | None:
    if not META_CSV.exists():
        return None
    try:
        return pd.read_csv(META_CSV).iloc[0].to_dict()
    except Exception:  # noqa: BLE001
        return None


def render_live_status(meta: dict | None) -> None:
    if not meta:
        return
    played = int(meta["n_played_groups"]); total = int(meta["n_groups_matches"])
    sims = int(meta["n_sims"])
    if played == 0:
        msg = (f"🔵 **Antes del inicio** — aún no se ha jugado ningún partido "
               f"(0 de {total} de la fase de grupos). Probabilidades de partida.")
    elif played < total:
        msg = (f"🟢 **Mundial en marcha** — {played} de {total} partidos de grupos "
               f"jugados. Las probabilidades ya incluyen esos resultados reales.")
    else:
        msg = "🟢 **Fase de grupos completada** — quedan las eliminatorias."
    st.info(f"{msg}  ·  _{sims:,} simulaciones_".replace(",", "."))


def pct(x: float) -> str:
    """Formatea probabilidad 0-1 como porcentaje legible."""
    v = x * 100
    if v >= 10:
        return f"{v:.0f}%"
    if v >= 1:
        return f"{v:.1f}%"
    return "<1%" if v > 0 else "0%"


# --- Sidebar -----------------------------------------------------------------

def render_sidebar(using_real: bool) -> None:
    with st.sidebar:
        st.markdown("## 🏆 WC Predictor Pro")
        st.caption("Quién ganará el Mundial 2026, según los datos")
        st.divider()
        st.radio(
            "Secciones",
            ["🏠 Favoritos", "🔎 Selección", "🗂️ Cuadro", "🎮 Simulador", "⚡ Sorpresas"],
            index=0,
            help="Día 4: la sección de Favoritos ya usa datos reales. El resto llega días 5–7.",
        )
        st.divider()
        if using_real:
            st.caption(
                "Las cifras salen de **simular el Mundial 50.000 veces** con datos "
                "reales de cada selección. Mira **Cómo funciona** abajo del todo."
            )
        else:
            st.caption("⚠️ Datos de ejemplo (aún no se ha generado la simulación).")


# --- Pantalla principal: Favoritos ------------------------------------------

def render_hero(df: pd.DataFrame) -> None:
    st.title("¿Quién ganará el Mundial 2026?")
    st.markdown(
        "#### Hemos simulado el torneo **50.000 veces** con los datos reales de las "
        "48 selecciones. Esto es lo que pasa de media."
    )
    fav = df.iloc[0]
    dark_horse = df[df["prob_campeon"] < 0.05].sort_values("prob_campeon", ascending=False).iloc[0]
    surprise_group = df.sort_values("prob_avanza_grupos").iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Máximo favorito",
        f"{fav['canonical_name']}",
        f"Gana {pct(fav['prob_campeon'])} de las veces",
    )
    c2.metric(
        "La sorpresa con más opciones",
        f"{dark_horse['canonical_name']}",
        f"Gana {pct(dark_horse['prob_campeon'])} de las veces",
    )
    c3.metric(
        "Lo tiene más difícil para pasar de fase",
        f"{surprise_group['canonical_name']}",
        f"Supera la fase de grupos {pct(surprise_group['prob_avanza_grupos'])}",
    )


def render_ranking(df: pd.DataFrame) -> None:
    st.subheader("Probabilidad de ganar el Mundial — las 48 selecciones")
    st.caption(
        "Cada porcentaje es cuántas veces, de cada 100 Mundiales simulados, esa "
        "selección acaba campeona o llega a esa fase. **Fuerza del equipo** (0–100) "
        "resume su nivel: mezcla resultados, ranking FIFA, forma, valor de la "
        "plantilla y experiencia en Mundiales."
    )
    table = df.copy()
    table["Pos"] = range(1, len(table) + 1)
    table["Grupo"] = table["group"]
    for col, src in [
        ("Gana el Mundial", "prob_campeon"),
        ("Llega a la final", "prob_final"),
        ("Llega a semifinales", "prob_semis"),
        ("Supera la fase de grupos", "prob_avanza_grupos"),
    ]:
        table[col] = (table[src] * 100)
    table = table.rename(columns={"canonical_name": "Selección", "fuerza": "Fuerza del equipo"})
    cols = ["Pos", "Selección", "Grupo", "Gana el Mundial", "Llega a la final",
            "Llega a semifinales", "Supera la fase de grupos", "Fuerza del equipo"]
    st.dataframe(
        table[cols],
        hide_index=True,
        use_container_width=True,
        height=560,
        column_config={
            "Gana el Mundial": st.column_config.NumberColumn("Gana el Mundial", format="%.1f%%"),
            "Llega a la final": st.column_config.NumberColumn("Llega a la final", format="%.0f%%"),
            "Llega a semifinales": st.column_config.NumberColumn("Llega a semifinales", format="%.0f%%"),
            "Supera la fase de grupos": st.column_config.NumberColumn(
                "Supera la fase de grupos", format="%.0f%%"),
            "Fuerza del equipo": st.column_config.ProgressColumn(
                "Fuerza del equipo", min_value=0, max_value=100, format="%d"),
        },
    )


def render_bar(df: pd.DataFrame) -> None:
    st.subheader("Los 12 grandes favoritos")
    st.caption("Probabilidad de levantar la copa.")
    top = df.head(12).copy()
    top["p"] = top["prob_campeon"] * 100
    fig = px.bar(
        top.sort_values("p"), x="p", y="canonical_name", orientation="h", text="p",
        labels={"p": "Probabilidad de ser campeón (%)", "canonical_name": ""},
        color="p", color_continuous_scale="Tealgrn",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(coloraxis_showscale=False, margin=dict(l=10, r=40, t=10, b=10), height=460)
    st.plotly_chart(fig, use_container_width=True)


def render_journey(df: pd.DataFrame) -> None:
    st.subheader("¿Hasta dónde llega cada favorito?")
    st.caption("De cada 100 Mundiales, cuántas veces alcanza cada ronda (8 mejores).")
    top = df.head(8)
    stages = [
        ("Fase de grupos", "prob_avanza_grupos"),
        ("Octavos", "prob_octavos"),
        ("Cuartos", "prob_cuartos"),
        ("Semifinales", "prob_semis"),
        ("Final", "prob_final"),
        ("Campeón", "prob_campeon"),
    ]
    rows = []
    for _, r in top.iterrows():
        for label, src in stages:
            rows.append({"Selección": r["canonical_name"], "Ronda": label, "%": r[src] * 100})
    long = pd.DataFrame(rows)
    order = [s[0] for s in stages]
    fig = px.line(
        long, x="Ronda", y="%", color="Selección", markers=True,
        category_orders={"Ronda": order},
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=460,
                      yaxis_title="Veces que llega (%)", legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)


# --- "Cómo funciona" (técnico, separado de las cifras del usuario) ----------

def render_how_it_works() -> None:
    with st.expander("ℹ️ Cómo funciona el modelo (metodología)", expanded=False):
        st.markdown(
            """
**En una frase:** medimos la fuerza de cada selección con un índice propio y
luego jugamos el Mundial 50.000 veces en el ordenador para ver cuántas veces
gana cada una.

**1. La "fuerza del equipo"** combina 8 ingredientes (entre paréntesis, cuánto pesa):
- Resultados históricos / ranking Elo (24%)
- Ranking FIFA oficial (19%)
- Forma reciente — últimos 20 partidos (17%)
- Valor de mercado de la plantilla (13%)
- Si tiene grandes estrellas (valor medio por jugador, 5%)
- Jugadores en las 5 grandes ligas europeas (10%)
- Edad ideal de la plantilla, ~26-27 años (5%)
- Experiencia en Mundiales anteriores (7%)

**2. La simulación** juega los 72 partidos reales de la fase de grupos (con
ventaja para los anfitriones USA, México y Canadá cuando juegan en casa) y
después la eliminatoria, 50.000 veces. La probabilidad de "ganar el Mundial" es
simplemente cuántas de esas 50.000 veces acaba campeona.

*Los pesos son una elección razonada y transparente, no una fórmula mágica.
La eliminatoria del MVP usa un cuadro por nivel; el cruce oficial exacto del
sorteo se incorpora en una próxima versión.*
            """
        )


# --- Fallback datos de ejemplo ----------------------------------------------

def render_sample(ranking: pd.DataFrame) -> None:
    st.title("¿Quién ganará el Mundial 2026?")
    st.warning("Mostrando datos de ejemplo. Genera la simulación con los scripts de ETL + Monte Carlo.")
    st.dataframe(ranking, hide_index=True, use_container_width=True)


def render_pipeline_status(df: pd.DataFrame | None) -> None:
    with st.expander("🔧 Estado del pipeline de datos (técnico)", expanded=False):
        steps = [
            ("Elo (eloratings.net)", ROOT / "data" / "raw" / "elo_ratings.csv"),
            ("Ranking FIFA", ROOT / "data" / "raw" / "fifa_ranking.csv"),
            ("Histórico de partidos", ROOT / "data" / "raw" / "matches_history.csv"),
            ("Valores Transfermarkt", ROOT / "data" / "raw" / "transfermarkt_squads.csv"),
            ("Tabla maestra", MASTER_CSV),
            ("Simulación Monte Carlo", SIM_CSV),
        ]
        for label, path in steps:
            (st.success if path.exists() else st.warning)(
                f"{'✓' if path.exists() else '✗'} {label}")
        st.caption("Regenerar todo:\n\n```bash\npython scripts/update_all.py\n```")


def main() -> None:
    df = load_data()
    render_sidebar(using_real=df is not None)
    if df is None:
        render_sample(get_sample_ranking())
        st.divider()
        render_pipeline_status(df)
        return

    render_hero(df)
    render_live_status(load_meta())
    st.divider()
    col_a, col_b = st.columns([3, 2])
    with col_a:
        render_ranking(df)
    with col_b:
        render_bar(df)
    st.divider()
    render_journey(df)
    st.divider()
    render_how_it_works()
    render_pipeline_status(df)


if __name__ == "__main__":
    main()
