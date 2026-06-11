"""wc_engine.py — Motor de simulación del Mundial (doc 03).

Simula N veces el torneo completo y estima, por selección, la probabilidad de
superar cada fase (avanzar de grupos, octavos, cuartos, semis, final, campeón).

Fidelidad de datos:
  - Grupos y calendario de la fase de grupos: REALES (reconstruidos de las
    fixtures del Mundial 2026 en data/raw/matches_history.csv).
  - Resultados ya jugados: se usan como DADOS (recálculo en tiempo real); solo
    se simulan los partidos pendientes.
  - Ventaja de local: REAL (campo `neutral`=False marca al anfitrión jugando en
    casa: USA, México, Canadá). Se suma HOME_GOALS_BONUS a sus goles esperados.
  - Eliminatoria: CUADRO OFICIAL del Mundial 2026 (Round of 32 -> final). Los
    cruces de 1º/2º son fijos por reglamento; los 8 mejores terceros se asignan a
    sus slots respetando los conjuntos de grupos permitidos por FIFA (matching
    precomputado por combinación, ver _build_thirds_assignment_table).

Vectorizado con NumPy: la fase de grupos genera todas las simulaciones de cada
partido de una vez; la eliminatoria se juega ronda a ronda sobre matrices (N, k).

Uso (módulo): from wc_engine import run_simulation; df = run_simulation(10000)
Uso (CLI):    python scripts/wc_engine.py --sims 10000
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wpi as wpi_mod  # noqa: E402  (win_probability, expected_goals)

# Re-exportadas para uso desde la app (mc.win_probability / mc.expected_goals).
win_probability = wpi_mod.win_probability
expected_goals = wpi_mod.expected_goals

ROOT = Path(__file__).resolve().parents[1]
WPI_CSV = ROOT / "data" / "processed" / "wpi_scores.csv"
MASTER_CSV = ROOT / "data" / "processed" / "teams_master.csv"
MATCHES_CSV = ROOT / "data" / "raw" / "matches_history.csv"
OUTPUT_PATH = ROOT / "data" / "results" / "simulation_results.csv"
META_PATH = ROOT / "data" / "results" / "sim_meta.csv"

BASE_GOALS = 1.3         # goles medios por equipo (doc 03)
HOME_GOALS_BONUS = 0.35  # plus de goles esperados al anfitrión en casa
N_BEST_THIRDS = 8        # mejores terceros (formato 48 selecciones)

# Composición oficial de los 12 grupos del Mundial 2026 (nombres = canonical_name
# de country_name_mapping.csv). Verificado contra el sorteo del 5-dic-2025.
OFFICIAL_GROUPS = {
    "A": {"Czech Republic", "Mexico", "South Africa", "South Korea"},
    "B": {"Bosnia and Herzegovina", "Canada", "Qatar", "Switzerland"},
    "C": {"Brazil", "Haiti", "Morocco", "Scotland"},
    "D": {"Australia", "Paraguay", "Turkey", "United States"},
    "E": {"Curaçao", "Ecuador", "Germany", "Ivory Coast"},
    "F": {"Japan", "Netherlands", "Sweden", "Tunisia"},
    "G": {"Belgium", "Egypt", "Iran", "New Zealand"},
    "H": {"Cape Verde", "Saudi Arabia", "Spain", "Uruguay"},
    "I": {"France", "Iraq", "Norway", "Senegal"},
    "J": {"Algeria", "Argentina", "Austria", "Jordan"},
    "K": {"Colombia", "DR Congo", "Portugal", "Uzbekistan"},
    "L": {"Croatia", "England", "Ghana", "Panama"},
}
LETTERS = list("ABCDEFGHIJKL")
L2I = {ltr: i for i, ltr in enumerate(LETTERS)}

# Cuadro oficial del Round of 32 (match 73-88). Cada entrada describe los dos
# participantes: ("W"/"R", letra) = ganador/segundo de ese grupo; ("3", slot) =
# mejor tercero asignado a ese slot.
R32 = {
    73: (("R", "A"), ("R", "B")),
    74: (("W", "E"), ("3", 74)),
    75: (("W", "F"), ("R", "C")),
    76: (("W", "C"), ("R", "F")),
    77: (("W", "I"), ("3", 77)),
    78: (("R", "E"), ("R", "I")),
    79: (("W", "A"), ("3", 79)),
    80: (("W", "L"), ("3", 80)),
    81: (("W", "D"), ("3", 81)),
    82: (("W", "G"), ("3", 82)),
    83: (("R", "K"), ("R", "L")),
    84: (("W", "H"), ("R", "J")),
    85: (("W", "B"), ("3", 85)),
    86: (("W", "J"), ("R", "H")),
    87: (("W", "K"), ("3", 87)),
    88: (("R", "D"), ("R", "G")),
}
# Conjuntos de grupos permitidos para cada slot de tercero (reglamento FIFA 2026).
THIRD_SLOT_ALLOWED = {
    74: "ABCDF", 77: "CDFGH", 79: "CEFHI", 80: "EHIJK",
    81: "BEFIJ", 82: "AEHIJ", 85: "EFGIJ", 87: "DEIJL",
}
THIRD_SLOTS = [74, 77, 79, 80, 81, 82, 85, 87]
# Árbol del resto de rondas: match -> (match_origen_1, match_origen_2).
R16 = {89: (74, 77), 90: (73, 75), 91: (76, 78), 92: (79, 80),
       93: (83, 84), 94: (81, 82), 95: (86, 88), 96: (85, 87)}
QF = {97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (95, 96)}
SF = {101: (97, 98), 102: (99, 100)}
FINAL = {104: (101, 102)}


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [wc_engine] {msg}")


# --- Tabla de asignación de terceros (precomputada) --------------------------

def _build_thirds_assignment_table() -> np.ndarray:
    """Para cada combinación de 8 grupos que aportan tercero, asigna cada slot a
    un grupo respetando THIRD_SLOT_ALLOWED (matching). Devuelve un array
    (4096, 8) indexado por bitmask de 12 bits: para cada slot de THIRD_SLOTS, el
    índice de grupo asignado (o -1 si la combinación no es válida)."""
    allowed_idx = [set(L2I[c] for c in THIRD_SLOT_ALLOWED[s]) for s in THIRD_SLOTS]
    table = np.full((1 << 12, 8), -1, dtype=np.int16)

    def match(groups: list[int]):
        """Backtracking: asigna slots (en orden) a grupos de `groups`."""
        assign = [-1] * 8
        used = set()

        def bt(slot: int) -> bool:
            if slot == 8:
                return True
            for g in groups:
                if g not in used and g in allowed_idx[slot]:
                    assign[slot] = g; used.add(g)
                    if bt(slot + 1):
                        return True
                    used.discard(g); assign[slot] = -1
            return False

        return assign if bt(0) else None

    valid = 0
    for combo in combinations(range(12), 8):
        sol = match(list(combo))
        if sol is not None:
            mask = sum(1 << g for g in combo)
            table[mask] = sol
            valid += 1
    if valid != 495:
        raise RuntimeError(f"Tabla de terceros incompleta: {valid}/495 combinaciones válidas.")
    return table


THIRDS_TABLE = _build_thirds_assignment_table()


# --- Carga de estructura del torneo ------------------------------------------

def load_tournament() -> dict:
    """Carga WPI por selección y reconstruye grupos (con letra oficial) + fixtures."""
    wpi_df = pd.read_csv(WPI_CSV)[["canonical_name", "wpi"]]
    matches = pd.read_csv(MATCHES_CSV)
    wc = matches[(matches["tournament"] == "FIFA World Cup") & (matches["date"] >= "2026-01-01")].copy()

    teams = sorted(set(wc["home_team"]) | set(wc["away_team"]))
    idx = {t: i for i, t in enumerate(teams)}
    wpi_map = dict(zip(wpi_df["canonical_name"], wpi_df["wpi"]))
    missing = [t for t in teams if t not in wpi_map]
    if missing:
        raise ValueError(f"Selecciones sin WPI: {missing}")
    wpi = np.array([wpi_map[t] for t in teams], dtype=float)

    # Asignar cada selección a su grupo oficial por composición.
    team_letter = {}
    for ltr, members in OFFICIAL_GROUPS.items():
        for t in members:
            if t in idx:
                team_letter[t] = ltr
    unknown = [t for t in teams if t not in team_letter]
    if unknown:
        raise ValueError(f"Selecciones sin grupo oficial (revisar OFFICIAL_GROUPS): {unknown}")
    # groups_by_letter[i] = lista de team_idx del grupo LETTERS[i].
    groups_by_letter = [[] for _ in LETTERS]
    for t in teams:
        groups_by_letter[L2I[team_letter[t]]].append(idx[t])
    if any(len(g) != 4 for g in groups_by_letter):
        raise ValueError(f"Grupos mal formados: {[len(g) for g in groups_by_letter]}")

    # Fixtures de grupos: (home_idx, away_idx, home_adv, score_h, score_a).
    fixtures = []
    n_played = 0
    for _, r in wc.iterrows():
        home_adv = not bool(r["neutral"])
        sh, sa = r["home_score"], r["away_score"]
        played = pd.notna(sh) and pd.notna(sa)
        n_played += int(played)
        fixtures.append((idx[r["home_team"]], idx[r["away_team"]], home_adv,
                         int(sh) if played else None, int(sa) if played else None))

    return {
        "teams": teams, "wpi": wpi, "groups": groups_by_letter, "team_letter": team_letter,
        "fixtures": fixtures, "n_played_groups": n_played, "n_groups_matches": len(fixtures),
    }


# --- Simulación de la fase de grupos -----------------------------------------

def match_outcome_probs(wpi_a: float, wpi_b: float, home_adv_a: bool = False,
                        max_goals: int = 9) -> tuple[float, float, float]:
    """Probabilidad (gana A, empate, gana B) de un partido, modelo Poisson (doc 03).

    Suma analítica sobre marcadores 0..max_goals. home_adv_a añade el plus de
    local a A. Útil para el detector de sorpresas y la vista de partido.
    """
    from math import exp, factorial
    lam_a, lam_b = wpi_mod.expected_goals(wpi_a, wpi_b, BASE_GOALS)
    if home_adv_a:
        lam_a += HOME_GOALS_BONUS

    def pmf(lam, k):
        return exp(-lam) * lam ** k / factorial(k)

    p_a = [pmf(lam_a, k) for k in range(max_goals + 1)]
    p_b = [pmf(lam_b, k) for k in range(max_goals + 1)]
    pa = pd_ = pb = 0.0
    for ga in range(max_goals + 1):
        for gb in range(max_goals + 1):
            p = p_a[ga] * p_b[gb]
            if ga > gb:
                pa += p
            elif ga == gb:
                pd_ += p
            else:
                pb += p
    return float(pa), float(pd_), float(pb)


def _standings_key(points, gf, ga):
    """Clave ordenable: puntos, luego dif. de goles, luego goles a favor."""
    return points * 1_000_000 + (gf - ga + 1000) * 1000 + gf


def simulate_groups(t: dict, n: int, rng: np.random.Generator):
    """Simula los partidos de grupos PENDIENTES; los jugados entran como dados."""
    n_teams = len(t["teams"]); wpi = t["wpi"]
    base_points = np.zeros(n_teams); base_gf = np.zeros(n_teams); base_ga = np.zeros(n_teams)
    pending = []
    for ih, ia, home_adv, sh, sa in t["fixtures"]:
        if sh is None:
            pending.append((ih, ia, home_adv)); continue
        base_points[ih] += 3 if sh > sa else (1 if sh == sa else 0)
        base_points[ia] += 3 if sa > sh else (1 if sh == sa else 0)
        base_gf[ih] += sh; base_ga[ih] += sa; base_gf[ia] += sa; base_ga[ia] += sh

    points = np.tile(base_points, (n, 1)); gf = np.tile(base_gf, (n, 1)); ga = np.tile(base_ga, (n, 1))
    for ih, ia, home_adv in pending:
        lam_h, lam_a = wpi_mod.expected_goals(wpi[ih], wpi[ia], BASE_GOALS)
        if home_adv:
            lam_h += HOME_GOALS_BONUS
        gh = rng.poisson(lam_h, n); gaway = rng.poisson(lam_a, n)
        points[:, ih] += np.where(gh > gaway, 3, np.where(gh == gaway, 1, 0))
        points[:, ia] += np.where(gaway > gh, 3, np.where(gh == gaway, 1, 0))
        gf[:, ih] += gh; ga[:, ih] += gaway; gf[:, ia] += gaway; ga[:, ia] += gh

    return _standings_key(points, gf, ga)


def group_standings(t: dict, key: np.ndarray):
    """Devuelve winners, runners, thirds (n,12 en orden A..L) y la clave de los 3ºs."""
    n = key.shape[0]
    winners = np.zeros((n, 12), dtype=int); runners = np.zeros((n, 12), dtype=int)
    thirds = np.zeros((n, 12), dtype=int); thirds_key = np.zeros((n, 12))
    for li, g in enumerate(t["groups"]):
        garr = np.array(g)
        sub = key[:, garr]
        order = np.argsort(-sub, axis=1)
        winners[:, li] = garr[order[:, 0]]
        runners[:, li] = garr[order[:, 1]]
        thirds[:, li] = garr[order[:, 2]]
        thirds_key[:, li] = np.take_along_axis(sub, order[:, 2:3], axis=1)[:, 0]
    return winners, runners, thirds, thirds_key


# --- Eliminatoria con cuadro oficial -----------------------------------------

def _play(t: dict, a: np.ndarray, b: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Partido eliminatorio vectorizado (a,b son team_idx (n,)) -> ganador (n,)."""
    diff = t["wpi"][a] - t["wpi"][b]
    p_a = 1.0 / (1.0 + 10.0 ** (-diff / wpi_mod.WIN_PROB_SCALE))
    return np.where(rng.random(a.shape) < p_a, a, b)


