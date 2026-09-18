# Story-Maker — Especificación técnica

**Versión 1.4** · 2026-09-18 · el qué y el porqué están en
[SPEC-FUNCIONAL.md](SPEC-FUNCIONAL.md).

Este documento dice **cómo está hecho**: archivos, contratos y formatos.

---

## 1. Estructura del repositorio

```
.claude/agents/                 un archivo por agente
.claude/skills/dirigir-novela/  el ciclo entero, para la sesión que orquesta
.claude/skills/luz/             el formato de una decisión
.claude/settings.json           las variables de entorno del proyecto
.claude/settings.local.json     las de cada persona; no se commitea
books/<slug>/                   una novela
```

**No hay código.** Ni un script, ni un validador, ni un archivo de Python.

Lo que en otro sistema sería un harness aquí son tres cosas: la sesión de
Claude Code, que orquesta siguiendo una skill; los agentes, que hacen el
trabajo y lo escriben; y las órdenes normales de la terminal, `mkdir`, `ls`,
`head`, `mv` y `cat`, que la sesión usa directamente.

La razón es que cada script intermedio es una pieza que hay que leer para
entender el sistema, y ninguno estaba haciendo nada que la sesión no pueda
hacer con una orden. Un script que interpreta `plan.md` con una expresión
regular, además, se rompe en silencio el día que el arquitecto cambia una
palabra del formato.

---

## 2. Los archivos de una novela

```
books/<slug>/
  plan.md                        el plan. Lo escribe el arquitecto
  capitulos/
    01.md                        aprobado: entra en la novela
    02.md                        aprobado
    03.borrador.md               en curso, todavía sin aprobar
  decisiones/
    03.intento1.revisor.md       una luz, con su motivo
    03.intento1.verificador.md   la otra, del mismo intento
    03.intento2.revisor.md
    03.intento2.verificador.md
  continuidad/
    01.md                        los hechos que fijó el capítulo 1
    02.md
    03.borrador.md               los del 3, a la espera de que el capítulo entre
  novela.md                      al final: el título y los capítulos aprobados
```

**El estado del sistema es la carpeta.** No hay un archivo de estado aparte con
contadores. Por dónde va la novela se sabe mirando qué capítulos existen sin el
sufijo `borrador`. En qué intento va un capítulo se sabe contando sus archivos
en `decisiones/`. Todo lo que el sistema sabe de sí mismo se ve con `ls`.

Un capítulo aprobado **pierde el sufijo**: `03.borrador.md` pasa a ser `03.md`,
y `continuidad/03.borrador.md` pasa a ser `continuidad/03.md` en el mismo
paso. Esos dos cambios de nombre son la aprobación.

**Cada intento tiene dos archivos en `decisiones/`**, porque los dos jueces se
pronuncian a la vez. Un intento con uno solo es uno en que la otra luz no se
entendió y se está repitiendo. Con los dos se lee quién rechazó: si la roja es
del revisor, la prosa; si es del verificador, la coherencia; si son las dos,
las dos. El contador de intentos no se reinicia: cada reescritura es un intento
nuevo y se vuelve a juzgar entera por los dos.

**`continuidad/` es la memoria del verificador.** Un archivo por capítulo
aprobado con los hechos que ese capítulo dejó fijados: cuándo y dónde, qué
queda establecido, dónde termina, qué imágenes no deberían repetirse. Lo
escribe el verificador que dio la luz verde, como borrador, y solo pierde el
sufijo cuando el capítulo entra. El siguiente verificador lee
`continuidad/[0-9][0-9].md` en vez de todos los capítulos, y el último capítulo
aprobado entero. Así lo que lee crece con el número de capítulos, pero en
listas de diez a veinte líneas y no en capítulos de mil palabras.

---

## 3. Quién escribe cada archivo

Los agentes **escriben sus propios archivos**. El arquitecto escribe `plan.md`,
el redactor escribe su borrador, el revisor y el verificador escriben su
decisión, y el verificador escribe además la continuidad del capítulo cuando
le da luz verde.

