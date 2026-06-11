"""download_transfermarkt.py — Scraping de valores de mercado (orquestador).

Recorre las 48 selecciones del Mundial (data/country_name_mapping.csv, columna
transfermarkt_id) y, para cada una, scrapea su plantilla en Transfermarkt y
extrae métricas de mercado vía scraper_transfermarkt.parse_squad.

Doc 02:
  - Empezar con requests + BeautifulSoup; si TM bloquea, usar cloudscraper.
  - Guardar SIEMPRE un dump crudo (data/raw/transfermarkt_html/) antes de
    transformar, para reprocesar sin re-scrapear.
  - time.sleep(1-2s) entre requests para no saturar.
  - Un fallo de scraping no rompe la app: se conserva el último CSV válido.

Métricas calculadas sobre los TOP-26 por valor de cada selección (comparable
con el tamaño real del Mundial). Cambiar con --squad-cap.

Salida: data/raw/transfermarkt_squads.csv

Uso:
    python scripts/download_transfermarkt.py [--squad-cap 26] [--season 2025]
                                             [--only spanien,japan] [--no-cache]
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scraper_transfermarkt as tm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MAPPING_CSV = ROOT / "data" / "country_name_mapping.csv"
RAW_HTML_DIR = ROOT / "data" / "raw" / "transfermarkt_html"
OUTPUT_PATH = ROOT / "data" / "raw" / "transfermarkt_squads.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
SLEEP_SECONDS = 1.5


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [transfermarkt] {msg}"
    enc = sys.stdout.encoding or "utf-8"
    # La consola de Windows (cp1252) no codifica todos los nombres: degradar.
    print(line.encode(enc, errors="replace").decode(enc))


def make_session(use_cloudscraper: bool = False):
    """Sesión requests normal o cloudscraper si TM bloquea (doc 02)."""
    if use_cloudscraper:
        import cloudscraper  # import perezoso: solo si hace falta
        s = cloudscraper.create_scraper()
    else:
        s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _looks_blocked(html: str) -> bool:
    head = html[:1500].lower()
    return any(k in head for k in ("just a moment", "captcha", "access denied", "cf-browser-verification"))


def fetch(session, url: str, cache_path: Path | None, use_cache: bool) -> str:
    """Descarga con cache de dump crudo. Reintenta una vez con cloudscraper."""
    if use_cache and cache_path and cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    resp = session.get(url, timeout=25)
    resp.raise_for_status()
    html = resp.text
    if _looks_blocked(html):
        raise RuntimeError("BLOCKED")  # el caller decide cambiar a cloudscraper
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(html, encoding="utf-8")
    return html


def get_top5_club_ids(session, use_cache: bool) -> set[int]:
    """Conjunto de verein_id de clubes de las 5 grandes ligas (con dump crudo)."""
    ids: set[int] = set()
    for code in tm.TOP5_LEAGUE_CODES:
        cache = RAW_HTML_DIR / f"league_{code}.html"
        html = fetch(session, tm.league_url(code), cache, use_cache)
        league_ids = tm.parse_league_club_ids(html)
        _log(f"Liga {code}: {len(league_ids)} clubes.")
        ids |= league_ids
        time.sleep(SLEEP_SECONDS)
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrapea valores de mercado de Transfermarkt.")
    parser.add_argument("--squad-cap", type=int, default=26,
                        help="Nº de jugadores top por valor a considerar (def. 26).")
    parser.add_argument("--season", type=int, default=2025, help="saison_id de TM (def. 2025).")
    parser.add_argument("--only", type=str, default=None,
                        help="Lista de slugs separados por coma para probar un subconjunto.")
    parser.add_argument("--no-cache", action="store_true", help="Ignorar dumps crudos y re-scrapear.")
    args = parser.parse_args()
    use_cache = not args.no_cache

    mapping = pd.read_csv(MAPPING_CSV)
    if args.only:
        only = {s.strip() for s in args.only.split(",")}
        mapping = mapping[mapping["transfermarkt_slug"].isin(only)]
    _log(f"Selecciones a scrapear: {len(mapping)} (squad_cap={args.squad_cap}).")

    # Sesión: probar requests; si la primera petición está bloqueada, cloudscraper.
    session = make_session(use_cloudscraper=False)
    try:
        top5 = get_top5_club_ids(session, use_cache)
    except RuntimeError:
        _log("Bloqueo detectado con requests → cambiando a cloudscraper.")
        session = make_session(use_cloudscraper=True)
        top5 = get_top5_club_ids(session, use_cache)
    _log(f"Clubes top-5 totales: {len(top5)}.")

    rows = []
    failures = []
    for _, team in mapping.iterrows():
        name, slug, vid = team["canonical_name"], team["transfermarkt_slug"], int(team["transfermarkt_id"])
        url = tm.squad_url(slug, vid, args.season)
        cache = RAW_HTML_DIR / f"squad_{vid}.html"
        try:
            try:
                html = fetch(session, url, cache, use_cache)
            except RuntimeError:
                _log(f"{name}: bloqueo → reintento con cloudscraper.")
                session = make_session(use_cloudscraper=True)
                html = fetch(session, url, cache, use_cache)
            data = tm.parse_squad(html, top5, squad_cap=args.squad_cap)
            data["canonical_name"] = name
            data["transfermarkt_id"] = vid
            rows.append(data)
            _log(f"OK {name:22} total {data['market_value_total']/1e6:6.0f}M "
                 f"| edad {data['avg_age']} | top5 {data['pct_top5_leagues']*100:3.0f}% "
                 f"| {data['top_player']}")
        except Exception as err:  # noqa: BLE001 - un fallo no debe abortar el resto
            failures.append((name, str(err)))
            _log(f"FAIL {name}: {err}")
        time.sleep(SLEEP_SECONDS)

    if not rows:
        _log("ERROR: no se obtuvo ninguna selección. Se conserva el CSV anterior si existe.")
        return 1

    cols = ["canonical_name", "transfermarkt_id", "n_players", "n_players_pool",
            "market_value_total", "market_value_avg", "avg_age",
            "top_player", "top_player_value", "pct_top5_leagues"]
    df = pd.DataFrame(rows)[cols]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    _log(f"Guardado {len(df)}/{len(mapping)} selecciones en {OUTPUT_PATH}")
    if failures:
        _log(f"FALLOS ({len(failures)}): {[f[0] for f in failures]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
