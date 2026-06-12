"""check_live_names.py — Diagnóstico de la API de resultados en vivo.

Comprueba que la clave FOOTBALL_DATA_TOKEN funciona y lista las 48 selecciones
del Mundial tal y como las nombra football-data.org, indicando cuáles casan con
nuestros datos y cuáles NO (para añadirlas a data/name_aliases.csv).

Uso (PowerShell):
    $env:FOOTBALL_DATA_TOKEN="tu_token"; python scripts/check_live_names.py
Uso (bash):
    FOOTBALL_DATA_TOKEN=tu_token python scripts/check_live_names.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import download_live_results as dlr  # noqa: E402

TEAMS_URL = "https://api.football-data.org/v4/competitions/WC/teams"


def main() -> int:
    token = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()
    if not token:
        print("Falta FOOTBALL_DATA_TOKEN. Ponlo y reintenta.")
        return 1
    try:
        resp = requests.get(TEAMS_URL, headers={"X-Auth-Token": token}, timeout=25)
        print(f"HTTP {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()
    except Exception as err:  # noqa: BLE001
        print(f"Error: {err}")
        return 1

    lookup = dlr.build_name_lookup()
    teams = data.get("teams", [])
    print(f"\nSelecciones devueltas por la API: {len(teams)}\n")
    ok, missing = [], []
    for t in teams:
        name = t.get("name", "")
        canon = lookup.get(dlr._norm(name))
        if canon:
            ok.append((name, canon))
        else:
            missing.append(name)
    print(f"--- CASAN ({len(ok)}) ---")
    for name, canon in sorted(ok):
        tag = "" if dlr._norm(name) == dlr._norm(canon) else f"  ->  {canon}"
        print(f"   {name}{tag}")
    print(f"\n--- NO CASAN ({len(missing)}) — añadir a data/name_aliases.csv ---")
    for name in sorted(missing):
        print(f"   {name}")
    if not missing:
        print("   (ninguna: todos los nombres casan)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