Hay una sola excepción. **Los renombrados de `NN.borrador.md` a `NN.md`, en
`capitulos/` y en `continuidad/`, los hace la sesión**, no un agente. La
aprobación es la consecuencia de dos luces verdes, no el acto de nadie. Si la
consumara el verificador, un agente podría dar por aprobado un capítulo sin
que el revisor se hubiera pronunciado. Por eso también la continuidad nace
como borrador: el verificador puede haber dado verde a un capítulo que el
revisor rechazó, y esos hechos no deben contar hasta que el capítulo entre.

Los agentes pueden escribir sus propios archivos porque todos son prosa en
Markdown. Un agente que escribe prosa no puede dejar un archivo ilegible, como
mucho deja un párrafo de más que se ve al leerlo. Si el plan fuera un YAML con
estructura haría falta otra cosa, y es una de las razones por las que no lo es.

### Por qué esto no necesita un guardián

Nada impide técnicamente que la sesión renombre un borrador sin haber leído las
dos luces. Lo que lo hace comprobable es que **las decisiones están en disco**:
cada juicio es un archivo con su veredicto, su motivo y su hora. Cualquiera
puede abrir `decisiones/` y ver si un capítulo aprobado tenía sus dos luces
verdes.

Se prefirió eso a un script que lo impidiera. Un guardián da una garantía más
fuerte, pero es una pieza más que hay que leer para entender el sistema, y la
garantía que da se puede reconstruir mirando los archivos.

---

## 4. Los contratos de los agentes

Cada agente corre en **su propio proceso, con contexto limpio**. Recibe un
prompt y devuelve texto. No ve lo que vieron los demás.

### Qué modelo corre cada uno

| Agente | Modelo | Por qué |
|---|---|---|
| arquitecto | `haiku` | escribe un documento con formato fijo a partir de una idea |
| director | `haiku` | lee una carpeta y elige una respuesta de una lista cerrada |
| redactor | `haiku` | escribe prosa contra un plan y unas luces que le dicen qué tocar |
| revisor | `sonnet` | juzga, y su luz vale |
| verificador | `sonnet` | juzga, y su luz vale |

El modelo va en el campo `model` del frontmatter de cada agente. El criterio
del sistema está en las dos luces, así que el modelo más capaz va ahí y el
resto corre en el más barato. La sesión que orquesta corre en el modelo con
que se abrió Claude Code; su trabajo es mecánico y está escrito paso a paso en
la skill.

### arquitecto

| | |
|---|---|
| **Recibe** | la idea del usuario y la longitud aproximada que pidió |
| **Devuelve** | el contenido de `plan.md` |
| **Escribe** | `plan.md` |
| **No hace** | no escribe prosa de la novela; no decide si un capítulo pasa |

### director

| | |
|---|---|
| **Recibe** | `plan.md`, la lista de archivos de `capitulos/` y de `decisiones/` |
| **Devuelve** | qué toca ahora: el capítulo, el agente y el motivo |
| **Escribe** | nada |
| **No hace** | no escribe prosa; no aprueba capítulos; no cambia el plan |

Sus respuestas posibles son pocas: escribir el capítulo N, revisarlo,
verificarlo, reescribirlo con estos motivos, parar y avisar, o cerrar la novela.

### redactor

| | |
|---|---|
| **Recibe** | `plan.md`, los capítulos ya aprobados, el capítulo que le toca, y —si es una corrección— **las rutas** de las luces rojas que recibió, que lee enteras con `Read` |
| **Devuelve** | el capítulo entero, solo prosa |
| **Escribe** | `capitulos/NN.borrador.md` |
| **No hace** | no juzga su capítulo; no cambia el plan; al corregir, no toca lo que no le señalaron |

Las luces rojas le llegan por ruta y no copiadas en el prompt. Así le llegan
literales, que es lo que la regla pide, y la sesión que orquesta no acumula en
su propio contexto textos que no tiene que juzgar.

### revisor

| | |
|---|---|
| **Recibe** | en el prompt: la ruta del borrador, la sección *La voz* del plan copiada, cuántas palabras pide el plan para ese capítulo y cuántas tiene el borrador según `wc -w` |
| **Devuelve** | una luz, con su motivo (§5) |
| **Escribe** | `decisiones/NN.intentoK.revisor.md` |
| **No hace** | no reescribe; no lee `plan.md`; no ve los intentos anteriores; no ve los otros capítulos; no cuenta palabras |

