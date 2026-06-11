# 02 — Arquitectura de datos y ETL

## Principio de diseño

Todo el almacenamiento es **archivo plano (CSV)**, con SQLite opcional solo si simplifica joins entre tablas grandes. Nada de bases de datos externas, nada de servicios cloud de pago. Cada fuente se actualiza con un script independiente y un script `update_all.py` que los orquesta.

```
data/
├── raw/                  # datos crudos descargados/scrapeados, sin procesar
│   ├── transfermarkt_squads.csv
│   ├── fifa_ranking.csv
│   ├── elo_ratings.csv
│   └── matches_history.csv
├── processed/            # datos limpios y normalizados, listos para el modelo
│   ├── teams_master.csv  # tabla maestra: 1 fila por selección con todas las variables
│   └── wpi_scores.csv    # WPI calculado + componentes
└── results/              # salidas de simulación
    ├── simulation_results.csv
    └── history_log.csv   # snapshot diario de probabilidades (para "evolución temporal")
```

## Fuentes de datos

### 1. Transfermarkt (scraping — pieza diferencial)

**Qué extraer** (por selección, de su página de plantilla del Mundial / valor de mercado):
- Valor total de la plantilla (`market_value_total`)
- Valor medio por jugador (`market_value_avg`)
- Jugador más valioso (nombre + valor)
- Edad media de la plantilla (`avg_age`)
- Nº de jugadores en ligas top-5 (Premier, LaLiga, Serie A, Bundesliga, Ligue 1) → `pct_top5_leagues`
- Distribución por posición (porteros, defensas, centrocampistas, delanteros)

**Cómo**: `requests` + `BeautifulSoup` sobre las páginas públicas de selecciones de Transfermarkt (`/[seleccion]/startseite/verein/...` y `/kader/verein/...`). Headers de User-Agent realistas, `time.sleep()` entre requests (1-2s) para no saturar. Si Transfermarkt bloquea por IP/JS, fallback a `cloudscraper` o `selenium` headless — pero empezar siempre por `requests` + `BeautifulSoup` por simplicidad.

**Riesgo y mitigación**: el HTML de Transfermarkt cambia sin aviso → aislar todos los selectores CSS en un único módulo `scraper_transfermarkt.py` con funciones pequeñas y testeables, y guardar siempre un dump crudo (`raw/`) antes de transformar, para poder reprocesar sin re-scrapear si falla la transformación.

### 2. Ranking FIFA

Descarga del ranking FIFA masculino más reciente. Si no hay API gratuita estable, scraping ligero de la web oficial de la FIFA o de fuentes secundarias (p.ej. datasets en Kaggle/GitHub actualizados periódicamente). Variable: `fifa_rank` y/o `fifa_points`.

### 3. Elo Ratings

Fuente recomendada: **eloratings.net**, que publica un CSV/JSON descargable con el Elo de todas las selecciones. Es la fuente más simple y fiable: una sola descarga, sin parsing complejo. Variable: `elo_rating`.

### 4. Resultados históricos

Dataset público de partidos internacionales (p.ej. "International football results from 1872 to present", disponible en Kaggle/GitHub como CSV). Se filtra a los últimos N años y a los últimos 10 partidos por selección para la variable de "forma reciente".

## Pipeline ETL

### Extracción (`extract`)
- `scraper_transfermarkt.py`: scrapea y guarda `raw/transfermarkt_squads.csv`
- `download_elo.py`: descarga `raw/elo_ratings.csv`
- `download_fifa_ranking.py`: obtiene `raw/fifa_ranking.csv`
- `download_matches_history.py`: descarga/actualiza `raw/matches_history.csv`

### Transformación (`transform`)
1. **Limpieza**: nombres de selecciones unificados (mapeo "Korea Republic" → "South Korea", etc. — crear `country_name_mapping.csv` como tabla de referencia, es el mayor punto de fricción al unir fuentes).
2. **Normalización 0-1**: min-max scaling por variable (`(x - min) / (max - min)`) sobre el conjunto de selecciones participantes en el Mundial — no sobre todas las selecciones del mundo, para que la escala tenga sentido relativo al torneo.
3. **Cálculo de "forma reciente"**: de `matches_history.csv`, para cada selección, tomar los últimos 10 partidos y calcular puntos obtenidos (3/1/0) normalizados.
4. **Unificación**: merge de todas las fuentes sobre `team_id`/`team_name` normalizado → `processed/teams_master.csv`.

### Carga (`load`)
- Todo se guarda como CSV en `processed/`. SQLite (`data/wcpp.db`) es opcional únicamente si el número de joins entre `matches_history` (miles de filas) y `teams_master` hace que pandas sea incómodo — no es necesario para el volumen de datos de un Mundial (32-48 selecciones).

## Scripts de automatización

| Script | Qué actualiza | Frecuencia recomendada |
|---|---|---|
| `update_transfermarkt.py` | `raw/transfermarkt_squads.csv` → re-ejecuta scraping completo | Semanal (los valores de mercado cambian poco) |
| `update_elo.py` | `raw/elo_ratings.csv` | Diario (cambia tras cada partido) |
| `update_matches.py` | `raw/matches_history.csv`, recalcula "forma reciente" | Diario durante el Mundial |
| `update_all.py` | Ejecuta los 3 anteriores + transformación + recálculo de WPI + simulación Monte Carlo + guarda snapshot en `results/history_log.csv` | Manual, 1 vez al día durante el torneo |

### Cómo se ejecutan

Manualmente desde terminal:
```bash
python scripts/update_all.py
```
Esto regenera `processed/teams_master.csv`, `processed/wpi_scores.csv` y `results/simulation_results.csv`. Streamlit lee estos CSV con `st.cache_data` (con TTL o botón de "recargar datos") — no hay backend separado ni cron obligatorio. Si se quiere automatizar sin servidor propio, una **GitHub Action programada** (cron diario) que ejecute `update_all.py` y haga commit de los CSV actualizados es la opción de coste 0 más simple (opcional, no bloqueante para el MVP).

### Cómo mantenerlos simples

- Cada script hace **una sola cosa** y escribe **un solo CSV de salida**.
- Sin clases ni abstracciones innecesarias: funciones puras `extract() -> df`, `transform(df) -> df`, `load(df, path)`.
- Logs simples por `print()` con timestamps — suficiente para un proyecto de 1 desarrollador.
- Cualquier fallo en scraping no debe romper la app: si `update_transfermarkt.py` falla, la app sigue funcionando con el último CSV válido en `raw/`.
