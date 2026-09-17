# Story-Maker — Especificación funcional

**Versión 10.0** · 2026-09-17 · la parte técnica está en [SPEC-TECNICO.md](SPEC-TECNICO.md).

Este documento dice **qué hace el sistema y por qué**: quién trabaja, en qué
orden, quién decide y cómo se ve después lo que pasó. No dice cómo está
programado; para eso está el técnico.

---

## 1. Qué es esto

Un harness que escribe **novelas deportivas cortas**: la historia de un
atleta, en tres actos, escena por escena. Lo conduce Claude Code; escriben y
critican subagentes con contexto limpio; deciden scripts y un crítico.

**La novela es la excusa.** Lo que se está construyendo son **capas de control
sobre un modelo**: los filtros que deciden si lo que produjo un modelo entra o
no entra. La novela es un buen banco de pruebas porque las incoherencias se
ven a simple vista: alguien que juega con la rodilla rota dos escenas antes de
que se la operen, un final que llega en la primera página, un personaje que
sabe algo que todavía no ocurrió.

| Capa | Qué controla | Cómo |
|---|---|---|
| **Canon calculado** | que los hechos no se contradigan | lo derivable no se guarda: no hay `edad`, hay `nacimiento`; no hay «estado actual», hay tramos con vigencia (§7) |
| **Validadores** | que la prosa respete esos hechos y la forma | siete reglas deterministas, sin modelo (§5) |
| **Crítico con evidencia** | que el criterio no sea una opinión | un veredicto motivado, un veto con cita, una rúbrica con cita en toda nota (§5, §6) |
| **Puertas** | que nada avance porque alguien opine que puede | cinco puntos de corte con criterio escrito y un script que lo aplica (§5) |
| **Traza** | que se pueda ver después qué pasó y por qué | cada puerta y cada agente dejan un evento en disco, en el momento (§8) |

> **El principio del que sale todo lo demás:** lo que se puede calcular no se
> recuerda. El modelo escribe; el código y otro modelo verifican.

---

## 2. Lo que esta versión quitó, y por qué

La versión 10 vuelve a las bases. El sistema había acumulado complejidad en
cosas que no eran el problema que se quería estudiar. Se quitó:

| Se quitó | Por qué |
|---|---|
| **La investigación de época** (agente `researcher`, `epoca.yaml`, lista de anacronismos, fuentes, la regla que los buscaba en la prosa) | No interesa que el libro sea fiel a la historia real. Si es de 1990, con lo que el modelo sabe de 1990 alcanza. La investigación era el paso más lento y menos determinista del arranque, y su ruido tapaba lo que se quería mirar. Ahora la época es un año y un lugar, y la vigilancia la hace el crítico de continuidad leyendo. |
| **El intake y su validación** | Era una copia de las decisiones que ya están en el canon. El JSON de entrada lo consume `crear_libro.py` y no se guarda: lo que se puede derivar no se guarda. |
| **El techo de palabras, el regulador y la contracción del plan** | Con la forma fija (párrafos × líneas × palabras por línea, comprobada en cada escena), el libro entero cabe por construcción. El techo era una regla que no podía cerrar nunca, y una puerta que no puede cerrarse no es una puerta. |
| **Eventos únicos, conocimiento fechado, flashbacks** | Precisión que no cambiaba una línea de prosa y que nadie rellenaba. Lo que queda de eso es trabajo del crítico de continuidad. |
| **La lectura de Langfuse en la UI, los informes y la skill de análisis** | La UI dependía de la red para decir «qué agente corrió». Ahora todo lo que muestra sale de la traza en disco. Langfuse queda como espejo opcional de salida. |
| **Tres libros de prueba y un diagrama viejo** | Describían el sistema anterior. Queda un fixture (`marco-1990`) y un libro real en curso (`nuria-1992`). |

Lo que **no** se tocó: quién decide en cada puerta, la rúbrica con cita, la
dimensión más floja, los scripts que rodean a cada agente, y la traza. Eso es
el proyecto.

