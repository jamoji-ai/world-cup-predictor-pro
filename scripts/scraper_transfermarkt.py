"""scraper_transfermarkt.py — Selectores y parseo de Transfermarkt (AISLADO).

Doc 02 (riesgo): el HTML de Transfermarkt cambia sin aviso, así que TODOS los
selectores CSS y la lógica de parseo viven SOLO en este módulo, en funciones
pequeñas y testeables. La orquestación (bucle sobre las 48, sleeps, guardado de
dump crudo) está en download_transfermarkt.py.

Qué extrae por selección (de su página de plantilla detallada):
  - market_value_total : valor total de la plantilla (€)
  - market_value_avg   : valor medio por jugador (€)
  - top_player / top_player_value : jugador más valioso
  - avg_age            : edad media
  - n_players          : nº de jugadores
  - pct_top5_leagues   : % de jugadores en clubes de las 5 grandes ligas

Fuente: requests + BeautifulSoup. Si Transfermarkt bloquea, el orquestador
cambia a cloudscraper (doc: probar cloudscraper antes que selenium).
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

# --- URLs / selectores (único punto a tocar si TM cambia) --------------------
BASE = "https://www.transfermarkt.com"
SQUAD_URL = BASE + "/{slug}/kader/verein/{vid}/saison_id/{season}/plus/1"
LEAGUE_URL = BASE + "/x/startseite/wettbewerb/{code}"

# Códigos de las 5 grandes ligas en Transfermarkt.
TOP5_LEAGUE_CODES = ["GB1", "ES1", "IT1", "L1", "FR1"]

_SQUAD_TABLE = "table.items"
_DATA_ROW_CLASSES = ("odd", "even")
_VEREIN_RE = re.compile(r"/verein/(\d+)")
_AGE_RE = re.compile(r"\((\d+)\)")


# --- Helpers de parseo --------------------------------------------------------

def parse_money(text: str) -> float | None:
    """'€40.00m' -> 40000000.0 ; '€900k' -> 900000.0 ; '-' -> None."""
    if not text:
        return None
    s = text.replace("€", "").replace("\xa0", "").strip()
    if not s or s in {"-", "–", "?"}:
        return None
    mult = 1.0
    low = s.lower()
    if low.endswith("bn"):
        mult, s = 1e9, s[:-2]
    elif low.endswith("m"):
        mult, s = 1e6, s[:-1]
    elif low.endswith("k"):
        mult, s = 1e3, s[:-1]
    try:
        return float(s.replace(",", "")) * mult
    except ValueError:
        return None


def _data_rows(soup: BeautifulSoup) -> list:
    table = soup.select_one(_SQUAD_TABLE)
    if table is None:
        return []
    return [
        r for r in table.select("tbody > tr")
        if r.get("class") and any(c in _DATA_ROW_CLASSES for c in r.get("class"))
    ]


def parse_squad(html: str, top5_club_ids: set[int], squad_cap: int | None = 26) -> dict:
    """Parsea la página de plantilla detallada -> métricas agregadas de mercado.

    `top5_club_ids` es el conjunto de verein_id de clubes de las 5 grandes ligas.
    `squad_cap`: si se indica (def. 26 = tamaño del Mundial), las métricas se
    calculan sobre los N jugadores MÁS VALIOSOS, para que las selecciones sean
    comparables (Transfermarkt lista grupos amplios y muy dispares: 39 vs 82).
    None = plantilla completa. Lanza ValueError si no hay tabla/jugadores.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows = _data_rows(soup)
    if not rows:
        raise ValueError("No se encontró la tabla de plantilla (table.items vacía).")

    # Registro por jugador: (nombre, valor, edad|None, en_top5|None).
    records: list[tuple[str, float, int | None, bool | None]] = []
    for r in rows:
        tds = r.find_all("td", recursive=False)
        if len(tds) < 3:
            continue
        name_a = tds[1].find("a")
        name = name_a.get_text(strip=True) if name_a else tds[1].get_text(" ", strip=True)
        val = parse_money(tds[-1].get_text(strip=True))
        if val is None:
            continue  # sin valor no entra en el ranking de plantilla
        m_age = _AGE_RE.search(tds[2].get_text(" ", strip=True))
        age = int(m_age.group(1)) if m_age else None
        club_id = None
        for a in r.select("a[href*='/verein/']"):
            mm = _VEREIN_RE.search(a["href"])
            if mm:
                club_id = int(mm.group(1))
                break
        in_top5 = (club_id in top5_club_ids) if club_id is not None else None
        records.append((name, val, age, in_top5))

    if not records:
        raise ValueError("Tabla encontrada pero sin valores de mercado parseables.")

    # Ordenar por valor desc y quedarnos con los `squad_cap` mejores.
    records.sort(key=lambda x: x[1], reverse=True)
    top_player, top_value = records[0][0], records[0][1]
    selected = records[:squad_cap] if squad_cap else records

    values = [r[1] for r in selected]
    ages = [r[2] for r in selected if r[2] is not None]
    club_known = [r[3] for r in selected if r[3] is not None]
    n_top5 = sum(1 for x in club_known if x)

    return {
        "n_players": len(selected),
        "n_players_pool": len(records),
        "market_value_total": round(sum(values), 2),
        "market_value_avg": round(sum(values) / len(values), 2),
        "avg_age": round(sum(ages) / len(ages), 2) if ages else None,
        "top_player": top_player,
        "top_player_value": round(top_value, 2),
        "pct_top5_leagues": round(n_top5 / len(club_known), 4) if club_known else 0.0,
    }


def parse_league_club_ids(html: str) -> set[int]:
    """Extrae los verein_id de los clubes de una página de liga."""
    soup = BeautifulSoup(html, "html.parser")
    ids: set[int] = set()
    table = soup.select_one(_SQUAD_TABLE)
    if table is None:
        return ids
    for a in table.select("a[href*='/verein/']"):
        m = _VEREIN_RE.search(a["href"])
        if m:
            ids.add(int(m.group(1)))
    return ids


def squad_url(slug: str, vid: int, season: int) -> str:
    return SQUAD_URL.format(slug=slug, vid=vid, season=season)


def league_url(code: str) -> str:
    return LEAGUE_URL.format(code=code)
