"""download_matches_history.py — Descarga el histórico de partidos internacionales.

Fuente (doc 02, sección 4): dataset público "International football results
from 1872 to present" (martj42), espejo en GitHub como CSV. Incluye, además del
histórico, las FIXTURES del Mundial 2026 (tournament == "FIFA World Cup", con
fechas futuras y marcador NA) — base del calendario para el Monte Carlo (Día 4).

Salida: data/raw/matches_history.csv (copia íntegra del dataset, sin filtrar).

Uso:
    python scripts/download_matches_history.py
"""
from __future__ import annotations

import io
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

SOURCE_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WCPP/1.0)"}
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "matches_history.csv"


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [download_matches] {msg}")


def extract(retries: int = 3) -> str:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as err:  # noqa: BLE001
            last_err = err
            _log(f"Intento {attempt}/{retries} fallido: {err}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"No se pudo descargar {SOURCE_URL}: {last_err}")


def transform(csv_text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(csv_text))
    expected = {"date", "home_team", "away_team", "home_score", "away_score", "tournament"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas esperadas en el dataset: {missing}")
    played = df["home_score"].notna().sum()
    fixtures = df["home_score"].isna().sum()
    _log(f"{len(df)} partidos totales · {played} jugados · {fixtures} fixtures futuras.")
    return df


def load(df: pd.DataFrame, path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    _log(f"Guardado en {path}")


def main() -> int:
    try:
        df = transform(extract())
        load(df)
    except Exception as err:  # noqa: BLE001
        _log(f"ERROR: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