---

## 3. Cómo se usa

No hay un comando que escriba la novela. **Se le pide a Claude Code**, en la
terminal o en el panel de VS Code:

```
> escribí una novela sobre un nadador que vuelve de una lesión, en 1975
> seguí con books/nuria-1992
```

1. Si no hay libro, Claude Code sigue la skill **`preparar-libro`**: exprime la
   idea, decide meta, obstáculo, precio e hilos, pregunta **una sola vez** lo
   que de verdad cambia el libro, y crea el canon con un script.
2. Con el canon listo sigue **`dirigir-novela`**: planifica, escribe escena por
   escena, las hace criticar, corrige lo que haga falta y compila.

Mientras trabaja dice una línea por escena aprobada y una por intento fallido,
con el motivo real. Al final hay un `books/<slug>/manuscript/novela.md` y una
traza de cómo se llegó.

También se puede lanzar desde la interfaz web, que por dentro hace exactamente
lo mismo, y que sirve sobre todo para **ver** el sistema y lo que pasó (§8).

---

## 4. El recorrido

Tres fases: **arranque** (una vez), **producción** (una vuelta por escena) y
**cierre** (una vez).

```
IDEA
 └─ preparar-libro (orquestador)  decide y pregunta una vez
     └─ crear_libro.py            escribe el canon: premisa, arco, personajes, timeline
 └─ G0  validate_canon.py         el canon está completo y es coherente
 └─ planner → guardar_plan.py     resumen y tres beats por escena

 POR CADA ESCENA (hasta 3 intentos):
     ├─ empaquetar.py             resuelve el canon a la fecha y arma el prompt
     ├─ escritor | corrector      la prosa
     ├─ guardar_prosa.py          limpia, comprueba la forma, guarda
     ├─ G1  validate_scene.py     los hechos y la forma
     ├─ critic-continuity ┐       dos llamadas separadas, contexto aislado
     ├─ critic-quality    ┘
     ├─ guardar_critica.py        junta las dos lentes, guarda
     ├─ G2  gate_scene.py         releva el veredicto del crítico
     └─ run_scene.py aprobar      marca aprobada, fija la voz con la primera

 AL CERRAR UN CAPÍTULO: lector-capitulo → G3 gate_chapter.py
 G4  validate_book.py             hilos cerrados, tres actos, desenlace
 compilar.py → novela.md
 traza.py                         qué pasó, en prosa
 reportar.py (opcional)           espejo en Langfuse
```

Todo lo que falla vuelve por el **corrector** y se revalida. El contador de
intentos vive en disco (`state.json`): reanudar mañana no reinicia la cuenta.

**G1 corre siempre antes que G2.** Es determinista y gratis; filtrar ahí antes
de convocar dos críticos es lo que mantiene el ciclo barato.

---

## 5. Los agentes

Viven en `.claude/agents/`. Cada uno corre en **su propio proceso, con contexto
limpio**: los dos críticos no se ven entre sí, no saben en qué intento van y no
leen la crítica anterior. Nadie recibe un archivo del canon: recibe **el canon
resuelto a la fecha de su escena**, en prosa, dentro de un prompt que arma un
script.

| Agente | Cuándo entra | Qué recibe | Qué devuelve | Qué **no** hace | Skill |
|---|---|---|---|---|---|
| **planner** | al arrancar, y cuando una escena se atasca | meta, obstáculo, precio, hilos, época, y las escenas con su fecha, su acto y lo que cierran | `resumen` y tres `beats` por escena, en JSON | no escribe prosa; no elige el acto (se calcula); no toca fechas ni hilos | `resolver-canon` |
| **escritor** | cada escena, primer intento | la voz del libro, el canon resuelto, lo que pasó antes, la forma | la prosa, y nada más | no escribe archivos; no juzga su escena; no toca el canon | `escribir-escena` |
| **corrector** | cada intento a partir del 2º | la escena actual, la lista de errores con su arreglo, el canon resuelto | la escena entera, corregida | no reescribe lo que ya pasó; no cambia el canon | `corregir-escena` |
| **critic-continuity** | cada intento, tras G1 | la escena, el canon resuelto, lo que pasó antes | hallazgos con cita; **un hallazgo veta** | no reescribe; no puntúa | `formato-critica` |
| **critic-quality** | cada intento, tras G1 | la escena, el acto y lo que se le pide, el canon resuelto, la voz | **`pasa` con motivo**, la dimensión más floja, la rúbrica con cita | no reescribe; no toca el canon | `formato-critica` |
| **lector-capitulo** | al cerrar un capítulo | las escenas del capítulo seguidas, y el contexto del arco | hallazgos con cita, bloqueantes o no | no repite G1/G2; **no decide si el capítulo pasa** | — |

