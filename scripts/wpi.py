"""wpi.py — World Predictor Index y funciones de probabilidad de partido.

Fórmula del WPI (pesos ajustados por el usuario sobre el doc 03, + variable
nueva "experiencia mundialista"):

    WPI = 0.24*elo_n + 0.19*fifa_n + 0.17*form_n
        + 0.13*value_n + 0.05*value_avg_n + 0.10*top5_n + 0.05*age_n
        + 0.07*wc_exp_n

Todas las variables vienen normalizadas 0-1 en processed/teams_master.csv
(generado por build_teams_master.py). Este módulo:
  - calcula el WPI por selección y lo guarda en processed/wpi_scores.csv,
  - expone win_probability() y expected_goals() para el motor Monte Carlo (Día 4).

Uso (CLI):
    python scripts/wpi.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MASTER_CSV = ROOT / "data" / "processed" / "teams_master.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "wpi_scores.csv"

# Pesos del WPI (ajustados por el usuario sobre el doc 03). Suman 1.0.
WEIGHTS = {
    "elo_n": 0.24,
    "fifa_n": 0.19,
    "form_n": 0.17,
    "value_n": 0.13,
    "value_avg_n": 0.05,
    "top5_n": 0.10,
    "age_n": 0.05,
    "wc_exp_n": 0.07,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Los pesos del WPI deben sumar 1.0"


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [wpi] {msg}")


def compute_wpi(df: pd.DataFrame) -> pd.Series:
    """Devuelve el WPI (0-1) por fila aplicando los pesos del doc 03.

    Las columnas normalizadas ausentes se tratan como 0.5 (neutro), de modo que
    si falta el componente de mercado el WPI sigue siendo calculable (doc:
    gestión de riesgo del Día 4).
    """
    wpi = pd.Series(0.0, index=df.index)
    for col, w in WEIGHTS.items():
        comp = df[col] if col in df.columns else pd.Series(0.5, index=df.index)
        wpi = wpi + w * comp.fillna(0.5)
    return wpi


# --- De WPI a probabilidad de partido ----------------------------------------
# Escala de sensibilidad calibrada (recalibración sobre el doc 03): con WPI en
# 0-1, controla cuánto destacan los favoritos. 0.55 da probabilidades de campeón
# realistas (favoritos ~16-22%), validado contra el consenso de mercado.
WIN_PROB_SCALE = 0.55


def win_probability(wpi_a: float, wpi_b: float, scale: float = WIN_PROB_SCALE) -> float:
    """Probabilidad logística de que A gane a B (resultado decisivo, sin empate)."""
    return 1.0 / (1.0 + 10.0 ** (-(wpi_a - wpi_b) / scale))


def expected_goals(wpi_a: float, wpi_b: float, base_goals: float = 1.3) -> tuple[float, float]:
    """Goles esperados (lambdas de Poisson) de A y B según su WPI relativo."""
    strength_diff = wpi_a - wpi_b
    lam_a = max(0.05, base_goals * (1.0 + strength_diff))
    lam_b = max(0.05, base_goals * (1.0 - strength_diff))
    return lam_a, lam_b


def main() -> int:
    if not MASTER_CSV.exists():
        _log(f"ERROR: no existe {MASTER_CSV}. Ejecuta build_teams_master.py antes.")
        return 1
    df = pd.read_csv(MASTER_CSV)
    df["wpi"] = compute_wpi(df)
    df = df.sort_values("wpi", ascending=False).reset_index(drop=True)
    df["wpi_rank"] = range(1, len(df) + 1)

    cols = ["wpi_rank", "canonical_name", "confederation", "wpi",
            "elo_n", "fifa_n", "form_n", "value_n", "value_avg_n", "top5_n", "age_n", "wc_exp_n"]
    df[cols].to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    _log(f"Guardado {len(df)} WPI en {OUTPUT_PATH}")
    _log("Top 12 por WPI:")
    for _, r in df.head(12).iterrows():
        print(f"    {r['wpi_rank']:>2}. {r['canonical_name']:<22} WPI {r['wpi']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
