"""World Cup Predictor Pro — app Streamlit.

Día 4 (MVP): el dashboard muestra las PROBABILIDADES reales de la simulación
Monte Carlo (data/results/simulation_results.csv), en lenguaje llano para
cualquier aficionado (sin jerga ni siglas). El detalle técnico (cómo se calcula)
vive en una sección aparte "Cómo funciona".

Ejecutar localmente:
    streamlit run app/main.py
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from sample_data import get_sample_ranking

# --- Rutas -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
SIM_CSV = ROOT / "data" / "results" / "simulation_results.csv"
META_CSV = ROOT / "data" / "results" / "sim_meta.csv"
HISTORY_CSV = ROOT / "data" / "results" / "history_log.csv"
MASTER_CSV = ROOT / "data" / "processed" / "teams_master.csv"

SCENARIO_SIMS = 6000   # simulaciones para escenarios interactivos (ligero para Cloud free)
SCENARIO_SEED = 7      # semilla fija: aísla el efecto del resultado fijado

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
        extra = pd.read_csv(MASTER_CSV)[[
            "canonical_name", "confederation", "top_player", "top_player_value",
            "market_value_total", "avg_age", "form_matches", "form_points", "form_max",
            "elo_n", "fifa_n", "form_n", "value_n", "value_avg_n", "top5_n", "age_n", "wc_exp_n",
        ]]
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

def render_sidebar(using_real: bool) -> str:
    with st.sidebar:
        st.markdown("## 🏆 WC Predictor Pro")
        st.caption("Quién ganará el Mundial 2026, según los datos")
        st.divider()
        section = st.radio(
            "Secciones",
            ["🏠 Favoritos", "🔎 Selección", "🗂️ Cuadro", "🎮 Simulador", "⚡ Sorpresas"],
            index=0,
            help="Favoritos, Selección y Cuadro ya funcionan. Simulador y Sorpresas: Día 6.",
        )
        st.divider()
        if using_real:
            st.caption(
                "Las cifras salen de **simular el Mundial 50.000 veces** con datos "
                "reales de cada selección. Mira **Cómo funciona** abajo del todo."
            )
        else:
            st.caption("⚠️ Datos de ejemplo (aún no se ha generado la simulación).")
    return section


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


# --- Vista de selección ------------------------------------------------------

RADAR_LABELS = [
    ("elo_n", "Nivel histórico"),
    ("fifa_n", "Ranking FIFA"),
    ("form_n", "Forma reciente"),
    ("value_n", "Valor de la plantilla"),
    ("value_avg_n", "Calidad de estrellas"),
    ("top5_n", "Juegan en grandes ligas"),
    ("age_n", "Edad ideal"),
    ("wc_exp_n", "Experiencia mundialista"),
]


def render_team_view(df: pd.DataFrame) -> None:
    st.title("Ficha de selección")
    names = df.sort_values("canonical_name")["canonical_name"].tolist()
    # Deep-link: ?seleccion=España preselecciona ese equipo (enlaces compartibles).
    preselect = st.query_params.get("seleccion")
    default_idx = names.index(preselect) if preselect in names else \
        names.index(df.iloc[0]["canonical_name"])
    team = st.selectbox("Elige una selección", names, index=default_idx)
    if st.query_params.get("seleccion") != team:
        st.query_params["seleccion"] = team
    row = df[df["canonical_name"] == team].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fuerza del equipo", f"{int(row['fuerza'])}/100", f"Grupo {row['group']}")
    c2.metric("Gana el Mundial", pct(row["prob_campeon"]))
    c3.metric("Plantilla", f"€{row['market_value_total']/1e6:.0f}M"
              if pd.notna(row["market_value_total"]) else "—")
    c4.metric("Jugador estrella", row["top_player"] if pd.notna(row["top_player"]) else "—",
              f"€{row['top_player_value']/1e6:.0f}M" if pd.notna(row.get("top_player_value")) else None)

    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.subheader("Perfil del equipo")
        st.caption("Cada eje va de 0 a 100. Cuanto más grande el área, más completo el equipo.")
        vals = [float(row[k]) * 100 for k, _ in RADAR_LABELS]
        labels = [lbl for _, lbl in RADAR_LABELS]
        fig = px.line_polar(
            r=vals + [vals[0]], theta=labels + [labels[0]], line_close=True,
        )
        fig.update_traces(fill="toself")
        fig.update_layout(margin=dict(l=40, r=40, t=20, b=20), height=420,
                          polar=dict(radialaxis=dict(range=[0, 100], showticklabels=False)))
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        st.subheader("¿Hasta dónde llega?")
        st.caption("De cada 100 Mundiales simulados, cuántas veces alcanza cada ronda.")
        stages = [("Supera la fase de grupos", "prob_avanza_grupos"), ("Octavos", "prob_octavos"),
                  ("Cuartos", "prob_cuartos"), ("Semifinales", "prob_semis"),
                  ("Final", "prob_final"), ("Campeón", "prob_campeon")]
        bars = pd.DataFrame({"Ronda": [s[0] for s in stages],
                             "%": [row[s[1]] * 100 for s in stages]})
        fig2 = px.bar(bars, x="%", y="Ronda", orientation="h", text="%",
                      category_orders={"Ronda": [s[0] for s in stages][::-1]})
        fig2.update_traces(texttemplate="%{text:.0f}%", textposition="outside",
                           marker_color="#1f9e89")
        fig2.update_layout(margin=dict(l=10, r=30, t=10, b=10), height=420,
                           xaxis_range=[0, 100], xaxis_title="", yaxis_title="")
        st.plotly_chart(fig2, use_container_width=True)

    render_share(
        f"{team} tiene un {pct(row['prob_campeon'])} de ganar el Mundial 2026 "
        f"según el modelo WPI de World Cup Predictor Pro.", key=f"share_{team}")


# --- Cuadro (bracket más probable) ------------------------------------------

@st.cache_data(ttl=1800)
def predicted_bracket(df: pd.DataFrame):
    """Cuadro más probable: dentro de cada grupo ganan los de mayor fuerza, y en
    cada cruce avanza el favorito. Usa el cuadro OFICIAL del Mundial 2026."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import wc_engine as mc

    wpi = dict(zip(df["canonical_name"], df["wpi"]))
    grp = {ltr: sorted([t for t in members], key=lambda t: -wpi.get(t, 0))
           for ltr, members in mc.OFFICIAL_GROUPS.items()}
    winners = {l: grp[l][0] for l in mc.LETTERS}
    runners = {l: grp[l][1] for l in mc.LETTERS}
    thirds = {l: grp[l][2] for l in mc.LETTERS}
    best = sorted(mc.LETTERS, key=lambda l: -wpi[thirds[l]])[:8]
    mask = sum(1 << mc.L2I[l] for l in best)
    slot_groups = mc.THIRDS_TABLE[mask]
    slot_team = {slot: thirds[mc.LETTERS[slot_groups[k]]] for k, slot in enumerate(mc.THIRD_SLOTS)}

    def part(spec):
        kind, ref = spec
        return winners[ref] if kind == "W" else runners[ref] if kind == "R" else slot_team[ref]

    matches, win = {}, {}
    for m, (a, b) in mc.R32.items():
        ta, tb = part(a), part(b)
        matches[m] = (ta, tb); win[m] = ta if wpi[ta] >= wpi[tb] else tb
    for tree in (mc.R16, mc.QF, mc.SF, mc.FINAL):
        for m, (x, y) in tree.items():
            ta, tb = win[x], win[y]
            matches[m] = (ta, tb); win[m] = ta if wpi[ta] >= wpi[tb] else tb
    return matches, win


