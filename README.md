# 🏆 World Cup Predictor Pro

Probabilidades del Mundial en tiempo real, combinando un índice propio (**WPI** —
World Predictor Index) y un motor de simulación **Monte Carlo**. App gratuita en
Streamlit, sin cuentas ni paywall.

> 🚧 En construcción (roadmap de 7 días — ver `docs/06_ROADMAP_7DIAS.md`).
> El README completo con la metodología detallada del WPI se redacta el Día 7.

## Cómo ejecutar en local

```bash
pip install -r requirements.txt
streamlit run app/main.py
```

## Actualizar datos (manual)

```bash
python scripts/download_elo.py     # Elo desde eloratings.net -> data/raw/elo_ratings.csv
```

## Estructura

```
app/        # App Streamlit (main.py)
scripts/    # Scripts de ETL manuales (download_*.py, update_*.py)
data/
  raw/        # datos crudos descargados/scrapeados
  processed/  # datos limpios (teams_master.csv, wpi_scores.csv)
  results/    # salidas de simulación
  country_name_mapping.csv   # normalización de nombres entre fuentes
docs/       # Especificación completa del producto (PRD, modelo, UX, roadmap)
```

## Stack

Streamlit · Python · Pandas · NumPy · Plotly · CSV. Despliegue: GitHub +
Streamlit Community Cloud. Presupuesto: 0 €.
