"""sample_data.py — Datos de ejemplo (placeholder) para el Día 1.

Permiten que la app sea visual ANTES de tener el pipeline ETL/WPI/Monte Carlo.
Los valores de prob_* son ilustrativos (NO salen de simulación todavía) y se
sustituirán por data/results/simulation_results.csv a partir del Día 4.
"""
from __future__ import annotations

import pandas as pd

# Ranking de favoritos de muestra. Las columnas imitan la salida real esperada
# (ver docs/04_FUNCIONALIDADES_UX_UI.md, "Ranking de campeones").
_SAMPLE_ROWS = [
    # team, flag, conf, elo, wpi, prob_campeon, prob_semis, trend
    ("Spain",         "🇪🇸", "UEFA",     2157, 0.91, 18.4, 41.2, "up"),
    ("Argentina",     "🇦🇷", "CONMEBOL", 2115, 0.88, 15.1, 37.8, "down"),
    ("France",        "🇫🇷", "UEFA",     2063, 0.86, 13.7, 35.5, "up"),
    ("England",       "🏴", "UEFA",     2024, 0.82, 10.3, 31.0, "flat"),
    ("Brazil",        "🇧🇷", "CONMEBOL", 1991, 0.81,  9.6, 29.4, "down"),
    ("Portugal",      "🇵🇹", "UEFA",     1989, 0.79,  7.8, 26.1, "up"),
    ("Netherlands",   "🇳🇱", "UEFA",     1948, 0.74,  5.2, 21.3, "flat"),
    ("Germany",       "🇩🇪", "UEFA",     1932, 0.73,  4.9, 20.0, "up"),
    ("Croatia",       "🇭🇷", "UEFA",     1912, 0.68,  3.1, 15.4, "down"),
    ("Japan",         "🇯🇵", "AFC",      1906, 0.61,  1.8, 10.2, "up"),
    ("Belgium",       "🇧🇪", "UEFA",     1894, 0.66,  2.4, 13.0, "down"),
    ("Uruguay",       "🇺🇾", "CONMEBOL", 1892, 0.64,  2.1, 12.1, "flat"),
    ("Mexico",        "🇲🇽", "CONCACAF", 1875, 0.59,  1.3,  8.4, "up"),
    ("Morocco",       "🇲🇦", "CAF",      1827, 0.57,  1.0,  7.1, "up"),
    ("United States", "🇺🇸", "CONCACAF", 1726, 0.52,  0.6,  4.8, "flat"),
    ("Canada",        "🇨🇦", "CONCACAF", 1788, 0.50,  0.5,  4.2, "up"),
]

_TREND_ICON = {"up": "↑", "down": "↓", "flat": "→"}


def get_sample_ranking() -> pd.DataFrame:
    """DataFrame de ranking de muestra, ordenado por prob_campeon desc."""
    df = pd.DataFrame(
        _SAMPLE_ROWS,
        columns=[
            "team", "flag", "confederation", "elo", "wpi",
            "prob_campeon", "prob_semis", "trend",
        ],
    )
    df["trend_icon"] = df["trend"].map(_TREND_ICON)
    return df.sort_values("prob_campeon", ascending=False).reset_index(drop=True)
