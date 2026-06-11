"""download_elo.py — Descarga los Elo Ratings de selecciones desde eloratings.net.

Fuente (ver docs/02_ARQUITECTURA_DATOS_ETL.md, sección 3):
  - https://www.eloratings.net/World.tsv     -> ranking + rating actual (sin cabecera)
  - https://www.eloratings.net/en.teams.tsv  -> código interno -> nombre del país

Salida: data/raw/elo_ratings.csv con columnas:
    rank, elo_code, team_name, elo_rating

Filosofía (doc 02): funciones puras extract/transform/load, un único CSV de
salida, logs simples por print(). No filtra a las selecciones del Mundial: eso
ocurre en la fase de transformación del ETL (Día 2+). Aquí descargamos TODO.

Uso:
    python scripts/download_elo.py
"""
from __future__ import annotations

import io
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# --- Configuración -----------------------------------------------------------

WORLD_URL = "https://www.eloratings.net/World.tsv"
TEAMS_URL = "https://www.eloratings.net/en.teams.tsv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/plain,*/*",
}

# Columnas del fichero World.tsv (sin cabecera). Solo necesitamos las 3 primeras
# útiles; el resto son estadísticas históricas que ignoramos en el MVP.
#   col 0: rank
#   col 2: código interno de eloratings (ES, AR, FR, ...)
#   col 3: Elo rating actual
WORLD_COL_RANK = 0
WORLD_COL_CODE = 2
WORLD_COL_ELO = 3

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "elo_ratings.csv"


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [download_elo] {msg}")


# --- Extract -----------------------------------------------------------------

def _fetch(url: str, retries: int = 3, backoff: float = 2.0) -> str:
    """Descarga texto crudo con reintentos. Lanza excepción si todo falla."""
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            if "<html" in resp.text[:200].lower():
                raise ValueError("La respuesta parece HTML (¿404/bloqueo?), no TSV.")
            return resp.text
        except Exception as err:  # noqa: BLE001 - logueamos y reintentamos
            last_err = err
            _log(f"Intento {attempt}/{retries} fallido para {url}: {err}")
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise RuntimeError(f"No se pudo descargar {url}: {last_err}")


def extract() -> tuple[str, str]:
    """Descarga los dos ficheros TSV crudos de eloratings.net."""
    _log(f"Descargando ranking mundial: {WORLD_URL}")
    world_tsv = _fetch(WORLD_URL)
    _log(f"Descargando tabla de nombres: {TEAMS_URL}")
    teams_tsv = _fetch(TEAMS_URL)
    return world_tsv, teams_tsv


# --- Transform ---------------------------------------------------------------

def _parse_teams(teams_tsv: str) -> dict[str, str]:
    """Construye {código -> nombre canónico} desde en.teams.tsv.

    Cada línea: <código>\t<nombre>\t<alias1>\t<alias2>...  Nos quedamos con el
    primer nombre (columna 1) como nombre canónico.
    """
    mapping: dict[str, str] = {}
    for line in teams_tsv.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] and parts[1]:
            mapping[parts[0].strip()] = parts[1].strip()
    _log(f"Tabla de nombres: {len(mapping)} códigos.")
    return mapping


def transform(world_tsv: str, teams_tsv: str) -> pd.DataFrame:
    """Convierte los TSV crudos en un DataFrame limpio y ordenado por Elo."""
    code_to_name = _parse_teams(teams_tsv)

    df = pd.read_csv(io.StringIO(world_tsv), sep="\t", header=None, dtype=str)
    out = pd.DataFrame(
        {
            "rank": pd.to_numeric(df[WORLD_COL_RANK], errors="coerce"),
            "elo_code": df[WORLD_COL_CODE].str.strip(),
            "elo_rating": pd.to_numeric(df[WORLD_COL_ELO], errors="coerce"),
        }
    )
    out["team_name"] = out["elo_code"].map(code_to_name)

    # Filas sin rating o sin código válido no aportan.
    before = len(out)
    out = out.dropna(subset=["elo_rating", "elo_code"]).copy()
    out["rank"] = out["rank"].astype("Int64")
    out["elo_rating"] = out["elo_rating"].round().astype(int)

    # Avisar de códigos sin nombre (no rompe: dejamos el código como nombre).
    missing = out["team_name"].isna().sum()
    if missing:
        _log(f"Aviso: {missing} códigos sin nombre en la tabla; uso el código.")
        out["team_name"] = out["team_name"].fillna(out["elo_code"])

    out = out.sort_values("elo_rating", ascending=False).reset_index(drop=True)
    out = out[["rank", "elo_code", "team_name", "elo_rating"]]
    _log(f"Transformadas {len(out)} selecciones (descartadas {before - len(out)}).")
    return out


# --- Load --------------------------------------------------------------------

def load(df: pd.DataFrame, path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    _log(f"Guardado {len(df)} filas en {path}")


# --- Orquestación ------------------------------------------------------------

def main() -> int:
    try:
        world_tsv, teams_tsv = extract()
        df = transform(world_tsv, teams_tsv)
        load(df)
    except Exception as err:  # noqa: BLE001
        _log(f"ERROR: {err}")
        _log("La app puede seguir usando el último CSV válido en data/raw/.")
        return 1
    # Resumen útil en consola.
    top = df.head(10)
    _log("Top 10 por Elo:")
    for _, row in top.iterrows():
        print(f"    {int(row['rank']):>3}  {row['elo_code']:<4} {row['team_name']:<22} {row['elo_rating']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
