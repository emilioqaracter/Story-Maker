# Plan de implementación · backend v1

> Compañero de [`specs/srs-backend-v1.md`](../specs/srs-backend-v1.md), que dice **qué** hay que construir. Este documento dice **en qué orden y con qué ficheros**.
> No es un SRS y no añade requisitos: todo lo que aparece aquí tiene su `RF`, `RD`, `RI` o `RNF` en la spec. Si algo no lo tiene, es un error de este documento.

---

## 1. Antes de escribir una línea

### 1.1 Lo que ya está decidido y no se vuelve a discutir

Si al implementar te parece que alguna de estas está mal, eso dispara el proceso B de [`AGENTS.md`](../AGENTS.md) §6.3, no un parche en el código.

| | Decisión | Dónde está |
|---|---|---|
| Modelo | Claude Haiku 4.5 para los once agentes | D-23 |
| Embeddings | `intfloat/multilingual-e5-large` con `fastembed`, dentro de la imagen. 1024 dimensiones | D-22, D-29 |
| Contador | `tiktoken` × factor, calibrado al arrancar. **Nunca crudo** | D-14, D-28 |
| Vectores | En tabla, similitud en Python, sin extensión nativa | D-12 |
| Persistencia | Un fichero SQLite por novela | RI-14 |
| Rutas | Dentro de cada funcionalidad; la aplicación se compone en `orchestration/` | D-01 |
| Contexto | Empuje para todos; tirón además para cinco agentes | D-19 |
| Tiempo de mundo | ISO 8601 más `world_seq` de desempate | D-07 |
| Retcon | No existe en v1: el canon congelado siempre gana | D-05 |

### 1.2 La regla de importación, activa desde el primer commit

Tres pisos, y se comprueba con `import-linter` en CI (RNF-15) **desde el tramo 0**, no al final:

```
orchestration/          ← conoce a todas; nadie lo conoce a él
    ↓
planning/  context/  generation/  verification/
    ↓
canon/                  ← todas leen de él; él no importa de ninguna
commons/                ← cualquiera puede importarlo
```

Dejarlo para el final significa descubrir en el tramo 8 que media docena de módulos cruzan la frontera, y reorganizarlos cuando ya tienen tests encima.

### 1.3 Diez trampas que van a morder

Están aquí porque las diez producen código que **funciona en la demo y falla en el capítulo 20**.

1. **`tiktoken` crudo.** Infracuenta en español. Todo lo que devuelve va multiplicado por el factor y redondeado hacia arriba. Un solo sitio que lo llame directo rompe el techo (RI-20).
2. **Algo voluble delante del prefijo cacheable.** Una marca de tiempo, un identificador de tirada, un contador de intento. El caché casa por prefijo: un byte distinto y se pierde la llamada entera, sin error (RF-103).
3. **La conexión de escritura fuera de `canon/`.** Ponla en `canon/db/` desde el principio; si vive en `commons/` alguien la importará (RD-09).
4. **Proyecciones que dependen del orden de inserción.** Ordena siempre por `(world_time, world_seq, id)`. La propiedad que lo detecta va en el tramo 1, no después (RD-03, RF-04).
5. **Fragmentos que cruzan la frontera de su escena.** Rompe el filtrado por metadatos, que es lo que hace barata la recuperación (RD-16, RF-70).
6. **Truncar.** Ni un fragmento, ni un paquete, ni un resultado de herramienta. Se sustituye por resumen o se niega (RF-84, RF-94).
7. **Escenas en paralelo.** El bloque 6 del paquete del Escritor es la prosa literal de la anterior. Van en serie, siempre (RF-45).
8. **Empezar el capítulo N+1 con el N sin congelar.** No existe para el sistema (RF-107).
9. **Cálculo de embeddings dentro de la transacción.** Son cientos de vectores; bloquean el fichero sin motivo (RNF-21, RF-68).
10. **La memoria de trabajo en un paquete.** Un borrador rechazado que llega al Escritor es el sistema aprendiendo de su propio error (RF-37).
11. **Embeber sin los prefijos de E5.** `multilingual-e5-large` exige `query: ` delante del texto de consulta y `passage: ` delante de cada fragmento indexado. Sin ellos el modelo carga, devuelve vectores y recupera peor, **sin error y sin señal** (RF-102).

