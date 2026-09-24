# Plan de implementación · backend

> Compañero de [`specs/srs-backend-v1.md`](../specs/srs-backend-v1.md), que dice **qué** hay que construir. Este documento dice **de dónde se parte, en qué orden se sigue y con qué ficheros**.
> No es un SRS y no añade requisitos: todo lo que aparece aquí tiene su `RF`, `RD`, `RI` o `RNF` en la spec, o su sección en `architecture.md`. Si algo no lo tiene, es un error de este documento.

El plan tiene tres bloques. El **bloque 1** cierra la versión 1 —pasos 1 a 6 de `architecture.md` §14— hasta que una tirada real va del brief al cierre de obra sin intervención. El **bloque 2** son los pasos 7 a 10, que compran escala y calidad, y no empieza hasta que el bloque 1 pasa su puerta. Sin esa frontera se pule calidad sobre un canon que todavía no evoluciona. El **bloque 3** es la versión 4 (§8): verificación formal, guardarraíl, observabilidad y evaluación, sin paso nuevo.

---

## 1. De dónde se parte

### 1.1 Lo que está en verde

Medido el 2026-09-23 sobre la rama `v2-oneshot`:

| Comprobación | Resultado |
|---|---|
| `pytest` | 688 recogidas y en verde, con el contrato generativo sobre todas las rutas |
| `mypy --strict` | Limpio, 225 ficheros |
| `import-linter` | 3 contratos, 0 rotos: las tres reglas de `architecture.md` §2.3 se cumplen, `supervision/` y `evals/` incluidas |
| TLC | El modelo de `orchestration/model/` con los estados de la versión 2, sin contraejemplo, con la salida guardada en `model/tlc/`: `chapter.cfg` 1.831 estados distintos y `run.cfg` 508.470, profundidad 242, con 5 capítulos y `PlanAttempts = 2`. Las mutaciones versionadas `mutations/m1` a `m4` dan contraejemplo, y `code-today/` conserva los contraejemplos B1 a B4 del código anterior al arreglo, que los cerró con una prueba por fallo (`orchestration/model/README.md` §7.1) |
| Lean | `python -m verification.formal.fixtures` en la puerta: la fixture limpia se demuestra y la sembrada falla en sus cuatro teoremas y en nada más (RF-246) |
| `gate.py` | Existe como un solo comando; CI lo ejecuta en cada cambio y la puerta lenta —`pip-audit`, mutación— a diario |

### 1.2 Estado por tramo del SRS

Lo que el SRS §11 pedía a cada tramo y lo que le faltaba al arrancar este plan, con el tramo que lo cerró. Hoy no falta nada de esta tabla (§1.7).

| Tramo | Entregado por el SRS | Lo que faltaba, y dónde se cerró |
|---|---|---|
| **T0** `commons/` | Puerto con `complete` en dos modos y `embed` local; contador `tiktoken` × factor con calibración al arrancar; memoria de trabajo acotada a `wm_*`; tipos que cruzan funcionalidades; ajustes con validación del identificador de novela | El emisor de la traza. **T9** |
| **T1** `canon/` lectura | Esquema de los cinco almacenes con versión, registro de eventos, proyecciones reconstruibles, `canon.query`, `state-at`, `knowledge-of`, `related`, carga del brief, rutas RI-01, RI-04 a RI-06 | Nada |
| **T2** `planning/` | `outline.check` determinista, prompt del Arquitecto, `scene_spec.from_entry`, registro de setups, puerta de acto, ruta RI-07 | Prompt del Planificador (`scene.spec` como agente de modelo); `replan.arc`. **T12** |
| **T3** `context/` | Construcción de la consulta, dos piernas, fusión por rangos, cupos, ensamblaje y compactación sin truncar, auditoría | Recetas por agente destino de §4.9. **T15** |
| **T4** `generation/` | Prompt del Escritor con prefijo cacheable; `match.simulate` determinista con semilla | `match.narrate`. **T13** |
| **T5** `verification/` | Los siete `check.*` deterministas con cita | `continuity.review`; `revise.targeted`. **T14** |
| **T6** `canon/` escritura | `prose.chunk`, índice en dos niveles con FTS5 y vectores, congelación transaccional que ya acepta `delta` y `new_proscribed`, purga de memoria de trabajo | `delta.extract`, `summarize.hierarchical` como skill y detección de términos a proscribir. **T10** |
| **T7** `canon/` arbitraje | Política de precedencia, total y sin ciclos | Las dos puertas del Árbitro, Orquestador y Documentalista. **T11** |
| **T8** `orchestration/` | `loop`, `checkpoint`, `admission`, `retries`, `dispatch`, servidor de herramientas con cupo, `app.py` | Rutas RI-02 y RI-03; raíz de composición que arme el motor real; paso por `admission` y `dispatch`; cuarentena de capítulo (D-26); modelo TLA+ de VER-18. **T14, T15** |

### 1.3 Estado por agente

| # | Agente | Estado |
|---|---|---|
| 0 | Orquestador | Código. Bucle entero cableado: admisión, dispatch, cuarentena, Jurado en paralelo, pase de estilo, retcon, Supervisor |
| 1 | Arquitecto | Prompt, verificador determinista y reintento con los defectos del intento anterior (RF-27) |
| 2 | Planificador | Prompt de `scene.spec` y reespecificación más estricta |
| 3 | Documentalista | Código. Recuperación completa y recetas por agente de §4.9 |
| 4 | Escritor | Prompt con prefijo cacheable; el reintento lleva el defecto y su evidencia (§4.1) |
| 5 | Especialista deportivo | `match.simulate` y `match.narrate` |
| 6 | Continuista | `check.*` y `continuity.review` con cita anclada |
| 7 | Jurado | Tres instancias en paralelo bajo admisión, anclaje, dispersión, mediana, segunda ronda y conjunto dorado |
| 8 | Reparador | `revise.targeted` con aceptación sin regresiones |
| 9 | Estilista | `style.polish`, reverificación con reversión y huella |
| 10 | Archivero | `delta.extract` validado al congelar |
| 11 | Árbitro | Precedencia, sus dos puertas y `retcon.propose` con la regla dura en código |
| 12 | Supervisor | Trece señales, veredicto acotado y replanificación por métrica; si no responde cuenta como sano |

### 1.4 Lo que la tirada real enseña

La primera tirada completa con modelo real llegó a la puerta del Jurado en el capítulo 1 y destapó fallos que ninguna prueba con dobles podía ver, porque los cuatro dependen de cómo escribe y cómo cita un modelo de verdad:

