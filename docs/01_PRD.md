# 01 — PRD: World Cup Predictor Pro

## Problema que resuelve

Durante un Mundial, los aficionados consumen previsiones dispersas (rankings FIFA, casas de apuestas, modelos de medios como FiveThirtyEight) que son poco transparentes, no interactivas y no permiten "jugar" con escenarios ("¿qué pasa si España gana mañana?"). No existe una herramienta gratuita, visual y abierta que combine datos deportivos y de mercado en un índice propio y permita simular el torneo en tiempo real.

## Propuesta de valor

"La probabilidad de que tu selección sea campeona del mundo, recalculada en tiempo real, con un índice propio (WPI) que combina rendimiento deportivo y valor de mercado — y que te deja simular tú mismo los resultados."

Diferenciales:
- **WPI propio**: combina Elo + Ranking FIFA + forma + datos de Transfermarkt (no solo Elo, como la mayoría de modelos abiertos).
- **Interactividad real**: bracket dinámico, simulador manual, "¿qué necesita mi selección?".
- **Gratis y abierto**: sin paywall, sin cuenta.
- **Shareable**: cada resultado (predicción, upset, bracket) es una pieza de contenido lista para redes.

## Público objetivo

- Aficionados al fútbol que siguen el Mundial y quieren más profundidad que un ranking estático.
- Comunidades de "sports analytics" / fantasy football / apuestas deportivas (uso informativo, no apuesta real).
- Creadores de contenido deportivo que buscan gráficos/datos para compartir.
- Perfil técnico secundario: otros desarrolladores/data people interesados en el modelo (potencial repo open source).

## Casos de uso

1. Un usuario entra el día del sorteo/inicio del Mundial y ve el ranking de favoritos al título.
2. Un usuario busca su selección y ve su "ficha" (WPI, Elo, ranking FIFA, valor de mercado, jugador más valioso, probabilidad de campeón/semis/etc.).
3. Un usuario abre el bracket interactivo y ve probabilidades en cada cruce posible.
4. Tras una jornada, el usuario consulta cómo cambiaron las probabilidades de su equipo (evolución temporal).
5. Un usuario quiere saber "¿qué necesita España para subir al 20% de probabilidad de ganar?" y usa el selector de escenarios.
6. Un usuario introduce un resultado hipotético (España 2-1 Alemania) y ve cómo se recalcula todo el torneo.
7. Un usuario consulta el "Upset Detector" para ver qué sorpresas son más probables en la próxima ronda.
8. Un usuario compara WPI vs Elo vs valor de mercado para detectar selecciones infra/sobrevaloradas y comparte el hallazgo en redes.

## Funcionalidades — Priorización MoSCoW

| Funcionalidad | Valor para el usuario | Complejidad | Prioridad |
|---|---|---|---|
| Cálculo del WPI por selección | Alto — es la base de todo el producto | Media | **Must** |
| Motor Monte Carlo (probabilidades por ronda y campeón) | Alto — núcleo del producto | Alta | **Must** |
| Dashboard / Ranking de campeones | Alto — primera impresión, muy visual | Baja | **Must** |
| Tarjetas por selección (ficha de equipo) | Alto — profundidad sin complejidad | Baja-Media | **Must** |
| ETL básico (Elo, ranking FIFA, resultados históricos) | Alto — sin datos no hay modelo | Media | **Must** |
| Scraping Transfermarkt (valor plantilla, edad, jugador top) | Alto — diferencial del producto | Alta | **Must** |
| Bracket interactivo del Mundial | Alto — pieza más visual y viral | Alta | **Should** |
| Simulador manual de partidos | Medio-Alto — alta interactividad | Media | **Should** |
| "¿Qué necesita mi selección?" (selector de escenarios) | Medio-Alto — muy compartible | Media | **Should** |
| Upset Detector | Medio — insight llamativo para redes | Media | **Should** |
| Evolución temporal (gráfico histórico de probabilidades) | Medio — requiere histórico acumulado | Media-Alta | **Could** |
| Equipos infra/sobrevalorados (WPI vs Elo vs mercado) | Medio — analítico, para usuarios avanzados | Baja-Media | **Could** |
| Mecanismos de compartir (botones, imágenes generadas) | Medio — crecimiento orgánico | Media | **Could** |
| Animaciones avanzadas / transiciones | Bajo — "nice to have" visual | Media | **Won't** (en v1) |
| Cuentas de usuario / personalización guardada | Bajo para v1 — no aporta al MVP | Alta | **Won't** |
| Predicciones en vivo durante partidos (in-play) | Alto pero fuera de alcance de 7 días | Muy alta | **Won't** |

## Funcionalidades MVP (entregable día 3-4)

Conjunto mínimo para tener "algo funcional y demostrable":
1. ETL inicial cargado (Elo, ranking FIFA, resultados históricos, scraping Transfermarkt básico) → CSVs.
2. Cálculo del WPI por selección.
3. Motor Monte Carlo (versión reducida, p.ej. 10.000 simulaciones) generando probabilidades de campeón.
4. Dashboard con ranking de campeones + tarjeta básica por selección.

El resto de funcionalidades (bracket interactivo, simulador, upset detector, etc.) se añaden en los días 5-7 (ver `06_ROADMAP_7DIAS.md`).
