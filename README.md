# 🏆 World Cup Predictor Pro

**Las probabilidades de que cada selección gane el Mundial 2026, recalculadas con
los datos reales y un índice propio (WPI) + simulación Monte Carlo.** Gratis, sin
cuentas, y con la metodología totalmente abierta.

> 🔗 **App en vivo:** _(añade aquí la URL de tu app de Streamlit, p. ej. `https://world-cup-predictor-pro.streamlit.app`)_

La app simula el torneo **50.000 veces** combinando rendimiento deportivo y valor
de mercado de cada selección, y muestra: ranking de favoritos, ficha por
selección, cuadro de eliminatorias, simulador manual de partidos, "¿qué necesita
mi selección?" y un detector de sorpresas. Todo en lenguaje llano.

---

## 🧠 Metodología (transparente a propósito)

El modelo tiene dos capas: **(1)** un índice de fuerza por selección (WPI) y
**(2)** una simulación Monte Carlo del torneo que lo convierte en probabilidades.

### 1. World Predictor Index (WPI)

Para cada selección se combinan 8 variables, todas normalizadas de 0 a 1 sobre el
conjunto de las 48 participantes. Los pesos:

| Variable | Qué mide | Peso |
|---|---|:---:|
| **Elo** (eloratings.net) | Fuerza según resultados históricos (el predictor más fiable) | 24% |
| **Ranking FIFA** | Posición oficial de la FIFA | 19% |
| **Forma reciente** | Puntos en los últimos 20 partidos (amistosos cuentan la mitad) | 17% |
| **Valor de plantilla** | Valor de mercado de los 26 mejores (Transfermarkt) | 13% |
| **Calidad de estrellas** | Valor medio por jugador | 5% |
| **Jugadores en grandes ligas** | % en Premier, LaLiga, Serie A, Bundesliga, Ligue 1 | 10% |
| **Edad media** | Madurez de la plantilla (óptimo ~26,5 años, función campana) | 5% |
| **Experiencia mundialista** | Rendimiento histórico en Mundiales, con más peso a lo reciente | 7% |

> Los pesos son una elección **razonada y defendible**, no el resultado de una
> optimización estadística (no la hay en un proyecto de 7 días). Esa honestidad
> es parte del valor: el modelo no es una caja negra.

**De WPI a resultado de partido:** los goles esperados de cada equipo salen de su
WPI relativo (distribución de Poisson, ~1,3 goles de media por equipo). En las
eliminatorias se usa una probabilidad logística calibrada (escala 0,55) para que
los favoritos destaquen de forma realista, comparable al consenso de mercado.

### 2. Simulación Monte Carlo

Por cada una de las 50.000 simulaciones:
1. **Fase de grupos** — se juegan los 72 partidos reales del calendario 2026, con
   **ventaja de local** para los anfitriones (USA, México, Canadá) cuando juegan
   en casa. Los partidos **ya disputados cuentan como resultado real**: solo se
   simula lo que queda por jugar (recálculo en tiempo real).
2. **Eliminatorias** — con el **cuadro oficial del Mundial 2026** (cruces reales
   del sorteo, incluida la colocación reglamentaria de los 8 mejores terceros).

La probabilidad de "ganar el Mundial" de una selección es, simplemente, en cuántas
de las 50.000 simulaciones acaba campeona.

### Fuentes de datos

- **Elo:** [eloratings.net](https://www.eloratings.net) (diario).
- **Ranking FIFA:** API pública de [fifa.com](https://inside.fifa.com).
- **Resultados y calendario:** dataset [martj42/international_results](https://github.com/martj42/international_results).
- **Valores de mercado:** scraping de [Transfermarkt](https://www.transfermarkt.com).

### Limitaciones honestas

- Los pesos del WPI no están optimizados con backtesting.
- El ranking FIFA usa la última fecha publicada por la FIFA.
- El cuadro mostrado antes del torneo es el **más probable** (favorito en cada
  cruce); se concreta con los resultados reales.

---

## 🚀 Cómo ejecutarlo en local

```bash
pip install -r requirements.txt
python scripts/update_all.py        # descarga datos + WPI + simulación
streamlit run app/main.py
```

## 🔄 Actualización de datos

Durante el Mundial, un solo comando regenera todo y guarda la foto diaria:

```bash
python scripts/update_all.py                 # todo (incluye Transfermarkt)
python scripts/update_all.py --skip-transfermarkt   # diario rápido (mercado cambia poco)
```

Luego `git commit` + `git push` y Streamlit Cloud redespliega solo. Este paso está
**automatizado** con una GitHub Action diaria (`.github/workflows/update-data.yml`);
para que pueda commitear, activa *Settings → Actions → Workflow permissions →
Read and write*.

## 🗂️ Estructura

```
app/main.py            # App Streamlit (todas las pantallas)
scripts/
  download_elo.py            # Elo de eloratings.net
  download_fifa_ranking.py   # Ranking FIFA
  download_matches_history.py# Histórico + fixtures 2026
  download_transfermarkt.py  # Valores de mercado (scraper aislado)
  scraper_transfermarkt.py   # Selectores/parseo de Transfermarkt
  build_teams_master.py      # Une fuentes + normaliza -> teams_master.csv
  wpi.py                     # Fórmula del WPI + probabilidades de partido
  montecarlo.py              # Motor de simulación (grupos + cuadro oficial)
  update_all.py              # Orquestador del pipeline completo
data/
  raw/        # datos crudos descargados
  processed/  # teams_master.csv, wpi_scores.csv
  results/    # simulation_results.csv, history_log.csv
  country_name_mapping.csv   # normalización de nombres + ids entre fuentes
docs/         # Especificación del producto
```

## 🛠️ Stack

Streamlit · Python · Pandas · NumPy · Plotly · CSV. Despliegue: GitHub + Streamlit
Community Cloud. Presupuesto: **0 €**.

---

*Proyecto con fines informativos y de divulgación de data science. No es una
herramienta de apuestas.*