---

## 2. Los ocho tramos

Cada tramo abre cuando el anterior pasa su puerta. El detalle de qué entrega y con qué se comprueba está en el SRS §11; aquí va el contenido fichero a fichero.

### T0 · `commons/`

Todo lo demás importa de aquí, así que va primero aunque no sea una funcionalidad.

```
commons/
├── provider/
│   ├── port.py           · protocolo: complete_once, complete_with_tools, embed
│   ├── claude.py         · implementación Haiku 4.5; traduce el esquema de salida
│   ├── embeddings.py     · fastembed; carga y verificación de dimensión al arrancar
│   └── errors.py         · tipos de fallo del proveedor
├── tokens/
│   ├── counter.py        · tiktoken × factor, redondeo hacia arriba
│   ├── factors.py        · un factor por modelo; sin factor, no se admite
│   └── calibration.py    · llamada de calibración al arrancar
└── types/                · artefactos que cruzan dos o más funcionalidades
    ├── outline.py  scene_spec.py  context_package.py
    ├── defect.py   canon_delta.py  arbitration.py
    └── prose.py
```

| Requisitos | RI-11 a RI-13, RI-20 a RI-22, RI-24, RNF-16, RNF-19 |
|---|---|
| **Puerta** | `mypy --strict` limpio; el contador contrastado contra un `usage` de doble |

**Lo que más importa de este tramo:** `port.py` tiene **dos** modos de `complete`, y quién usa cuál no lo decide el agente sino su ficha en `architecture.md` §6.3. Si el puerto expone uno solo, los cinco agentes con herramientas no tienen dónde vivir.

### T1 · `canon/` · esquema y lectura

```
canon/
├── db/
│   ├── connection.py     · dos fábricas: lectura y escritura. La de escritura NO sale de aquí
│   ├── schema.sql        · las tablas de los cinco almacenes
│   ├── triggers.sql      · abortan UPDATE y DELETE sobre event
│   └── migrations/       · versión de esquema; hacia delante en escritura
├── events/               · inserción y lectura del registro
├── projections/          · entity, alias, attribute, relation, knowledge, competence, document_version
├── graph/                · recorrido recursivo sobre aristas vigentes
└── skills/
    ├── query.py  state_at.py  knowledge_of.py  related.py
```

| Requisitos | RD-01 a RD-17, RF-01 a RF-11, RF-67 |
|---|---|
| **Puerta** | Independencia del orden de inserción; reconstruibilidad desde cero; vigencia correcta en cualquier instante |

**Escribe estas tres propiedades antes que las funciones**, porque las tres son de las que se comprueban generando casos, no ejemplos: proyectar los mismos eventos en distinto orden da el mismo estado; regenerar el canon desde cero es igual a mantenerlo incremental; una consulta en `t` no devuelve nada cuya vigencia haya terminado antes de `t`.

### T2 · `planning/`

```
planning/
├── outline/
│   ├── plan.py           · outline.plan, agente de modelo
│   └── check.py          · outline.check, DETERMINISTA
├── scene_spec/           · conversión de tramo a especificaciones
├── ledger/               · registro de setups y su máquina de estados
├── act_gate/             · puerta de cierre de acto
└── routes.py             · GET /novels/{id}/debt
```

| Requisitos | RF-25 a RF-31, RF-105, RF-106 |
|---|---|
| **Puerta** | `outline.check` rechaza una escaleta con un arco sin resolución y acepta una válida |

**`check.py` no llama a ningún modelo.** Es un verificador estructural: cobertura de arcos, doble arco resuelto en escenas distintas, curva de tensión monótona por acto, todo setup con payoff planificado, reparto de palabras. Si te ves pidiéndole a un modelo que valide la escaleta, has cruzado la restricción de «determinista antes que modelo».

### T3 · `context/`

El tramo más grande, y donde vive el RAG híbrido.