El revisor **no ve el resto de la novela ni el plan** a propósito. Su pregunta
es si este capítulo está bien escrito. Si pudiera leer qué tiene que pasar en
el capítulo, juzgaría si pasa, que es la pregunta del verificador, y los dos
fallarían juntos. Lo que necesita del plan se lo extrae la sesión con `sed` y
`grep` y se lo pone en el prompt.

### verificador

| | |
|---|---|
| **Recibe** | el borrador del capítulo, `plan.md`, las listas de hechos `continuidad/[0-9][0-9].md` de los capítulos aprobados, y el último capítulo aprobado entero |
| **Devuelve** | una luz, con su motivo (§5) |
| **Escribe** | `decisiones/NN.intentoK.verificador.md`; con luz verde, también `continuidad/NN.borrador.md` |
| **No hace** | no reescribe; no juzga la calidad de la prosa; no ve los intentos anteriores; no lee todos los capítulos enteros |

La lista de hechos tiene un formato fijo, escrito en su archivo de agente:
cuándo y dónde, hechos que quedan fijados, dónde termina, imágenes que no
deberían repetirse. Entre diez y veinte líneas.

### Cuánto deliberan los jueces

Los dos jueces llevan en su archivo una instrucción de presupuesto: leer una
vez con atención, anotar lo que choca de verdad, decidir y escribir. Sin
informe por cada punto de la lista, sin releer buscando algo que rechazar. El
razonamiento que no termina en el archivo de la decisión se paga y se tira, y
en una corrida sin esa instrucción fue el 64 % de los tokens de salida.

---

## 5. El formato de una luz

Una decisión es un archivo Markdown. La primera línea es la única que la
sesión necesita leer para saber el veredicto:

```
LUZ: VERDE
```

o

```
LUZ: ROJA
```

Después va el motivo, en prosa. En una luz roja, un bloque por cada problema:

```
LUZ: ROJA

## El protagonista sabe algo que todavía no ha pasado

**Dónde:** «Marta ya sabía que el equipo la iba a dejar fuera de la Vuelta.»

**Qué cambiar:** la decisión del equipo se comunica en el capítulo 7. Aquí
Marta puede sospecharlo, pero no puede darlo por hecho.
```

El formato exacto lo fija la skill **`luz`**, que los jueces cargan por el campo
`skills` de su frontmatter. No hay que recordarles el formato al llamarlos.

Se eligió una primera línea fija en vez de un JSON porque se lee con un
`head -1` y también con los ojos. El motivo va en prosa porque su destinatario
es el redactor, que es un modelo de lenguaje y no un parser.

**Una luz sin motivo no cuenta.** Si un archivo dice `LUZ: ROJA` y nada más, la
llamada se repite.

**Una luz que no se entiende no se interpreta.** Si la primera línea no es
ninguna de las dos, la sesión repite esa llamada en lugar de deducir qué quiso
decir el juez. Deducirlo sería decidir, y eso no le toca.

---

## 6. Quién orquesta

**La sesión de Claude Code**, siguiendo la skill `dirigir-novela`. Lee la
carpeta, despacha a los agentes, lee sus luces y renombra los borradores
aprobados. No hay ningún programa que la conduzca.

El **director** es un agente al que la sesión consulta cuando no está claro
cómo seguir: al retomar una novela a medias, cuando el ciclo se atasca, o
cuando alguien pregunta cómo va. Para el camino normal no hace falta, porque
el ciclo se sigue solo.

La sesión usa las órdenes normales de la terminal. Crear la novela es un
`mkdir`, ver el estado es un `ls`, leer un veredicto es un `head -1`, aprobar
son dos `mv` y compilar es un `cat`. Nada de eso merece un script.

### Lo que la sesión saca del plan para el revisor

Antes de despachar a los jueces, un solo `Bash`:

```bash
p=books/<slug>/plan.md; b=books/<slug>/capitulos/<NN>.borrador.md
sed -n '/^## La voz/,/^## /{/^## /d;p}' "$p"                      # la voz
grep -E "^### Cap[ií]tulo <N> -" "$p" | grep -oE "[0-9]+ palabras"   # las pedidas
wc -w < "$b"                                                        # las que tiene
```