def _knockout(t, winners, runners, thirds, thirds_key, n, rng):
    """Juega R32->final con el cuadro oficial. Devuelve dict fase->team_idx (n,k)."""
    # 8 mejores terceros: posiciones (grupos) seleccionadas y su asignación a slots.
    best_pos = np.argsort(-thirds_key, axis=1)[:, :N_BEST_THIRDS]      # (n,8) índices de grupo
    best_thirds_team = np.take_along_axis(thirds, best_pos, axis=1)     # (n,8) team_idx
    mask = np.zeros(n, dtype=np.int32)
    for j in range(N_BEST_THIRDS):
        mask |= (1 << best_pos[:, j]).astype(np.int32)
    slot_groups = THIRDS_TABLE[mask]                                    # (n,8) grupo por slot
    # team del tercero asignado a cada slot.
    rows = np.arange(n)
    slot_team = {slot: thirds[rows, slot_groups[:, k]] for k, slot in enumerate(THIRD_SLOTS)}

    def participant(spec):
        kind, ref = spec
        if kind == "W":
            return winners[:, L2I[ref]]
        if kind == "R":
            return runners[:, L2I[ref]]
        return slot_team[ref]  # "3"

    win = {}
    for m, (pa, pb) in R32.items():
        win[m] = _play(t, participant(pa), participant(pb), rng)
    for tree in (R16, QF, SF, FINAL):
        for m, (x, y) in tree.items():
            win[m] = _play(t, win[x], win[y], rng)

    return {
        "qualify": np.concatenate([winners, runners, best_thirds_team], axis=1),  # (n,32)
        "r16": np.stack([win[m] for m in R32], axis=1),       # ganadores de R32 -> octavos
        "qf": np.stack([win[m] for m in R16], axis=1),        # ganadores octavos -> cuartos
        "semis": np.stack([win[m] for m in QF], axis=1),      # -> semis
        "final": np.stack([win[m] for m in SF], axis=1),      # -> final
        "champion": win[104][:, None],                        # campeón
    }