```
context/
├── query/                · filtros, términos léxicos desde alias, texto semántico, exclusiones
├── retrieval/
│   ├── lexical.py        · FTS5 con BM25
│   ├── semantic.py       · coseno sobre vectores, en Python
│   ├── fusion.py         · fusión recíproca de rangos, constante 60
│   └── quotas.py         · lugar, voz, promesa, espejo, libre
├── packing/
│   ├── assemble.py       · ensamblaje por receta
│   ├── compact.py        · prioridad inversa; nunca trunca
│   └── recipes/          · una por agente destino
└── audit/                · context.audit
```

| Requisitos | RF-32 a RF-39, RF-72 a RF-89, RF-103, RNF-20, RNF-23 |
|---|---|
| **Puerta** | La fusión es determinista sobre el mismo canon; ningún paquete supera el presupuesto de su agente destino |

**Cero llamadas de modelo en todo el tramo**, salvo el vector de la consulta, que además ahora es local. Si aparece una, algo está mal planteado: los sinónimos salen de la tabla de alias y la consulta semántica es la propia especificación de escena.

### T4 · `generation/`

```
generation/
├── writer/               · scene.write
└── sports/
    ├── simulate.py       · motor de reglas, DETERMINISTA dada una semilla
    └── narrate.py        · dramatiza la cronología ya resuelta
```

| Requisitos | RF-40 a RF-45 |
|---|---|
| **Puerta** | `match.simulate` es determinista dada una semilla y no alinea a nadie indisponible |

**`simulate.py` corre antes que `narrate.py`, siempre.** El marcador, la cronología de hitos y los cambios de estado físico los decide el motor de reglas; el modelo solo los dramatiza. Invertirlo reintroduce toda la familia de defectos de verosimilitud deportiva que este diseño elimina de raíz.

### T5 · `verification/`

```
verification/
├── checks/               · timeline, ledger, availability, format, repetition, lexicon, knowledge
├── continuity/           · continuity.review, agente de modelo con herramientas
└── repair/               · revise.targeted; revalida desde la primera puerta
```

| Requisitos | RF-46 a RF-54 |
|---|---|
| **Puerta** | Cobertura de mutación ≥ 90 % en los siete verificadores deterministas |

**El 90 % de mutación se acota a `checks/` y no al resto**, porque son la red de seguridad del sistema entero: un verificador cuyos tests no detectan su ruptura es peor que no tener verificador, porque produce confianza falsa.

### T6 · `canon/` · escritura

```
canon/
├── prose_index/
│   ├── chunk.py          · por párrafos, ≤450 tokens, un párrafo de solape
│   ├── embed.py          · llama al modelo local de commons/
│   └── index.py          · dos niveles: escena y fragmento; FTS5 y vectores
├── summaries/            · escena y capítulo
├── archivist/            · delta.extract
└── freeze/               · la transacción
```

| Requisitos | RF-12, RF-55 a RF-58, RF-68 a RF-71, RF-90, RNF-21 |
|---|---|
| **Puerta** | Congelar no deja ninguna fila de memoria de trabajo; un fallo de embeddings no escribe nada |

**El orden de `freeze/` es la mitad del tramo.** Fuera de la transacción: cortar, resumir, vectorizar. Dentro y todo junto o nada: eventos, proyecciones, índice, resúmenes, purga. Escribirlo al revés deja el fichero bloqueado mientras se calculan cientos de vectores.

### T7 · `canon/` · arbitraje

```
canon/
└── arbiter/
    ├── precedence.py     · la política, total y sin ciclos
    └── entries.py        · las dos puertas: Orquestador y Documentalista
```

| Requisitos | RF-59 a RF-63 |
|---|---|
| **Puerta** | La precedencia es total y sin ciclos; fusionar dos deltas es asociativo |

**Desde aquí el sistema es autónomo.** Antes de este tramo, cualquier contradicción lo detiene porque no hay quién la resuelva.

### T8 · `orchestration/`

```
orchestration/
├── loop.py               · bucles de capítulo y de escena
├── checkpoint.py         · punto de reanudación, al cerrar cada escena
├── admission.py          · semáforo de entrada, FIFO estricta, cupos de tirón
├── retries.py            · presupuesto de reintentos y cuarentena por nivel
├── dispatch.py           · frontera de confianza: valida salida, aplica tope de 50.000
├── tools/
│   ├── budget.py         · context.budget
│   └── lookup.py         · canon.lookup, con control de presupuesto
├── app.py                · composición FastAPI: monta el router de cada funcionalidad
└── routes.py             · POST /novels/{id}/run, GET /novels/{id}
```

