# 04 — Funcionalidades clave y diseño UX/UI

Estética de referencia: FiveThirtyEight (claridad de datos), FotMob/Sofascore (tarjetas de equipo y partido), Bloomberg sports (dashboards densos pero ordenados). Mobile-first, jerarquía: **ranking → selección → simulación**.

## Funcionalidades principales

### 1. Ranking de campeones
Tabla dinámica ordenada por `prob_campeon` desc. Columnas: bandera, selección, WPI, Elo, % campeón, % semifinales, tendencia (↑/↓ vs. snapshot anterior en `history_log.csv`). Implementación: `st.dataframe` con formato condicional o tabla custom con Plotly.

### 2. Bracket interactivo del Mundial
Árbol del torneo (octavos → final) renderizado con Plotly (shapes + annotations) o `st.graphviz_chart` simplificado. Cada cruce muestra el % de probabilidad de cada equipo de ganar ese partido, con color de fondo según favorito (gradiente verde→rojo según probabilidad). Click/selección de equipo resalta su camino hasta la final.

### 3. Evolución temporal
Gráfico de líneas (Plotly `line`) con `prob_campeon` por selección a lo largo de los snapshots diarios de `history_log.csv`. Selector múltiple de selecciones a comparar (máx. 5 para legibilidad).

### 4. "¿Qué necesita mi selección?"
Selector de equipo + próximo rival (o partido genérico). Muestra 3 escenarios (gana / empata / pierde) recalculando WPI ajustado temporalmente (+/- delta en `form_n`) y relanzando una simulación reducida (10.000) → nueva `prob_campeon` para cada escenario, con delta porcentual destacado (+2.3pp / -1.1pp, etc.).

### 5. Simulador manual de partidos
Formulario: equipo A, equipo B, marcador. El usuario fija resultados de partidos ya jugados o hipotéticos → el motor recalcula clasificaciones de grupo y relanza Monte Carlo desde ese punto fijado (los partidos fijados no se simulan, se usan como dados).

### 6. Upset Detector
Para cada cruce de la siguiente ronda (real o simulada), calcular la probabilidad de que el equipo "no favorito" (menor WPI) gane. Listar los top 5 cruces con mayor probabilidad de sorpresa (ej. >25%), con frase generada: *"Japón tiene un {pct}% de eliminar a Inglaterra"*.

### 7. Equipos infra/sobrevalorados
Scatter plot (Plotly) `WPI` (eje Y) vs. `valor de mercado normalizado` (eje X), con línea de regresión/diagonal de referencia. Equipos por encima de la diagonal = "rinden más de lo que su mercado sugiere" (infravalorados); por debajo = sobrevalorados. Tabla complementaria con el delta numérico.

## Pantallas

### Landing page
- **Layout**: hero con título, claim ("Probabilidades del Mundial en tiempo real"), CTA "Ver dashboard". Debajo, 3-4 datos destacados en tarjetas grandes (favorito actual, mayor sorpresa potencial, equipo más infravalorado).
- **Componentes**: hero, 3-4 `st.metric`/tarjetas, botón a dashboard.
- **Prioridad visual**: máxima — primera impresión, debe transmitir "esto es serio y bonito" en 3 segundos.

### Dashboard principal
- **Layout**: sidebar con filtros (confederación, fase), columna principal con ranking de campeones (tabla) arriba y, debajo, 2 columnas: gráfico de barras top 10 `prob_campeon` (Plotly) + mini-bracket o accesos directos a otras vistas.
- **Componentes**: tabla ranking, bar chart, tarjetas de acceso a Bracket/Simulador/Upset Detector.
- **Interacción**: clic en una fila del ranking → navega a "Vista selección".
- **Prioridad visual**: alta — es la pantalla más visitada.

### Vista selección
- **Layout**: cabecera con bandera, nombre, WPI grande y desglose (radar chart Plotly de las 7 variables normalizadas). Debajo: métricas de mercado (valor plantilla, jugador más valioso, edad media), probabilidades por fase (barras horizontales), y mini gráfico de evolución temporal de esa selección.
- **Componentes**: header, radar chart, métricas, barras de probabilidad por fase, line chart histórico.
- **Interacción**: selector de selección (dropdown o desde dashboard).
- **Prioridad visual**: alta — es donde el usuario "profundiza".

### Vista partido
- **Layout**: dos tarjetas de equipo enfrentadas (estilo FotMob), con WPI de cada uno, probabilidad de victoria/empate/derrota (barra horizontal de 3 segmentos), y comparación de variables clave (Elo, ranking FIFA, valor plantilla) lado a lado.
- **Componentes**: tarjetas enfrentadas, barra de probabilidad 1X2, tabla comparativa.
- **Interacción**: accesible desde el bracket (clic en un cruce) o selector manual de dos equipos.
- **Prioridad visual**: media-alta.

### Bracket
- **Layout**: pantalla dedicada, scroll horizontal en mobile, árbol completo en desktop. Cada nodo = "Vista partido" en miniatura.
- **Componentes**: árbol Plotly/custom, leyenda de colores, toggle "ver probabilidades" / "ver resultado más probable".
- **Interacción**: clic en cruce → expande detalle del partido.
- **Prioridad visual**: máxima — pieza más compartible/viral.

### Simulador
- **Layout**: formulario simple (selects + inputs numéricos para marcador) arriba, resultados recalculados (nuevo ranking de campeones + delta vs. el oficial) abajo.
- **Componentes**: formulario, tabla de deltas, botón "resetear a datos oficiales".
- **Interacción**: cada cambio recalcula con spinner de carga (Monte Carlo reducido a 10.000 para velocidad).
- **Prioridad visual**: media — funcional más que estética, pero debe sentirse "instantáneo".

## Notas de implementación en Streamlit

- Usar `st.tabs` o `st.sidebar` con `st.radio`/`st.selectbox` para navegación entre las 6 pantallas (Streamlit no tiene multi-página fluida nativa salvo `st.navigation`/`pages/`, usar esa estructura si la versión lo soporta).
- Animaciones: Plotly permite transiciones suaves en `update_layout` y `frames` para animaciones simples; evitar dependencias JS adicionales.
- Mobile-first: `st.columns` con proporciones que colapsen bien, gráficos con `use_container_width=True`, evitar tablas anchas con muchas columnas en vista por defecto (usar expanders).