| Fallo | Causa | Corrección |
|---|---|---|
| El examen dio por falladas 5 de 6 respuestas correctas | Exigía el nombre completo de la clave | D-64: basta la clave entera o una palabra distintiva suya |
| El Jurado descartó 15 de sus puntuaciones y el ritmo se quedó sin nivel | Citas que unían párrafos con « / » y citas de ritmo atribuidas a «el capítulo» | D-65 y D-66; el prompt del juez exige copia literal de un párrafo, de 8 a 25 palabras |
| Tres intentos de escena seguidos en presente | El reintento no llevaba el defecto: era la misma llamada otra vez | El reintento lleva el defecto y su evidencia, como ya pedía `architecture.md` §4.1 |
| `check.timeline` marcaba «1 de esta» como fecha | La expresión aceptaba cualquier palabra tras «de» | Solo nombres de mes |
| La tirada cayó entera cuando el CLI salió con error en una llamada del Jurado | El fallo del proveedor no se capturaba: subía hasta el bucle | Consume un intento del mismo presupuesto de la llamada, como `architecture.md` §4.8 pide para el fallo intermitente; agotado, sube, y la tirada se reanuda desde la última escena cerrada (RF-20) |
| La segunda tirada abortó en el capítulo 1 con cuatro dimensiones del Jurado sin nivel | El juez recortaba citas con «...» y citaba frases cortas; lo descartado contaba como defecto del texto y el Reparador arreglaba lo que no estaba roto | D-71: la cita que no ancla vuelve al juez con su motivo dentro del presupuesto de llamada; la traza de la puerta de capítulo lleva ya los defectos con su cita |
| El Continuista marcó como S1 cuatro adjetivos que la guía de estilo prohíbe | El prompt dice que no valora estilo y el modelo lo hace igual; CAL-06 pone el estilo en S3 y su dueño es el Estilista | RF-51 en código: el prompt enumera los ámbitos de continuidad y el anclaje descarta lo que caiga fuera como defecto de proceso (RF-111) |
| El Supervisor declaró deriva tras el capítulo 1 por «recuperaciones degradadas» | La recuperación se marcaba degradada siempre que la pierna semántica volvía vacía, y al empezar la obra no hay prosa que recuperar | Degradado es que la pierna no pudo ejecutarse, como dicen `architecture.md` §4.4 y §11: sin vector de consulta, o con prosa indexada que no devuelve |
| El capítulo 2 dio por agotada su primera escena al primer fallo | El presupuesto de reintentos era uno para la obra entera, y cada escena heredaba los intentos de la anterior | Presupuesto nuevo por capítulo, y contador de escena a cero al empezar cada escena y al entrar en la puerta de capítulo (RF-18, §7.3) |

La tirada se archivó en `runs-golden/intento-1/` y se relanzó con las correcciones.

### 1.5 Decisiones ya fijadas que este plan respeta

Están en el SRS §9 y en `architecture.md`. Si al implementar parece que alguna está mal, eso dispara el proceso B de `AGENTS.md` §6.3, no un parche.

| Decisión | Dónde |
|---|---|
| Traza local JSONL por tirada como fuente de verdad, con Langfuse como espejo; un fallo al trazar o al exportar se registra y se continúa | D-11, RI-16, RNF-13 |
| Claude Haiku 4.5 a través del CLI de Claude Code, con la suscripción del autor | D-23, `architecture.md` §4.8 |
| El andamiaje del CLI —38.600 tokens medidos— no cuenta contra el techo de 100.000; sí contra la ventana real, donde la admisión lo descuenta | D-35 |
| Capítulo en cuarentena se rehace de inmediato; no se salta al siguiente | D-26, RF-107 |
| Retcon no existe en la versión 1: el canon congelado siempre gana | D-05 |
| Puerta de capítulo sin Jurado: cero S1 y máximo 2 S2 del Continuista | D-06 |
| Puerta de acto solo en su mitad determinista, la deuda | D-27 |
| Sin Supervisor replanifica el Planificador a nivel de escena y el Arquitecto a nivel de tramo | D-04 |
| Dos fábricas de escritura: canon en `canon/db/`, memoria de trabajo en `commons/db/` | D-30 |
| La proscripción la inserta la congelación | D-32, RF-108 |

### 1.6 Trampas que siguen vivas

Producen código que funciona en la demo y falla en el capítulo 20.

1. **`tiktoken` crudo.** Todo lo que devuelve va multiplicado por el factor y redondeado hacia arriba (RI-20).
2. **Algo voluble delante del prefijo cacheable.** Un byte distinto invalida la llamada entera, sin error (RF-103). Con el CLI la instrucción del sistema es lo único estable entre llamadas: ahí va el prefijo.
3. **Confundir las dos fábricas de escritura** (RD-09, RD-18).
4. **Proyecciones que dependen del orden de inserción.** `(world_time, world_seq)` es único; la colisión se rechaza (D-34).
5. **Fragmentos que cruzan la frontera de su escena** (RD-16, RF-70).
6. **Truncar.** Se sustituye por resumen o se niega (RF-84, RF-94).
7. **Escenas en paralelo.** Van en serie, siempre (RF-45).
8. **Empezar el capítulo N+1 con el N sin congelar** (RF-107).
9. **Embeddings dentro de la transacción** (RNF-21).
10. **La memoria de trabajo en un paquete** (RF-37).
11. **Embeber sin los prefijos de E5**: `query: ` y `passage: ` (RF-102).
12. **Un delta vacío tratado como éxito.** Una escena que cambia algo produce eventos; un `delta.extract` que devuelve vacío sobre una escena con cambio de valor declarado es un fallo del agente y consume un reintento, no una congelación limpia.
13. **Contrastar el estimado contra un `usage` que lleva el andamiaje del CLI.** El `usage` incluye los 38.600 del CLI; el estimado del paquete no. Se comparan después de sumar el andamiaje al estimado, o RNF-19 dispara siempre (D-35).

### 1.7 Estado de los tramos de este plan

| Tramo | Estado |
|---|---|
| T9 a T15 | Puerta pasada |
| T16 | Código listo; falta que la tirada real cierre la obra y su fichero se copie a `golden/v1-seed/` |
| T17 | Hecho |
| T18, T19 | Puerta pasada con dobles; la medida sobre la semilla espera a T16 |
| T20 a T23 | Construidos, cableados en el bucle y en verde |
| T24 | Bucle completo, rutas RI-29 y RI-30, TLC sin contraejemplo; falta la tirada real de la versión 2 y su comparación con la semilla |
| T37 | Hecho: `specs/srs-backend-v4.md` y su propagación |
| T38 a T44 | Construidos, integrados en `v2-oneshot` y en verde. Queda una línea de código de T44: `violenta` y `macabra` en `canon/brief_rules.py:ADULT_TERMS`, con su prueba (D-99) |
| T45 a T51, T53 | Construidos, integrados en `v2-oneshot` y en verde, con su sincronización inversa en `specs/srs-backend-v4.md` (D-107 a D-112) |
| T52 | En curso: las cinco tiradas de evaluación, de una en una y sobre un commit etiquetado (RNF-58). Espera también a T16 para la lectura humana de una novela completa |

---

## 2. Bloque 1 · cerrar la versión 1

Ocho tramos, T9 a T16, que continúan la numeración del SRS §11 para que un identificador de tramo signifique una sola cosa. **Un tramo no empieza hasta que el anterior pasa su puerta.** Cada tramo termina con la sincronización inversa de `AGENTS.md` §6.5 —estructura, spec, matriz de verificación, glosario, §2 de `AGENTS.md`— y no se da por cerrado hasta que vuelve.

El orden tiene una regla: **primero lo que hace que el canon evolucione, después lo que lo protege, al final lo que lo ejecuta de verdad.** Archivero antes que Árbitro porque sin delta no hay conflicto que arbitrar; Continuista antes que la raíz de composición porque una tirada real sin Continuista congela errores con la misma solemnidad que aciertos.

### T9 · Traza local y saneamiento