El **orquestador** (Claude Code siguiendo `dirigir-novela`) no está en la
tabla porque no es un subagente: es quien despacha. Elige el camino, corre los
scripts y acata lo que digan. **Lo único que no puede hacer es decidir que una
escena está bien.**

### Por qué dos críticos y no uno

Son dos criterios incompatibles. La continuidad es binaria, hay contradicción
o no la hay, y **veta**: un solo hallazgo cierra la puerta. La calidad es
gradual y decide en conjunto. Mezclarlas haría que una escena bien escrita
compensara una contradicción, que es justo lo que no puede pasar.

### Las skills

Una skill es el manual de un trabajo concreto, escrito una vez en disco y
cargado idéntico en cada invocación. Es lo que hace que la escena 6 suene igual
que la 1 sin que nadie haya visto las dos.

| Skill | Para quién | Qué fija |
|---|---|---|
| `preparar-libro` | el orquestador | cómo convertir una idea en un canon: qué se calcula, qué se decide, y cuándo preguntar |
| `dirigir-novela` | el orquestador | el recorrido entero, qué correr y qué delegar, las reglas que no se rompen, qué hacer al atascarse |
| `resolver-canon` | planner, y quien lo necesite | cómo se entrega el canon resuelto a una fecha |
| `escribir-escena` | escritor | la voz, la época mostrada y no explicada, la forma |
| `corregir-escena` | corrector | la regla del bisturí: tocar solo lo señalado |
| `formato-critica` | los dos críticos | el JSON exacto del veredicto, el veto y la rúbrica |

---

## 6. Las puertas

Una **puerta** es un punto donde el trabajo se para y alguien dice sí o no. Si
dice que no, la escena vuelve atrás con los motivos y se reescribe.

Hay dos tipos, y la diferencia es el proyecto entero:

- **Puertas de hecho**: comprueban cosas con una respuesta correcta, que se
  pueden contar o comparar. Las abre un script. No opinan, no cuestan nada, no
  se discuten.
- **Puertas de criterio**: comprueban cosas que no se pueden contar. **Decide
  un modelo**, sobre trabajo ajeno y sin ver los intentos anteriores; el script
  solo comprueba que su decisión sea utilizable.

| Puerta | Cuándo | Quién decide | Qué comprueba | Si no abre |
|---|---|---|---|---|
| **G0** el canon | una vez, antes de planificar | script | premisa con época y dos hilos (V1); arco con protagonista, meta, obstáculo, precio y tres actos (V2); timeline coherente con la época y la estructura (V3) | no se escribe una sola línea |
| **G1** los hechos | cada intento | script | la escena cae en su fecha (V3); nadie hace lo que su estado le impide (V4); la forma cuadra (V5) | vuelve al corrector, sin gastar críticos |
| **G2** el criterio | tras G1 | **critic-quality** decide; critic-continuity puede vetar | que el veredicto exista y traiga motivo; que nombre la dimensión más floja; que el veto traiga cita; que toda nota cite; que la crítica no sea más vieja que la prosa | vuelve al corrector con el motivo del crítico |
| **G3** el capítulo | al cerrar un capítulo | lo lee **lector-capitulo**; el script aplica | capítulo completo; toda cita existe en el texto; ningún hallazgo bloqueante | las escenas señaladas vuelven al bucle |
| **G4** la obra | al final | script | todas aprobadas; cada hilo cerrado exactamente una vez (V6); los tres actos con escena y la última en el desenlace (V7) | se replanifica y se vuelve al bucle |

