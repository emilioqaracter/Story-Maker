# Bitácora de la automejora

Una fila por novela. La escribe la sesión que afina siguiendo la skill
`automejora`; `/goal` la lee para saber si el loop terminó. Qué significa
cada columna está en [SPEC-AUTOMEJORA-TECNICO.md](../SPEC-AUTOMEJORA-TECNICO.md) §5.

**Corte entre la novela 2 y la 3.** Después de la 2 se cambiaron a mano los
jueces y el redactor (commit `05bf0bf`): el redactor revisa su propio borrador
antes de entregarlo, y la lección de los jueces se escribe para acabar copiada
en sus instrucciones y ya no habla de erratas. La regla que dejó la novela 2
quedó absorbida en ese cambio. Las novelas 1 y 2 corrieron con el sistema
anterior, así que la comparación final de §8 no es de nueve contra nueve con el
mismo sistema: las tres primeras miden el sistema viejo.

| Novela | Fecha | Idea | Regla que traía | Entran | Rojas rev. | Rojas ver. | Intentos | Terminó | Lección más repetida | Regla nueva | Decisión |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-18 | Nadadora de 15 años, Barcelona 1972, Múnich | ninguna | 0 | 4 | 2 | 7 | sí | El cierre explica el significado en vez de mostrarlo (3 lecciones; 1 descartada por nombrar la historia) | El último párrafo se queda dentro de la escena · `ed02d8b` | sin regla |
| 2 | 2026-09-18 | Pelotari de Guipúzcoa, 1976, final contra su aprendiz | El último párrafo se queda dentro de la escena | 0 | 3 | 1 | 3 | no | Releer el capítulo antes de entregarlo: frases a medias y términos que cambian de género (2 lecciones) | Relee el capítulo entero antes de entregarlo · `41334ea` | se revierte (`392b4a9`) |
| 3 | 2026-09-18 | Árbitro de Segunda, 1981, da por bueno un gol que no fue | Antes de entregar: el redactor se revisa solo (rediseño `05bf0bf`) | escribiendo |  |  |  |  |  |  |  |
