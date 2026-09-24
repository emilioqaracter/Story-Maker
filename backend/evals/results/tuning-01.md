# Iteración de tuning 01 · el Jurado y el Especialista en el perfil `prueba`

`specs/srs-backend-v4.md` RF-272 y D-128. Un brief repetido, `01-semilla`, antes y después de publicar versiones nuevas de los prompts del juez, el Especialista y el Arquitecto. VER-10, VER-16.

## Qué se cambió

| Agente | `prompt_version` antes | después | Cambio |
|---|---|---|---|
| juez | `7fe707a80eb1` | `742b19fab78d` | Pide copiar la cita de una sola frase, sin recortar ni unir frases, sin comillas añadidas y con su puntuación original |
| especialista | `e74fc875b5f6` | `41fcc6dfbad0` | Lleva el resultado tal como lo comprueba `check.ledger`: marcador final en cifras con el local primero, como única pareja de cifras; goleadores con nombre completo y minuto; última frase con el marcador |
| arquitecto | `4466609c77c5` | `dac47a65d9f1` | La replanificación recibe la forma del perfil y el presupuesto de palabras (D-129) |

Con los prompts cambiaron dos números del perfil `prueba`: el Jurado aprueba una dimensión con mediana 2 en vez de 3, y la cita mínima baja de 8 a 5 palabras (D-128). En `novela` no cambia nada.

## Antes y después

Ambas tiradas usan el brief `01-semilla`, el perfil `prueba` (3 capítulos de 1 escena de unas 500 palabras) y el modelo `haiku`. Datos de `python -m evals.compare`, en [`tuning-01.json`](tuning-01.json).

| Métrica | Antes · `eval-01-umbral3` | Después · `eval-01` |
|---|---|---|
| Capítulos congelados | **1 de 3** | **3 de 3** |
| Palabras congeladas | 907 | 1.423 |
| Defectos por 1.000 palabras | 13,2 | **4,2** |
| S1 por 1.000 palabras | 12,1 | **4,2** |
| Tasa de reparación | 1,00 | **0,33** |
| Cuarentenas | 1 | **0** |
| Replanificaciones | 4 | 1 |
| Citas descartadas | 2 | 5 |
| Llamadas al modelo | 54 | 127 |
| Reintentos de llamada del juez | 10 | 41 |
| Coste | 2,77 USD | 6,54 USD (2,18 por capítulo, frente a 2,77) |
| Reloj de pared | 32 min, parada a mano sin cerrar | 60 min, cortada por el tope en el conjunto dorado del cierre |

**Medias del Jurado por dimensión**

| | arc | continuity | pacing | style_guide | subtext | theme | voice |
|---|---|---|---|---|---|---|---|
| Antes | 3,0 | 4,0 | 4,0 | 4,0 | 3,0 | 3,0 | 3,0 |
| Después | **4,0** | 3,3 | 3,7 | 3,3 | 3,0 | 3,0 | **3,7** |

`evals.compare` marca como peores `continuity`, `pacing` y `style_guide`. Antes son la media de un solo capítulo. Después son la de tres, y el umbral de aprobación bajó a 2.

## Lectura

- **El tuning cumplió lo que buscaba: que el ciclo termine.** Antes, el capítulo 2 agotaba la escalera. El encuentro suspendía por `check.ledger` S1 (la prosa daba marcadores parciales en cifras), y el capítulo acababa en cuarentena y replanificación. Después, los tres capítulos se congelan sin cuarentenas, con un tercio de defectos por palabra y una sola reparación.
- **No cumplió: bajar el coste del Jurado.** Los reintentos del juez por cita sin anclar pasan de 10 a 41: con tres capítulos juzgados en vez de uno, sigue siendo el agente que más gasta, con el 67 % del coste. Queda como hallazgo abierto, no corregido.
- **La tirada de después no cerró la obra.** El tope de 60 min la cortó en el conjunto dorado del cierre (5 casos de Jurado sobre la obra entera). Eso dio D-131: en `prueba`, el conjunto dorado del cierre es de 1 caso.

## Hallazgos de las tiradas reales

| Decisión | Hallazgo | Corrección |
|---|---|---|
| D-113 | Con escenas de un párrafo, las citas del Jurado no anclan: 48 reintentos y 29 citas descartadas ([`aborted/eval-01-perfil-parrafo.md`](aborted/eval-01-perfil-parrafo.md)) | Perfil de 3 capítulos de unas 500 palabras |
| D-114 | `personalization` sin destinatario no puede pasar nunca | El Jurado no la puntúa sin destinatario ni elementos, ni `tone` sin tono |
| D-128 | Jurado lento y encuentro suspendido por marcadores parciales | Esta iteración |
| D-129 | La replanificación salía del perfil | La réplica recibe forma y presupuesto |
| D-130 | Un hecho sobre una entidad desconocida tumbaba la congelación por FK | Se descarta como S2 `unknown-entity` y la congelación sigue |
| D-131 | El conjunto dorado del cierre agotaba el tope | 1 caso en `prueba` |

**Regenerar la comparación**

```
cd backend
python -m evals.compare \
  --reference runs-evals/antes-tuning/eval-01-umbral3.sqlite \
  --reference-trace runs-evals/antes-tuning/eval-01-umbral3.trace.jsonl \
  --candidate runs-evals/eval-01.sqlite --candidate-trace runs-evals/eval-01.trace.jsonl \
  > evals/results/tuning-01.json
```

Las tiradas viven en `runs-evals/`, fuera de git.