Esto funciona porque el arquitecto escribe los encabezados `## La voz` y
`### Capitulo N - <título> - <N> palabras - <parte>` con ese formato exacto, y
su archivo de agente se lo exige. Es la única parte del plan que se lee con
una orden en vez de con los ojos, y por eso esos dos encabezados van sin tilde.

### Los dos jueces en el mismo turno

La sesión despacha al revisor y al verificador **en un solo mensaje, con dos
llamadas a `Agent`**. Corren a la vez, en procesos distintos, y ninguno ve la
luz del otro. Después lee las dos primeras líneas con `head -1`. Si alguna no
se entiende, repite solo esa llamada.

### El cierre

```bash
{ head -1 books/<slug>/plan.md; echo; cat books/<slug>/capitulos/[0-9][0-9].md; } > books/<slug>/novela.md
```

La primera línea del plan es el título de la novela, así que el libro empieza
por su título. `[0-9][0-9].md` no casa con `NN.borrador.md`, así que un
capítulo que no pasó las dos luces no puede colarse en el libro por un
descuido al cerrarlo.

---

## 7. La traza

**No la escribe este repositorio.** Claude Code ya registra lo que hace, y el
trabajo es mandarlo a donde se pueda mirar.

### En Langfuse, con el plugin oficial

Langfuse publica un plugin para Claude Code que captura las conversaciones y
las llamadas a herramientas, incluidos los despachos de subagente, y las manda
como trazas:

```bash
claude plugin marketplace add langfuse/Claude-Observability-Plugin
claude plugin install langfuse-observability@langfuse-observability
```

Las credenciales se piden al instalarlo y la clave secreta queda en el llavero
del sistema. El proyecto activa el envío con un bloque `env` en
`.claude/settings.json`, que fija también el entorno con
`LANGFUSE_TRACING_ENVIRONMENT`, para que todas las trazas del proyecto caigan
en el mismo entorno y se pueda filtrar por él. Las claves, si se ponen a mano,
y el identificador de persona `LANGFUSE_USER_ID`, van en
`.claude/settings.local.json`, que no se commitea: uno es secreto y el otro es
de cada cual.

Lo que se ve en Langfuse: una traza por turno, una generación por respuesta,
una observación anidada por cada llamada a herramienta y a subagente, y todos
los turnos de una sesión agrupados. La sesión de Langfuse es la sesión de
Claude Code, cuyo identificador la terminal tiene en `CLAUDE_CODE_SESSION_ID`.

### Cómo se llama cada subagente en la traza

El plugin nombra la observación de un subagente `Subagent: <description>`,
donde `description` es el campo con ese nombre que la sesión pasa a la
herramienta `Agent` al despacharlo. El tipo de agente queda solo en los
metadatos. Por eso la skill fija el formato del campo: el nombre del agente,
el capítulo y el intento, `redactor · cap 03 · intento 2`. Con eso el grafo
de la traza se lee como la carpeta `decisiones/`: quién hizo qué, sobre qué
capítulo, en qué intento.

### Las luces como puntuaciones

Cada luz se manda a Langfuse como un *score* categórico de la sesión, en el
mismo `Bash` en que la sesión la lee con `head -1`:

```bash
npx -y langfuse-cli --env .env api scores create --body-json '{
  "name": "luz-revisor", "value": "VERDE", "dataType": "CATEGORICAL",
  "sessionId": "'"$CLAUDE_CODE_SESSION_ID"'",
  "comment": "<slug> cap <NN> intento <K>",
  "metadata": {"novela": "<slug>", "capitulo": "<NN>", "intento": <K>, "juez": "revisor"}
}' >/dev/null 2>&1 || true
```

`luz-revisor` y `luz-verificador` con valor `VERDE` o `ROJA`. Las credenciales
las lee `langfuse-cli` de `.env`, que está en `.gitignore`. El `|| true` es la
regla: si no hay red o Langfuse no responde, el ciclo sigue, porque la luz que
manda es la de `decisiones/`. Es una orden más de la skill, igual que `mv` o
`head -1`, y no un script.