| Requisitos | RF-13 a RF-24, RF-91 a RF-100, RF-107, RNF-01 a RNF-09, RNF-24 |
|---|---|
| **Puerta** | Los invariantes de `verification.md` §7 comprobados por model checking |

**`dispatch.py` concentra el riesgo del sistema entero.** Es donde el texto de un modelo se convierte en objeto tipado. Todo lo que pase de ahí sin validar contamina el canon, y no hay revisión humana detrás que lo detecte.

---

## 3. Lo que se construye en cada tramo aunque no lo parezca

Tres cosas son transversales y **no tienen tramo propio a propósito**. Dejarlas para el final es la forma conocida de que no se hagan.

| Qué | Cuándo | Por qué no al final |
|---|---|---|
| **Rutas HTTP** | Cada tramo añade las suyas dentro de su carpeta | Concentrarlas al final deja los ocho tramos anteriores sin forma de ejercitarse |
| **Trazas a Langfuse** | Cada llamada, desde la primera | Es el único mecanismo para detectar que algo lleva diez capítulos degradándose (RNF-13) |
| **La regla de importación** | Desde el primer commit, en CI | Ver §1.2 |

---

## 4. Definición de terminado

Los ocho tramos compilando no es terminado. Esto sí:

- [ ] Los ocho tramos pasaron su puerta
- [ ] La puerta de CI del SRS §7.2 en verde
- [ ] Todo requisito con su método principal ejecutándose, o en el riesgo aceptado del SRS §7.4
- [ ] **Una tirada completa va del brief al cierre de obra sin intervención** (RNF-03)
- [ ] Copiar el fichero de la novela y abrirlo da las mismas proyecciones y la misma recuperación (RD-12)

El cuarto es el que cuenta. Los demás comprueban que el camino existe; ese comprueba que funciona.

---

## 5. Cobertura de `architecture.md`

Qué secciones de la arquitectura tienen sitio en este plan, cuáles no lo tienen **porque quedan fuera de la versión 1**, y cuáles no lo tienen **porque falta especificarlas**. La tercera columna es la única que importa: es la lista de trabajo pendiente.

| Sección de `architecture.md` | Dónde cae en el plan | Estado |
|---|---|---|
| §1 Principios de diseño | §1.3, las trampas los encarnan uno a uno | Cubierto |
| §2.1 Monorepo | Estructura de los tramos | Cubierto |
| §2.2 Frontera con el frontend | — | **Fuera de v1** |
| §2.3 Paquete por funcionalidad | §1.2 y el árbol de cada tramo | Cubierto salvo `supervision/`, que es del paso 10 |
| §3.1 Los cinco almacenes | T1 y T6 | Cubierto |
| §3.2 Memoria de trabajo | Trampa 10 | **Hueco A**: sin carpeta dueña ni módulo |
| §3.3 Escritura del índice | T6, `freeze/` | Cubierto |
| §4.1 Techos de ocupación | T0 `tokens/`, T8 `admission.py` | Cubierto |
| §4.2 Presupuesto por agente | T3 `recipes/` | Cubierto |
| §4.3 Paquete del Escritor | T3 `recipes/` | Cubierto |
| §4.4 Recuperación híbrida | T3 entero | Cubierto |
| §4.5 Resúmenes jerárquicos | T6 `summaries/` | Cubierto en sus dos niveles bajos; arco y obra son del paso 7 |
| §4.6 Control de deriva | — | **Hueco B**: la lista de proscripción no tiene quién la mantenga |
| §4.7 Aislamiento | — | **Hueco C**: sin módulo ni comprobación |
| §4.8 Proveedores, caché y medición | T0 entero | Cubierto |
| §4.9 Recetas por agente | T3 `recipes/` | Cubierto |
| §4.10 Gestión del contexto en el ciclo | T8 | Cubierto |
| §5.1 Skills deterministas | Repartidas por tramo | Cubierto salvo `style.fingerprint` y `metrics.report`, de pasos posteriores |
| §5.2 Skills de modelo | Repartidas por tramo | **Hueco D**: falta `replan.arc`, que la v1 sí usa |
| §5.3 Herramientas | T8 `tools/` | Cubierto |
| §6.1 Matriz agente × skill | Implícita en el reparto por tramo | Cubierto |
| §6.2 Contratos de entrada y salida | T0 `types/` | Cubierto |
| §6.3 Matriz agente × herramienta | T8 `tools/` | Cubierto |
| §7.1 y §7.2 Flujos | T8 `loop.py` | Cubierto |
| §7.3 Reparación y cuarentena | T8 `retries.py` | Cubierto |
| §7.4 El Orquestador como código | T8, módulo a módulo | Cubierto |
| §8 Sustitutos de decisiones humanas | Repartido | Cubierto salvo el retcon, fuera de v1 |
| §9.1 Verificadores deterministas | T5 `checks/` | Cubierto |
| §9.2 Jurado | — | **Fuera de v1** |
| §9.3 Puertas | T2 `act_gate/`, T8 | Cubierto |
| §10 Escritura de canon | T6 y T7 | Cubierto |
| §11 Observabilidad | §3, como transversal | **Hueco E**: declarada sin módulo ni fichero |
| §12 Riesgos | — | No es implementable; vive en el SRS §7.4 |
| §13 Decisiones abiertas | §6 | Cubierto |
| §14 Orden de construcción | §2 | Cubierto |