def render_bracket(df: pd.DataFrame) -> None:
    st.title("El cuadro más probable")
    meta = load_meta()
    if meta and int(meta["n_played_groups"]) == 0:
        st.caption(
            "Aún no se ha jugado ningún partido, así que este es el cuadro **más "
            "probable** hoy: en cada grupo pasan los dos equipos más fuertes y en "
            "cada cruce gana el favorito. Se irá concretando con los resultados reales."
        )
    else:
        st.caption("Cuadro más probable según la fuerza de cada equipo y el sorteo oficial.")
    matches, win = predicted_bracket(df)

    champ = win[104]
    fin = matches[104]
    st.success(f"🏆 Campeón más probable: **{champ}**  ·  Final: {fin[0]} vs {fin[1]}")
    st.caption("Los equipos en **verde** son los que avanzan. En móvil, desliza el cuadro "
               "en horizontal.")
    render_bracket_boxes(matches, win)


# Orden de los partidos por columna siguiendo el árbol real (para que cada cruce
# quede alineado con el de la ronda siguiente que alimenta).
_BRACKET_COLUMNS = [
    ("Dieciseisavos", [74, 77, 73, 75, 83, 84, 81, 82, 76, 78, 79, 80, 86, 88, 85, 87]),
    ("Octavos", [89, 90, 93, 94, 91, 92, 95, 96]),
    ("Cuartos", [97, 98, 99, 100]),
    ("Semifinales", [101, 102]),
    ("Final", [104]),
]