Como alternativa, Claude Code exporta trazas OpenTelemetry nativas que se
pueden apuntar al endpoint OTLP de Langfuse. Está en beta y requiere
`CLAUDE_CODE_ENABLE_TELEMETRY`, `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA` y
`OTEL_TRACES_EXPORTER`. El plugin es el camino soportado.

### En disco, sin haber escrito nada

Aunque Langfuse esté apagado, el registro de lo que se decidió **no se pierde**,
porque son los propios archivos de la novela:

| Pregunta | Dónde está la respuesta |
|---|---|
| ¿qué se decidió sobre el capítulo 3? | `decisiones/03.intento*.md` |
| ¿por qué se rechazó? | el motivo entero, dentro de ese archivo |
| ¿cuántos intentos costó? | cuántos archivos hay de ese capítulo |
| ¿cuándo pasó? | la fecha de modificación de cada archivo |
| ¿qué entró en el libro? | los capítulos sin `borrador` en el nombre |

Esto es lo que hace que el sistema no necesite un archivo de traza propio. La
traza que importa, la de los juicios y sus motivos, la escriben los jueces al
emitirlos, porque emitir un juicio **es** escribir el archivo.

---

## 8. Convenciones

- **Código y comentarios en español, sin tildes.** La consola de Windows viene
  en cp1252 y una tilde en un `print` rompe la salida. La prosa de las novelas y
  de estos documentos sí lleva tildes.
- **Todo lo que lee la entrada estándar la reconfigura a UTF-8**, por el mismo
  motivo.
- **Un error dice tres cosas**: qué está mal, cuál es la verdad y cómo se
  arregla. Un error que solo dice que algo falló obliga a leer el código.
- **Cada cambio de especificación se registra en el historial del documento que
  toca, en la misma entrega**, con qué cambió y por qué.

---

## 9. Qué hay construido y qué está comprobado

| Pieza | Construida | Comprobada corriendo |
|---|---|---|
| arquitecto, redactor, revisor, verificador | sí | sí, dos novelas enteras en `books/`: `ciclista-2010` y `veterano-2010` |
| skill `dirigir-novela` | sí | sí, esas dos novelas de punta a punta, del plan al `novela.md` |
| skill `luz` | sí | sí, se precarga sola por el campo `skills` del frontmatter de cada juez |
| director | sí | **no**, el ciclo normal no lo necesitó |
| plugin de Langfuse | sí, instalado y activado en `settings.json` | sí, la novela `veterano-2010` tiene su traza entera |
| jueces a la vez, revisor sin plan, luces por ruta | sí | **no**, todavía no se escribió una novela con ellos |
| `continuidad/` y el verificador que la escribe y la lee | sí | **no** |
| luces como puntuaciones en Langfuse | sí | **a medias**: la orden se probó en seco con `--curl` y la petición sale bien formada, pero no se ha mandado ninguna en una corrida |
| nombre de agente en `description` | sí | **no**, hay que ver una traza nueva |
| modelos por agente (`haiku` y `sonnet`) | sí | **no** |

Las corridas que lo comprueban se conservan enteras en `books/`: cada carpeta
`decisiones/` tiene sus juicios con sus motivos, y por sus nombres se
reconstruye el camino de cada capítulo sin haber estado delante. La medida de
la próxima novela es la traza de `veterano-2010`: tres capítulos, 3,02 USD y
17 minutos y medio; con estos cambios tiene que salir por debajo de la mitad
del coste y en menos de 14 minutos, con las mismas seis luces.

**Los agentes y las skills se cargan al arrancar la sesión.** Una sesión que ya
estaba abierta cuando se crearon no los ve, y hay que reiniciarla.

Esta tabla se actualiza cuando cambie alguna de las dos columnas.

---

## 10. Historial técnico