---

## 6. Lo que falta por especificar

Cinco huecos y una contradicción. **Los dos primeros bloquean**: no se puede escribir el tramo al que pertenecen sin resolverlos, porque no es un detalle lo que falta, es un dueño.

### Hueco A · La memoria de trabajo no tiene carpeta dueña — bloqueante

Las cinco tablas `wm_*` existen en el esquema (RD-07) y nadie las posee. Peor: **contradicen la regla de escritura**. RD-09 dice que la fábrica de conexión de escritura solo es importable desde `canon/`, pero quien escribe `wm_run_state` al cerrar cada escena es `orchestration/`, quien escribe `wm_draft` es `generation/` y quien escribe `wm_defect` es `verification/`. Con la regla tal cual, ninguno de los tres puede hacer su trabajo.

**Recomendación:** separar las dos escrituras, porque son dos cosas distintas que comparten fichero por comodidad, no por naturaleza. Una fábrica de escritura **de canon**, exclusiva de `canon/`, y otra **de memoria de trabajo**, en `commons/db/`, que cualquiera puede usar y que tiene prohibido por análisis estático tocar una tabla que no empiece por `wm_`. Así la regla que de verdad importa —que el canon solo lo escribe la congelación— queda intacta y comprobable, y el estado efímero deja de ser un caso especial sin dueño.

### Contradicción · `setup.ledger` tiene dos dueños — bloqueante

`architecture.md` §2.3 y §6.1 lo asignan a `supervision/` y al agente 12, el Supervisor. El SRS lo mete en `planning/` (RF-31, dentro de §4.4). **Y el Supervisor no existe en la versión 1**, así que la asignación de la arquitectura deja el registro de setups sin nadie justo en la versión que lo necesita: sin él no hay deuda narrativa, y sin deuda narrativa no hay ni puerta de cierre de acto (RF-105) ni condición de cierre de obra (RF-23).

**Recomendación:** el SRS tiene razón y la arquitectura se corrige. `setup.ledger` vive en `planning/`, que es quien planta los setups al escribir la escaleta y quien los cobra al especificar escenas. El Supervisor lo **lee** cuando llegue, por la misma vía por la que todos leen del canon. Esto es un cambio de `architecture.md` y por tanto proceso B.

### Hueco B · La lista de proscripción no tiene quién la mantenga

El bloque 9 del paquete del Escritor son los 30 términos proscritos más recientes (§4.6), y la regla dice que todo n-grama o imagen usado dos veces entra automáticamente en la lista (RF-49). `check.repetition` los **detecta**; nadie los **inserta**.

