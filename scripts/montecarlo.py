"""montecarlo.py — Motor de simulación del Mundial (doc 03).

Simula N veces el torneo completo y estima, por selección, la probabilidad de
superar cada fase (avanzar de grupos, octavos, cuartos, semis, final, campeón).

Fidelidad de datos:
  - Grupos y calendario de la fase de grupos: REALES (reconstruidos de las
    fixtures del Mundial 2026 en data/raw/matches_history.csv).
  - Ventaja de local: REAL (campo `neutral`=False marca al anfitrión jugando en
    casa: USA, México, Canadá). Se suma HOME_GOALS_BONUS a sus goles esperados.
  - Eliminatoria (MVP): bracket por SIEMBRA (los 32 clasificados se siembran por
    posición de grupo y WPI en un cuadro estándar). NO es el cruce oficial exacto
    del sorteo — eso se incorpora en el Día 5. Para las probabilidades de
    campeón/fase es una aproximación razonable.

Vectorizado con NumPy: la fase de grupos genera todas las simulaciones de cada
partido de una vez; la eliminatoria se juega ronda a ronda sobre matrices (N, k).

Uso (módulo): from montecarlo import run_simulation; df = run_simulation(10000)
Uso (CLI):    python scripts/montecarlo.py --sims 10000
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wpi as wpi_mod  # noqa: E402  (win_probability, expected_goals)

ROOT = Path(__file__).resolve().parents[1]
WPI_CSV = ROOT / "data" / "processed" / "wpi_scores.csv"
MASTER_CSV = ROOT / "data" / "processed" / "teams_master.csv"
MATCHES_CSV = ROOT / "data" / "raw" / "matches_history.csv"
OUTPUT_PATH = ROOT / "data" / "results" / "simulation_results.csv"
META_PATH = ROOT / "data" / "results" / "sim_meta.csv"

BASE_GOALS = 1.3        # goles medios por equipo (doc 03)
HOME_GOALS_BONUS = 0.35  # plus de goles esperados al anfitrión en casa
N_GROUP_QUALIFY = 2     # 1º y 2º de cada grupo avanzan
N_BEST_THIRDS = 8       # mejores terceros (formato 48 selecciones)

# Cuadro estándar de siembra para 32 (reparte a los cabezas de serie). Números
# de siembra 1..32 en orden de cuadro; pares adyacentes se enfrentan.
BRACKET32_SEEDS = [
    1, 32, 16, 17, 8, 25, 9, 24, 4, 29, 13, 20, 5, 28, 12, 21,
    2, 31, 15, 18, 7, 26, 10, 23, 3, 30, 14, 19, 6, 27, 11, 22,
]


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [montecarlo] {msg}")


# --- Carga de estructura del torneo ------------------------------------------

def load_tournament() -> dict:
    """Carga WPI por selección y reconstruye grupos + fixtures con ventaja local."""
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

    # Grupos = componentes conexas (union-find) del grafo "se enfrentan".
    parent = {t: t for t in teams}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for _, r in wc.iterrows():
        parent[find(r["home_team"])] = find(r["away_team"])
    from collections import defaultdict
    gmap = defaultdict(list)
    for t in teams:
        gmap[find(t)].append(idx[t])
    groups = [sorted(v) for v in gmap.values()]
    groups.sort(key=lambda g: g[0])
    if len(groups) != 12 or any(len(g) != 4 for g in groups):
        raise ValueError(f"Estructura de grupos inesperada: {[len(g) for g in groups]}")

    # Fixtures de grupos: (home_idx, away_idx, home_adv, score_h, score_a).
    # score_* es None si el partido aún no se ha jugado (se simulará); si tiene
    # marcador real, se usa como DADO (recálculo en tiempo real, Día 5).
    fixtures = []
    n_played = 0
    for _, r in wc.iterrows():
        home_adv = not bool(r["neutral"])  # neutral=False -> anfitrión en casa
        sh, sa = r["home_score"], r["away_score"]
        played = pd.notna(sh) and pd.notna(sa)
        if played:
            n_played += 1
        fixtures.append((
            idx[r["home_team"]], idx[r["away_team"]], home_adv,
            int(sh) if played else None, int(sa) if played else None,
        ))

    return {
        "teams": teams, "wpi": wpi, "groups": groups, "fixtures": fixtures,
        "n_played_groups": n_played, "n_groups_matches": len(fixtures),
    }


# --- Simulación de la fase de grupos -----------------------------------------

def _standings_key(points, gf, ga):
    """Clave ordenable: puntos, luego dif. de goles, luego goles a favor."""
    return points * 1_000_000 + (gf - ga + 1000) * 1000 + gf


def simulate_groups(t: dict, n: int, rng: np.random.Generator):
    """Simula los partidos de grupos PENDIENTES; los jugados entran como dados.

    Devuelve la clave de clasificación (n, 48). Los partidos con marcador real
    aportan puntos/goles fijos (idénticos en todas las simulaciones); solo los no
    jugados se sortean con Poisson.
    """
    n_teams = len(t["teams"])
    wpi = t["wpi"]
    # Aportación fija de los partidos ya jugados (vector por selección).
    base_points = np.zeros(n_teams); base_gf = np.zeros(n_teams); base_ga = np.zeros(n_teams)
    pending = []
    for ih, ia, home_adv, sh, sa in t["fixtures"]:
        if sh is None:
            pending.append((ih, ia, home_adv))
            continue
        base_points[ih] += 3 if sh > sa else (1 if sh == sa else 0)
        base_points[ia] += 3 if sa > sh else (1 if sh == sa else 0)
        base_gf[ih] += sh; base_ga[ih] += sa
        base_gf[ia] += sa; base_ga[ia] += sh

    points = np.tile(base_points, (n, 1))
    gf = np.tile(base_gf, (n, 1))
    ga = np.tile(base_ga, (n, 1))

    for ih, ia, home_adv in pending:
        lam_h, lam_a = wpi_mod.expected_goals(wpi[ih], wpi[ia], BASE_GOALS)
        if home_adv:
            lam_h += HOME_GOALS_BONUS
        gh = rng.poisson(lam_h, n)
        gaway = rng.poisson(lam_a, n)
        points[:, ih] += np.where(gh > gaway, 3, np.where(gh == gaway, 1, 0))
        points[:, ia] += np.where(gaway > gh, 3, np.where(gh == gaway, 1, 0))
        gf[:, ih] += gh; ga[:, ih] += gaway
        gf[:, ia] += gaway; ga[:, ia] += gh

    return _standings_key(points, gf, ga)


def group_standings(t: dict, key: np.ndarray):
    """De la clave (n,48) saca 1ºs (n,12), 2ºs (n,12) y los 8 mejores 3ºs (n,8)."""
    firsts, seconds, thirds, thirds_key = [], [], [], []
    for g in t["groups"]:
        garr = np.array(g)
        sub = key[:, garr]                      # (n,4)
        order = np.argsort(-sub, axis=1)        # mejores primero
        firsts.append(garr[order[:, 0]])
        seconds.append(garr[order[:, 1]])
        thirds.append(garr[order[:, 2]])
        thirds_key.append(np.take_along_axis(sub, order[:, 2:3], axis=1)[:, 0])

    firsts = np.stack(firsts, axis=1)           # (n,12)
    seconds = np.stack(seconds, axis=1)
    thirds = np.stack(thirds, axis=1)
    thirds_key = np.stack(thirds_key, axis=1)

    best = np.argsort(-thirds_key, axis=1)[:, :N_BEST_THIRDS]   # (n,8) posiciones
    best_thirds = np.take_along_axis(thirds, best, axis=1)      # (n,8) team idx
    return firsts, seconds, best_thirds


# --- Eliminatoria (bracket por siembra) --------------------------------------

def _seed_bracket(t: dict, firsts, seconds, best_thirds, n: int):
    """Construye el cuadro de 32 sembrado: 1ºs > 2ºs > 3ºs, y por WPI dentro de cada tier."""
    qual = np.concatenate([firsts, seconds, best_thirds], axis=1)   # (n,32) team idx
    tier = np.concatenate([
        np.zeros((n, 12)), np.ones((n, 12)), np.full((n, 8), 2.0)
    ], axis=1)
    wpi_q = t["wpi"][qual]                                          # (n,32)
    seed_score = tier * 10.0 - wpi_q                               # menor = mejor siembra
    order = np.argsort(seed_score, axis=1)                        # (n,32) siembra 1..32
    seeded = np.take_along_axis(qual, order, axis=1)              # team idx por siembra
    # Colocar en el cuadro estándar.
    pos = np.array(BRACKET32_SEEDS) - 1
    bracket = seeded[:, pos]                                       # (n,32) orden de cuadro
    return qual, bracket


def _play_round(t: dict, arr: np.ndarray, rng: np.random.Generator):
    """Juega una ronda eliminatoria. arr (n, m) -> ganadores (n, m/2).

    Probabilidad de victoria = win_probability de wpi.py (escala calibrada),
    vectorizada sobre todas las simulaciones y partidos de la ronda.
    """
    a = arr[:, 0::2]; b = arr[:, 1::2]
    diff = t["wpi"][a] - t["wpi"][b]
    p_a = 1.0 / (1.0 + 10.0 ** (-diff / wpi_mod.WIN_PROB_SCALE))
    r = rng.random(a.shape)
    return np.where(r < p_a, a, b)


# --- Orquestación de una simulación completa ---------------------------------

def run_simulation(n: int = 10000, seed: int | None = None) -> pd.DataFrame:
    """Corre N simulaciones y devuelve probabilidades por fase y selección."""
    t = load_tournament()
    rng = np.random.default_rng(seed)
    n_teams = len(t["teams"])

    key = simulate_groups(t, n, rng)
    firsts, seconds, best_thirds = group_standings(t, key)
    qual, bracket = _seed_bracket(t, firsts, seconds, best_thirds, n)

    # Contadores por fase.
    counts = {k: np.zeros(n_teams) for k in
              ["qualify", "r16", "qf", "semis", "final", "champion"]}

    def tally(name, team_idx_matrix):
        np.add.at(counts[name], team_idx_matrix.ravel().astype(int), 1)

    tally("qualify", qual)               # 32 que pasan de grupos
    r16 = _play_round(t, bracket, rng)   # ganadores ronda de 32 -> octavos (16)
    tally("r16", r16)
    qf = _play_round(t, r16, rng)        # -> cuartos (8)
    tally("qf", qf)
    sf = _play_round(t, qf, rng)         # -> semis (4)
    tally("semis", sf)
    fin = _play_round(t, sf, rng)        # -> final (2)
    tally("final", fin)
    champ = _play_round(t, fin, rng)     # -> campeón (1)
    tally("champion", champ)

    # Etiqueta de grupo (A..L) por orden de reconstrucción.
    group_label = {}
    for gi, g in enumerate(t["groups"]):
        for ti in g:
            group_label[ti] = chr(ord("A") + gi)

    rows = []
    for i, team in enumerate(t["teams"]):
        rows.append({
            "canonical_name": team,
            "group": group_label[i],
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

    _log(f"Simulando {args.sims} torneos...")
    df = run_simulation(args.sims, args.seed)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    pd.DataFrame([{
        "generated": date.today().isoformat(),
        "n_sims": df.attrs["n_sims"],
        "n_played_groups": df.attrs["n_played_groups"],
        "n_groups_matches": df.attrs["n_groups_matches"],
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