def render_bracket_boxes(matches: dict, win: dict) -> None:
    """Dibuja el cuadro con cajitas de enfrentamiento (HTML/CSS en un iframe)."""
    import streamlit.components.v1 as components

    css = """
    <style>
      .wrap { overflow-x:auto; padding:4px 2px 12px; }
      .bracket { display:flex; gap:16px; width:max-content;
                 font-family:'Source Sans Pro',system-ui,sans-serif; }
      .round { display:flex; flex-direction:column; justify-content:space-around;
               min-width:150px; }
      .round h4 { margin:0 0 8px; font-size:0.8rem; color:#6b7280;
                  text-transform:uppercase; letter-spacing:.04em; text-align:center; }
      .match { border:1px solid #e1e4e8; border-radius:8px; overflow:hidden;
               margin:5px 0; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.04); }
      .team { padding:6px 10px; font-size:0.82rem; color:#374151;
              border-bottom:1px solid #f0f1f3; white-space:nowrap; }
      .team:last-child { border-bottom:none; }
      .team.win { font-weight:700; color:#0b6b57; background:#e6f5ef; }
      .round.champ { justify-content:center; }
      .round.champ .match { border-color:#0b6b57; }
      .round.champ .team { font-size:0.9rem; }
    </style>
    """
    parts = ["<div class='wrap'><div class='bracket'>"]
    for title, ms in _BRACKET_COLUMNS:
        parts.append(f"<div class='round'><h4>{title}</h4>")
        for m in ms:
            a, b = matches[m]; w = win[m]
            parts.append(
                f"<div class='match'>"
                f"<div class='team {'win' if w == a else ''}'>{a}</div>"
                f"<div class='team {'win' if w == b else ''}'>{b}</div>"
                f"</div>"
            )
        parts.append("</div>")
    # Columna del campeón.
    parts.append(
        f"<div class='round champ'><h4>Campeón</h4>"
        f"<div class='match'><div class='team win'>🏆 {win[104]}</div></div></div>"
    )
    parts.append("</div></div>")
    components.html(css + "".join(parts), height=1220, scrolling=True)


# --- Helpers de simulación (Día 6) ------------------------------------------

def _mc():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import wc_engine as mc
    return mc


@st.cache_data(ttl=1800)
def get_fixtures() -> list[dict]:
    """Lista de partidos de la fase de grupos (nombres, grupo, local, marcador)."""
    mc = _mc()
    t = mc.load_tournament()
    teams, tl = t["teams"], t["team_letter"]
    out = []
    for ih, ia, home_adv, sh, sa in t["fixtures"]:
        out.append({"home": teams[ih], "away": teams[ia], "group": tl[teams[ih]],
                    "home_adv": home_adv, "played": sh is not None})
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def simulate_scenario(extra_key: tuple, n: int = SCENARIO_SIMS, seed: int = SCENARIO_SEED) -> pd.DataFrame:
    """Simulación con resultados hipotéticos fijados (cacheada por escenario)."""
    mc = _mc()
    df = mc.run_simulation(n, seed=seed, extra_results=list(extra_key) or None)
    return df.set_index("canonical_name")