### La rúbrica

Cinco dimensiones, cada una 0, 1 o 2, anclada a una conducta observable.
**No decide nada**: es la medida que permite comparar una corrida con otra y
una versión del prompt con la siguiente. Dos reglas la hacen útil:

- **Toda nota exige cita textual, el 2 incluido.** Si solo se exigiera
  evidencia para las notas bajas, el camino más cómodo sería poner 2 en todo.
- **La dimensión más floja es obligatoria, aunque todas sean un 2.** Con el
  crítico decidiendo, la rúbrica tiende al techo y deja de distinguir; nombrar
  la más débil fuerza una comparación relativa.

| Dimensión | 0 | 1 | 2 |
|---|---|---|---|
| conflicto | no pasa nada: termina como empezó | hay tensión, se resuelve sin costo | algo cambia y tiene precio |
| voz | podría haberlo escrito cualquiera | correcto pero neutro | suena a este libro y a este personaje |
| concreción | se nombran emociones | mezcla mostrar y explicar | la acción y el detalle físico llevan el peso |
| frescura | cliché o frases hechas | alguna muletilla | limpio |
| avance | el protagonista termina donde empezó | se mueve, pero nada le cuesta | algo cambia para él, y paga por ello |

---

## 7. El canon

El **canon** es el expediente del libro: quién es el protagonista, qué quiere,
qué se lo impide, qué le va a costar, en qué época y lugar transcurre, qué
escenas hay y cuándo. Son los YAML de `books/<slug>/context/`.

**Solo lo cambia una persona.** Si una escena contradice el canon, se cambia la
escena. Un ciclo que puede editar el canon para que su texto pase deja de
validar nada. Lo único que el ciclo escribe en `context/` es el **plan**
(`resumen` y `beats` de cada escena) y la **voz** (la muestra fijada con la
primera escena aprobada).

Dos cubos, y de dónde sale cada dato depende de cuál:

| Cubo | Ejemplos | De dónde sale |
|---|---|---|
| **Se decide** | quién es, qué quiere, qué se lo impide, qué le cuesta, qué dos cosas más están en juego, en qué año y dónde | una persona, o el orquestador si le dieron vía libre |
| **Se calcula** | en qué acto cae cada escena, las fechas de las escenas, la clave de cada personaje, la edad a una fecha, el estado vigente | `crear_libro.py` al crear; `resolver_canon.py` al escribir. Nunca se pregunta, nunca se guarda |

**La época no se investiga.** El libro lleva un año y un lugar; el modelo sabe
cómo se vivía entonces. Si hay un detalle que importa fijar, va en una o dos
frases de `notas`. La coherencia de época es trabajo del crítico de
continuidad, que lee con el año en la cabeza.

**El estado de un personaje tiene vigencia.** `lesionado desde el 19 de agosto
hasta el 24 de noviembre, no puede: jugó, entrenó, corrió` es un tramo. A la
fecha de cada escena se calcula cuál rige, se le dice al escritor, y un script
comprueba que la prosa no lo contradiga. Es lo que sostiene un arco de
recuperación, y es la regla que demuestra que el canon se calcula.

**Los tres actos se calculan por fecha** sobre la ventana de la época
(25 / 50 / 25). El escritor recibe en qué acto está y qué se espera de él; el
crítico juzga primero eso; G4 comprueba que los tres tengan escena y que la
última caiga en el desenlace.

---

## 8. La trazabilidad

Un sistema que no se puede mirar por dentro se depura reescribiendo prompts,
que es justo lo que no se quiere. Por eso **todo lo que hace el ciclo deja un
evento en disco, en el momento**, y lo escriben los scripts, nunca el
orquestador.