| Versión | Fecha | Cambio | Por qué |
|---|---|---|---|
| **1.0** | 2026-09-17 | Primera versión. Carpeta por novela con el plan, los capítulos, las decisiones y la traza. El estado del sistema es la carpeta, sin archivo de contadores. Los agentes escriben sus propios archivos, salvo la traza y el renombrado de aprobación. La luz es un Markdown cuya primera línea da el veredicto. Traza en JSONL, con el mapa a sesiones, trazas, observaciones y scores de Langfuse. | El criterio vive en los agentes, así que el código se queda con lo que no se puede delegar sin perder garantías: anotar lo que pasó y consumar la aprobación. El estado en la propia carpeta evita que haya dos versiones de la verdad. |
| **1.1** | 2026-09-17 | **Se elimina todo el código.** Fuera los seis scripts de `harness/` y el hook de trazas. La sesión de Claude Code orquesta siguiendo la skill `dirigir-novela` y usa las órdenes normales de la terminal. La traza pasa a Langfuse mediante su plugin oficial para Claude Code, y en disco la sostienen los propios archivos de decisión. | Los scripts estaban ocupando el sitio del orquestador y ninguno hacía algo que la sesión no pueda hacer con una orden. Uno de ellos interpretaba `plan.md` con una expresión regular, que se rompe en silencio si el arquitecto cambia una palabra. El hook existía para que no se perdiera la traza, pero Claude Code ya registra sus propios despachos y el plugin de Langfuse los recoge sin que haya que escribir nada. |
| **1.2** | 2026-09-17 | Cómo se leen los intentos en `decisiones/`: un intento con un solo archivo es uno que no llegó al verificador, y el contador no se reinicia al cambiar de juez. El ejemplo de luz roja se alinea con el formato de la skill `luz`, que los jueces cargan por su frontmatter. El `cat` de cierre explica su patrón de dos dígitos. La tabla de lo comprobado recoge la primera novela completa. | La primera corrida entera dejó once archivos de decisión, y ahí se vio que la forma de la carpeta ya cuenta quién rechazó qué sin abrir un archivo: eso merecía estar escrito, porque es la garantía que sustituye al guión que no existe. El ejemplo de luz roja no coincidía con lo que la skill pide ni con lo que los jueces escriben. |
| **1.3** | 2026-09-17 | Las dos especificaciones pasan de la raíz a `docs/`. Los enlaces entre ellas siguen siendo relativos y no cambian; el del README sí. | Una raíz con dos archivos de spec de treinta kilobytes esconde lo único que hay que ver al llegar: el README, `books/` y `.claude/`. La carpeta `docs/` es el sitio convenido para la referencia. |
| **1.4** | 2026-09-18 | Modelo por agente: `haiku` para arquitecto, director y redactor, `sonnet` para los dos jueces (§4). Los jueces se despachan en el mismo turno y cada intento tiene dos archivos (§2, §6). El revisor recibe en el prompt la voz, las palabras pedidas y las contadas con `wc -w`, extraídas por la sesión con `sed` y `grep`; no lee `plan.md` (§4, §6). Las luces rojas llegan al redactor por ruta (§4). Nueva carpeta `continuidad/` con una lista de hechos por capítulo aprobado, que escribe el verificador como borrador y la sesión renombra al aprobar (§2, §3, §4). Presupuesto de deliberación en los jueces (§4). `novela.md` empieza por el título (§6). El entorno de Langfuse va en `settings.json` y el usuario en `settings.local.json`; los despachos se nombran por el campo `description` y las luces se mandan como *scores* de sesión con `langfuse-cli` (§7). La tabla de lo comprobado distingue lo que corrió de lo que no (§9). | La traza de `veterano-2010` dio los números: el orquestador con el modelo caro se llevaba el 56 % del coste por hacer `mv` y `head -1`, y los jueces, que son los que deciden, corrían en uno más barato. El revisor leía el plan entero y juzgaba lo mismo que el verificador. Serializarlos ahorró una llamada y costó un 23 % del reloj. Copiar las luces rojas en el contexto de la sesión y hacer que el verificador leyera todos los capítulos hacía crecer el coste con el cuadrado de los capítulos, y la novela de 6.000 palabras no cabía. El 64 % de los tokens de salida era deliberación que no quedaba en ningún archivo. El proyecto de Langfuse tenía cero *scores*, la traza cayó en el entorno `default` porque la variable solo estaba en `.env`, y en el grafo los subagentes salían sin nombre porque el plugin usa el campo `description` y nadie lo fijaba. Cada arreglo es una orden más en la skill o una línea más en un agente; ninguno es un script. |
