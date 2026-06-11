"""download_fifa_ranking.py — Descarga el ranking FIFA masculino más reciente.

Fuente (doc 02, sección 2): API interna de la web oficial de la FIFA. No hay API
pública estable, así que:
  1. Se descarga la página del ranking (Next.js) y se extraen los `dateId`
     disponibles (formato idNNNNN).
  2. Se toma el `dateId` más alto = fecha más reciente.
  3. Se consulta el endpoint JSON `ranking-overview?dateId=...`.

Salida: data/raw/fifa_ranking.csv con columnas:
    fifa_rank, fifa_name, country_code, fifa_points, confederation, ranking_date

Si la web cambia de estructura, este es el único punto a tocar (todos los
selectores/regex viven aquí). La app no se rompe: usa el último CSV válido.

Uso:
    python scripts/download_fifa_ranking.py
"""
from __future__ import annotations

import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

PAGE_URL = "https://inside.fifa.com/fifa-world-ranking/men"
API_URL = "https://inside.fifa.com/api/ranking-overview?locale=en&dateId={date_id}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "fifa_ranking.csv"


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [download_fifa] {msg}")


def _get(url: str, retries: int = 3) -> requests.Response:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=25)
            resp.raise_for_status()
            return resp
        except Exception as err:  # noqa: BLE001
            last_err = err
            _log(f"Intento {attempt}/{retries} fallido para {url}: {err}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"No se pudo descargar {url}: {last_err}")


def find_latest_date_id(page_html: str) -> str:
    """Extrae el dateId más reciente (mayor número) de la página del ranking."""
    ids = re.findall(r"id1\d{4}", page_html)
    if not ids:
        raise ValueError("No se encontró ningún dateId en la página de la FIFA.")
    latest = max(ids, key=lambda s: int(s[2:]))  # ordenar por la parte numérica
    _log(f"dateId más reciente encontrado: {latest} (de {len(set(ids))} fechas).")
    return latest


def extract() -> dict:
    _log(f"Descargando página de ranking: {PAGE_URL}")
    page = _get(PAGE_URL).text
    date_id = find_latest_date_id(page)
    _log(f"Consultando API de ranking para {date_id}")
    data = _get(API_URL.format(date_id=date_id)).json()
    if not data.get("rankings"):
        raise ValueError(f"La API devolvió un ranking vacío para {date_id}.")
    return data


def transform(data: dict) -> pd.DataFrame:
    rows = []
    for entry in data["rankings"]:
        item = entry.get("rankingItem", {})
        rows.append(
            {
                "fifa_rank": item.get("rank"),
                "fifa_name": item.get("name"),
                "country_code": item.get("countryCode"),
                "fifa_points": item.get("totalPoints"),
                "confederation": (entry.get("tag") or {}).get("id"),
                "ranking_date": entry.get("lastUpdateDate"),
            }
        )
    df = pd.DataFrame(rows).dropna(subset=["fifa_rank", "fifa_name"])
    df["fifa_rank"] = df["fifa_rank"].astype(int)
    df = df.sort_values("fifa_rank").reset_index(drop=True)
    _log(f"Ranking FIFA con {len(df)} selecciones (fecha {df['ranking_date'].iloc[0]}).")
    return df


def load(df: pd.DataFrame, path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    _log(f"Guardado {len(df)} filas en {path}")


def main() -> int:
    try:
        df = transform(extract())
        load(df)
    except Exception as err:  # noqa: BLE001
        _log(f"ERROR: {err}")
        _log("La app puede seguir usando el último CSV válido en data/raw/.")
        return 1
    _log("Top 10 ranking FIFA:")
    for _, r in df.head(10).iterrows():
        print(f"    {r['fifa_rank']:>3}  {r['fifa_name']:<22} {r['fifa_points']:.1f}  ({r['confederation']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