### Qué se registra

`books/<slug>/reports/traza.jsonl`, un evento por línea, append-only:

| Evento | Quién lo escribe | Qué dice |
|---|---|---|
| **puerta** | la propia puerta al emitir su veredicto (G0 a G4 y `compilar`) | cuál, sobre qué escena o capítulo, si abrió, y **con qué errores** si no (regla, mensaje, arreglo) |
| **agente / inicio** | `empaquetar.py` al armar el prompt | qué agente, sobre qué escena, en qué intento, cuántos caracteres recibió |
| **agente / fin** | el script que guarda su respuesta (`guardar_prosa.py`, `guardar_critica.py`, `gate_chapter.py`) | cuánto tardó, y lo que importa de lo que devolvió: si la forma cuadró, si hubo que recortar un preámbulo, cuántos hallazgos, si aprobó, cuál fue la dimensión más floja |

Además, por escena quedan en `manuscript/`: la prosa, el JSON de G1, el JSON
de la crítica, y el prompt exacto que recibió cada agente.

Si el ciclo se corta a la mitad, lo que pasó hasta ahí queda igual.

### Cómo se lee

- **`python harness/scripts/traza.py books/<slug>`** imprime la corrida en
  prosa: cuántas llamadas a agentes y cuánto tardaron, por agente; cuántas
  veces se aplicó cada puerta y cuántas cerró; y escena por escena, cuántos
  intentos costó y qué dijo cada puerta en cada uno, con sus errores.
- **La interfaz web** tiene tres vistas, todas leídas del disco: *El sistema*
  (los agentes con su skill, las puertas con quién las abre, el ciclo en orden
  tal como lo declara `harness/flujo.yaml`; las piezas que están trabajando
  se encienden), *Lo que pasó* (la línea de tiempo de puertas y agentes de
  todos los libros) y *Las novelas* (el expediente de cada libro: escena por
  escena, en su acto, con intentos, veredicto, dimensión más floja, rúbrica,
  puertas y agentes; y el texto).
- **Langfuse**, opcional: `reportar.py` manda una traza por escena con sus
  intentos y sus puertas, y el veredicto y la rúbrica como scores. Sirve para
  comparar corridas. Sin claves en `.env` no hace nada.

### Qué se puede saber, y qué no

De la traza se sabe **qué pasó y por qué**: cada cierre de puerta con su error,
cada agente con su duración, cuántos intentos costó cada escena. Lo que no está
son los tokens y el coste de cada llamada: eso lo hace Claude Code y no pasa
por ningún script del repo. Si hace falta, el hook oficial de Claude Code lo
manda a Langfuse por conversación.

---

## 9. Las reglas que no se rompen

Cada una está porque su ausencia rompió algo.

1. **Nadie abre su propia puerta.** El escritor no decide si escribió bien; el
   planificador no decide si su plan sirve. El crítico **sí** decide si la
   escena pasa, pero sobre trabajo ajeno y sin ver los intentos anteriores.
2. **Ningún agente escribe archivos, ni el orquestador.** Devuelven prosa o
   JSON y un script lo guarda. Un agente escribiendo YAML mete un `:` sin
   comillas y deja el canon ilegible; pedirle que cree un archivo abre una
   superficie de permisos que falla en silencio. Hay un solo dueño del estado.
3. **Los prompts los arma un script.** El orquestador pasa una ruta, no copia
   el canon. Cada copia a mano era un sitio donde transcribir mal y miles de
   tokens por generación.
4. **El canon solo lo cambia una persona.** Si una escena lo contradice, se
   cambia la escena.
5. **Toda nota de la rúbrica exige cita**, el 2 incluido, y **toda crítica
   nombra la dimensión más floja**.
6. **Todo error dice qué está mal, cuál es la verdad y cómo se arregla.** Un
   error sin `arreglo` no es accionable.

### Las políticas de contexto

Un validador no salva a un modelo al que nunca le dijeron lo que necesitaba.

