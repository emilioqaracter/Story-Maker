# Lectura humana frente al Jurado (LLM-as-judge)

Novela `eval-01`, version 1 del manuscrito, leida por revisor 1 con las rubricas version 2. Generada por `python -m evals.human_vs_jury` (RF-271): no se edita a mano.

El Jurado es el ultimo veredicto aprobado de cada capitulo. Sin umbral de acuerdo (D-95); una diferencia de 2 o mas es el rango que ya invalida un veredicto del Jurado (D-39).

| Dimension | Capitulos | Media humana | Media del Jurado | Diferencia media absoluta | Capitulos con diferencia de 2 o mas |
|---|---|---|---|---|---|
| `voice` | 3 | 5.00 | 3.67 | 1.33 | 2 |
| `style_guide` | 3 | 5.00 | 3.33 | 1.67 | 1, 2 |
| `pacing` | 3 | 5.00 | 3.67 | 1.33 | 2 |
| `subtext` | 3 | 5.00 | 3.00 | 2.00 | 1, 2, 3 |
| `theme` | 3 | 5.00 | 3.00 | 2.00 | 1, 2, 3 |
| `continuity` | 3 | 5.00 | 3.33 | 1.67 | 1, 2 |
| `tone` | 0 | — | — | — | ninguno |
| `arc` | 3 | 5.00 | 4.00 | 1.00 | ninguno |
| `personalization` | 0 | — | — | — | ninguno |

## Por capitulo

| Capitulo | Dimension | Humano | Jurado | Diferencia |
|---|---|---|---|---|
| 1 | `voice` | 5 | 4 | +1 |
| 1 | `style_guide` | 5 | 3 | +2 |
| 1 | `pacing` | 5 | 4 | +1 |
| 1 | `subtext` | 5 | 3 | +2 |
| 1 | `theme` | 5 | 3 | +2 |
| 1 | `continuity` | 5 | 3 | +2 |
| 1 | `arc` | 5 | 4 | +1 |
| 2 | `voice` | 5 | 3 | +2 |
| 2 | `style_guide` | 5 | 3 | +2 |
| 2 | `pacing` | 5 | 3 | +2 |
| 2 | `subtext` | 5 | 3 | +2 |
| 2 | `theme` | 5 | 3 | +2 |
| 2 | `continuity` | 5 | 3 | +2 |
| 2 | `arc` | 5 | 4 | +1 |
| 3 | `voice` | 5 | 4 | +1 |
| 3 | `style_guide` | 5 | 4 | +1 |
| 3 | `pacing` | 5 | 4 | +1 |
| 3 | `subtext` | 5 | 3 | +2 |
| 3 | `theme` | 5 | 3 | +2 |
| 3 | `continuity` | 5 | 4 | +1 |
| 3 | `arc` | 5 | 4 | +1 |

## Fuera de la comparacion

- Capitulo 1, `tone`: el veredicto aprobado no tiene nivel de esa dimension.
- Capitulo 1, `personalization`: el veredicto aprobado no tiene nivel de esa dimension.
- Capitulo 2, `tone`: el veredicto aprobado no tiene nivel de esa dimension.
- Capitulo 2, `personalization`: el veredicto aprobado no tiene nivel de esa dimension.
- Capitulo 3, `tone`: el veredicto aprobado no tiene nivel de esa dimension.
- Capitulo 3, `personalization`: el veredicto aprobado no tiene nivel de esa dimension.

<!-- lectura a mano: debajo de esta linea no se regenera -->

## Lectura a mano

**Procedencia de la lectura.** Los niveles de `evals/human/eval-01.json` los fijó el usuario: 5 en todas las dimensiones de los tres capítulos. Las 27 citas literales (de párrafos que no se repiten) y las justificaciones las eligió y redactó Claude a petición del usuario. Por eso esta comparación no mide un juicio humano independiente dimensión a dimensión: mide la distancia entre una valoración global máxima del usuario y el Jurado.

**Lectura.** El Jurado puntúa entre 3 y 4 donde el usuario pone 5: la diferencia media va de 1,00 (`arc`) a 2,00 (`subtext`, `theme`). Las dos dimensiones en las que el Jurado es más severo, subtexto y tema, son las más interpretativas. `tone` y `personalization` quedan fuera porque el brief 01 no trae tono ni destinatario (D-114).

**Defecto de la novela visto al leerla.** En cada capítulo un párrafo aparece dos veces seguidas en el texto leído (capítulo 1, «Dani esperó…»; capítulo 2, «En el minuto quince…»; capítulo 3, «La advertencia de Dani…» y «En el peso del silencio…»). Es el solape de fragmentos que `manuscript._current_texts` no quita (ya anotado como riesgo en `backend/PLAN.md` §6): ningún validador del ciclo lo ve, porque miran la escena y no el texto unido.