# --- Probabilidades por grupo (para "rellena tu cuadro") ---------------------

def group_position_probs(n: int = 20000, seed: int | None = None) -> dict:
    """Distribución de posiciones finales por grupo, simulando la fase de grupos.

    Para cada grupo (A..L) devuelve:
      - teams: las 4 selecciones del grupo, en orden fijo.
      - pair:   array (16,) con P(1º=i, 2º=j) indexado por i*4+j (i,j = índice en teams).
      - triple: array (64,) con P(1º=i, 2º=j, 3º=k) indexado por i*16+j*4+k.
    Permite calcular la probabilidad de un pronóstico de grupos sin depender de la
    simulación global (donde una combinación exacta es demasiado rara).
    """
    t = load_tournament()
    rng = np.random.default_rng(seed)
    key = simulate_groups(t, n, rng)  # (n, 48)
    out = {}
    for li, g in enumerate(t["groups"]):
        garr = np.array(g)
        sub = key[:, garr]                       # (n, 4)
        order = np.argsort(-sub, axis=1)         # posiciones (0=1º) -> índice en garr
        first, second, third = order[:, 0], order[:, 1], order[:, 2]
        pair = np.bincount(first * 4 + second, minlength=16) / n
        triple = np.bincount(first * 16 + second * 4 + third, minlength=64) / n
        out[LETTERS[li]] = {
            "teams": [t["teams"][i] for i in garr],
            "pair": pair, "triple": triple,
        }
    return out


