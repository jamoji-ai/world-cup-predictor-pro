# 06 — Roadmap de ejecución (7 días)

Objetivo: algo visual desde el día 1, simulación funcional antes del día 4, producto presentable antes del día 7.

## Backlog priorizado (resumen)

1. Setup repo + esqueleto Streamlit con datos de ejemplo (placeholder)
2. ETL: Elo + ranking FIFA + histórico de partidos
3. ETL: scraping Transfermarkt
4. Cálculo del WPI (`wpi.py`)
5. Motor Monte Carlo (`montecarlo.py`)
6. Dashboard principal (ranking de campeones + tarjeta de selección) ⇒ **MVP**
7. Bracket interactivo
8. Vista selección completa (radar, evolución temporal)
9. Simulador manual + "¿Qué necesita mi selección?"
10. Upset Detector + infra/sobrevalorados
11. Pulido visual, mobile, mecanismos de compartir
12. Despliegue final + contenido de lanzamiento

## Cronograma día a día

### Día 1 — Esqueleto visual + setup
- Crear repo GitHub, estructura de carpetas (`data/`, `scripts/`, `app/`).
- Streamlit app mínima desplegada en Streamlit Cloud (aunque sea con datos dummy/hardcodeados) → **algo visible desde el día 1**.
- Definir `country_name_mapping.csv` (lista de 32-48 selecciones del Mundial con nombres normalizados por fuente).
- `download_elo.py` funcionando → primer CSV real (`raw/elo_ratings.csv`).

### Día 2 — ETL deportivo + ranking FIFA
- `download_fifa_ranking.py` y `download_matches_history.py`.
- Cálculo de "forma reciente" (últimos 10 partidos).
- Primer `processed/teams_master.csv` con variables deportivas (sin mercado todavía).
- Dashboard ya muestra ranking con Elo + FIFA + forma (sin WPI completo).

### Día 3 — Scraping Transfermarkt + WPI
- `scraper_transfermarkt.py`: valor de plantilla, edad media, % ligas top-5, jugador más valioso.
- Unificación en `teams_master.csv` (todas las variables).
- `wpi.py`: implementación de la fórmula del WPI con normalización y ponderaciones documentadas.
- Dashboard actualizado: ranking ahora ordenado por WPI.

### Día 4 — Motor Monte Carlo → **MVP funcional**
- `montecarlo.py`: simulación de fase de grupos + eliminatorias, vectorizada con NumPy.
- `update_all.py` orquestando ETL + WPI + simulación → `results/simulation_results.csv`.
- Dashboard principal muestra `prob_campeon`, `prob_semis`, etc. por selección.
- **Checkpoint MVP**: ranking de campeones real, basado en datos reales y simulación real, desplegado.

### Día 5 — Bracket interactivo + vista selección
- Bracket visual (Plotly) con probabilidades por cruce.
- Vista selección: radar chart de las 7 variables del WPI + métricas de mercado + probabilidades por fase.
- Primer snapshot guardado en `history_log.csv` (base para evolución temporal).

### Día 6 — Interactividad: simulador + escenarios + upset detector
- Simulador manual de partidos (recalcula clasificación + relanza Monte Carlo reducido).
- "¿Qué necesita mi selección?" (escenarios gana/empata/pierde).
- Upset Detector (top sorpresas de la siguiente ronda).
- Gráfico de evolución temporal (si ya hay ≥2 snapshots).

### Día 7 — Pulido, mobile, viralidad y lanzamiento
- Revisión mobile-first (columnas, tamaños de gráfico, navegación).
- Comparativa infra/sobrevalorados (WPI vs Elo vs mercado).
- Botones de compartir + deep-linking con `st.query_params`.
- Landing page final + textos de "metodología" (transparencia del WPI).
- Preparar 2-3 piezas de contenido de lanzamiento (ver `05_STACK_DESPLIEGUE_VIRALIDAD.md`) y publicar.

## Notas de gestión del riesgo

- Si el scraping de Transfermarkt (día 3) se retrasa o falla, el WPI puede calcularse temporalmente solo con variables deportivas (Elo + FIFA + forma) con pesos reescalados — no bloquea el MVP del día 4. El componente de mercado se añade en cuanto el scraping funcione, sin tocar el resto del pipeline.
- Si Monte Carlo vectorizado da problemas de rendimiento, reducir N a 5.000 para la app en vivo sin cambiar la arquitectura.
- Cualquier funcionalidad "Could" (evolución temporal, infra/sobrevalorados) que no llegue al día 7 se documenta como "roadmap v1.1" — no compromete el lanzamiento.
