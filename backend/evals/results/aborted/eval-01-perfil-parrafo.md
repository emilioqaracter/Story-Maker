# eval-01 con el perfil de un párrafo · tirada abortada

Primer intento de la tirada de `01-semilla` para T52 (RF-272). Corrió sobre `ola4-base` (commit `69d605e`), con el perfil `prueba` de entonces: 3 capítulos de 1 escena de 100 a 170 palabras. Empezó a las 10:03:32 UTC y la integradora la mató a las 10:49 sin que hubiera congelado el capítulo 1. Cuenta como **fallo cerrado**, no como resultado de la novela. De ella salen los dos primeros hallazgos de las tiradas reales, que ya están corregidos: D-113, el perfil de 3 capítulos de unas 500 palabras, y D-114, el Jurado sin `personalization` cuando no hay destinatario.

El extracto de su traza, con el formato de `evals.brief_table`, está en [`eval-01-perfil-parrafo.json`](eval-01-perfil-parrafo.json). Va aparte de `evals/results/traces/` para que no entre en la tabla de los cinco briefs, porque corrió sobre otro commit y otro perfil. Para regenerar su fila: `python -m evals.brief_table table --extracts evals/results/aborted --out <salida>.md`.

## Coste, medido en su traza

| Agente | Llamadas | Tokens de entrada | Tokens de salida | Minutos de modelo | USD |
|---|---|---|---|---|---|
| juez | 75 | 3.065.658 | 530.263 | 81,4 | 4,744 |
| continuista | 6 | 292.003 | 21.441 | 3,8 | 0,408 |
| arquitecto | 3 (2 ok) | 123.708 | 23.700 | 3,4 | 0,261 |
| reparador | 4 | 151.601 | 14.491 | 2,3 | 0,210 |
| lector | 6 | 235.789 | 4.799 | 1,4 | 0,157 |
| escritor | 3 | 119.505 | 2.866 | 0,7 | 0,086 |
| planificador | 2 | 80.453 | 5.277 | 0,8 | 0,076 |
| **Total** | **99** | **4.068.717** | **602.837** | **93,9** | **5,942** |

El reloj de pared fue de 44,2 minutos, entre el primer y el último registro. Los minutos de modelo superan a los de pared porque las tres instancias del Jurado van en paralelo. Los USD son el `cost_usd` que el CLI informa por llamada: la tirada va sobre la suscripción y ese coste no se factura.

## Qué pasó

El capítulo 1 llegó seis veces a la puerta de capítulo, que pasó cinco, y el Jurado lo suspendió en las cinco rondas que se llegaron a hacer. La escalera se agotó hasta `cuarentena-y-replanificar-tramo` (10:47:13), y la tirada murió replanificando.

| Hora | Jurado del capítulo 1 | Citas descartadas |
|---|---|---|
| 10:10 | voice 2, style_guide 4, pacing 3, subtext 2, theme 2, continuity 4, tone 4, arc 3, **personalization 1** | 0 |
| 10:19 | theme sin nivel; personalization 3 y el resto de 3 a 4 | 9 |
| 10:28 | voice, style_guide, subtext, tone y personalization sin nivel | 12 |
| 10:37 | subtext 2, **personalization 2** | 2 |
| 10:47 | voice, theme y personalization sin nivel | 6 |

**Hallazgo 1, el perfil de un párrafo (D-113).** Con escenas de 150 palabras, el Jurado tiene que dar nueve citas de 8 palabras o más, cada una única en la escena (`verification/checks/evidence.py`, `MIN_QUOTE_WORDS`). Recorta con «[...]» o repite frases, y las citas no anclan: 48 reintentos de llamada del juez por «cita(s) sin anclar» y 29 citas descartadas como `process.defect`. Una dimensión sin tres puntuaciones ancladas, o con demasiada dispersión entre ellas, queda sin nivel, y sin nivel cuenta como bajo umbral. El juez hizo el 75 % de los tokens de entrada y el 87 % de los minutos de modelo.

**Hallazgo 2, `personalization` sin destinatario (D-114).** `01-semilla` no tiene `recipient`. El encargo que recibía el Jurado decía «Destinatario: (sin destinatario)» (`verification/jury/prompts.py`, `commission_text`), pero se le pedía puntuar las nueve dimensiones. `personalization` salió 1, 3, sin nivel, 2 y sin nivel en las cinco rondas: un juicio sin objeto, que cae bajo el umbral en cuatro de cinco, y es S2 (D-94). El segundo intento, ya con D-113, lo confirmó sin ruido de citas: a las 11:27:26 el Jurado dio 3 o 4 en todo, con 0 citas descartadas, y 1 en `personalization`. Ese capítulo no podía pasar nunca. Le habría pasado lo mismo a la semilla de T16, `golden/v1-seed`, que tampoco tiene destinatario.

Los dos se corrigieron en `v2-oneshot` y la serie de los cinco briefs se relanzó sobre `8352c6d` (`ola4-base-3`).
