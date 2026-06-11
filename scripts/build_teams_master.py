"""build_teams_master.py — Fase de transformación del ETL (doc 02).

Une las fuentes crudas (Elo, FIFA, partidos) sobre las 48 selecciones del
Mundial (data/country_name_mapping.csv) y calcula la "forma reciente", dejando
un único processed/teams_master.csv con las variables DEPORTIVAS, en crudo y
normalizadas 0-1 sobre el conjunto de participantes.

Día 2: solo variables deportivas (Elo, FIFA, forma). Las de mercado
(Transfermarkt) y el WPI completo se añaden en el Día 3.

--- Forma reciente (ajuste sobre doc 03) ---
El doc 03 fijaba "últimos 10 partidos, puntos/30". Se AMPLÍA la ventana
(--form-window, por defecto 20) porque muchas selecciones disputan amistosos
pre-Mundial con alineaciones B que, con solo 10 partidos, falsean la forma.
Normalización: puntos / (3 * nº_partidos_usados), siempre en 0-1.
Opcional: --friendly-weight (<1.0) pondera menos los amistosos.

Uso:
    python scripts/build_teams_master.py [--form-window 20] [--friendly-weight 1.0]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MAPPING_CSV = ROOT / "data" / "country_name_mapping.csv"
ELO_CSV = ROOT / "data" / "raw" / "elo_ratings.csv"
FIFA_CSV = ROOT / "data" / "raw" / "fifa_ranking.csv"
MATCHES_CSV = ROOT / "data" / "raw" / "matches_history.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "teams_master.csv"

DEFAULT_FORM_WINDOW = 20
DEFAULT_FRIENDLY_WEIGHT = 0.5  # amistosos pesan la mitad (alineaciones B pre-Mundial)


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [build_master] {msg}")


def _minmax(s: pd.Series) -> pd.Series:
    """Normalización min-max 0-1 sobre las participantes. Constante -> 0.5."""
    lo, hi = s.min(), s.max()
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(0.5, index=s.index)
    return (s - lo) / (hi - lo)


# --- Forma reciente ----------------------------------------------------------

def compute_form(
    matches: pd.DataFrame,
    teams: list[str],
    window: int,
    friendly_weight: float,
) -> pd.DataFrame:
    """Puntos ponderados de los últimos `window` partidos JUGADOS por selección.

    Devuelve DataFrame con: canonical_name, form_points, form_max, form_matches.
    `form_points` y `form_max` ya incluyen la ponderación de amistosos, de modo
    que form_n = form_points / form_max queda en 0-1.
    """
    m = matches.copy()
    m = m[m["home_score"].notna() & m["away_score"].notna()]
    m["date"] = pd.to_datetime(m["date"], errors="coerce")
    m = m.dropna(subset=["date"])
    m["home_score"] = m["home_score"].astype(int)
    m["away_score"] = m["away_score"].astype(int)
    is_friendly = m["tournament"].str.strip().str.lower().eq("friendly")
    m["weight"] = np.where(is_friendly, friendly_weight, 1.0)

    rows = []
    for team in teams:
        played = m[(m["home_team"] == team) | (m["away_team"] == team)]
        played = played.sort_values("date").tail(window)
        if played.empty:
            rows.append((team, 0.0, 0.0, 0))
            continue
        is_home = played["home_team"] == team
        gf = np.where(is_home, played["home_score"], played["away_score"])
        ga = np.where(is_home, played["away_score"], played["home_score"])
        pts = np.where(gf > ga, 3, np.where(gf == ga, 1, 0))
        w = played["weight"].to_numpy()
        rows.append((team, float((pts * w).sum()), float(3 * w.sum()), int(len(played))))

    form = pd.DataFrame(rows, columns=["canonical_name", "form_points", "form_max", "form_matches"])
    return form


# --- Edad (placeholder Día 2) ------------------------------------------------
# La edad media real llega del scraping de Transfermarkt (Día 3). Aquí no se
# calcula todavía; la columna se añadirá entonces.


def build(form_window: int, friendly_weight: float) -> pd.DataFrame:
    # --- Cargar fuentes ---
    mapping = pd.read_csv(MAPPING_CSV)
    _log(f"Mapping: {len(mapping)} selecciones del Mundial.")

    elo = pd.read_csv(ELO_CSV)[["elo_code", "elo_rating"]]
    df = mapping.merge(elo, on="elo_code", how="left")
    miss_elo = df["elo_rating"].isna().sum()
    if miss_elo:
        _log(f"AVISO: {miss_elo} selecciones sin Elo (revisar elo_code en mapping).")

    if FIFA_CSV.exists():
        fifa = pd.read_csv(FIFA_CSV)[["fifa_name", "fifa_rank", "fifa_points"]]
        df = df.merge(fifa, on="fifa_name", how="left")
        miss_fifa = df["fifa_rank"].isna().sum()
        if miss_fifa:
            _log(f"AVISO: {miss_fifa} selecciones sin ranking FIFA (revisar fifa_name).")
    else:
        _log("AVISO: no hay fifa_ranking.csv; columnas FIFA quedan vacías.")
        df["fifa_rank"] = np.nan
        df["fifa_points"] = np.nan

    matches = pd.read_csv(MATCHES_CSV)
    form = compute_form(matches, df["canonical_name"].tolist(), form_window, friendly_weight)
    df = df.merge(form, on="canonical_name", how="left")
    _log(
        f"Forma: ventana {form_window} partidos, friendly_weight={friendly_weight}. "
        f"Media partidos usados: {df['form_matches'].mean():.1f}."
    )

    # --- Normalización 0-1 sobre las participantes (doc 02, paso 2) ---
    df["elo_n"] = _minmax(df["elo_rating"])
    # FIFA: menor rank = mejor -> invertir. Usamos puntos (mayor = mejor) si hay.
    df["fifa_n"] = _minmax(df["fifa_points"])
    df["form_n"] = (df["form_points"] / df["form_max"]).where(df["form_max"] > 0, 0.0)

    df = df.sort_values("elo_rating", ascending=False).reset_index(drop=True)

    cols = [
        "canonical_name", "confederation", "elo_code",
        "elo_rating", "fifa_rank", "fifa_points",
        "form_points", "form_max", "form_matches",
        "elo_n", "fifa_n", "form_n",
    ]
    return df[cols]


def main() -> int:
    parser = argparse.ArgumentParser(description="Construye teams_master.csv (variables deportivas).")
    parser.add_argument("--form-window", type=int, default=DEFAULT_FORM_WINDOW,
                        help="Nº de partidos recientes para la forma (def. 20).")
    parser.add_argument("--friendly-weight", type=float, default=DEFAULT_FRIENDLY_WEIGHT,
                        help="Peso de los amistosos en la forma, 0-1 (def. 1.0 = igual que oficiales).")
    args = parser.parse_args()

    try:
        df = build(args.form_window, args.friendly_weight)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
        _log(f"Guardado {len(df)} selecciones en {OUTPUT_PATH}")
    except Exception as err:  # noqa: BLE001
        _log(f"ERROR: {err}")
        return 1

    _log("Top 10 por Elo (con FIFA y forma):")
    for _, r in df.head(10).iterrows():
        fr = "" if pd.isna(r["fifa_rank"]) else f"FIFA#{int(r['fifa_rank'])}"
        print(f"    {r['canonical_name']:<20} Elo {int(r['elo_rating'])}  {fr:<9} "
              f"forma {r['form_n']:.2f} ({int(r['form_matches'])}p)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
