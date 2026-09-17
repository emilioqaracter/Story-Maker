# Story-Maker — Especificación técnica

**Versión 1.3** · 2026-09-17 · el qué y el porqué están en
[SPEC-FUNCIONAL.md](SPEC-FUNCIONAL.md).

Este documento dice **cómo está hecho**: archivos, contratos y formatos.

---

## 1. Estructura del repositorio

```
.claude/agents/                 un archivo por agente
.claude/skills/dirigir-novela/  el ciclo entero, para la sesión que orquesta
.claude/skills/luz/             el formato de una decisión
.claude/settings.json           las variables de entorno del proyecto
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
    03.intento2.revisor.md
    03.intento2.verificador.md
  novela.md                      al final: los capítulos aprobados, seguidos
```

**El estado del sistema es la carpeta.** No hay un archivo de estado aparte con
contadores. Por dónde va la novela se sabe mirando qué capítulos existen sin el
sufijo `borrador`. En qué intento va un capítulo se sabe contando sus archivos
en `decisiones/`. Todo lo que el sistema sabe de sí mismo se ve con `ls`.

Un capítulo aprobado **pierde el sufijo**: `03.borrador.md` pasa a ser `03.md`.
Ese cambio de nombre es la aprobación.

**En `decisiones/` se lee también por qué se repitió un intento.** Un intento con
un solo archivo, el del revisor, es uno que nunca llegó al verificador: la
prosa no pasó y no tenía sentido pagar la llamada más cara. Un intento con los
dos archivos se rechazó por coherencia, o se aprobó. El contador de intentos no
se reinicia al cambiar de juez: cada reescritura es un intento nuevo y se
vuelve a juzgar entera.

---

## 3. Quién escribe cada archivo

Los agentes **escriben sus propios archivos**. El arquitecto escribe `plan.md`,
el redactor escribe su borrador, el revisor y el verificador escriben su
decisión.

Hay una sola excepción. **El renombrado de `NN.borrador.md` a `NN.md` lo hace
la sesión**, no un agente. La aprobación es la consecuencia de dos luces
verdes, no el acto de nadie. Si la consumara el verificador, un agente podría
dar por aprobado un capítulo sin que el revisor se hubiera pronunciado.

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
| **Recibe** | `plan.md`, los capítulos ya aprobados, el capítulo que le toca, y —si es una corrección— las luces rojas que recibió, enteras y literales |
| **Devuelve** | el capítulo entero, solo prosa |
| **Escribe** | `capitulos/NN.borrador.md` |
| **No hace** | no juzga su capítulo; no cambia el plan; al corregir, no toca lo que no le señalaron |

### revisor

| | |
|---|---|
| **Recibe** | el borrador del capítulo, la voz del plan y las palabras que debería tener |
| **Devuelve** | una luz, con su motivo (§5) |
| **Escribe** | `decisiones/NN.intentoK.revisor.md` |
| **No hace** | no reescribe; no ve los intentos anteriores; no ve los otros capítulos |

El revisor **no ve el resto de la novela** a propósito. Su pregunta es si este
capítulo está bien escrito, y para eso el resto sobra.

### verificador

| | |
|---|---|
| **Recibe** | el borrador del capítulo, `plan.md` y los capítulos aprobados hasta ahora |
| **Devuelve** | una luz, con su motivo (§5) |
| **Escribe** | `decisiones/NN.intentoK.verificador.md` |
| **No hace** | no reescribe; no juzga la calidad de la prosa; no ve los intentos anteriores |

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
es un `mv` y compilar es un `cat`. Nada de eso merece un script.

El `cat` de cierre lleva el patrón de dos dígitos a propósito:

```bash
cat books/<slug>/capitulos/[0-9][0-9].md > books/<slug>/novela.md
```

`[0-9][0-9].md` no casa con `NN.borrador.md`, así que un capítulo que no pasó
las dos luces no puede colarse en el libro por un descuido al cerrarlo.

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
`.claude/settings.json`, y las claves, si se ponen a mano, van en
`.claude/settings.local.json`, que no se commitea.

Lo que se ve en Langfuse: una traza por turno, una generación por respuesta,
una observación anidada por cada llamada a herramienta y a subagente, y todos
los turnos de una sesión agrupados.

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
| arquitecto, redactor, revisor, verificador | sí | sí, una novela entera: tres capítulos, once juicios y tres rechazos corregidos |
| skill `dirigir-novela` | sí | sí, esa misma novela de punta a punta, del plan al `novela.md` |
| skill `luz` | sí | sí, se precarga sola por el campo `skills` del frontmatter de cada juez |
| director | sí | **no**, el ciclo normal no lo necesitó |
| plugin de Langfuse | **no instalado** | **no** |

La corrida que lo comprueba se conserva entera en `books/ciclista-2010/`: su
carpeta `decisiones/` tiene los once juicios con sus motivos, y por sus nombres
se reconstruye el camino de cada capítulo sin haber estado delante.

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