```
commons/tracing/
└── trace.py              · emisor y lector: un registro JSONL por llamada, defecto, reintento, admisión y arbitraje
orchestration/
├── dispatch.py           · cada llamada emite su registro con agente, tokens reales, estimados y andamiaje (D-35)
├── admission.py          · emite admisión, encolado y liberación con la ocupación en vuelo
└── loop.py               · emite cada decisión de la escalera con su regla, y cada puerta con su veredicto
```

| Requisitos | RI-16, RI-17, RI-23, RF-24, RF-39, RF-100, RNF-13, RNF-14, RNF-24 |
|---|---|
| **Puerta** | Una tirada con dobles deja un registro por llamada con agente, capítulo, intento, tokens reales y estimados; borrar el fichero de traza a mitad no detiene la tirada |

**Lo que se hace aquí y no después:** la traza va antes que cualquier agente nuevo porque los tramos T10 a T14 se depuran leyéndola. Añadirla al final es la forma conocida de no añadirla. El registro lleva el andamiaje del CLI como campo propio, para que RNF-19 compare lo comparable (trampa 13).

### T10 · Archivero

```
canon/archivist/
├── prompts.py            · delta.extract: prefijo cacheable con el catálogo de tipos de evento; instrucción con el capítulo y el estado en t
├── extract.py            · valida la salida; renumera los desempates detrás de lo registrado (RD-19); el delta vacío es un fallo
└── proscription.py       · n-gramas que el capítulo hace repetidos, sin palabras funcionales, para que la congelación los inserte
canon/summaries/
└── prompts.py            · summarize.hierarchical, niveles escena y capítulo, con los tamaños de §4.5
orchestration/loop.py     · el Archivero extrae antes de congelar; `_freeze` escribe solo el delta validado
```

| Requisitos | RF-12, RF-55, RF-56, RF-57, RF-58, RF-90, RF-108 |
|---|---|
| **Puerta** | Tras congelar un capítulo con dobles, `event` contiene los eventos del delta y `state-at` en el instante del capítulo devuelve el cambio; un delta vacío sobre una escena con cambio de valor consume un reintento; un delta que no valida no escribe nada |

**El Archivero tiene herramientas** (`canon.lookup`, `context.budget`, cupo 15.000, `architecture.md` §6.3): para saber si un hecho es nuevo tiene que poder preguntar si ya existe. Es la primera llamada con herramientas que corre de verdad, así que aquí se estrena `complete_with_tools` contra el servidor de `orchestration/tools/`.

### T11 · Árbitro, las dos puertas

```
canon/arbiter/
├── precedence.py         · ya existe
└── entries.py            · puerta 1: `validate_delta`, cada rechazo es un S1 con cita para el Reparador (RF-60)
                          · puerta 2: `resolve_claims`, la usa el Documentalista sobre los hechos del paquete
```

Sin `retcon.propose`: en la versión 1 el canon congelado gana siempre (D-05), así que la política decide sin llamada de modelo. El prompt del Árbitro llega con el retcon, en T23.

| Requisitos | RF-59 a RF-63 |
|---|---|
| **Puerta** | Un delta que contradice un hecho congelado se resuelve por precedencia sin detener la tirada y queda registrado en la traza; un paquete con dos hechos incompatibles se arbitra antes de llegar al Escritor |

**Por qué `context/audit` puede llamar al Árbitro sin romper la regla de importación:** el Árbitro vive en `canon/`, del que toda funcionalidad puede importar (`architecture.md` §2.3 y §6.2). No es una excepción a los tres pisos.

### T12 · Planificador y replanificación

```
planning/scene_spec/
├── spec.py               · ya existe: la parte determinista, `from_entry`
└── prompts.py            · scene.spec como agente de modelo; `parse` impone EST-I1; los defectos previos endurecen la especificación
planning/replan/
└── arc.py                · replan.arc: reemplaza solo el tramo pedido, recoloca cobros y resoluciones; nunca toca lo congelado
orchestration/loop.py     · la puerta de acto replanifica el acto siguiente; la cuarentena de capítulo replanifica el suyo
```

| Requisitos | RF-28 a RF-31, RF-105, RF-106; RF-19 en su parte de replanificación |
|---|---|
| **Puerta** | Toda especificación producida por el doble del Planificador cumple EST-I1 y pasa `outline.check` de vuelta; una puerta de acto fallida replanifica el acto siguiente y la deuda vuelve a estar planificada |

### T13 · Especialista deportivo

```
generation/sports/
├── simulate.py           · ya existe
└── narrate.py            · match.narrate: la cronología entra como dato con nombres y minutos
verification/checks/deterministic.py · `check.milestones`: todo goleador de la cronología aparece en la prosa
orchestration/loop.py     · escena con `is_match`: simulate antes que narrate, siempre; `verify_match` contrasta marcador, goleadores y disponibilidad
```

| Requisitos | RF-42 a RF-44 |
|---|---|
| **Puerta** | Una escena de encuentro narrada por el doble contiene exactamente los hitos de la cronología; un hito inventado dispara `check.ledger` con cita |

### T14 · Continuista, Reparador y cuarentena

```
verification/checks/evidence.py · `check.evidence`: normaliza, exige ocho palabras y una sola aparición, devuelve la posición en el original
verification/gates.py     · las dos puertas de la versión 1 como funciones puras: escena y capítulo (D-06)
verification/continuity/
├── prompts.py            · continuity.review: capítulo entero y canon que podría contradecirlo
└── review.py             · ancla cada cita con `check.evidence`; la que no ancla se descarta y consta (RF-111)
verification/repair/
├── prompts.py            · revise.targeted: la escena entera con el defecto y su cita delante
└── targeted.py           · agrupa por zona y decide si la reparación valió: la que abre un S1 nuevo se revierte (RF-54)
verification/quiz/
├── build.py              · quiz.build: preguntas con clave desde la especificación, sin modelo
├── prompts.py            · quiz.answer: solo el capítulo, las preguntas y la instrucción; sin prefijo cacheable
└── grade.py              · quiz.grade: cada respuesta errónea es un S2 que entra por la puerta de capítulo
orchestration/loop.py     · puerta de capítulo, pases de reparación con la escalera de escena, cuarentena que rehace y replanifica (D-26)
```

| Requisitos | RF-46 a RF-54, RF-110 a RF-115, RI-19 |
|---|---|
| **Puerta** | Un S1 sembrado por un doble en un capítulo se detecta con cita, se repara, se revalida desde `check.*` y se congela; una respuesta errónea del examen entra como S2 por la misma puerta; un capítulo que agota su presupuesto se rehace entero y nunca se salta; cobertura de mutación ≥ 90 % leída de CI, no supuesta |

**El Continuista es el agente caro** (47.500 de entrada más 25.000 de cupo) y el primero que tocará el techo al crecer la obra (`architecture.md` §12). Su recuperación es dirigida por afirmaciones, sin cupos y con la pierna léxica al frente (D-17): aquí se escribe su receta en `context/packing/`, y con ella las de los demás agentes destino de §4.9 que T3 dejó genéricas.

### T15 · Raíz de composición y ejecución real

