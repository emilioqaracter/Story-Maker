# Lectura humana frente al Jurado (LLM-as-judge)

Novela `novela-prueba`, version 1 del manuscrito, leida por revisor 1 con las rubricas version 1. Generada por `python -m evals.human_vs_jury` (RF-271): no se edita a mano.

El Jurado es el ultimo veredicto aprobado de cada capitulo. Sin umbral de acuerdo (D-95); una diferencia de 2 o mas es el rango que ya invalida un veredicto del Jurado (D-39).

| Dimension | Capitulos | Media humana | Media del Jurado | Diferencia media absoluta | Capitulos con diferencia de 2 o mas |
|---|---|---|---|---|---|
| `voice` | 2 | 3.50 | 3.50 | 0.00 | ninguno |
| `style_guide` | 2 | 4.00 | 4.00 | 0.00 | ninguno |
| `pacing` | 2 | 2.00 | 3.50 | 1.50 | 1 |
| `subtext` | 2 | 3.50 | 4.50 | 1.00 | 2 |
| `theme` | 1 | 3.00 | 4.00 | 1.00 | ninguno |

## Por capitulo

| Capitulo | Dimension | Humano | Jurado | Diferencia |
|---|---|---|---|---|
| 1 | `voice` | 3 | 3 | +0 |
| 1 | `style_guide` | 4 | 4 | +0 |
| 1 | `pacing` | 1 | 3 | -2 |
| 1 | `subtext` | 4 | 4 | +0 |
| 1 | `theme` | 3 | 4 | -1 |
| 2 | `voice` | 4 | 4 | +0 |
| 2 | `style_guide` | 4 | 4 | +0 |
| 2 | `pacing` | 3 | 4 | -1 |
| 2 | `subtext` | 3 | 5 | -2 |

## Fuera de la comparacion

- Capitulo 2, `theme`: el veredicto aprobado no tiene nivel de esa dimension.