@st.cache_data(ttl=1800)
def wpi_map() -> dict:
    return dict(zip(load_data()["canonical_name"], load_data()["wpi"]))


# --- Simulador (🎮): ¿qué necesita? + simulador libre -----------------------

def render_simulator(df: pd.DataFrame) -> None:
    st.title("Juega tú con el Mundial")
    tab1, tab2 = st.tabs(["🎯 ¿Qué necesita mi selección?", "🎮 Simulador libre"])
    with tab1:
        _render_what_if(df)
    with tab2:
        _render_free_sim(df)


def _render_what_if(df: pd.DataFrame) -> None:
    st.caption("Elige una selección y un partido de su grupo. Te enseñamos cómo "
               "cambian sus opciones de ganar el Mundial si gana, empata o pierde.")
    fixtures = get_fixtures()
    teams = sorted(df["canonical_name"].tolist())
    team = st.selectbox("Selección", teams, key="whatif_team")
    # Solo partidos que quedan por jugar: los ya jugados son resultado fijo.
    its = [f for f in fixtures if team in (f["home"], f["away"]) and not f["played"]]
    labels = [f"vs {f['away'] if f['home'] == team else f['home']} (Grupo {f['group']})" for f in its]
    if not its:
        st.info(f"{team} ya ha jugado todos sus partidos de la fase de grupos. "
                "Prueba el simulador libre o mira el cuadro de eliminatorias.")
        return
    pick = st.selectbox("Partido", range(len(its)), format_func=lambda i: labels[i], key="whatif_match")
    f = its[pick]
    rival = f["away"] if f["home"] == team else f["home"]

    base = simulate_scenario(())
    scenarios = [("Gana", 2, 0), ("Empata", 1, 1), ("Pierde", 0, 2)]
    st.markdown(f"### {team} — {rival}")
    cols = st.columns(3)
    base_champ = base.loc[team, "prob_campeon"]
    for col, (name, gf, ga) in zip(cols, scenarios):
        res = simulate_scenario(((team, rival, gf, ga),))
        champ = res.loc[team, "prob_campeon"]
        adv = res.loc[team, "prob_avanza_grupos"]
        delta = (champ - base_champ) * 100
        with col:
            st.markdown(f"**Si {name.lower()} ({gf}-{ga})**")
            st.metric("Gana el Mundial", pct(champ),
                      f"{delta:+.1f} puntos" if abs(delta) >= 0.05 else "≈ igual")
            st.caption(f"Pasa de grupos: {pct(adv)}")
    st.caption(f"Referencia actual de {team}: gana el Mundial {pct(base_champ)} · "
               f"pasa de grupos {pct(base.loc[team, 'prob_avanza_grupos'])}.")