```
context/retrieval/
├── candidates.py         · de identificadores de fragmento a candidatos con lugar, POV, diálogo y promesas
└── retrieve.py           · `prose.retrieve`: piernas, fusión, cupos; degradación marcada sin fallo cerrado
context/packing/recipes.py · las tablas de §4.2 y §4.9 como datos; los once bloques del Escritor; receta plana de los demás
generation/writer/drafts.py · borradores en `wm_draft`: los lee la reanudación y el bloque 6 del Escritor
commons/provider/claude_cli.py · bucle de herramientas por protocolo (D-46)
orchestration/
├── engine.py             · `Composer`: arma cada callable del `Engine` con receta, auditoría, admisión, dispatch y parseo
├── compose.py            · arranque real: embeddings verificados (RF-101), factor calibrado por llamada (RF-104), `python -m orchestration.compose`
├── routes.py             · RI-02 POST /novels/{id}/run · RI-03 GET /novels/{id} · RI-27 GET /novels/{id}/trace
├── loop.py               · reanudación desde la última escena cerrada, con los borradores; probada con caída simulada
└── model/
    ├── chapter.tla       · máquina de estados del ciclo de vida del capítulo, `architecture.md` §7
    └── chapter.cfg       · los seis invariantes de `verification.md` §5.10; TLC corre en la puerta lenta de CI
```

| Requisitos | RF-13 a RF-23, RF-66, RF-91 a RF-99, RF-107, RNF-01 a RNF-09, RNF-11, RI-02, RI-03, RI-08, RI-27 |
|---|---|
| **Puerta** | TLC no encuentra contraejemplo a los seis invariantes; una tirada con dobles lanzada por `POST /novels/{id}/run`, interrumpida a mitad de capítulo y relanzada, termina con el mismo manuscrito; `schemathesis` en verde sobre las tres rutas |

**El modelo TLA+ es lo único de la puerta de T8 que no se pasó.** Va aquí y no en T8 porque el flujo que modela —admisión, cuarentena, reparación, reanudación— no está entero hasta T14. Modelar un flujo a medias es modelar otro flujo. Corre en la puerta lenta de CI, no en cada cambio.

### T16 · Tirada real y semilla del conjunto dorado

```
golden/
└── v1-seed/
    ├── brief.json        · el brief de la tirada
    ├── novel.sqlite      · el fichero congelado
    └── trace.jsonl       · su traza completa
```

| Requisitos | RNF-03, RD-12; la Definición de terminado del SRS §11.2 |
|---|---|
| **Puerta** | Una tirada **con modelo real** va del brief al cierre de obra sin intervención; copiar el fichero y abrirlo devuelve las mismas proyecciones y la misma recuperación; la traza muestra que ningún estimado quedó por debajo del real sumado el andamiaje |

Es la puerta del bloque entero. El fichero que produce es el primer elemento del conjunto dorado CAL-10, que el bloque 2 necesita para calibrar al Jurado y afinar la recuperación: se guarda en el repositorio porque es el único artefacto que demuestra que el sistema funciona y no solo que el camino existe.

---

## 3. Bloque 2 · versión 2: pasos 7 a 10 y retcon

No empieza hasta que T16 pasa. Su spec ya existe: [`specs/srs-backend-v2.md`](../specs/srs-backend-v2.md), que es T17. Los tramos de abajo son los de su §11 con los ficheros que cada uno toca; los requisitos y las puertas son los de la spec y no se repiten distintos aquí.

### T17 · `specs/srs-backend-v2.md`

Hecho. Cierra las decisiones abiertas nº 2, 3, 4 y 9 de `architecture.md` §13 (D-36 a D-39), deja la nº 10 para la medida de T19, y mete el retcon (D-43) y los evals (D-44) en el alcance. Cualquier cambio en los tramos siguientes que exija un número o un término nuevo vuelve aquí primero.

### T18 · Resúmenes de arco y de obra

```
canon/summaries/
├── prompts.py            · gana los niveles arc y work
└── levels.py             · cuándo se regenera cada nivel: arco al cerrarse, obra cada 5 capítulos
canon/db/migrations.py    · esquema v2: summary_version con los capítulos que cubre cada nivel (RD-23), y las tablas de T20 a T23
context/packing/recipes.py· los bloques de resumen de arco y obra entran donde §4.9 los pone
```

| Requisitos | RF-116 a RF-120, RD-23, RI-35, RNF-29 |
|---|---|
| **Puerta** | El paquete del Continuista en el capítulo 20 de la semilla ocupa menos que sin resúmenes de arco |

### T19 · `evals/` · medir antes de tocar

```
evals/
├── retrieval_golden.py   · conjunto dorado de recuperación construido desde la escaleta y el canon de la semilla
├── retrieval_score.py    · acierto por cupo y agregado, determinista
├── grid.py               · malla acotada sobre tamaño de fragmento, constante de fusión y reparto de cupos
├── compare.py            · dos tiradas, mismas medidas, tabla de diferencias
└── adversarial/          · los casos de verification.md §5.9 como pruebas que afirman la contramedida
orchestration/engine.py   · cada llamada lleva el identificador de versión de su prompt (RI-34): hash de sus módulos de prompt
```

| Requisitos | RF-121 a RF-125, RF-156 a RF-158, RD-27, RI-34, RNF-35, RNF-36 |
|---|---|
| **Puerta** | La malla corre entera sobre la semilla y el valor elegido queda registrado en `architecture.md` §4.4 y §13. `evals/` vive en el piso de `orchestration/` (D-44) |

### T20 · Jurado y conjunto dorado de defectos

```
commons/types/rubrics.py  · las rúbricas CAL-02 como datos versionados, sembradas con el brief (RNF-37)
verification/jury/
├── prompts.py            · voice, pacing, subtext y theme .audit; sin guía de estilo en el prefijo
├── verdict.py            · check.evidence sobre cada puntuación, dispersión, mediana, veredicto inválido
└── golden.py             · las cinco transformaciones deterministas que siembran defectos
verification/routes.py    · RI-29 GET /novels/{id}/chapters/{n}/verdict
canon/db/migrations.py    · scene_verdict (RD-20)
canon/freeze/rows.py      · filas de veredicto, huella y métricas que la congelación escribe junto al capítulo
orchestration/loop.py     · tres llamadas admitidas por separado y lanzadas en paralelo; puerta de capítulo completa
```

| Requisitos | RF-126 a RF-136, RD-20, RI-29, RNF-28, RNF-31, RNF-32, RNF-37 |
|---|---|
| **Puerta** | El Jurado detecta ≥ 90 % del conjunto dorado; tres instancias sobre un capítulo en el techo de EST-07 caben y corren en paralelo bajo admisión |

### T21 · Estilista y huella

```
verification/style/
├── fingerprint.py        · las cinco métricas de RF-137 con spaCy en proceso (D-40)
├── drift.py              · referencia de los tres primeros capítulos, desviación, deriva sostenida
└── prompts.py            · style.polish
context/packing/recipes.py · muestra modélica por puntuación de voz, rotativa (RF-140); sustituye a la elección por recencia
verification/routes.py    · RI-30 GET /novels/{id}/style
canon/db/migrations.py    · chapter_fingerprint (RD-21)
orchestration/loop.py     · Estilista tras el Jurado; reverificación por el Continuista; puerta de capítulo cerrado con huella
```

| Requisitos | RF-137 a RF-143, RD-21, RI-30, RNF-33 |
|---|---|
| **Puerta** | La huella de la semilla es estable dentro de tolerancia; un pase de estilo que abre un S1 se revierte |

### T22 · Supervisor y métricas de salud