**Recomendación:** que los inserte la congelación, en `canon/`, en la misma transacción que escribe el índice. La lista es una proyección de la prosa congelada, exactamente igual que el índice de prosa, y mantenerla fuera de la transacción abre la puerta a que proscriba términos de un capítulo que acabó en cuarentena.

### Hueco C · El aislamiento no tiene comprobación

CTX-11 dice que cada agente corre en su ventana propia y limpia, y §4.7 lo desarrolla: el Continuista no ve el paquete que generó la prosa, el Jurado no ve el del Escritor. En el SRS solo existe como RF-52, para el Continuista. No hay nada que impida que un paquete arrastre restos de otro.

**Recomendación:** no hace falta módulo, hace falta una propiedad. El paquete se construye siempre desde cero en `context/` y nunca se muta ni se reutiliza entre llamadas; que lo sea es comprobable con una propiedad sobre el ensamblador. Es barato y cierra el hueco sin inventar una pieza.

### Hueco D · `replan.arc` no aparece en ningún tramo

La versión 1 lo usa: RF-19 dice que el Arquitecto replanifica el tramo cuando un capítulo agota sus reintentos, y RF-106 que replanifica el tramo siguiente cuando falla la puerta de acto. `architecture.md` §2.3 lo pone en `planning/`. El plan lo omitió.

**Recomendación:** añadir `planning/replan/` al tramo T2. No es una decisión, es un olvido de este documento.

### Hueco E · La observabilidad no tiene módulo

§3 la declara transversal y RNF-13 exige que toda llamada, defecto, reintento, admisión y arbitraje se trace. Ningún tramo nombra un fichero.

**Recomendación:** `commons/tracing/`, con el cliente de Langfuse y la cola local de RNF-13 para cuando no responda. Va en `commons/` y no en `orchestration/` porque lo usan todas las funcionalidades, que es exactamente el criterio de entrada a `commons/`.

### También faltan, y son menores

| Qué | Dónde va |
|---|---|
| `canon/routes.py` | T1 y T6: RI-01, RI-04, RI-05 y RI-06 son suyas y el plan no las lista |
| Carga del brief como eventos | T1: la ejecuta `canon/` al crear el fichero (D-09) |

---

## 7. El modelo de embeddings, fijado

**`intfloat/multilingual-e5-large`**, 1024 dimensiones, 2,24 GB, dentro de la imagen.

De los modelos multilingües que sirve `fastembed`, había tres candidatos reales:

| Modelo | Dim | Tamaño | Entrenado para |
|---|---:|---:|---|
| `paraphrase-multilingual-MiniLM-L6-v2` | 384 | 0,22 GB | Similitud entre frases |
| `paraphrase-multilingual-mpnet-base-v2` | 768 | 1,00 GB | Similitud entre frases |
| **`intfloat/multilingual-e5-large`** | 1024 | 2,24 GB | **Recuperación** |

**Se elige por para qué fue entrenado, no por tamaño.** Los dos primeros son modelos de paráfrasis: miden si dos frases parecidas y de longitud parecida dicen lo mismo. Este sistema hace lo contrario: usa una especificación de escena —corta y estructurada— para buscar fragmentos de prosa —largos y narrativos—. Eso es recuperación asimétrica, y es justo donde un modelo de paráfrasis rinde peor y uno de recuperación rinde mejor.

**El tamaño no restringe aquí.** Una obra son 600 a 1.200 fragmentos más un vector de consulta por escena, en local y de una novela cada vez. A 1024 dimensiones, los vectores de una obra entera ocupan unos 5 MB en el fichero. Los 2,24 GB se pagan una vez, en la imagen.

**Si el tamaño de la imagen llegara a ser un problema**, la alternativa es `paraphrase-multilingual-mpnet-base-v2`: 1 GB, y se pierde el entrenamiento para recuperación. El esquema guarda modelo y dimensión (RD-13), así que cambiarlo es reindexar.

**La trampa que trae, y por la que está en §1.3:** los modelos E5 exigen prefijos. `query: ` delante del texto de consulta y `passage: ` delante de cada fragmento que se indexa. Sin ellos el modelo carga sin quejarse, devuelve vectores de la dimensión correcta y recupera peor — sin error, sin aviso y sin que ninguna puerta lo note.
