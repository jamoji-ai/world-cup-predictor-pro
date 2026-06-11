# World Cup Predictor Pro — Paquete de planificación

Este paquete estructura el proyecto descrito en `prompt_inicial_proyecto_mundial.txt` en documentos accionables, listos para ejecutar el desarrollo en 7 días.

## 1. Recomendación: ¿Cowork o Claude Code?

**Conclusión corta: esto es un MVP funcional, no un artefacto. Y el desarrollo (Fases 2-10) debe hacerse en Claude Code, no en Cowork.**

### Por qué no es un artefacto

Un artefacto (HTML/React) corre en el navegador, sin backend Python. Este proyecto depende de:
- Scraping de Transfermarkt (requiere Python + librerías como `requests`/`BeautifulSoup`/`Selenium`, ejecución en servidor o local).
- ETL con Pandas/NumPy y persistencia en CSV/SQLite.
- Simulación Monte Carlo (10.000-50.000 iteraciones) — coste computacional inviable en el navegador.
- Streamlit, que es un framework de servidor Python.

Ninguno de estos componentes es viable como artefacto. El entregable real es **una app Streamlit + scripts Python en un repo de GitHub, desplegada en Streamlit Cloud**.

### Por qué Claude Code para el desarrollo

| Necesidad del proyecto | Cowork | Claude Code |
|---|---|---|
| Repo Git versionado (Fase 8: GitHub + Streamlit Cloud) | Limitado | Nativo |
| Desarrollo iterativo de múltiples módulos (`scraper.py`, `etl.py`, `wpi.py`, `montecarlo.py`, `app.py`...) | Posible pero incómodo | Diseñado para esto |
| Ejecutar y depurar scraping/ETL repetidamente, instalar dependencias persistentes | Sandbox efímero | Entorno local persistente |
| Despliegue continuo (push a GitHub → redeploy Streamlit Cloud) | No | Sí |

### Para qué SÍ usar Cowork (lo que estamos haciendo ahora)

- Fase 1 (definición de producto), documentación, research de fuentes de datos, y estructurar el "prompt maestro" que le pasarás a Claude Code.
- Generar los `.md` de este paquete, que sirven como **especificación de producto y arquitectura** (equivalente a un PRD + ADR).

## 2. Flujo recomendado

1. **Ahora (Cowork)**: revisas y ajustas estos `.md`. Son tu fuente de verdad.
2. **Claude Code**: abres un proyecto nuevo (carpeta local o repo Git), copias `PROMPT_CLAUDE_CODE.md` como prompt inicial (idealmente como `CLAUDE.md` del repo + primer mensaje), y dejas que Claude Code construya día a día siguiendo `ROADMAP_7DIAS.md`.
3. **Mantenimiento**: scripts `update_*.py` se ejecutan manualmente (o con cron/GitHub Actions opcional) — Claude Code es ideal también para iterar sobre estos scripts cuando Transfermarkt cambie su HTML.

## 3. Índice de documentos

| Archivo | Contenido |
|---|---|
| `01_PRD.md` | Problema, propuesta de valor, público, casos de uso, MoSCoW |
| `02_ARQUITECTURA_DATOS_ETL.md` | Fuentes de datos, scraping Transfermarkt, pipeline ETL, scripts de actualización |
| `03_MODELO_WPI_MONTECARLO.md` | Fórmula del WPI y motor de simulación Monte Carlo |
| `04_FUNCIONALIDADES_UX_UI.md` | Las 7 funcionalidades clave + diseño de las 6 pantallas |
| `05_STACK_DESPLIEGUE_VIRALIDAD.md` | Stack tecnológico, despliegue gratuito, estrategia de viralidad |
| `06_ROADMAP_7DIAS.md` | Backlog priorizado y cronograma día a día |
| `PROMPT_CLAUDE_CODE.md` | Prompt final para pegar en Claude Code y arrancar el desarrollo |

## 4. Próximo paso

Abre Claude Code en una carpeta nueva, pega el contenido de `PROMPT_CLAUDE_CODE.md` (junto con los demás `.md` como archivos de referencia en el repo) y arranca el Día 1 del roadmap.
