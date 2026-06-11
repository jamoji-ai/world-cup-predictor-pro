# Prompt final para Claude Code

> Cómo usarlo: crea una carpeta nueva para el proyecto, copia dentro los 6 archivos `.md` de este paquete (o todo el contenido relevante dentro de un `docs/` o `CLAUDE.md`), abre Claude Code en esa carpeta y pega este mensaje como primer prompt.

---

Vamos a construir **World Cup Predictor Pro**, una app Streamlit gratuita que calcula en tiempo real las probabilidades de cada selección de ganar el Mundial, combinando un índice propio (WPI) y un motor de simulación Monte Carlo.

Tienes en este repo (carpeta `docs/`) la especificación completa del producto, ya cerrada:
- `01_PRD.md` — producto, público, funcionalidades MoSCoW
- `02_ARQUITECTURA_DATOS_ETL.md` — fuentes de datos, scraping de Transfermarkt, pipeline ETL y scripts de actualización
- `03_MODELO_WPI_MONTECARLO.md` — fórmula del WPI y diseño del motor Monte Carlo
- `04_FUNCIONALIDADES_UX_UI.md` — funcionalidades clave y diseño de las 6 pantallas
- `05_STACK_DESPLIEGUE_VIRALIDAD.md` — stack, despliegue (GitHub + Streamlit Cloud), viralidad
- `06_ROADMAP_7DIAS.md` — plan de ejecución día a día

**Restricciones que no se negocian**: presupuesto 0€, despliegue gratuito (GitHub + Streamlit Community Cloud), un único desarrollador, stack Streamlit + Python + Pandas + NumPy + Plotly + CSV (SQLite solo si aporta simplicidad real), mantenimiento mínimo (scripts manuales `update_*.py`).

## Lo que necesito de ti

Quiero ejecutar el roadmap de `06_ROADMAP_7DIAS.md` de forma incremental, día a día, dejando cada día algo ejecutable y, si es posible, desplegado.

1. **Empieza por el Día 1**: crea la estructura de carpetas (`data/raw`, `data/processed`, `data/results`, `scripts/`, `app/`), inicializa el repo Git, y monta un esqueleto de app Streamlit (`app/main.py`) que ya muestre un dashboard básico (aunque sea con datos de ejemplo/hardcodeados), para tener algo visual desde ya. Crea también `country_name_mapping.csv` con las selecciones del Mundial y `scripts/download_elo.py` funcional contra eloratings.net.

2. Tras cada día, **muéstrame qué se ha construido, cómo probarlo localmente (`streamlit run app/main.py`), y pregúntame antes de pasar al siguiente día** si quiero ajustar algo.

3. Sigue estrictamente las decisiones de arquitectura y modelo ya documentadas en `02_*` y `03_*` (fórmula del WPI, pesos, estructura del Monte Carlo) — si detectas un problema real con alguna de ellas (p.ej. una fuente de datos ya no está disponible), dímelo explícitamente y propón la alternativa más simple antes de cambiarla.

4. Para el scraping de Transfermarkt (Día 3), ve con cuidado: implementa primero contra 2-3 selecciones de prueba, valida que el HTML parseado es correcto, y solo entonces escala a las 32-48 selecciones del Mundial. Si Transfermarkt bloquea las requests, prueba `cloudscraper` antes de pasar a `selenium`.

5. Cuando lleguemos al Día 4 (MVP funcional con Monte Carlo), avísame explícitamente — es el checkpoint clave del proyecto.

6. Para el Día 7, ayúdame también a redactar el README del repo (con la metodología del WPI explicada de forma transparente, ya que es parte del valor del producto) y a dejar el repo listo para conectar a Streamlit Community Cloud.

Confirma que has leído los `.md` de `docs/` y empecemos por el Día 1.
