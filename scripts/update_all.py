"""update_all.py — Orquestador del pipeline completo (doc 02).

Ejecuta, en orden:
  1. Descargas (Elo, ranking FIFA, partidos, Transfermarkt) — un fallo en una
     fuente NO aborta el resto (la app sigue con el último CSV válido).
  2. Transformación: build_teams_master.py
  3. WPI: wpi.py
  4. Simulación Monte Carlo "oficial" (50.000 sims) -> results/simulation_results.csv
  5. Snapshot diario en results/history_log.csv (para la evolución temporal).

Pensado para ejecutarse manualmente 1 vez al día durante el Mundial, seguido de
git commit + push (Streamlit Cloud redespliega solo).

Uso:
    python scripts/update_all.py                 # todo, simulación a 50.000
    python scripts/update_all.py --sims 20000    # simulación más ligera
    python scripts/update_all.py --skip-download  # solo recalcular con datos ya bajados
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[0]
RESULTS = ROOT / "data" / "results"
SIM_CSV = RESULTS / "simulation_results.csv"
HISTORY_CSV = RESULTS / "history_log.csv"

# Descargas: (script, ¿crítico?). Si una no-crítica falla, se continúa.
DOWNLOADS = [
    ("download_elo.py", False),
    ("download_fifa_ranking.py", False),
    ("download_matches_history.py", False),
    ("download_transfermarkt.py", False),
]
TRANSFORMS = [
    ("build_teams_master.py", True),
    ("wpi.py", True),
]


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [update_all] {msg}")


def run_script(name: str, critical: bool) -> bool:
    _log(f"--- Ejecutando {name} ---")
    res = subprocess.run([sys.executable, str(SCRIPTS / name)])
    ok = res.returncode == 0
    if not ok:
        msg = f"{name} terminó con código {res.returncode}"
        if critical:
            _log(f"ERROR CRÍTICO: {msg}. Abortando.")
        else:
            _log(f"AVISO: {msg}. Se continúa con el último CSV válido.")
    return ok


def append_history_snapshot() -> None:
    """Añade a history_log.csv una fila por selección con la fecha y prob_campeon."""
    if not SIM_CSV.exists():
        _log("No hay simulation_results.csv; no se guarda snapshot.")
        return
    sim = pd.read_csv(SIM_CSV)
    today = date.today().isoformat()
    snap = sim[["canonical_name", "prob_campeon", "prob_semis", "prob_avanza_grupos"]].copy()
    snap.insert(0, "date", today)
    if HISTORY_CSV.exists():
        hist = pd.read_csv(HISTORY_CSV)
        hist = hist[hist["date"] != today]  # reemplazar snapshot de hoy si se reejecuta
        out = pd.concat([hist, snap], ignore_index=True)
    else:
        out = snap
    out.to_csv(HISTORY_CSV, index=False, encoding="utf-8")
    _log(f"Snapshot {today} guardado en {HISTORY_CSV} ({len(snap)} selecciones).")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline completo del Mundial.")
    parser.add_argument("--sims", type=int, default=50000, help="Simulaciones oficiales (def. 50000).")
    parser.add_argument("--skip-download", action="store_true", help="No re-descargar fuentes.")
    parser.add_argument("--skip-transfermarkt", action="store_true",
                        help="Descargar todo menos Transfermarkt (valores cambian poco; ideal para el cron diario).")
    args = parser.parse_args()

    if not args.skip_download:
        for name, critical in DOWNLOADS:
            if args.skip_transfermarkt and name == "download_transfermarkt.py":
                _log("Saltando Transfermarkt (--skip-transfermarkt): se usa el CSV existente.")
                continue
            if not run_script(name, critical) and critical:
                return 1
    else:
        _log("Saltando descargas (--skip-download).")

    for name, critical in TRANSFORMS:
        if not run_script(name, critical) and critical:
            return 1

    _log(f"--- Simulación Monte Carlo oficial ({args.sims} sims) ---")
    res = subprocess.run([sys.executable, str(SCRIPTS / "montecarlo.py"), "--sims", str(args.sims)])
    if res.returncode != 0:
        _log("ERROR CRÍTICO: la simulación falló. Abortando.")
        return 1

    append_history_snapshot()
    _log("Pipeline completo. Recuerda: git add -A && git commit && git push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
