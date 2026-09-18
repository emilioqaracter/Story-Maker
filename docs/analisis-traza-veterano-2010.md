# Análisis de la última traza — `veterano-2010`

Qué hizo el sistema cuando escribió *Cuarenta*, qué costó, y qué cambiaría yo
antes de la siguiente novela.

## La traza

| | |
|---|---|
| **Traza** | `a40cb200bd75d709b1de631bc151c5da` — "Claude Code Turn" |
| **Proyecto Langfuse** | `cmu5tos9r011oad0de26hskjq` ([abrir](https://cloud.langfuse.com/project/cmu5tos9r011oad0de26hskjq/traces/a40cb200bd75d709b1de631bc151c5da)) |
| **Cuándo** | 17 sep 2026, 18:09:42 → 18:27:09 UTC |
| **Qué produjo** | `books/veterano-2010/` — 3 capítulos, 1.517 palabras, novela cerrada |
| **Tamaño de la traza** | 199 observaciones: 89 llamadas al modelo, 94 herramientas, 16 subagentes |

La corrida terminó bien: los tres capítulos entraron con dos luces verdes cada
uno, ningún capítulo llegó al tercer intento, y ningún agente aprobó su propio
trabajo. **El círculo funciona.** Lo que sigue es sobre el precio que se paga
por que funcione.

## Los números

**Coste total: 3,02 USD. Tiempo de reloj: 17 min 28 s.** Eso son
**0,0020 USD por palabra publicada** y unos 35 segundos por cada 50 palabras.

### A dónde se fue el dinero

| Bloque | Llamadas | Coste | % | Segundos de modelo |
|---|---:|---:|---:|---:|
| **Orquestador** (Opus) | 30 | 1,703 | **56,5 %** | 162 |
| **Revisor** (Sonnet) | 20 | 0,546 | 18,1 % | 333 |
| **Verificador** (Sonnet) | 16 | 0,454 | 15,1 % | 276 |
| **Redactor** — escribir | 12 | 0,134 | 4,5 % | 88 |
| **Redactor** — reescribir | 8 | 0,111 | 3,7 % | 56 |
| **Arquitecto** | 3 | 0,067 | 2,2 % | 50 |
| | **89** | **3,016** | | **966** |

### A dónde se fue el tiempo

| | Segundos | % del reloj |
|---|---:|---:|
| Revisor + verificador | 631 | **60 %** |
| Redactor (5 pasadas) | 157 | 15 %|
| Orquestador pensando entre despachos | 162 | 15 % |
| Arquitecto | 53 | 5 % |
| Esperando al usuario (`AskUserQuestion`) | 33 | 3 % |

### Tokens

2,74 M en total, de los que 2,42 M (88 %) son lecturas de caché — la caché está
funcionando muy bien, sólo 178 tokens entraron como input frío. De los 83.927
tokens de salida, **58.436 (70 %) los produjeron los dos jueces**.

---

## Hallazgos

Ordenados por lo que cuesta arreglarlos contra lo que devuelven.

### 1. El modelo caro está en el sitio que no decide nada

El orquestador corre en **Opus** y se lleva **56,5 % del coste** para hacer
`mkdir`, `head -1`, `mv` y pasar prompts. Los cinco agentes que sí juzgan y sí
escriben corren en **Sonnet** y se reparten el 43,5 % restante. El reparto está
exactamente al revés de donde está el criterio.

La traza lo enseña sin ambigüedad: las 30 llamadas del orquestador produjeron
12.834 tokens de salida (dispatch y comentarios), a un coste medio de **0,057
USD por llamada**; las 20 llamadas del revisor produjeron 32.612 tokens de
juicio a **0,027 USD por llamada**.

**Qué cambiar:** bajar el orquestador a Sonnet y subir los dos jueces a Opus.
El despacho es mecánico y está escrito paso a paso en la skill; el juicio no.
A igualdad de llamadas, la corrida pasaría de ~3,02 a ~1,60 USD *y* los
veredictos los daría el modelo mejor.

### 2. El sistema no llega a la novela que él mismo propone por defecto

`dirigir-novela` dice: *"Si el usuario no dijo longitud, elegí vos una novela
corta de unas 6000 palabras"*. Esa novela no cabe hoy.

El contexto del orquestador crece de forma monótona y él lo relee entero en
cada llamada:

```
llamada  1: 31.842 tokens de contexto   (arranque)
llamada  4: 49.905                      (capítulo 1 en marcha)
llamada 30: 74.799                      (novela cerrada)
```

Son **~10.000 tokens por capítulo**, con ~9 llamadas del orquestador por
capítulo. Como cada llamada relee todo, el coste del orquestador crece con el
cuadrado del número de capítulos:

| Novela | Capítulos | Contexto final estimado | Coste estimado |
|---|---:|---:|---:|
| Esta corrida | 3 | 75 k | 3,02 USD |
| El defecto de la skill (6.000 pal.) | 12 | ~165 k | ~10 USD |
| 15.000 palabras | 30 | ~345 k | no entra en la ventana |

El verificador tiene el mismo problema en pequeño: lee **todos** los capítulos
aprobados, y en la traza se ve crecer (2 → 3 → 4 lecturas). A 30 capítulos son
30 lecturas por verificación.

**Qué cambiar:** dos cosas independientes.

- Que el orquestador no arrastre el contenido: hoy hace `cat plan.md` y `cat`
  de las luces rojas enteras dentro de su propio contexto. La luz roja tiene que
  llegarle al redactor entera —eso es innegociable y está bien— pero puede
  llegarle **por ruta**, no por copia: el redactor ya tiene `Read`.
- Que el verificador reciba un **resumen de continuidad** acumulado (hechos,
  lesiones, objetos, fechas) en vez de todos los capítulos. Ese resumen es un
  artefacto nuevo en la carpeta, encaja con "el estado es la carpeta", y lo
  puede mantener el propio verificador al dar luz verde.

### 3. El revisor está haciendo el trabajo del verificador

`revisor.md` dice: *"No juzgás si el capítulo encaja con el resto de la novela:
eso es del verificador y no es asunto tuyo"*, y le manda leer sólo la sección
*"La voz"* del plan más la línea de palabras.

En la traza, **el revisor leyó `plan.md` entero las cinco veces**. Y sus
veredictos juzgan encaje con el plan, que es el criterio nº 2 del verificador:

> «El capítulo cumple con el nudo que pedía el plan: Julian pasa de la lesión
> confirmada por ecografía a mentir sobre su estado y conseguir la
> convocatoria» — `02.intento1.revisor.md`

> «El capítulo cumple el arco que el plan pedía para el desenlace: Julian entra
> desde el banco, participa del gol, se confirma el título…» — `03.intento1.revisor.md`

Comparadas lado a lado, las luces verdes del revisor y del verificador para los
capítulos 2 y 3 recitan los mismos hitos. Hasta la única luz roja del revisor
(capítulo 1) es de conformidad con el plan: *"la voz no tiene el ritmo
entrecortado que pide el plan"*.

**Por qué importa:** dos jueces que miran lo mismo fallan juntos. La prueba está
en el capítulo 3: el revisor le dio verde y el verificador cazó que el dolor se
había mudado del gemelo al tobillo. El verificador hizo su trabajo *y* el del
revisor; el revisor no hizo el suyo.

**Qué cambiar:** que el revisor no reciba `plan.md`. Que el orquestador le pase,
en el prompt, sólo el bloque *"La voz"* y el número de palabras. Si no puede
leer el plan, no puede juzgar el plan, y vuelve a la pregunta que es suya: *¿está
bien escrito esto?*

### 4. La razón por la que el verificador va después ya no es cierta

La skill justifica serializar así: *"No llames al verificador: es la llamada más
cara"*. La traza dice otra cosa:

| | Invocaciones | Coste medio | Duración media |
|---|---:|---:|---:|
| Revisor | 5 | **0,109 USD** | 67 s |
| Verificador | 4 | **0,113 USD** | 69 s |

Cuestan lo mismo (4 % de diferencia). La serialización ahorró **una** llamada de
verificador en toda la corrida (0,11 USD) y a cambio pagó cinco idas y vueltas
extra del orquestador (~0,25 USD) y **unos 240 s de reloj**, un 23 % del total.

**Qué cambiar:** despachar revisor y verificador **en paralelo**, en el mismo
turno. Con el hallazgo 3 aplicado son dos preguntas de verdad distintas, y
preguntarlas a la vez es más honesto además de más rápido: ninguno de los dos
sabe lo que dijo el otro.

Si se quiere conservar el ahorro, la regla correcta ya no es "el verificador es
más caro" sino "el verificador es el que más contexto arrastra", y eso sí es
verdad y lo será cada vez más.

### 5. El 64 % de los tokens de salida es deliberación que nadie guarda

La llamada más cara de toda la corrida es el revisor del capítulo 1: **9.881
tokens de salida y 92,7 segundos** para juzgar 472 palabras. El archivo que
escribió tiene 1.800 caracteres.

En la traza, esa generación registra `assistant_text.orig_len: 0` y una sola
llamada a `Write`. Es decir: ~9.400 de esos 9.881 tokens son razonamiento
interno que **se paga, se cronometra y se tira**. Sumando los dos jueces son
~54.000 tokens de deliberación, el 64 % de toda la salida de la corrida.

Escribir un capítulo cuesta 1.276 tokens de salida. **Juzgarlo cuesta ocho veces
más que escribirlo.**

**Por qué importa:** el README promete *"todo lo que se decide, lo decide un
agente, y deja escrito por qué"*. El "por qué" que queda escrito es la
conclusión —con cita y con qué cambiar, que es mucho más de lo que hace casi
nadie— pero el camino hasta ella es el artefacto más caro del sistema y es el
único que no se guarda en ninguna parte.

**Qué cambiar:** no hay que guardarlo todo, pero sí decidirlo a propósito. Dos
opciones, y yo elegiría la primera:

- Aceptarlo y **acotarlo**: decirle al juez en su prompt que el presupuesto de
  deliberación es proporcional al capítulo. 9.400 tokens de análisis para 472
  palabras es desproporción, no rigor.
- Capturarlo: el plugin de Langfuse admite `CC_LANGFUSE_MAX_CHARS`, pero en
  estas generaciones el texto ni siquiera llega, así que habría que mirar la
  captura de `thinking` del hook antes de prometer nada.

### 6. Las luces no llegan a Langfuse

**El proyecto tiene 0 scores.** Los veredictos existen en
`books/<slug>/decisiones/`, que es exactamente donde el diseño quiere que estén,
pero eso significa que desde Langfuse no se puede responder a nada de esto:

- ¿sube o baja la tasa de luz roja entre corridas?
- ¿qué juez rechaza más?
- ¿los capítulos del desenlace se atascan más que los de la introducción?
- ¿cambiar el prompt del redactor redujo los reintentos, o sólo lo parece?

Hoy la respuesta es leer carpetas a mano y acordarse de la corrida anterior.

**Qué cambiar:** que el orquestador, en el mismo `Bash` donde ya hace
`head -1` para leer la luz, mande el veredicto como score:

```bash
npx langfuse-cli api scores create --body-json '{
  "name": "luz-revisor", "value": "VERDE", "dataType": "CATEGORICAL",
  "traceId": "<traza>", "comment": "cap 03 intento 2"
}'
```

**Tensión a resolver antes de adoptarlo:** el proyecto se apoya en que no hay
código determinista, y esto es un comando más en una skill —igual que `mv` o
`head -1`—, no un script. Pero añade una dependencia de red a un paso que hoy es
sólo sistema de archivos, y si Langfuse no responde, el ciclo no puede pararse
por eso. Decisión tuya; yo lo haría sin bloquear el ciclo.

### 7. Cosas pequeñas que la traza deja ver

**`novela.md` pierde el título.** El `cat` final concatena capítulos y nada más,
así que la novela se llama *"Capitulo 1 - El cuerpo antes del partido"*. El
título *Cuarenta* está en `plan.md` y no llega al libro. Un `echo` antes del
`cat` lo arregla.

**Las palabras se cuentan a ojo teniendo `wc -w` al lado.** El revisor estimó
"unas 460" (eran 472) y "cerca de 490" (eran 505) — buenas estimaciones, pero es
un LLM estimando algo que la terminal cuenta exacto. El revisor no tiene `Bash`,
y está bien que no lo tenga: que el orquestador le pase el número en el prompt,
ya que hace un `Bash` antes de cada despacho de todos modos.

**El entorno está mal etiquetado.** Esta traza cayó en `environment: default`
aunque `.env` fija `LANGFUSE_TRACING_ENVIRONMENT`. Otras trazas de la misma
tarde sí salieron como `desarrollo`. La causa es que `.claude/settings.json`
declara `TRACE_TO_LANGFUSE` y `LANGFUSE_BASE_URL` pero **no**
`LANGFUSE_TRACING_ENVIRONMENT`, así que sólo se aplica cuando la sesión arranca
desde un shell que cargó el `.env`. Mientras siga así, filtrar por entorno en
Langfuse miente. Mover esa variable a `settings.json` lo cierra.

**No hay `userId` en ninguna observación**, así que las corridas no se pueden
agrupar por persona el día que haya más de una.

**Las claves están bien guardadas:** `.env` está en `.gitignore` y no hay
secretos en el repositorio.

---

## Qué haría, y en qué orden

| # | Cambio | Toca | Devuelve |
|---|---|---|---|
| 1 | Orquestador a Sonnet, jueces a Opus | `.claude/agents/*.md`, skill | −47 % coste y mejor criterio donde importa |
| 2 | Al revisor no le llega `plan.md`, sólo *"La voz"* + palabras | `revisor.md`, skill | Dos jueces de verdad independientes |
| 3 | Revisor y verificador en paralelo | `dirigir-novela` | −23 % de reloj |
| 4 | Luces rojas al redactor por ruta, no copiadas al contexto | `dirigir-novela` | Sube el techo de capítulos |
| 5 | Resumen de continuidad para el verificador | agente + skill | Quita la lectura cuadrática |
| 6 | Presupuesto de deliberación en los jueces | `revisor.md`, `verificador.md` | −40 % de tokens de salida |
| 7 | Luces como scores en Langfuse | `dirigir-novela` | Se puede comparar corridas |
| 8 | Título en `novela.md`, `wc -w` en el prompt, entorno en `settings.json` | varios | Defectos concretos, coste casi cero |

Los cambios 1 a 3 son los que más devuelven por lo poco que cuestan, y se pueden
medir: si se repite esta misma novela con ellos aplicados, la traza tiene que
enseñar menos de 1,70 USD y menos de 14 minutos, con las mismas seis luces.

Cualquiera de estos cambios que se adopte va a las specs **con su entrada de
changelog y su porqué**, en la misma entrega.

---

## Cómo se obtuvieron estos datos

El servidor MCP de Langfuse (`MCP_DOCKER`) no levantó en esta sesión, así que
los datos salen de la API pública vía `langfuse-cli`, con las credenciales de
`.env`:

```bash
set -a && . ./.env && set +a && export LANGFUSE_HOST="$LANGFUSE_BASE_URL"

# la última traza
npx langfuse-cli api observations list --is-root-observation --limit 20 \
  --fields "core,basic,time,metrics,trace_context" --json

# sus 199 observaciones
npx langfuse-cli api observations list \
  --trace-id a40cb200bd75d709b1de631bc151c5da --all \
  --fields "core,basic,time,metrics,model,usage,trace_context,metadata" --json
```

Nota: `GET /api/public/traces` y `GET /api/public/observations/{id}` están
obsoletos en la API 4.35.0 y devuelven error. La ruta viva es
`observations list` (`/api/public/v2/observations`).