def _render_free_sim(df: pd.DataFrame) -> None:
    st.caption("Fija los resultados que quieras de los partidos que aún no se han "
               "jugado y mira cómo cambia todo. Útil para tus propios '¿y si...?'.")
    # Solo partidos pendientes: los ya jugados ya están fijados en la simulación.
    fixtures = [f for f in get_fixtures() if not f["played"]]
    if "fixed" not in st.session_state:
        st.session_state.fixed = []
    if not fixtures:
        st.info("Ya se ha jugado toda la fase de grupos. El cuadro de eliminatorias "
                "muestra lo que queda.")
        return

    labels = [f"{f['home']} vs {f['away']} (Grupo {f['group']})" for f in fixtures]
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    mi = c1.selectbox("Partido", range(len(fixtures)), format_func=lambda i: labels[i], key="free_match")
    gh = c2.number_input(fixtures[mi]["home"], 0, 15, 1, key="free_gh")
    ga = c3.number_input(fixtures[mi]["away"], 0, 15, 0, key="free_ga")
    if c4.button("➕ Añadir", use_container_width=True):
        f = fixtures[mi]
        st.session_state.fixed = [x for x in st.session_state.fixed
                                  if {x[0], x[1]} != {f["home"], f["away"]}]
        st.session_state.fixed.append((f["home"], f["away"], int(gh), int(ga)))

    if st.session_state.fixed:
        st.markdown("**Resultados fijados:**")
        for a, b, x, y in st.session_state.fixed:
            st.markdown(f"- {a} {x}–{y} {b}")
        if st.button("🔄 Reiniciar"):
            st.session_state.fixed = []
            st.rerun()

        base = simulate_scenario(())
        res = simulate_scenario(tuple(st.session_state.fixed))
        comp = pd.DataFrame({
            "Selección": res.index,
            "Antes": (base["prob_campeon"] * 100).reindex(res.index).values,
            "Ahora": (res["prob_campeon"] * 100).values,
        })
        comp["Cambio"] = comp["Ahora"] - comp["Antes"]
        comp = comp.reindex(comp["Cambio"].abs().sort_values(ascending=False).index).head(12)
        st.markdown("**Quién más cambia (probabilidad de ganar el Mundial):**")
        st.dataframe(
            comp, hide_index=True, use_container_width=True,
            column_config={
                "Antes": st.column_config.NumberColumn("Antes", format="%.1f%%"),
                "Ahora": st.column_config.NumberColumn("Ahora", format="%.1f%%"),
                "Cambio": st.column_config.NumberColumn("Cambio", format="%+.1f pp"),
            },
        )
    else:
        st.info("Añade al menos un resultado para ver el efecto.")


# --- Detector de sorpresas (⚡) ---------------------------------------------

def render_upsets(df: pd.DataFrame) -> None:
    st.title("Detector de sorpresas")
    st.caption("Los partidos de la próxima jornada donde el equipo más débil (según "
               "su fuerza) tiene más opciones de dar la campanada.")
    mc = _mc()
    w = wpi_map()
    fixtures = [f for f in get_fixtures() if not f["played"]]
    rows = []
    for f in fixtures:
        home, away = f["home"], f["away"]
        pa, pdraw, pb = mc.match_outcome_probs(w[home], w[away], home_adv_a=f["home_adv"])
        # "Sorpresa" = gana el de menor fuerza.
        if w[home] <= w[away]:
            underdog, fav, p_up = home, away, pa
        else:
            underdog, fav, p_up = away, home, pb
        rows.append({"underdog": underdog, "fav": fav, "p": p_up, "group": f["group"]})
    top = sorted(rows, key=lambda r: -r["p"])[:8]
    if not top:
        st.info("No hay partidos pendientes ahora mismo.")
        return
    for r in top:
        st.markdown(
            f"**{r['underdog']}** puede ganar a **{r['fav']}**  ·  "
            f"`{r['p']*100:.0f}%`  _(Grupo {r['group']})_"
        )
        st.progress(float(min(1.0, max(0.0, r["p"]))))


# --- "Cómo funciona" (técnico, separado de las cifras del usuario) ----------

def render_evolution(df: pd.DataFrame) -> None:
    if not HISTORY_CSV.exists():
        return
    try:
        hist = pd.read_csv(HISTORY_CSV)
    except Exception:  # noqa: BLE001
        return
    dates = sorted(hist["date"].unique())
    st.subheader("Cómo evoluciona la probabilidad de ganar el Mundial")
    if len(dates) < 2:
        st.caption("📅 Aún solo hay una foto de hoy. En cuanto pasen los días (y los "
                   "partidos), aquí verás cómo sube y baja cada favorito.")
        return
    top_teams = df.head(6)["canonical_name"].tolist()
    h = hist[hist["canonical_name"].isin(top_teams)].copy()
    h["%"] = h["prob_campeon"] * 100
    fig = px.line(h, x="date", y="%", color="canonical_name", markers=True,
                  labels={"date": "", "canonical_name": ""})
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=380,
                      yaxis_title="Gana el Mundial (%)", legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)