```
supervision/
├── metrics.py            · metrics.report: las trece señales de §11 desde la traza y el canon, con umbral y estado
├── prompts.py            · el Supervisor, con canon.lookup y context.budget, cupo 20.000; su veredicto —sano, o deriva con la señal y el tramo— acotado por código
└── routes.py             · RI-28 GET /novels/{id}/health
canon/db/migrations.py    · chapter_metrics (RD-22)
planning/act_gate/gate.py · la mitad de juicio: curva realizada frente a planificada (RF-148)
orchestration/loop.py     · Supervisor tras cada congelación; replan.arc por métrica
pyproject.toml            · supervision/ entra en los tres contratos de import-linter
```

| Requisitos | RF-144 a RF-150, RD-22, RI-28, RNF-26, RNF-27 |
|---|---|
| **Puerta** | Las trece señales se calculan desde la traza de la semilla; una deriva sembrada dispara `replan.arc` sin detener la tirada |

### T23 · Retcon

```
canon/arbiter/
├── retcon.py             · retcon.propose —el modelo solo propone— y la regla dura como código: no cobrado y ≤ 3 pasajes (RF-152)
└── refreeze.py           · recongelación atómica de una escena: índice, resumen, vigencia del hecho anterior
canon/db/migrations.py    · retcon (RD-24)
canon/routes.py           · RI-31 GET /novels/{id}/retcons
```

| Requisitos | RF-151 a RF-155, RD-24 a RD-26, RI-31, RNF-30 |
|---|---|
| **Puerta** | Un retcon admisible recongela sus escenas y deja canon e índice coherentes; uno inadmisible no toca nada |

### T24 · Bucle completo y tirada real de la versión 2

```
orchestration/
├── loop.py               · el flujo de §7.1 entero, trece agentes
└── model/chapter.tla     · estados nuevos: juzgando, puliendo, supervisando, retcon
golden/v2-run/            · la tirada real de la versión 2, comparada con v1-seed por evals/compare.py
```

| Requisitos | RF-159 a RF-161, RI-32, RI-33, RI-36, RNF-34 |
|---|---|
| **Puerta** | TLC sin contraejemplo; una tirada real con los trece agentes cierra la obra sin intervención y ninguna dimensión de CAL-01 queda peor que en `golden/v1-seed/` |

---

## 4. Lo que se construye en cada tramo aunque no lo parezca

| Qué | Cuándo | Por qué no al final |
|---|---|---|
| **Traza** | Desde T9, en cada llamada | Los tramos siguientes se depuran leyéndola |
| **Rutas HTTP** | Cada tramo añade las suyas dentro de su carpeta | Concentrarlas deja los tramos anteriores sin forma de ejercitarse |
| **Regla de importación** | Ya está en CI; cada tramo la mantiene en verde | Ver `pyproject.toml` |
| **Sincronización inversa** | Al cerrar cada tramo, `AGENTS.md` §6.5 | Sin ella la spec describe en dos meses un sistema que ya no existe |
| **Dobles deterministas de cada agente de modelo** | En el mismo tramo que el agente | Sin doble no hay prueba en CI, y una prueba que gasta modelo real no corre en cada cambio |

---

## 5. Definición de terminado

**Bloque 1:**

- [ ] T9 a T16 pasaron su puerta
- [ ] La puerta de CI del SRS §7.2 en verde, y la puerta lenta —mutación ≥ 90 %, TLC sin contraejemplo— leída
- [ ] Todo requisito del SRS v1 con su método principal ejecutándose, o en el riesgo aceptado de §7.4
- [ ] **Una tirada real va del brief al cierre de obra sin intervención** (RNF-03)
- [ ] Copiar el fichero de la novela y abrirlo da las mismas proyecciones y la misma recuperación (RD-12)
- [ ] `golden/v1-seed/` existe y es la tirada que lo demuestra

**Bloque 2:**

- [ ] T18 a T24 pasaron su puerta
- [ ] Todo requisito del SRS v2 con su método principal ejecutándose, o en su §7.4
- [ ] Una tirada real con los trece agentes cierra la obra sin intervención y ninguna dimensión de CAL-01 queda peor que en `golden/v1-seed/`
- [ ] La decisión abierta nº 10 cerrada con la medida de T19; las nº 1, 5 y 6 declaradas abiertas con su motivo en los dos sitios

---

## 6. Riesgos de este plan

| Riesgo | Señal | Qué se hace |
|---|---|---|
| El CLI de Claude Code cambia su andamiaje y los 38.600 dejan de ser el suelo | El campo de andamiaje de la traza se mueve entre tiradas | El valor es una constante medida en `claude_cli.py`; se recalibra al arrancar igual que el factor del contador, y RNF-19 lo delata |
| La tirada real de T16 no cierra por coste o por tiempo | La traza muestra reintentos en escalera antes del cierre | Se acorta el brief, no la puerta: la condición es cerrar sin intervención, no cerrar largo |
| El Continuista no cabe con el andamiaje en la ventana real | Ocupación real de su paquete en la traza | Es el riesgo que T18 existe para retirar; hasta entonces, riesgo aceptado del SRS §7.4 |
| Un agente nuevo devuelve algo que valida pero no significa nada —delta vacío, defecto sin cita— | Tasa de descartes por `check.evidence` y de deltas vacíos en la traza | Trampa 12: se rechaza y consume reintento, nunca se congela |
| El Escritor no ve las prohibidas del guardarraíl cuando hay muchos n-gramas proscritos | `context/packing/recipes.py:proscription_recent` ordena `proscribed` por `added_chapter DESC` con tope, y las del guardarraíl tienen `added_chapter = 0`: reintentos por `check.forbidden` que el paquete habría evitado | El guardarraíl las sigue parando, así que no se congela ninguna; el dueño de `context/` ordena primero por nivel, `level <> 'estilo'`, en un cambio propio |
| Tres fallos de código que el arreglo de B1 a B4 vio y no tocó | `loop.py:_work_closes` usa `report.words`, que tras reanudar solo cuenta los capítulos de esa invocación, así que RF-23 mira una longitud parcial; `canon/manuscript.py:_current_texts` une fragmentos sin quitar el solape y la historia se guarda con `scene_text_from_chunks`, que sí lo quita; la especificación reescrita por `engine.respec` no se guarda y, tras caer después de una cuarentena de especificación, el capítulo se rehace con la de `specs_for` | Proceso C para el dueño de cada fichero: `_work_closes` con `_frozen_words(path)` siempre, una sola regla de unión de fragmentos, y la especificación reescrita en el punto de reanudación (`architecture.md` §7.4) |
| Empezar el bloque 2 sin la semilla de T16 | Un módulo en `supervision/`, `jury/` o `evals/` sin `golden/v1-seed/` en el repositorio | El SRS v2 lo declara supuesto (§2.6): sin semilla no hay contra qué medir, y medir es lo que el bloque 2 hace |

---

## 7. Cobertura de `architecture.md`

Una fila por sección. Lo que queda sin tramo en el bloque 1 está en el bloque 2 o fuera del backend.

