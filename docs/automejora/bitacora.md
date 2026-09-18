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

**Segundo corte, entre la novela 4 y la 5.** Commit `5a29806`: toda luz verde
termina con un refuerzo, y la lección de los jueces nombra la capacidad general
en vez de la situación en que falló. Las novelas 1 a 4 corrieron con jueces que
callaban en verde y daban lecciones atadas al caso.

| Novela | Fecha | Idea | Regla que traía | Entran | Rojas rev. | Rojas ver. | Intentos | Terminó | Lección más repetida | Regla nueva | Decisión |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-18 | Nadadora de 15 años, Barcelona 1972, Múnich | ninguna | 0 | 4 | 2 | 7 | sí | El cierre explica el significado en vez de mostrarlo (3 lecciones; 1 descartada por nombrar la historia) | El último párrafo se queda dentro de la escena · `ed02d8b` | sin regla |
| 2 | 2026-09-18 | Pelotari de Guipúzcoa, 1976, final contra su aprendiz | El último párrafo se queda dentro de la escena | 0 | 3 | 1 | 3 | no | Releer el capítulo antes de entregarlo: frases a medias y términos que cambian de género (2 lecciones) | Relee el capítulo entero antes de entregarlo · `41334ea` | se revierte (`392b4a9`) |
| 3 | 2026-09-18 | Árbitro de Segunda, 1981, da por bueno un gol que no fue | Antes de entregar: el redactor se revisa solo (rediseño `05bf0bf`) | 2 | 0 | 1 | 4 | sí | Subrayar una imagen que ya cargó el sentido (2 lecciones; vecina de la regla revertida en la 1, pero no solo del cierre) | Una imagen que ya cargó el sentido no se subraya · `6ceb4a9` | se queda |
| 4 | 2026-09-18 | Boxeador de Vallecas, 1985, diez días para salvar el gimnasio | Una imagen que ya cargó el sentido no se subraya | 0 | 3 | 2 | 8 | sí | Repetir una fórmula ya usada: palabra, frase de golpe o imagen (4 de 13 lecciones) | Una fórmula no se usa dos veces · `e45efeb` | se revierte (`cffc3d3`) |
| 5 | 2026-09-18 | Ex atleta de 60 años, Montjuïc 1992, final de 1500 | Una fórmula no se usa dos veces | 1 | 3 | 2 | 7 | sí | Enunciar lo que el cuerpo ya muestra (5 de 12); descartada por probada y revertida en la 1 y la 3, se toma la siguiente: datos verificables que no cuadran (3) | Un dato ya fijado se usa tal como está · `5cede4c` | se queda |
| 6 | 2026-09-18 | Pívot de Badalona, 1996, el chaval es hijo del amigo muerto | Un dato ya fijado se usa tal como está | 1 | 3 | 1 | 7 | sí | Enunciar el significado que la acción ya muestra (8 de 13); se toma aunque la familia se revirtió en la 1 y la 3, por el ángulo nuevo del orden (evidencia antes que juicio) | Primero la evidencia, y la conclusión nunca · `6b9cfdb` | se queda |
| 7 | 2026-09-18 | Futbolista del Oviedo, 1999, el partido que decide el equipo femenino | Primero la evidencia, y la conclusión nunca | escribiendo |  |  |  |  |  |  |  |