def render_value_analysis(df: pd.DataFrame) -> None:
    st.subheader("¿Quién rinde más (o menos) de lo que cuesta?")
    st.caption("Comparamos la fuerza del equipo con el valor de su plantilla. Por "
               "encima de la línea rinden más de lo que su valor sugiere; por debajo, "
               "menos.")
    d = df.dropna(subset=["market_value_total"]).copy()
    if d.empty:
        return
    d["valor_m"] = d["market_value_total"] / 1e6
    d["logv"] = np.log10(d["valor_m"])
    # Recta de tendencia fuerza ~ log(valor); el residuo marca infra/sobrevalorado.
    coef = np.polyfit(d["logv"], d["wpi"], 1)
    d["esperado"] = np.polyval(coef, d["logv"])
    d["residuo"] = d["wpi"] - d["esperado"]

    fig = px.scatter(
        d, x="valor_m", y="wpi", text="canonical_name", log_x=True,
        color="residuo", color_continuous_scale="RdYlGn",
        labels={"valor_m": "Valor de la plantilla (millones €)", "wpi": "Fuerza del equipo"},
    )
    xs = np.linspace(d["logv"].min(), d["logv"].max(), 50)
    fig.add_scatter(x=10 ** xs, y=np.polyval(coef, xs), mode="lines",
                    line=dict(dash="dash", color="#888"), name="Tendencia", showlegend=False)
    fig.update_traces(textposition="top center", textfont_size=8, selector=dict(mode="markers+text"))
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=480, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    best = d.sort_values("residuo", ascending=False).head(3)
    worst = d.sort_values("residuo").head(3)
    c1.markdown("**💚 Rinden por encima de su valor**")
    for _, r in best.iterrows():
        c1.markdown(f"- {r['canonical_name']} · €{r['valor_m']:.0f}M")
    c2.markdown("**🔴 Rinden por debajo de su valor**")
    for _, r in worst.iterrows():
        c2.markdown(f"- {r['canonical_name']} · €{r['valor_m']:.0f}M")


def render_share(text: str, key: str) -> None:
    """Bloque de compartir: texto listo + botón a X. La URL a compartir es la del
    navegador (las vistas usan query params para enlazar a una selección)."""
    with st.expander("📣 Compartir este dato"):
        st.code(text, language=None)
        url = "https://twitter.com/intent/tweet?text=" + urllib.parse.quote(text)
        st.link_button("Compartir en X (Twitter)", url)
        st.caption("Para enlazar a esta vista, copia la URL de tu navegador.")


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
después la eliminatoria con el **cuadro oficial del Mundial 2026** (cruces
reales del sorteo, incluida la colocación de los 8 mejores terceros), 50.000
veces. La probabilidad de "ganar el Mundial" es cuántas de esas 50.000 veces
acaba campeona. **Los partidos ya jugados cuentan como resultado real**: solo se
simula lo que queda por jugar.

*Los pesos son una elección razonada y transparente, no una fórmula mágica.*
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


def _safe(fn, df) -> None:
    """Ejecuta una pantalla y, si falla, muestra el error sin romper la app."""
    try:
        fn(df)
    except Exception as err:  # noqa: BLE001
        import traceback
        st.error(f"Ups, esta sección ha fallado: {type(err).__name__}: {err}")
        with st.expander("Detalle técnico"):
            st.code("".join(traceback.format_exc()))


def main() -> None:
    df = load_data()
    section = render_sidebar(using_real=df is not None)
    if df is None:
        render_sample(get_sample_ranking())
        st.divider()
        render_pipeline_status(df)
        return

    if section.startswith("🔎"):
        render_team_view(df)
    elif section.startswith("🗂️"):
        render_bracket(df)
    elif section.startswith("🎮"):
        _safe(render_simulator, df)
    elif section.startswith("⚡"):
        _safe(render_upsets, df)
    else:  # Favoritos
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
        render_value_analysis(df)
        st.divider()
        render_evolution(df)
        fav = df.iloc[0]
        render_share(
            f"El favorito al Mundial 2026 es {fav['canonical_name']} con un "
            f"{pct(fav['prob_campeon'])} de ganarlo, según el modelo WPI de "
            f"World Cup Predictor Pro.", key="share_fav")

    st.divider()
    render_how_it_works()
    render_pipeline_status(df)


if __name__ == "__main__":
    main()