| Sección | Tramo | Estado |
|---|---|---|
| §1 Principios | §1.6, las trampas | Cubierto |
| §2.1 a §2.3 Monorepo y paquete por funcionalidad | En verde; `supervision/` en T22, `evals/` en T19; `verification/formal/` en T43, `.claude/` en T45, `frontend/visual/` en T49 | Cubierto |
| §3.1 Cinco almacenes | T1, T6 entregados; delta en T10; niveles de proscripción en T41, hecho × escena y cronología en T42, elementos del brief en T47 | Cubierto en T10; bloque 3 |
| §3.2 Memoria de trabajo | T0 entregado | Cubierto |
| §3.3 Escritura del índice | T6 entregado; hecho × escena en T42 | Cubierto |
| §4.1 a §4.3 Techos y presupuestos | T0, T8 entregados; andamiaje en T9; Jurado a 13.200 en T47 | Cubierto en T9 |
| §4.4 Recuperación híbrida | T3 entregado; afinado en T19 | Cubierto |
| §4.5 Resúmenes jerárquicos | Niveles bajos en T10; arco y obra en T18 | Cubierto |
| §4.6 Control de deriva | Proscripción en T10; huella en T21 | Cubierto |
| §4.7 Aislamiento | T3 entregado como propiedad | Cubierto |
| §4.8 Proveedores, CLI y contador | T0 entregado; D-35 en T9; CLI aislado y Langfuse en T40 | Cubierto |
| §4.9 Recetas por agente | T14; receta del Jurado con el encargo en T47 | Cubierto en T14 |
| §4.10 Contexto en el ciclo | T15 | Cubierto en T15 |
| §5 Skills y herramientas | Repartidas por tramo; `*.audit` en T20, `style.*` en T21, `metrics.report` en T22, `retcon.propose` en T23; la longitud de capítulo en `check.format` y los argumentos estrictos en T39 y T41, `check.forbidden` en T41, `check.formal` en T43, las `*.audit` nuevas en T47 | Cubierto |
| §6 Agentes | §1.3 y T10 a T14; Jurado T20, Estilista T21, Supervisor T22 | Cubierto |
| §7.1 a §7.3 Flujos, reparación y cuarentena | T14, T15; el flujo completo en T24 | Cubierto |
| §7.4 Orquestador como código | T8 entregado; cableado en T15 | Cubierto en T15 |
| §8 Sustitutos de decisiones humanas | Repartido; el retcon en T23 | Cubierto |
| §9.1 Verificadores deterministas | T5 entregado; T39, T41 y T43 los endurecen; la tabla validador × punto se contrasta en la puerta en T50 | Cubierto |
| §9.2 Jurado | T20; rúbricas versión 2 en T47 | Bloques 2 y 3 |
| §9.3 Puertas | T12, T14, T15; la mitad de juicio en T20 y T22; prohibidas y cronología antes de congelar en T41 y T46; elementos en el cierre en T47 | Cubierto |
| §10 Escritura de canon | T10, T11; el retcon en T23; comprobaciones antes de toda congelación en T41 y T46 | Cubierto |
| §11 Observabilidad | T9; las trece señales en T22; Langfuse en T40 y T48; audit log en T45 | Cubierto |
| §12 Riesgos | §6 de este plan y SRS §7.4 | Cubierto |
| §13 Decisiones abiertas | T17 cierra nº 2, 3, 4 y 9; T19 cierra nº 10 | Cubierto |
| §14 Orden de construcción | §2 y §3 de este plan; la versión 4, en §8 | Cubierto |

### 7.1 Tramos de la versión 4: requisito, método y ficheros

Los tramos de `specs/srs-backend-v4.md` §11 con los requisitos que entrega cada uno, su método principal, los ficheros que toca y la ola y la sesión que lo construye. **Un fichero con dos dueños en la misma ola se integra en el orden de la columna de la derecha**, y el segundo parte del commit del primero.

