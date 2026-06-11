# 05 — Stack, despliegue y viralidad

## Stack tecnológico

| Capa | Elección | Por qué |
|---|---|---|
| Frontend/app | **Streamlit** | Permite construir UI interactiva en Python puro, sin frontend separado. Encaja con el perfil del desarrollador (Python + BI). |
| Datos | **Pandas / NumPy** | Manipulación y normalización de datos, vectorización para Monte Carlo. |
| Visualización | **Plotly** | Gráficos interactivos (radar, bracket, líneas, scatter) nativos en Streamlit, con hover/zoom gratis. |
| Almacenamiento | **CSV** (SQLite opcional) | Cero infraestructura, versionable en Git, suficiente para 32-48 selecciones. |
| Scraping | `requests` + `BeautifulSoup` (+ `cloudscraper`/`selenium` si necesario) | Mínima dependencia, fácil de depurar. |

### Por qué es la mejor opción para 7 días
- Cero curva de aprendizaje de frontend (no hay que tocar React/JS).
- Un solo lenguaje (Python) para ETL, modelo y UI → todo el código vive en el mismo repo y mismo entorno.
- Plotly + Streamlit cubren el 90% de los requisitos visuales (radar, bracket, líneas, barras, scatter) sin librerías extra.
- Despliegue gratuito y prácticamente sin configuración (Streamlit Cloud lee directamente un repo de GitHub).

### Limitaciones
- Streamlit no es ideal para animaciones muy elaboradas o interacciones tipo "drag and drop" — se prioriza claridad sobre espectacularidad.
- Recarga de página completa en cada interacción (mitigado con `st.cache_data` y `st.session_state`).
- Streamlit Cloud free tier tiene límites de recursos (RAM/CPU) — relevante para Monte Carlo: usar 10.000 simulaciones por defecto en la app, 50.000 solo en el cálculo offline (`update_all.py`) cuyo resultado se guarda y se lee.
- Concurrencia limitada en el plan gratuito si el tráfico es alto (riesgo real si el bracket se vuelve viral) — mitigación: cachear agresivamente, evitar recomputar Monte Carlo por usuario.

## Despliegue gratuito

### Flujo
1. Repo en **GitHub** (público, lo que además da credibilidad/visibilidad al proyecto).
2. **Streamlit Community Cloud** conectado al repo → cada `git push` a `main` redespliega automáticamente.
3. Los CSV de `data/processed/` y `data/results/` se versionan en el propio repo (son pequeños — decenas de KB a pocos MB).
4. Actualización de datos: ejecutar `update_all.py` localmente, hacer `git commit` + `git push` de los CSV actualizados → Streamlit Cloud recoge el cambio automáticamente.

### Simplicidad del sistema
- No hay servidor propio, no hay base de datos gestionada, no hay variables de entorno complejas (a lo sumo, ninguna o un user-agent para scraping).
- "Base de datos" = archivos CSV en Git → diff legible, rollback trivial (`git revert`).

### Coste 0€
- GitHub: gratis (repo público).
- Streamlit Community Cloud: gratis para apps públicas.
- Fuentes de datos (eloratings.net, datasets públicos, Transfermarkt scraping): gratis.

### Mantenimiento mínimo
- Una sola tarea recurrente: ejecutar `update_all.py` y hacer push (manual, ~5 min/día durante el Mundial).
- Opcional (no bloqueante): GitHub Action programada que ejecute `update_all.py` y commitee automáticamente — elimina incluso esos 5 minutos, pero añade una capa de configuración que puede dejarse para después del día 7.

## Viralidad y shareability

### Mecanismos de compartir
- **Botones de "compartir"** en cada tarjeta/insight clave (predicción de equipo, bracket, upset, ranking) que generan un texto pre-formateado + enlace directo a esa vista (usar query params de Streamlit, `st.query_params`, para deep-linking a una selección/vista concreta).
- **Generación de imagen** (opcional, día 7 si hay tiempo): exportar la tarjeta de equipo o el bracket como imagen (Plotly `to_image` con `kaleido`) para descarga/compartir directo en redes visuales (Instagram).

### Optimización por plataforma
- **X (Twitter)**: texto corto + dato impactante + enlace. Formato ideal: *"🇯🇵 Japón tiene un 32% de probabilidad de eliminar a Inglaterra en octavos según nuestro modelo WPI. [enlace al bracket]"*.
- **LinkedIn**: enfoque "data story" — post explicando la metodología (WPI) y un hallazgo (equipo infravalorado), apelando a audiencia de analytics/data.
- **Instagram**: imagen del bracket o de la tarjeta de equipo (radar chart), formato cuadrado/vertical, texto mínimo en la imagen.
- **Reddit** (r/soccer, r/dataisbeautiful, r/MachineLearning): post mostrando la metodología y pidiendo feedback — la transparencia del modelo (pesos del WPI documentados) encaja muy bien con la cultura de estos subreddits.

### Ideas de contenido viral basadas en el modelo
1. "El modelo predice que [equipo] tiene más probabilidades de ganar el Mundial que [favorito tradicional] — así calculamos el WPI."
2. Ranking diario de "mayores subidas/bajadas" de probabilidad tras cada jornada (genera contenido recurrente, no solo un post único).
3. Top 5 "upsets" más probables de la siguiente ronda, actualizado cada día.
4. Comparativa "WPI vs. casas de apuestas" (sin promover apuestas, solo como validación del modelo).
5. Hilo explicando la metodología completa (Elo + mercado + Monte Carlo) como contenido educativo de data science aplicado.