# --- Orquestación de una simulación completa ---------------------------------

def apply_hypothetical(t: dict, extra_results) -> dict:
    """Fija marcadores hipotéticos en la fase de grupos (simulador manual, Día 6).

    extra_results: iterable de (equipo_a, equipo_b, goles_a, goles_b). Se localiza
    el partido entre esos dos equipos y se fija su marcador respetando quién es
    local/visitante en el calendario. No altera n_played_groups (es un "¿y si...?").
    """
    if not extra_results:
        return t
    idx = {name: i for i, name in enumerate(t["teams"])}
    fixed = {}
    for a, b, ga, gb in extra_results:
        if a not in idx or b not in idx:
            continue
        fixed[frozenset((idx[a], idx[b]))] = (idx[a], int(ga), int(gb))
    new_fixtures = []
    for ih, ia, home_adv, sh, sa in t["fixtures"]:
        key = frozenset((ih, ia))
        if key in fixed:
            ref_team, ref_ga, ref_gb = fixed[key]
            if ih == ref_team:
                sh, sa = ref_ga, ref_gb
            else:
                sh, sa = ref_gb, ref_ga
        new_fixtures.append((ih, ia, home_adv, sh, sa))
    t = dict(t)
    t["fixtures"] = new_fixtures
    return t


def run_simulation(n: int = 10000, seed: int | None = None, extra_results=None) -> pd.DataFrame:
    """Corre N simulaciones y devuelve probabilidades por fase y selección.

    extra_results: marcadores hipotéticos a fijar antes de simular (ver
    apply_hypothetical) — usado por el simulador manual.
    """
    t = load_tournament()
    t = apply_hypothetical(t, extra_results)
    rng = np.random.default_rng(seed)
    n_teams = len(t["teams"])

    key = simulate_groups(t, n, rng)
    winners, runners, thirds, thirds_key = group_standings(t, key)
    reached = _knockout(t, winners, runners, thirds, thirds_key, n, rng)

    counts = {k: np.zeros(n_teams) for k in reached}
    for stage, mat in reached.items():
        np.add.at(counts[stage], mat.ravel().astype(int), 1)

    rows = []
    for i, team in enumerate(t["teams"]):
        rows.append({
            "canonical_name": team,
            "group": t["team_letter"][team],
            "wpi": round(float(t["wpi"][i]), 4),
            "prob_avanza_grupos": counts["qualify"][i] / n,
            "prob_octavos": counts["r16"][i] / n,
            "prob_cuartos": counts["qf"][i] / n,
            "prob_semis": counts["semis"][i] / n,
            "prob_final": counts["final"][i] / n,
            "prob_campeon": counts["champion"][i] / n,
        })
    df = pd.DataFrame(rows).sort_values("prob_campeon", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    df.attrs["n_played_groups"] = t["n_played_groups"]
    df.attrs["n_groups_matches"] = t["n_groups_matches"]
    df.attrs["n_sims"] = n
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="Motor Monte Carlo del Mundial.")
    parser.add_argument("--sims", type=int, default=10000, help="Nº de simulaciones (def. 10000).")
    parser.add_argument("--seed", type=int, default=None, help="Semilla para reproducibilidad.")
    args = parser.parse_args()

    if not WPI_CSV.exists():
        _log(f"ERROR: falta {WPI_CSV}. Ejecuta build_teams_master.py y wpi.py antes.")
        return 1

    _log(f"Simulando {args.sims} torneos (cuadro oficial)...")
    df = run_simulation(args.sims, args.seed)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    pd.DataFrame([{
        "generated": date.today().isoformat(), "n_sims": df.attrs["n_sims"],
        "n_played_groups": df.attrs["n_played_groups"], "n_groups_matches": df.attrs["n_groups_matches"],
    }]).to_csv(META_PATH, index=False, encoding="utf-8")
    _log(f"Guardado en {OUTPUT_PATH}")
    _log("Top 12 candidatos al título:")
    for _, r in df.head(12).iterrows():
        print(f"    {int(r['rank']):>2}. {r['canonical_name']:<20} (Gr.{r['group']})  "
              f"campeón {r['prob_campeon']*100:5.1f}%  | semis {r['prob_semis']*100:5.1f}%  "
              f"| pasa grupos {r['prob_avanza_grupos']*100:5.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
