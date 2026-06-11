# 03 — Modelo WPI y Motor Monte Carlo

## 1. World Predictor Index (WPI)

### Variables de entrada (todas normalizadas 0-1, ver `02_ARQUITECTURA_DATOS_ETL.md`)

| Grupo | Variable | Símbolo |
|---|---|---|
| Deportivas | Elo Rating normalizado | `elo_n` |
| Deportivas | Ranking FIFA normalizado (invertido: nº1 = 1.0) | `fifa_n` |
| Deportivas | Forma últimos 10 partidos (puntos/30) | `form_n` |
| Mercado | Valor total de plantilla normalizado | `value_n` |
| Mercado | Valor medio por jugador normalizado | `value_avg_n` |
| Estructurales | % jugadores en ligas top-5 | `top5_n` |
| Estructurales | Edad media (óptimo ~26-27, penaliza extremos) | `age_n` |

### Ponderaciones propuestas (justificación)

```
WPI = 0.30 * elo_n
    + 0.20 * fifa_n
    + 0.15 * form_n
    + 0.15 * value_n
    + 0.05 * value_avg_n
    + 0.10 * top5_n
    + 0.05 * age_n
```

Justificación:
- **Elo (30%)**: es el predictor individual más robusto y validado para fútbol de selecciones (mejor que el ranking FIFA por separado, según múltiples estudios de sports analytics).
- **Ranking FIFA (20%)**: complementa al Elo con la "vara de medir" oficial usada para bombos/sorteos, y captura algo de inercia institucional.
- **Forma reciente (15%)**: corrige el "momentum" — un equipo puede tener buen Elo histórico pero llegar de baja forma.
- **Valor total de plantilla (15%)**: proxy de calidad/profundidad de plantilla — el componente "de mercado" central, justifica el scraping.
- **Valor medio por jugador (5%)**: matiza el valor total (una plantilla cara pero con pocas estrellas vs. plantilla con superestrellas).
- **% jugadores en ligas top-5 (10%)**: proxy de nivel competitivo habitual de los jugadores.
- **Edad media (5%)**: penaliza levemente plantillas demasiado jóvenes (inexperiencia) o demasiado veteranas (desgaste). Función en forma de "campana" centrada en ~26 años, no lineal.

> Estos pesos son un punto de partida razonable y defendible, no un resultado de optimización estadística (no hay tiempo en 7 días para backtesting riguroso). Documentar esto explícitamente en la app ("metodología") da transparencia y es parte del valor diferencial frente a "cajas negras".

### Edad media → función campana

```python
def age_score(avg_age, optimal=26.5, spread=4):
    return np.exp(-((avg_age - optimal) ** 2) / (2 * spread ** 2))
```
Esto da `age_n` cercano a 1 para edades cercanas a 26.5 y decae suavemente hacia los extremos.

### De WPI a probabilidad de partido (Bradley-Terry / Elo-style)

Para dos selecciones A y B con `WPI_A` y `WPI_B`, la probabilidad de que A gane (sin contar empates) se calcula con la fórmula logística estilo Elo:

```python
def win_probability(wpi_a, wpi_b, k=10):
    diff = (wpi_a - wpi_b) * 100  # escalar a rango tipo Elo
    return 1 / (1 + 10 ** (-diff / (k * 40)))
```

Para incluir el **empate** (relevante en fase de grupos), se usa un modelo de resultado discreto basado en distribución de Poisson para los goles esperados de cada equipo, donde el "gol esperado" (`xG` proxy) se deriva del WPI relativo:

```python
def expected_goals(wpi_a, wpi_b, base_goals=1.3):
    # equipo con mayor WPI relativo anota más de la media histórica (~1.3 goles/equipo)
    strength_diff = wpi_a - wpi_b
    return base_goals * (1 + strength_diff), base_goals * (1 - strength_diff)
```

Luego se simula el marcador con `np.random.poisson(lambda_a)` y `np.random.poisson(lambda_b)` → si hay empate y la fase requiere desempate (eliminatorias), se decide con `win_probability` (representando penaltis/prórroga).

## 2. Motor Monte Carlo

### Algoritmo

```
PARA cada simulación (1..N, N entre 10.000 y 50.000):
    1. Copiar estructura del torneo (grupos + fixture de eliminatorias)
    2. FASE DE GRUPOS:
       - Para cada partido del calendario de grupos:
           simular marcador (Poisson con lambdas según WPI)
           asignar puntos (3/1/0)
       - Calcular clasificación de cada grupo (puntos, dif. de goles, goles a favor)
       - Determinar 1º y 2º de cada grupo (+ mejores terceros si aplica formato 48 selecciones)
    3. FASE ELIMINATORIA:
       - Construir bracket de octavos según cruces reales del formato del Mundial
       - Para cada eliminatoria:
           simular marcador; si empate, usar win_probability() para decidir ganador
       - Avanzar ganadores hasta la final
    4. Registrar para esta simulación: equipo eliminado en grupos / octavos / cuartos / semis / finalista / campeón

DESPUÉS de las N simulaciones:
    Para cada selección, probabilidad(fase) = (nº simulaciones donde llegó al menos a esa fase) / N
```

### Salidas requeridas

Por cada selección: `prob_fase_grupos` (siempre 100% trivialmente — se reporta más bien `prob_avanza_grupos`), `prob_octavos`, `prob_cuartos`, `prob_semis`, `prob_final`, `prob_campeon`.

### Optimización para Streamlit

- **Vectorización con NumPy**: en vez de un bucle Python por partido y por simulación (lento para 50.000 iteraciones × ~50-60 partidos), vectorizar generando matrices de goles con `np.random.poisson(lambda_matrix, size=(N, n_partidos))` de una vez para toda la fase de grupos.
- **`st.cache_data`**: cachear el resultado de la simulación completa (`run_simulation(teams_master_hash, n_sims)`), para que no se recalculen 50.000 simulaciones en cada interacción del usuario con la UI.
- **Reducción dinámica de N**: usar 10.000 simulaciones para interacciones en tiempo real (slider, "qué necesita mi selección") y permitir 50.000 para el cálculo "oficial" diario (`update_all.py`, guardado en `results/simulation_results.csv`), que la app lee directamente sin recalcular.
- **Pre-cómputo del bracket fijo**: si el formato de cruces del Mundial es conocido de antemano, pre-generar la estructura de árbol una sola vez y reutilizarla en todas las simulaciones.
- **Límite de tiempo objetivo**: 10.000 simulaciones vectorizadas deben ejecutarse en segundos (<5s) en hardware modesto — suficiente para interacciones en vivo del simulador manual.