| Tramo | ENT | Requisitos | Método principal | Ficheros | Ola · sesión · orden |
|---|---|---|---|---|---|
| T37 | 42 en su parte de documento | — | VER-15 | `specs/srs-backend-v4.md`; `docs/architecture.md`, `verification.md`, `definitions.md`; `specs/srs-backend-v2.md` y `v3.md` en su sitio; `backend/PLAN.md`; `frontend/PLAN.md`; `AGENTS.md` | 1 · S-DOC |
| T38 | 51 a 57 | RF-228, RF-229 | VER-18 | `orchestration/model/run.tla`, `run.cfg`, `chapter.tla`, `chapter.cfg`, `mutations/`, `tlc/`, `README.md`; `.github/workflows/backend.yml` (paso de TLC con versión fija, al cambiar el modelo) | 1 · S-TLA |
| T39 | 26, 37; 38 en su medida | RF-230, RF-231 | VER-05 | `orchestration/tools/server.py` y `test_server.py`; `verification/checks/deterministic.py` y `test_deterministic.py`, con `check_chapter_length` ya escrita y sin llamar; `orchestration/engine.py`, solo `_name_candidates`, y `test_engine.py` | 1 · S-CHECKS · antes de S-B |
| T40 | 28, 63, 67 | RF-233 a RF-235, RI-60 a RI-62, RD-44, RNF-53, RNF-54 | VER-05, VER-09, VER-11 | `commons/tracing/langfuse_export.py` y su test; `commons/tracing/trace.py`, solo el observador; `commons/provider/port.py`, `claude_cli.py` y `test_claude_cli.py`; `orchestration/dispatch.py` y `test_dispatch.py`; `orchestration/compose.py` y `app.py`, que enganchan el conductor en vivo y emiten `work.cost`; `pyproject.toml`. Además, lo que T39 dejó en `commons/`: `claude_cli.py:_tool_protocol` pasa a mostrar el esquema que exporta el servidor de herramientas (RF-230), que `orchestration/tools/server.py` le pasa con `ToolServer.input_schemas()` e `INPUT_SCHEMAS`, porque `commons/` no importa de `orchestration/`; `compose.py`, con `run_novel` y `amend_novel` que aceptan `compose=` para inyectar el motor; `orchestration/test_compose.py`, la prueba de la puerta; y `conftest.py`, que quita `LANGFUSE_*` y `OTEL_*` antes de recoger las pruebas para que ninguna tirada de prueba salga a Langfuse | 2 · S-A · 1.º |
| T41 | 38; 40, 70, 71, 72, 73, 75; 74 en su parte local | RF-232, RF-236 a RF-240, RD-37, RD-38 | VER-12, VER-06, VER-05, VER-09 | `canon/normalize.py`, la normalización única, porque `canon/` no importa de `verification/`; `verification/checks/forbidden.py`, que la reexporta, y `test_forbidden.py`; `verification/checks/deterministic.py`, para quitar las prohibidas de `check_repetition`; `orchestration/engine.py`, `verify_scene`; `orchestration/loop.py`, comprobación antes de `_freeze`, motivo del aborto, `guardrail.match` y la llamada a `check_chapter_length` en `_approve_chapter` (RF-232), con su prueba y la de `_work_closes` fuera de rango; `canon/db/migrations.py`, una migración; `canon/db/schema.sql`, comentario; `canon/db/forbidden_global.txt`; `canon/brief.py`, solo la carga por niveles en `create_novel`; pruebas de `loop`, `engine` y migraciones | 2 · S-B · 2.º |
| T42 | 30, 31; 18 en su parte de esquema | RF-241, RF-242, RD-39, RD-40, RD-34 | VER-06, VER-05 | `canon/db/migrations.py`, una migración, que además añade el disparador que impide borrar de `manuscript_version` (RD-34); `canon/prose_index/usage.py`, el registro y su relleno, y `canon/prose_index/chronology.py`, la lectura de la vista, que llaman `canon/freeze/freeze.py` y `canon/arbiter/refreeze.py`; `canon/manuscript.py`, `commit_amendment`, que refresca el registro en una enmienda sin escenas que reescribir; `orchestration/amend.py`, solo la lectura del registro en `affected_scenes`; pruebas: `canon/prose_index/test_usage.py`, `test_chronology.py`, `canon/db/test_migration_5.py` y `orchestration/test_fact_usage.py` | 2 · S-M · 3.º |
| T43 | 32, 46, 47, 48 | RF-243 a RF-246, RI-63, RD-41, RNF-55 | VER-04, VER-06, VER-05, VER-15 | `verification/formal/`: `generate.py`, `check.py`, `fixtures/`, `fixtures/__main__.py`, el comando de la puerta; `lean/` con `lakefile.toml`, `lean-toolchain`, `lake-manifest.json`, `StoryMaker/Types.lean`, `Invariants.lean`, `Fixture.lean`, `Seeded.lean` en su propia `lean_lib`, la `lean_lib Generated` sin versionar y `last-build.txt`; y sus pruebas, `test_generate.py` y `test_check.py`; `gate.py`; `.github/workflows/backend.yml`, tras el paso de TLC de T38; `.gitignore`, `.lake/` y los ficheros generados | 2 · S-C · 4.º |
| T44 | 04, 07, 58, 59, 60 | RF-247 a RF-250, RI-64, RD-42, RD-43 | VER-05, VER-08, VER-10 | `canon/brief_rules.py`, con la normalización de T41 en `canon/normalize.py`; `canon/brief.py`, modelos y `to_events`; `brief/extract.py`; `brief/draft.py`; `backend/openapi.json`; cliente regenerado en `frontend/commons/api/`; `backend/evals/briefs/01` a `05`; `evals/test_briefs.py` y `test_temporal.py`; pruebas de reglas, entrevista y rutas | 2 · S-F · después de S-B |
| T45 | 24, 25, 76 | RF-251 a RF-253, RI-65, RI-66, RD-45, RNF-56 | VER-05, VER-12, VER-06 | `.claude/settings.json`; `.claude/hooks/chapter_gate.py` y `policy.py`; `commons/tracing/trace.py` y `test_trace.py`, la cadena; `orchestration/routes.py`, RI-27; `openapi.json` y cliente; pruebas con subprocess dentro de `backend/`: `verification/test_chapter_hook.py` y `verification/test_policy_hook.py`; `orchestration/test_loop.py`, la regla de `guardrail.match` que espera una prueba; `.gitignore`, `.claude/audit/` | 3 · S-E · 1.º |
| T46 | 49; 71 en su nivel `novela`; 16 en el renombrado de dos palabras | RF-254 a RF-256, RI-67, RD-49, RF-225 | VER-05 | `orchestration/loop.py`, `_approve_chapter` (`_formal_before_freeze`) y `_try_retcon`; `orchestration/amend.py`, `_apply`, que pasa el número de solicitud al contexto de sus llamadas (D-100), `_formal_or_reject`, `_apply_forbid` y `counts` con la forma de hoy de RF-225 y D-78, que quita el `xfail` que dejó S-TESTS; `orchestration/engine.py`, `formal_check` y `call_context`; `orchestration/compose.py`, `lake` al componer el motor; `verification/formal/check.py`, `check_toolchain`; `brief/interpret.py`; `canon/manuscript.py`, la solicitud con `kind` y `term` y `commit_forbid`; `canon/arbiter/refreeze.py`, que recongela sin evento; `canon/db/migrations.py`, la migración 7, y `canon/db/test_migration_7.py`; `orchestration/routes.py`, RI-49; `openapi.json` y cliente; en el frontend, `commons/change-request/RequestForm.tsx`, que muestra un `forbid`, con sus pruebas y fixtures; pruebas de `loop` y `amend` | 3 · S-G · 2.º |
| T47 | 39, 43 | RF-257 a RF-261, RF-273, RD-47, RNF-57 | VER-05, VER-17, VER-19, VER-12 | `commons/types/rubrics.py`; `verification/jury/prompts.py` y `verdict.py`; `context/packing/recipes.py`, receta del Jurado; `orchestration/engine.py`, `judge_chapter` y el Archivero; `orchestration/loop.py`, traza del Jurado; `canon/events/types.py`; `canon/db/migrations.py`, una migración; `canon/brief.py`, eventos de los elementos; `canon/archivist/prompts.py` y `extract.py`; `canon/freeze/`, usos anclados; `canon/prose_index/usage.py`, que conserva las filas `element.*` y vuelve a anclarlas al recongelar; `canon/projections/rebuild.py`, `brief_element`; `planning/outline/check.py`, también el encuentro sin reglamento (RF-273), y `prompts.py`; `planning/ledger/setups.py`; `planning/act_gate/gate.py`, los usos en `check_act`; la migración 8; pruebas, con `orchestration/test_jury_budget.py` y `verification/jury/test_rubrics_v2.py`; las salidas esperadas de T51 con nueve dimensiones | 3 · S-J · 3.º |
| T48 | 64, 65, 66, 68, 69, 74 | RF-262 a RF-266, RI-68, RD-46 | VER-09, VER-05, VER-16 | `commons/tracing/langfuse_export.py`; `commons/settings.py`, ruta de la traza de entrevista; `brief/extract.py`, `interpret.py`, `routes.py` y `store.py`; `orchestration/tools/server.py` y `engine.py`, el registro `tool`; `orchestration/dispatch.py`; `orchestration/prompts_sync.py`; `orchestration/app.py`, reenvío de la entrevista al crear la novela; `orchestration/amend.py`, `create_request`, que escribe el `call` de `amend.interpret` tras `amend.request`; `evals/compare.py` | 3 · S-S · 4.º |
| T49 | 41 | RF-267, RI-69 | VER-05 | `.mcp.json`; `frontend/visual/tour.mjs`, `verdict.ts`, `verdict.test.ts`, `seed.py` y `results/`; `frontend/package.json` | 3 · S-V · 5.º |
| T50 | 42 | RF-268 | VER-15 | `backend/coherence.py` y su prueba | 3 · quien integra, después de T39, T41, T43 y T46 |
| T51 | 44, 45, 61 en su parte de código | RF-269 a RF-271, RD-48 | VER-10 | `evals/brief_table.py`, `human_template.py`, `human_vs_jury.py` y sus pruebas; esquema de `evals/human/` | 3 o 4 · con dobles, sin tirada |
| T52 | 44, 45, 50, 61, 62 | RF-272, RNF-58 | VER-10, VER-16 | `evals/results/briefs.md`, `human-vs-jury.md`, `tuning-01.md` y `traces/`; `evals/formal/CASOS.md` y `test_case.py`; `evals/human/<novela>.json`; enlace desde §1.4 | 4 · en secuencia, cuando T16 termine |
| T53 | — | RF-274, RD-50 | VER-05, VER-08 | `commons/types/length.py`, los perfiles; `canon/brief.py`, `length_profile` y el rango de obra por perfil; `planning/outline/types.py`, que reexporta los perfiles en vez de `CHAPTER_WORDS`, `check.py` y `prompts.py`; `orchestration/compose.py`, el número de capítulos, `engine.py`, el rango de escena del Escritor y de `check.format`, y `loop.py`, `check_chapter_length` en `_approve_chapter`; `verification/checks/deterministic.py`; `backend/evals/briefs/01` a `05` con `prueba`, y sus pruebas; `backend/openapi.json` y el cliente regenerado en `frontend/commons/api/` | 3 · S-MINI · después de S-FIX y S-S |

