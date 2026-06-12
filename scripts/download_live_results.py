"""download_live_results.py — Resultados en vivo del Mundial (football-data.org).

Trae los marcadores de los partidos YA FINALIZADOS desde la API de
football-data.org (plan gratuito, incluye la competición "WC") mucho antes de
que el dataset histórico (martj42) los publique. Estos resultados se fusionan en
el modelo como partidos jugados (ver wc_engine.load_tournament).

Requiere una clave gratuita en la variable de entorno FOOTBALL_DATA_TOKEN
(regístrate en https://www.football-data.org/client/register). Si no hay clave o
la API falla, el script NO rompe nada: simplemente no actualiza y el modelo sigue
usando la fuente histórica.

Salida: data/raw/live_results.csv con columnas:
    home_team, away_team, home_score, away_score   (nombres canónicos)

Uso:
    FOOTBALL_DATA_TOKEN=xxxx python scripts/download_live_results.py
"""
from __future__ import annotations

import os
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
MAPPING_CSV = ROOT / "data" / "country_name_mapping.csv"
ALIASES_CSV = ROOT / "data" / "name_aliases.csv"
OUTPUT_PATH = ROOT / "data" / "raw" / "live_results.csv"

API_URL = "https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED"


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [live_results] {msg}")


def _norm(s: str) -> str:
    """Minúsculas sin acentos para comparar nombres de selección."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.strip().lower()


def build_name_lookup() -> dict[str, str]:
    """Normalizado -> nombre canónico. Combina el mapping (canónico + nombre FIFA)
    con el diccionario editable data/name_aliases.csv (source_name -> canonical)."""
    mp = pd.read_csv(MAPPING_CSV)
    lookup = {}
    for _, r in mp.iterrows():
        canon = r["canonical_name"]
        lookup[_norm(canon)] = canon
        lookup[_norm(r["fifa_name"])] = canon
    if ALIASES_CSV.exists():
        try:
            al = pd.read_csv(ALIASES_CSV)
            for _, r in al.iterrows():
                lookup[_norm(r["source_name"])] = r["canonical_name"]
        except Exception as err:  # noqa: BLE001
            _log(f"AVISO: no se pudo leer {ALIASES_CSV.name}: {err}")
    return lookup


def fetch(token: str) -> dict | None:
    try:
        resp = requests.get(API_URL, headers={"X-Auth-Token": token}, timeout=25)
        if resp.status_code == 403:
            _log("403: la clave no tiene acceso a la competición WC (revisa el plan/clave).")
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as err:  # noqa: BLE001
        _log(f"Error consultando la API: {err}")
        return None


def transform(data: dict, lookup: dict[str, str]) -> pd.DataFrame:
    rows, missing = [], set()
    for m in data.get("matches", []):
        if m.get("status") != "FINISHED":
            continue
        home = (m.get("homeTeam") or {}).get("name")
        away = (m.get("awayTeam") or {}).get("name")
        ft = (m.get("score") or {}).get("fullTime") or {}
        hs, as_ = ft.get("home"), ft.get("away")
        if home is None or away is None or hs is None or as_ is None:
            continue
        ch, ca = lookup.get(_norm(home)), lookup.get(_norm(away))
        if ch is None:
            missing.add(home)
        if ca is None:
            missing.add(away)
        if ch and ca:
            rows.append({"home_team": ch, "away_team": ca,
                         "home_score": int(hs), "away_score": int(as_)})
    if missing:
        _log(f"AVISO: nombres sin mapear (añadir a ALIASES): {sorted(missing)}")
    return pd.DataFrame(rows)


def main() -> int:
    token = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()
    if not token:
        _log("Sin FOOTBALL_DATA_TOKEN: se omite (el modelo usará la fuente histórica).")
        return 0  # no es un error: es opcional
    data = fetch(token)
    if data is None:
        _log("No se pudieron obtener resultados en vivo; se conserva el CSV anterior si existe.")
        return 0
    df = transform(data, build_name_lookup())
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    _log(f"Guardados {len(df)} resultados finalizados en {OUTPUT_PATH}")
    for _, r in df.iterrows():
        print(f"    {r['home_team']} {r['home_score']}-{r['away_score']} {r['away_team']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