| Fallo | Política |
|---|---|
| relleno de contexto | ningún paso recibe un archivo del canon: recibe la resolución a su fecha |
| prerrequisitos invisibles | si no está escrito en el canon, no existe |
| borradores rancios | contexto limpio por llamada; una crítica más vieja que la prosa no abre G2 |
| vaivén de altitud | ante un fallo se cambia la regla o el dato, nunca el nivel del prompt |
| depurar solo el prompt | antes de tocar un prompt, comprobar que el dato llegó |
| métricas silenciosas | ninguna puerta abre sin evidencia citable |

> Escribir para no olvidar, aislar para no contaminar, seleccionar para no
> ahogar, comprimir para no interpretar.

---

## 10. Decisiones heredadas

Lo que la versión 10 conserva viene de fallos reales de las versiones
anteriores. Se listan para que nadie las deshaga sin saber qué rompió su
ausencia. El detalle completo está en el historial de git (`SPEC.md` hasta
la 9.2).

| Decisión | Qué la motivó |
|---|---|
| El crítico decide y el script solo comprueba que pueda decidir | Sumar una rúbrica contra un umbral daba una puerta siempre abierta con aspecto de control |
| Cita obligatoria en toda nota, el 2 incluido | La primera corrida completa devolvió un 10/10 a un primer borrador con las cinco citas vacías |
| Dimensión más floja obligatoria | Con el crítico decidiendo, la rúbrica dio 10 / 9 / 10 y no distinguía nada |
| Un hallazgo de continuidad cuenta como veto aunque la lente no lo marque | Un hallazgo con su cita quedaba escrito en el JSON y la puerta lo ignoraba |
| Una crítica más vieja que la prosa no abre G2 | Aprobar con la crítica de un texto que ya cambió es aprobar a ciegas |
| Los prompts los arma un script | El orquestador gastaba más de mil tokens de salida y 35 segundos por generación copiando el canon a mano |
| Los archivos los escriben los scripts | El corrector coló un preámbulo que hubo que recortar a mano; un agente escribiendo YAML lo dejó ilegible |
| Una escena sin beats es un error, no una omisión | El planner devolvió una escena sin beats y el script la saltó en silencio |
| Se comprueba el sistema antes de escribir | Un `:` sin comillas dejó a un agente sin cargar y se supo tres pasos tarde, con el genérico gastando 3,7 veces más |
| La traza la escriben las puertas al emitir, y los agentes al empaquetar y guardar | Una métrica que dependía de la salida de consola decía «cero puertas cerraron» con tres cerradas en disco |
| El prompt a `claude -p` viaja por stdin | En Windows `claude` es un shim `.cmd` y cmd.exe corta el argumento en el primer salto de línea |
| El orquestador corre en sesión limpia | El coste de la primera novela lo dominó el contexto de sesión releído en cada generación, cien veces más que el trabajo de los agentes |
| La novela es de un protagonista, en tres actos | El género romántico anterior metía en el canon una relación con cinco etapas y reglas de pareja que no eran el problema a estudiar |

---

## 11. Historial

Toda modificación de esta especificación se registra aquí, en la misma
entrega que la cambia, con **qué** cambió y **por qué**.

| Versión | Fecha | Cambio | Por qué |
|---|---|---|---|
| **10.0** | 2026-09-17 | **Vuelta a las bases.** Se quita la investigación de época (agente `researcher`, `epoca.yaml`, anacronismos, skills `epoca` y `analizar-traza`), el intake, el techo de palabras y el regulador, los eventos únicos y el conocimiento fechado, la lectura de Langfuse en la UI, los informes y tres libros de prueba. Las reglas se renumeran V1-V7. La traza se lee con `traza.py`. Dos especificaciones nuevas, funcional y técnica, sustituyen al SPEC anterior. | El sistema había puesto la complejidad en la fidelidad histórica y en el control del tamaño, que no eran el problema. Lo que se quiere estudiar son las puertas, el criterio con evidencia y la traza: eso se conserva entero y ahora se ve. |