---

## 8. Bloque 3 · versión 4

Su spec es [`specs/srs-backend-v4.md`](../specs/srs-backend-v4.md), que es T37. No añade paso al orden de construcción: endurece los pasos 4, 5, 9 y 11. Los ficheros de cada tramo están en §7.1; los requisitos y las puertas son los de la spec y no se repiten distintos aquí.

**Orden de integración.** Una sola sesión integra en `v2-oneshot`, en el orden de §7.1, y pasa `python gate.py` después de cada merge. Las migraciones de `canon/db/migrations.py` se numeran en ese mismo orden: T41 la 4, T42 la 5, el arreglo de B1 a B4 la 6 (`wm_run_state`, `specs/srs-backend-v1.md` RD-07), T46 la 7 y T47 la 8. Las tiradas con modelo de T52 van de una en una y sobre un commit etiquetado (RNF-58).

### T37 · `specs/srs-backend-v4.md`

Hecho. Autoriza lo que construyen las olas 2 y 3 y deja escritas en su §9 las respuestas del interrogatorio.

### T38 · TLA+ del flujo completo

| Requisitos | RF-228, RF-229 |
|---|---|
| **Puerta** | TLC sin error sobre `chapter.cfg` y `run.cfg`, con la salida guardada; cada mutación de `model/mutations/` da contraejemplo |

### T39 · Verificadores endurecidos

| Requisitos | RF-230, RF-231 |
|---|---|
| **Puerta** | «Nalah» suelto, al principio de frase o con tilde cambiada da S1 con Nala en el canon; `"full": "no"` y una clave de más se rechazan; `check_chapter_length` marca 1.499 y 4.001 palabras y no 1.500 ni 4.000 |

### T40 · Langfuse base

| Requisitos | RF-233 a RF-235, RI-60 a RI-62, RD-44, RNF-53, RNF-54 |
|---|---|
| **Puerta** | Con un cliente doble, una tirada con dobles da una traza por generación con `session_id`, generations con tokens, coste y latencia, y `work.cost`; si el cliente lanza, la tirada cierra igual; la lista de argumentos del CLI no carga configuración de usuario ni de proyecto |

### T41 · Guardarraíl de prohibidas

| Requisitos | RF-232, RF-236 a RF-240, RD-37, RD-38 |
|---|---|
| **Puerta** | La tirada de la sonda de la auditoría, con una prohibida en la prosa, no congela ningún capítulo con la palabra dentro: o repara, o acaba en `RunAbortedError` con término y nivel; `mar` no casa en `Marcos` y `luz` sí en `luces`; una prueba por nivel; un capítulo escrito de 1.200 palabras deja un S2 de `check.format` en la puerta de capítulo y `chapter.gate` lo cita, y con otros dos S2 no pasa (RF-232) |

### T42 · Hecho × capítulo y cronología

| Requisitos | RF-241, RF-242, RD-39, RD-40, RD-34 |
|---|---|
| **Puerta** | Tras congelar dos capítulos, `fact_usage` y `affected_scenes` dan las mismas escenas; `chronology` devuelve las escenas en orden de mundo aunque se congelaran en otro; un `DELETE` sobre `manuscript_version` falla |

### T43 · Lean

| Requisitos | RF-243 a RF-246, RI-63, RD-41, RNF-55 |
|---|---|
| **Puerta** | La fixture limpia compila con `lake build` y la sembrada falla en su teorema; dos generaciones del mismo canon dan el mismo fichero; sin `lake`, `run_lean` devuelve fallo |

### T44 · Brief

| Requisitos | RF-247 a RF-250, RI-64, RD-42, RD-43 |
|---|---|
| **Puerta** | Seis años con tono «thriller erótico» es contradicción; un campo de más da 422 y un hecho extraído con un campo de más cuenta como inválido; los cinco briefs validan y cada uno cumple su propiedad |

### T45 · Hooks de Claude Code y audit log

| Requisitos | RF-251 a RF-253, RI-65, RI-66, RD-45, RNF-56 |
|---|---|
| **Puerta** | Escribir un `*.chapter.md` en presente queda bloqueado con el defecto; leer `.env` se deniega y la decisión queda en el audit log; borrar una línea de una traza lo señala `verify_chain` |

### T46 · Puerta formal y prohibición por solicitud

| Requisitos | RF-254 a RF-256, RI-67, RD-49, RF-225 |
|---|---|
| **Puerta** | Un fallo de Lean inyectado impide congelar hasta que la reparación lo arregla, y una enmienda que rompe un invariante se rechaza sin crear versión; pedir «que no aparezca X» produce la versión siguiente sin X; «Marcos Vela» a «Mateo Ruiz» con un reparado limpio se aplica |

### T47 · Jurado versión 2 y elementos obligatorios

| Requisitos | RF-257 a RF-261, RF-273, RD-47, RNF-57 |
|---|---|
| **Puerta** | El Jurado puntúa nueve dimensiones con justificación trazada y cabe en 13.200; un recuerdo obligatorio sin uso anclado impide cerrar la obra y el motivo lo nombra; una escena con `is_match` en un brief sin reglamento hace fallar `outline.check` |

### T48 · Langfuse completo

| Requisitos | RF-262 a RF-266, RI-68, RD-46 |
|---|---|
| **Puerta** | Con un cliente doble, entrevista, tirada y solicitud de la misma novela comparten sesión; cada agente sale con su rol; cada herramienta es un hijo de su generation; cada verificador de la traza tiene su score; publicar dos veces los prompts sin cambios no crea versión |

### T49 · Validación visual

| Requisitos | RF-267, RI-69 |
|---|---|
| **Puerta** | El recorrido pasa sobre una copia sana y falla, con su registro fechado, sobre una copia sin dedicatoria |

### T50 · Tabla de validadores en la puerta

| Requisitos | RF-268 |
|---|---|
| **Puerta** | Borrar una fila `check.*` de `architecture.md` §9.1, o añadir un `kind` sin fila, hace fallar `coherence.py` |

### T51 · Herramientas de evaluación

| Requisitos | RF-269 a RF-271, RD-48 |
|---|---|
| **Puerta** | La tabla por brief, la plantilla humana y la comparación se regeneran idénticas desde ficheros de prueba |

### T52 · Tiradas de evaluación

| Requisitos | RF-272, RNF-58 |
|---|---|
| **Puerta** | `evals/results/briefs.md`, `human-vs-jury.md`, `tuning-01.md` y `evals/formal/CASOS.md` existen, versionados, y se regeneran con un comando desde ficheros versionados |

### T53 · Perfil de extensión `prueba`

| Requisitos | RF-274, RD-50 |
|---|---|
| **Puerta** | Una tirada con dobles de cada brief de evaluación cierra con 3 capítulos de 1 escena y entre 300 y 500 palabras; un brief `novela` sin perfil se comporta igual que hoy |
