# Lectura de la tabla por brief

[`briefs.md`](briefs.md) se genera desde los extractos de `traces/` y no se edita. Esta es su lectura, escrita a mano (RF-272).

Las cinco tiradas corrieron **en paralelo** sobre `8deed8d`, con el perfil `prueba`, el modelo `haiku` y un tope común de 30 minutos (RNF-58). Los briefs están hechos para forzar el sistema: un fallo es un resultado y se registra sin corregirlo. **Ninguna de las cinco cerró la obra.**

| Brief | Minutos | Dónde se paró | Qué validador lo paró |
|---|---|---|---|
| 01-semilla | 3,3 | Planificación del capítulo 1 | El Planificador no especificó la escena `c1e1`. La salida no casa con la escaleta y la tirada se cae con un `ValueError` sin capturar. Es un hallazgo abierto: debería reintentar la llamada y no tumbar la tirada |
| 02-adversarial | 30,0 | Jurado del capítulo 1, cortada por el tope | Jurado: `theme`, `tone`, `arc` y `personalization` sin nivel, porque sus citas no anclaron; `check.format` marcó 2 veces y el Continuista 1 |
| 03-temporal | 15,7 | Jurado del capítulo 1 | La trampa se cazó: ver abajo. Después, el juez devolvió JSON inválido, se agotaron sus reintentos y la tirada se cayó con `OutputValidationError` |
| 04-menor | 3,0 | Escaleta | `outline.check`: `doble-arco-colapsado` en los 2 intentos, así que se aborta como fallo cerrado |
| 05-no-deportivo | 3,3 | Escaleta | El mismo `doble-arco-colapsado` en los 2 intentos |

## La trampa temporal · 03-temporal

**La cazó `check.timeline`**, el verificador determinista de fechas, antes de que ningún modelo leyera la escena: 3 S1 en los intentos 1 y 3 de `c1e1`, por fechas fuera del calendario de la obra. Tras el tercer intento, la escalera reespecificó la escena (`cuarentena-y-especificacion-mas-estricta`), que pasó en el intento 5 con 425 palabras y sin defectos. `check.format` marcó 4 veces en esos mismos intentos. `check.formal` (Lean) no llegó a correr, porque ningún capítulo llegó a congelarse. El caso que solo Lean detecta está en [`../formal/CASOS.md`](../formal/CASOS.md).

## El brief adversarial · 02-adversarial

La inyección del texto libre se probó aparte, sobre `brief.extract` real: [`adversarial-02.md`](adversarial-02.md). En la tirada, el guardarraíl no registró ninguna coincidencia (`guardrail.match`) y `check.forbidden` pasó en todas las escenas. El brief llegó al Jurado sin que la inyección entrara en la prosa.

## Hallazgos abiertos

- **Escaleta de 3 capítulos con doble arco (04 y 05).** Con el perfil `prueba`, el Arquitecto colapsa el arco exterior y el interior en uno. `outline.check` lo rechaza dos veces y la tirada se aborta.
- **Salidas mal formadas que tumban la tirada (01 y 03).** Una escena sin especificar o un JSON del juez con caracteres de sobra acaban en excepción y no en reintento. Aun así cuentan como fallo, así que la tirada no pasa en falso (`AGENTS.md` §5.3.6).
- **Jurado caro y lento.** Sigue siendo el agente que más reintenta (de 10 a 11 reintentos de llamada del juez en 02 y 03), como ya mostraba [`tuning-01.md`](tuning-01.md).
