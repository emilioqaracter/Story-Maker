# architecture.md

> Documentación de dominio · ver [`../AGENTS.md`](../AGENTS.md) para el índice completo.
> Relacionados: [definitions](definitions.md) · [domain-knowledge](domain-knowledge.md) · [verification](verification.md)

Arquitectura de un sistema **autónomo** de generación de novelas largas, con el caso de referencia de la épica deportiva. Consume el vocabulario de `definitions.md` y los modelos de `domain-knowledge.md`.

Dos restricciones fijan todo el diseño:

- **No hay intervención externa en ningún punto del ciclo** (PRO-11). El sistema planifica, escribe, verifica, corrige, arbitra y cierra por sí mismo.
- **100.000 tokens es el techo, en dos planos.** Por llamada, la ventana física (CTX-01). Para el sistema, el techo de concurrencia (CTX-20): la suma de todo lo que está en vuelo en el mismo instante.

---

## 1. Principios de diseño

1. **El canon es la fuente de verdad, no el texto.** La prosa es una proyección. Si la verdad vive solo en los capítulos escritos, cada llamada obliga a releerlo todo y la coherencia se degrada.
2. **El estado se deriva de eventos.** Registro append-only y proyecciones calculadas. Permite responder "qué era cierto en el capítulo 12" sin ambigüedad.
3. **El contexto se presupuesta, no se acumula.** Cada llamada recibe un paquete construido a propósito (CTX-03). Tener 100.000 tokens no es motivo para usarlos.
4. **Lo verificable se verifica sin modelo.** Fechas, marcadores, nombres, longitudes y repeticiones se comprueban con código. El juez LLM se reserva para lo subjetivo.
5. **Escritura y evaluación se aíslan.** El contexto que generó un texto no lo juzga.
6. **Granularidad de generación: escena. Granularidad de control: capítulo.**
7. **Ningún capítulo se cierra sin integrar su delta canónico (CAN-11).**
8. **Toda decisión tiene dueño.** Sin validación externa, cada bifurcación necesita una regla de precedencia, un umbral numérico o un agente responsable. Donde no haya ninguna de las tres cosas, el sistema se bloquea y eso es un fallo de diseño, no una espera.
9. **El bloqueo se resuelve replanificando, no parando.** Agotados los reintentos, se cuarentena el artefacto y se recalcula el tramo (CAL-13, PRO-12).

---

## 2. Vista de contexto del sistema

```mermaid
graph TD
  BRIEF["Brief · PRO-01"] --> ORQ

  ORQ["Orquestador · código"] --> CAPA1["Planificación"]
  ORQ --> CAPA2["Contexto"]
  ORQ --> CAPA3["Generación"]
  ORQ --> CAPA4["Verificación y crítica"]
  ORQ --> CAPA5["Canon y arbitraje"]
  ORQ --> CAPA6["Supervisión"]

  CAPA2 <--> MEM["Capa de memoria"]
  CAPA5 --> MEM
  CAPA4 --> MEM
  CAPA1 --> MEM
  CAPA6 --> MEM

  MEM --> M1["Canon estructurado"]
  MEM --> M2["Registro de eventos"]
  MEM --> M3["Grafo de entidades"]
  MEM --> M4["Índice de prosa"]
  MEM --> M5["Resúmenes jerárquicos"]

  CAPA5 --> SAL["Manuscrito congelado"]
  CAPA6 -.replanifica.-> CAPA1
```

El diagrama es la vista lógica. Todo lo que aparece en él vive en `backend/`.

### 2.1 Reparto físico: monorepo

El repositorio es un monorepo con dos artefactos desplegables.

| Carpeta | Stack | Contiene |
|---|---|---|
| `backend/` | Python y FastAPI | Orquestador, los 13 agentes, el catálogo de skills, los cinco almacenes de la capa de memoria y las puertas de calidad |
| `frontend/` | React | Lectura del manuscrito y visualización del estado: grafo de entidades, curva de tensión, deuda narrativa y salud de la tirada |

**El frontend es un observador de solo lectura.** No aprueba, no corrige, no desbloquea y no escribe canon. El motivo no es de alcance sino de diseño: cualquier interacción de la interfaz que condicione el ciclo reintroduce la aprobación manual que PRO-11 prohíbe, y lo hace por la puerta de atrás, sin regla de precedencia ni agente responsable.

De ahí se sigue una prueba barata de que el diseño se respeta: **el sistema completa una novela con el frontend apagado**. El día que no pueda, hay un fallo de diseño.

### 2.2 Frontera entre las dos mitades

| Qué cruza | Dirección | Forma |
|---|---|---|
| Brief (PRO-01) | frontend → backend | Encargo inicial. Es entrada, no revisión: ocurre antes del ciclo y no lo interrumpe |
| Manuscrito congelado | backend → frontend | Solo capítulos cerrados. Un borrador (PRO-06) no sale |
| Proyecciones de estado | backend → frontend | Grafo de entidades, curva de tensión, deuda narrativa. Derivadas, nunca el registro de eventos en crudo |
| Traza de ejecución | backend → frontend | Las métricas de §11, en lectura |

El contrato es el esquema OpenAPI que genera FastAPI, y es el único punto de acoplamiento entre las dos mitades. Se verifica con VER-08 de [`verification.md`](verification.md): el cliente del frontend se genera desde ese mismo esquema, de modo que un cambio incompatible rompe la compilación en vez de romper la pantalla.

El grafo de entidades y la curva de tensión a lo largo de la obra no se leen bien en una tabla, así que necesitan representación gráfica. Con qué librería se dibujan es una decisión abierta: no está fijada y no condiciona nada del backend, porque el contrato entre las dos mitades es el esquema OpenAPI y no la tecnología de pintado.

---

### 2.3 Organización interna: paquete por funcionalidad

Las dos mitades se organizan **por funcionalidad, no por capa técnica**. Una funcionalidad es una carpeta que contiene todo lo suyo (modelos, lógica, rutas, persistencia y sus tests), y lo compartido vive en `commons/`.

El motivo es el mismo a los dos lados: agrupar por capa técnica, con un `models/` y un `services/` y un `routers/`, obliga a tocar cinco carpetas para cambiar una sola cosa y deja invisible dónde empieza y dónde acaba cada pieza. Agrupar por funcionalidad hace el cambio local y la frontera visible.

#### Backend

Las funcionalidades son las seis capas del diagrama de §2, más el Orquestador:

```
backend/
├── commons/         · lo que usan dos o más funcionalidades
├── orchestration/   · agente 0, raíz de composición
├── planning/        · agentes 1 y 2
├── context/         · agente 3 y el catálogo de skills de contexto
├── generation/      · agentes 4 y 5
├── verification/    · agentes 6, 7, 8 y 9
├── canon/           · agentes 10 y 11, más los cinco almacenes de §3
└── supervision/     · agente 12
```

| Carpeta | Agentes de §6 | Skills de §5 |
|---|---|---|
| `orchestration/` | 0 Orquestador | Presupuestos, admisión CTX-20, recuento de reintentos |
| `planning/` | 1 Arquitecto, 2 Planificador | `outline.plan`, `scene.spec`, `replan.arc` |
| `context/` | 3 Documentalista | `context.*`, `prose.retrieve`, `canon.query` |
| `generation/` | 4 Escritor, 5 Especialista deportivo | `scene.write`, `match.simulate`, `match.narrate` |
| `verification/` | 6 Continuista, 7 Jurado, 8 Reparador, 9 Estilista | `check.*`, `*.audit`, `revise.targeted`, `style.*` |
| `canon/` | 10 Archivero, 11 Árbitro | `delta.extract`, `summarize.hierarchical`, `retcon.propose` |
| `supervision/` | 12 Supervisor | `setup.ledger`, `metrics.report` |

#### Frontend

Paquete por funcionalidad también, y **explícitamente no Feature-Sliced Design**: nada de `app/`, `pages/`, `widgets/`, `features/`, `entities/` y `shared/` como capas. Las funcionalidades son las vistas de §2.2:

```
frontend/
├── commons/         · cliente generado desde el OpenAPI, tipos y componentes compartidos
├── manuscript/      · lectura de capítulos congelados
├── entity-graph/    · grafo de entidades con vigencia
├── tension-curve/   · curva de tensión de la obra
├── narrative-debt/  · setups abiertos sin payoff
└── run-health/      · métricas de §11
```

El cliente generado vive en `commons/` y no en cada funcionalidad: es uno solo, sale del esquema OpenAPI (§2.2) y duplicarlo rompería la garantía de VER-08 de que un cambio incompatible rompe la compilación.

#### Las tres reglas que evitan que esto se degrade

1. **Una funcionalidad no importa de otra funcionalidad.** Solo de `commons/`. Si dos se necesitan entre sí, o lo común baja a `commons/` o la frontera está mal puesta.
2. **La excepción es `orchestration/`**, que es la raíz de composición: conoce a todas las funcionalidades y ninguna lo conoce a él. Es la forma en código de la regla de §6.2, «todo entra y sale por el Orquestador».
3. **A `commons/` se entra por uso, no por previsión.** Algo baja cuando lo usan dos funcionalidades, nunca cuando parece que podría usarse. Sin esa regla, `commons/` acaba siendo el vertedero donde cae todo y la organización por funcionalidad deja de significar nada.

La regla 1 y su excepción son estáticamente comprobables, así que no se dejan en convención: son un patrón de análisis estático en la puerta de CI (VER-02).

---

## 3. Capa de memoria

La memoria tiene **dos horizontes**, y confundirlos es lo que degrada una novela larga.

| Horizonte | Qué guarda | Cuándo muere |
|---|---|---|
| **Largo plazo** (§3.1) | Lo que es verdad en el universo: canon, eventos, relaciones, prosa congelada, resúmenes | Nunca. Es la novela |
| **Corto plazo** (§3.2) | Lo que el sistema sostiene mientras produce un capítulo: borradores, defectos, veredictos, reintentos | Al congelar el capítulo |

La regla que los separa: **el largo plazo guarda lo que es verdad; el corto plazo, lo que todavía se está decidiendo.** Un borrador no es canon hasta que pasa las puertas, y tratarlo como si lo fuera es el camino corto al envenenamiento de canon (CTX-13).

**Los dos viven en SQLite, en local, con un fichero por novela.** El motivo está en `AGENTS.md` §3.2.

### 3.1 Largo plazo: los cinco almacenes

Cinco almacenes con responsabilidades separadas. Unificarlos en un único índice vectorial es el error estructural más frecuente en este tipo de sistema. Separación lógica, no física: cinco conjuntos de tablas en la misma base.

| Almacén | Contenido | Implementación en SQLite | Consulta que resuelve |
|---|---|---|---|
| **Canon estructurado** | Entidades, atributos, fichas, guía de estilo, escaleta | Tablas relacionadas con columna de versión | "Dame la ficha del entrenador" |
| **Registro de eventos** | Hechos canónicos fechados, append-only | Tabla de eventos con inserción única, más vistas materializadas por proyección | "Qué sabía el protagonista en la jornada 14" |
| **Grafo de entidades** | Relaciones tipadas con vigencia | Tabla de aristas con vigencia desde y hasta, recorrida con CTE recursivo | "Quién tiene conflicto abierto con quién" |
| **Índice de prosa** | Texto congelado, troceado por escena | FTS5 para el léxico, que ya trae BM25. La parte vectorial es **decisión abierta**: ver abajo | "Cómo describí el estadio la primera vez" |
| **Resúmenes jerárquicos** | Escena → capítulo → arco → obra | Tabla con nivel y referencia al padre | "Resume los actos I y II en 400 palabras" |

**Lo único que SQLite no resuelve de serie es la búsqueda vectorial del índice de prosa.** FTS5 cubre el lado léxico con BM25 incluido, pero la recuperación híbrida (CTX-08) necesita además similitud semántica. Ninguna de las salidas posibles está elegida: es la decisión abierta nº 7 de §13, no un detalle de implementación.

**Troceado del índice de prosa**: la unidad es la escena, no un bloque de N tokens. Cada trozo lleva metadatos de capítulo, POV, lugar, instante de mundo y personajes presentes, de modo que la recuperación se filtre antes de puntuarse.

**Consistencia entre almacenes**: el registro de eventos manda. Canon estructurado y grafo son proyecciones reconstruibles. El índice de prosa se reindexa al congelar un capítulo.

### 3.2 Corto plazo: la memoria de trabajo (PRO-13)

Todo lo que el sistema sostiene mientras produce un capítulo y que **no es verdad todavía**. Vive en el mismo fichero, en tablas marcadas como efímeras.

| Tabla | Qué guarda | Se vacía |
|---|---|---|
| `run_state` | En qué capítulo, escena y paso va la tirada. Es el punto de reanudación (PRO-14) | Al terminar la novela |
| `draft` | Prosa de escena y de capítulo aún no congelada (PRO-06) | Al congelar: pasa al índice de prosa |
| `defect` | Defectos abiertos (CAL-05) con su evidencia y su estado en el bucle de §7.3 | Al congelar |
| `verdict` | Puntuaciones del jurado por dimensión, con su dispersión (CAL-11) | Al congelar |
| `admission` | Qué llamadas están en vuelo y cuáles esperan en la cola de CTX-20 | Al terminar cada llamada |

**Tres reglas.**

1. **La memoria de trabajo nunca entra en la ventana de un modelo.** Lo que el agente ve es su paquete de contexto (CTX-03), que el Documentalista ensambla. Si un borrador rechazado llegara al contexto del Escritor, el sistema estaría aprendiendo de su propio error.
2. **Se purga al congelar** (PRO-I1). La prosa aprobada pasa al índice; defectos, veredictos y cola desaparecen.
3. **Lo que se purga no se pierde: se traza.** §11 exige conservar defectos, puntuaciones y arbitrajes, y eso es trabajo de la observabilidad (VER-09), no del fichero de la novela. **SQLite guarda lo que es verdad; la traza guarda lo que pasó.** Duplicarlo en tablas históricas haría crecer el fichero con material que ya nadie consulta.

**Por qué en SQLite y no en memoria del proceso.** `AGENTS.md` §3.2 promete que copiar el fichero es copiar el estado completo, y de ahí salen la reproducibilidad de una tirada, el conjunto dorado (CAL-10) y los evals (VER-10). Con el estado de trabajo en el proceso esa promesa deja de ser cierta, y una caída en el capítulo 28 se lleva el capítulo entero.

---

## 4. Ingeniería de contexto con ventana de 100.000 tokens

### 4.1 Del límite físico al presupuesto operativo

100.000 tokens es el techo del proveedor, no el objetivo de llenado. La distracción (CTX-14) y la dilución de atención aparecen mucho antes de agotar la ventana, y en generación de prosa el coste se paga en cada escena de cada capítulo.

Reglas duras de ocupación (CTX-18) y de concurrencia (CTX-20):

| Regla | Valor | Motivo |
|---|---|---|
| Entrada máxima por llamada | 70.000 tokens | Solo el Arquitecto se acerca; el resto opera muy por debajo |
| Entrada + salida máximas | 85.000 tokens | Deja margen para reintentos que añaden el defecto y su evidencia |
| Margen reservado | 15.000 tokens | Absorbe regeneración dirigida sin rehacer el paquete |
| Acción al desbordar | Compactación por prioridad inversa (CTX-19) | Nunca truncamiento por el final |
| Techo concurrente del sistema | 100.000 tokens (CTX-20) | Suma de entrada y salida de todo lo que está en vuelo. **Sin margen reservado**: los 15.000 de arriba son por llamada, para que el defecto y su evidencia quepan al reintentar |
| Política de admisión | FIFO estricta | El Orquestador no arranca una llamada si no cabe: la encola. Sin reordenar por hueco, que mataría de hambre al Arquitecto y al Continuista, que son las llamadas grandes |

**Orden de compactación** cuando el material excede el presupuesto: primero los fragmentos recuperados, después la prosa literal previa, después los resúmenes, después las fichas secundarias. Nunca se tocan las anclas, el conocimiento del POV ni la especificación de la escena.

### 4.2 Presupuesto por agente

| Agente | Entrada | Salida | Ocupación de la ventana | Frecuencia |
|---|---:|---:|---:|---|
| Arquitecto narrativo | 55.000 | 15.000 | 70 % | Una vez por obra y por replanificación de arco |
| Planificador de capítulo | 28.000 | 6.000 | 34 % | Una vez por capítulo |
| Escritor de escena | 17.000 | 3.000 | 20 % | Por escena |
| Especialista deportivo | 12.000 | 3.000 | 15 % | Por encuentro |
| Continuista | 45.000 | 5.000 | 50 % | Por capítulo |
| Estilista | 20.000 | 7.000 | 27 % | Por capítulo |
| Juez (por instancia) | 9.000 | 1.500 | 11 % | 3 instancias por capítulo |
| Reparador | 12.000 | 3.000 | 15 % | Por defecto agrupado |
| Archivero | 22.000 | 5.000 | 27 % | Por capítulo |
| Árbitro | 15.000 | 2.000 | 17 % | Por conflicto |
| Supervisor | 30.000 | 3.000 | 33 % | Por capítulo cerrado |

**Qué corre en paralelo.** Solo el Jurado: sus tres instancias son deliberadamente independientes entre sí (§9.2), así que se lanzan a la vez y suman 31.500 tokens. Todo lo demás va en serie. Las escenas de un capítulo **no** se paralelizan, y no por coste: el bloque 6 del paquete del Escritor es la prosa literal de la escena anterior (§4.3), no compactable, así que escribir la escena *n* exige tener escrita la *n−1*. Paralelizarlas compraría velocidad rompiendo justo el bloque que sostiene la voz.

Con eso, las combinaciones que CTX-20 llega a acotar son estas:

| Concurrencia | Suma | Cabe |
|---|---:|:-:|
| Jurado ×3 | 31.500 | Sí |
| Continuista más Jurado ×3 | 81.500 | Sí, deja 18.500 |
| Arquitecto más Supervisor | 103.000 | No |
| Escritores de escena en paralelo | 20.000 cada uno | Máximo 5, 4 con margen |

Las dos últimas filas no ocurren en el flujo de §7: el Supervisor corre sobre capítulo cerrado y el Arquitecto solo al planificar, y las escenas van en serie. CTX-20 está para que sigan sin ocurrir cuando el paralelismo crezca, no para describir lo que pasa hoy.

El agente caro no es el que más escribe, es el **Continuista**: necesita el capítulo entero más el canon que podría contradecir. Es también el primero que tocará el techo cuando la novela crezca, y el que justifica la recuperación selectiva.

### 4.3 Presupuesto detallado del Escritor de escena

Es la llamada que más veces se ejecuta, así que es donde el presupuesto importa.

| # | Bloque | Tokens | Compactable | Notas |
|---|---|---:|---|---|
| 1 | Ancla: guía de estilo condensada e invariantes (CTX-17) | 2.000 | No | Idéntica en todas las llamadas |
| 2 | Fichas del elenco activo (CTX-05) | 1.600 | Sí | 4–6 personajes × ~280 tokens |
| 3 | Estado del mundo en t (MUN-10) | 1.200 | Parcial | Incluye estado físico y clasificación |
| 4 | Conocimiento del POV (PER-10) | 600 | No | Solo deltas respecto al estado público |
| 5 | Resúmenes jerárquicos (CTX-06) | 1.400 | Sí | Obra 500, arco 500, capítulo 400 |
| 6 | Prosa literal de la escena anterior (CTX-07) | 4.500 | No | El bloque que sostiene la voz |
| 7 | Recuperación puntual, 4–6 fragmentos (CTX-08) | 3.000 | Sí | Descripciones previas, escenas espejo |
| 8 | Setups abiertos relevantes (CAN-08) | 700 | Sí | Filtrados por personaje y arco |
| 9 | Lista de proscripción (POE-12) | 500 | Sí | 30 elementos más recientes |
| 10 | Muestra modélica de voz | 800 | Sí | Rotativa, nunca la escena anterior |
| 11 | Especificación de la escena | 900 | No | Va al final por CTX-16 |
| — | **Total entrada** | **17.200** | | 17 % de la ventana |
| — | Reserva de salida | 3.000 | | Escena de hasta ~2.000 palabras |

El 80 % restante de la ventana no es espacio libre que llenar. Es margen deliberado: si esos 17.000 tokens están bien elegidos, añadir 50.000 más de canon tangencial empeora el resultado.

### 4.4 Pipeline de ensamblaje

```mermaid
graph LR
  A["Especificación de escena"] --> B["Expansión de consulta"]
  B --> C1["Consulta estructurada al canon"]
  B --> C2["Recuperación semántica"]
  B --> C3["Recuperación léxica por nombres"]
  B --> C4["Consulta al grafo"]
  C1 --> D["Fusión y deduplicación"]
  C2 --> D
  C3 --> D
  C4 --> D
  D --> E["Rerank por relevancia a la escena"]
  E --> F["Ajuste a presupuesto · 17.200 tokens"]
  F --> G["Compactación del excedente · CTX-19"]
  G --> H["Ordenación por prioridad y recencia"]
  H --> I["Paquete de contexto · CTX-03"]
  I --> J["Auditoría automática del paquete"]
  J --> K["Llamada de generación"]
  J -.conflicto detectado.-> ARB["Árbitro"]
```

**Auditoría del paquete (paso J)**: antes de gastar la llamada, se comprueba que no haya dos versiones del mismo hecho (CTX-15), que todo el elenco tenga ficha, que las anclas estén presentes y que el total no exceda el presupuesto. Si aparece un conflicto de hechos, no se genera: se resuelve primero en el Árbitro.

### 4.5 Resúmenes jerárquicos

Se generan al congelar, nunca sobre la marcha:

- Escena cerrada: 60–100 palabras con cambio de valor y delta canónico.
- Capítulo cerrado: 150–250 palabras, construidas desde los resúmenes de escena, no desde el texto completo.
- Arco cerrado: 300 palabras.
- Obra: se regenera cada 5 capítulos.

Esto es lo que mantiene la memoria completa dentro de 100.000 tokens cuando la novela pasa de 150.000 palabras. Sin jerarquía, el Continuista deja de caber en la ventana alrededor del capítulo 20.

### 4.6 Control de deriva (CTX-12)

- **Anclas fijas** en toda llamada: guía de estilo condensada e invariantes.
- **Huella estilística (POE-13)** por capítulo: longitud media y varianza de frase, ratio adjetivo/sustantivo, n-gramas de 4 más frecuentes, riqueza léxica. Se compara contra la referencia de los primeros capítulos congelados. Desviación sostenida dispara un pase de estilo automático.
- **Lista de proscripción dinámica**: todo n-grama o imagen usado dos veces entra automáticamente en POE-12.
- **Muestra modélica rotativa**: un fragmento congelado de alta puntuación, distinto del inmediatamente anterior, para que la referencia de voz no sea siempre la última salida del propio sistema (POE-14).

### 4.7 Aislamiento (CTX-11)

Cada agente corre en su propia ventana limpia y devuelve solo salida estructurada. El Escritor nunca ve los informes de defectos de otros capítulos, el Juez nunca ve el paquete del Escritor y el Archivero nunca ve las rúbricas. Es lo que permite que trece agentes trabajen sobre una novela de 200.000 palabras sin que ninguno necesite más de 70.000 tokens; once consumen ventana, porque el Orquestador y el Documentalista son código.

El aislamiento acota **lo que cada agente ve**, no **cuántos corren a la vez**. Eso segundo lo acota CTX-20, y lo hace cumplir la admisión del Orquestador (§4.1).

---

## 5. Catálogo de skills

Una **skill** es una capacidad reutilizable con contrato fijo de entrada y salida. Las usan varios agentes; no pertenecen a ninguno. Las deterministas son código y no consumen ventana; las de modelo encapsulan instrucción, rúbrica y formato de salida.

### 5.1 Skills deterministas

| Skill | Función | Salida |
|---|---|---|
| `canon.query` | Consulta estructurada de entidades y fichas | Fichas en formato compacto |
| `canon.state-at` | Proyecta el estado del mundo en un instante | Estado en t |
| `canon.knowledge-of` | Proyecta qué sabe un personaje en t (PER-10) | Lista de hechos conocidos |
| `prose.retrieve` | Recuperación híbrida con filtro por metadatos | Fragmentos rankeados |
| `context.pack` | Ensambla y ordena el paquete según presupuesto | Paquete de contexto |
| `context.compact` | Reduce bloques por prioridad inversa | Paquete ajustado |
| `context.audit` | Detecta conflictos, huecos y exceso de tokens | Informe de validez |
| `check.timeline` | Fechas, orden de eventos, duración de elipsis | Defectos con evidencia |
| `check.ledger` | Marcadores, clasificación y estadísticas recalculadas | Defectos con evidencia |
| `check.availability` | Disponibilidad física y lesiones (DEP-I2) | Defectos con evidencia |
| `check.format` | POV único, tiempo verbal, persona, longitud | Defectos con evidencia |
| `check.repetition` | N-gramas repetidos y términos proscritos | Lista con recuento |
| `check.lexicon` | Nombres, alias y léxico del mundo | Defectos con evidencia |
| `match.simulate` | Motor de reglas que resuelve un encuentro completo | Cronología del encuentro y resultado |
| `style.fingerprint` | Calcula la huella estilística del texto | Vector de métricas y desviación |
| `setup.ledger` | Mantiene el registro de setups y su estado | Deuda narrativa vigente |
| `metrics.report` | Agrega métricas de salud por capítulo | Cuadro de mando |

`match.simulate` es la skill que más devuelve en épica deportiva: **el encuentro se resuelve primero con reglas y después se narra**. El modelo no inventa el marcador, lo dramatiza. Elimina de raíz toda la familia de defectos de verosimilitud deportiva.

### 5.2 Skills de modelo

| Skill | Función | Salida |
|---|---|---|
| `outline.plan` | Genera arcos, actos y curva de tensión | Escaleta estructurada |
| `scene.spec` | Convierte una entrada de escaleta en especificación completa | Especificación de escena |
| `scene.write` | Escribe la prosa de una escena | Prosa |
| `match.narrate` | Narra un encuentro ya resuelto por `match.simulate` | Prosa de secuencia |
| `continuity.review` | Contrasta prosa contra canon en lo no determinista | Defectos con cita |
| `voice.audit` | Verifica idiolecto y distinción entre voces | Puntuación con evidencia |
| `pacing.audit` | Evalúa ritmo, densidad y cambio de valor | Puntuación con evidencia |
| `subtext.audit` | Evalúa diálogo y subtexto | Puntuación con evidencia |
| `theme.audit` | Evalúa resonancia temática y uso de motivos | Puntuación con evidencia |
| `revise.targeted` | Corrige un fragmento dado el defecto y su evidencia | Fragmento corregido |
| `dialogue.pass` | Pase específico sobre diálogo | Prosa revisada |
| `style.polish` | Pase de estilo, poda y proscripción | Prosa pulida |
| `delta.extract` | Extrae hechos, eventos y cambios de estado | Delta canónico estructurado |
| `summarize.hierarchical` | Resume al nivel pedido | Resumen |
| `retcon.propose` | Propone reinterpretación de canon con pasajes afectados | Propuesta arbitrable |
| `replan.arc` | Recalcula un tramo de escaleta tras un bloqueo | Escaleta parcial |

**Contrato común de las skills de auditoría**: toda puntuación llega acompañada de la cita textual que la justifica. Sin evidencia, la puntuación se descarta automáticamente. Es lo que impide que un juez sin supervisión externa apruebe por inercia.

---

## 6. Catálogo de agentes

| # | Agente | Misión | Skills principales | Criterio de salida |
|---|---|---|---|---|
| 0 | **Orquestador** | Dirige el flujo, aplica presupuestos, admite o encola llamadas contra CTX-20 y cuenta reintentos. Es código, no modelo. | Todas las deterministas | — |
| 1 | **Arquitecto narrativo** | Arcos, doble arco (DEP-20), curva de tensión, escaleta de obra | `outline.plan`, `canon.query` | Escaleta que supera el verificador estructural |
| 2 | **Planificador de capítulo** | Convierte el tramo de escaleta en especificaciones de escena | `scene.spec`, `canon.state-at`, `setup.ledger` | Todas las escenas con función y cambio de valor declarados |
| 3 | **Documentalista** | Ensambla el paquete de contexto de cada llamada. Es código. | `context.pack`, `prose.retrieve`, `canon.*`, `context.audit` | Paquete válido dentro de presupuesto |
| 4 | **Escritor de escena** | Produce la prosa | `scene.write` | Escena generada dentro de longitud |
| 5 | **Especialista deportivo** | Resuelve y narra encuentros; custodia DEP-19 | `match.simulate`, `match.narrate`, `check.availability` | Encuentro consistente con reglamento y plantilla |
| 6 | **Continuista** | Verificación de continuidad de capítulo | `check.*`, `continuity.review` | Cero defectos S1 |
| 7 | **Jurado** (3 instancias) | Evalúa las dimensiones subjetivas | `voice.audit`, `pacing.audit`, `subtext.audit`, `theme.audit` | Puntuaciones sobre umbral y dispersión baja |
| 8 | **Reparador** | Corrección dirigida de defectos agrupados | `revise.targeted`, `dialogue.pass` | Defecto cerrado sin abrir otros |
| 9 | **Estilista** | Pase de voz, poda y proscripción | `style.polish`, `style.fingerprint`, `check.repetition` | Huella dentro de tolerancia |
| 10 | **Archivero** | Extrae el delta canónico y regenera resúmenes | `delta.extract`, `summarize.hierarchical` | Delta completo y estructurado |
| 11 | **Árbitro** | Resuelve conflictos por política de precedencia (PRO-10) | `retcon.propose`, `canon.query` | Conflicto cerrado y registrado |
| 12 | **Supervisor** | Vigila deuda narrativa, curva de tensión y deriva; dispara replanificación | `setup.ledger`, `metrics.report`, `replan.arc` | Métricas dentro de umbral |

Tres agentes son los que suelen faltar en implementaciones ingenuas: el **Archivero** (sin él el canon se queda atrás respecto al texto), el **Árbitro** (sin él un conflicto detiene el sistema, porque no hay a quién preguntar) y el **Supervisor** (sin él la novela pierde forma en el segundo acto sin que nada lo señale).

### 6.1 Matriz agente × skill

```mermaid
graph LR
  subgraph Agentes
    A1["Arquitecto"]
    A2["Planificador"]
    A3["Documentalista"]
    A4["Escritor"]
    A5["Esp. deportivo"]
    A6["Continuista"]
    A7["Jurado"]
    A8["Reparador"]
    A9["Estilista"]
    A10["Archivero"]
    A11["Árbitro"]
    A12["Supervisor"]
  end

  subgraph Skills
    S1["outline.plan"]
    S2["scene.spec"]
    S3["context.pack"]
    S4["prose.retrieve"]
    S5["scene.write"]
    S6["match.simulate"]
    S7["match.narrate"]
    S8["check.*"]
    S9["continuity.review"]
    S10["*.audit"]
    S11["revise.targeted"]
    S12["style.polish"]
    S13["delta.extract"]
    S14["summarize.hierarchical"]
    S15["retcon.propose"]
    S16["setup.ledger"]
    S17["replan.arc"]
  end

  A1 --> S1
  A1 --> S16
  A2 --> S2
  A2 --> S16
  A3 --> S3
  A3 --> S4
  A4 --> S5
  A5 --> S6
  A5 --> S7
  A5 --> S8
  A6 --> S8
  A6 --> S9
  A7 --> S10
  A8 --> S11
  A9 --> S12
  A10 --> S13
  A10 --> S14
  A11 --> S15
  A12 --> S16
  A12 --> S17
```

---

### 6.2 Contrato de entrada y salida por agente

**Todo entra y sale por el Orquestador**, que es el único que conoce el flujo (§7.2), con una sola excepción documentada al pie de esta sección. Las columnas de abajo dicen qué artefacto recibe y qué artefacto devuelve cada agente, no con quién se comunica.

Los artefactos se nombran por la skill que los produce (`scene.spec`, `delta.extract`) o por su ID de `definitions.md` cuando ya existe (CTX-03, CAN-11). No hay una familia de IDs propia para artefactos: duplicaría el espacio de nombres.

| # | Agente | **Entrada** | **Salida** |
|---|---|---|---|
| 0 | **Orquestador** | Brief (PRO-01) | Manuscrito congelado. Es el bus: recibe y despacha todo lo demás |
| 1 | **Arquitecto narrativo** | Brief (PRO-01) · canon existente si lo hay | Escaleta de obra: arcos, actos y curva de tensión (`outline.plan`) |
| 2 | **Planificador de capítulo** | Tramo de escaleta congelada · estado del mundo en t (`canon.state-at`) · deuda narrativa vigente (`setup.ledger`) | Especificaciones de escena 1..k (`scene.spec`), cada una con función y cambio de valor |
| 3 | **Documentalista** | Una `scene.spec` · presupuesto en tokens del agente destino | Paquete de contexto válido (CTX-03) dentro de presupuesto |
| 4 | **Escritor de escena** | Paquete de contexto (CTX-03) | Prosa de la escena (`scene.write`) |
| 5 | **Especialista deportivo** | Paquete de contexto (CTX-03) · estado de la plantilla | Cronología y resultado del encuentro (`match.simulate`) · prosa de la secuencia (`match.narrate`) |
| 6 | **Continuista** | Capítulo completo (PRO-06) · canon que podría contradecirlo | Informe de continuidad: defectos (CAL-05) con cita localizable |
| 7 | **Jurado** (×3) | Capítulo (PRO-06) · rúbricas (CAL-02) | Puntuación por dimensión con evidencia · dispersión entre instancias |
| 8 | **Reparador** | Fragmento · defecto (CAL-05) · su evidencia | Fragmento o capítulo corregido (`revise.targeted`) |
| 9 | **Estilista** | Capítulo aprobado por Jurado y Continuista | Capítulo pulido (`style.polish`) · huella estilística (`style.fingerprint`) |
| 10 | **Archivero** | Capítulo final, aún sin congelar | Delta canónico (CAN-11, `delta.extract`) · resúmenes jerárquicos (`summarize.hierarchical`) |
| 11 | **Árbitro** | Conflicto: dos afirmaciones incompatibles con su procedencia | Afirmación vigente según precedencia (PRO-10) · registro del arbitraje |
| 12 | **Supervisor** | Métricas del capítulo cerrado · deuda narrativa · curva de tensión acumulada | Veredicto de salud y, si hay deriva, tramo replanificado (`replan.arc`) |

**Dos entradas que conviene no confundir.** Lo que el Orquestador entrega a un agente de modelo es una `scene.spec` o un capítulo; lo que entra de verdad en la ventana es el paquete de contexto (CTX-03) que el Documentalista ensambla a partir de eso. La tabla recoge el contrato lógico. La composición real del paquete está en §4.3 para el Escritor de escena, que es la llamada que más veces se ejecuta y la única que hoy la justifica.

**Los dos agentes que son código.** El Orquestador y el Documentalista no consumen ventana y por eso no aparecen en la tabla de presupuestos de §4.2. Su contrato es igual de vinculante: un Documentalista que devuelve un paquete fuera de presupuesto rompe la restricción de contexto antes de que ningún modelo llegue a verla.

El Orquestador lleva además **el contador de CTX-20**. Es el único que sabe qué hay en vuelo, así que es el único que puede admitir o encolar una llamada. Dos reglas: la admisión es FIFO estricta, y si no puede estimar el presupuesto de una llamada no la admite, por la regla de fallo cerrado.

**El Árbitro entra por dos puertas.** Lo llama el Orquestador cuando el delta del Archivero choca con el canon, y lo llama el Documentalista cuando `context.audit` detecta hechos en conflicto dentro del paquete, antes de generar (§7.2). Es el único agente al que invoca alguien distinto del Orquestador, y es deliberado: arbitrar antes de generar es mucho más barato que reparar después.

---

## 7. Flujo del sistema de agentes

### 7.1 Vista general

```mermaid
graph TD
  ST["Brief"] --> A1["1 · Arquitecto narrativo"]
  A1 --> VE["Verificador estructural de escaleta"]
  VE -->|falla| A1
  VE -->|pasa| FZ1["Congelar escaleta"]

  FZ1 --> A2["2 · Planificador de capítulo"]
  A2 --> A3

  subgraph BE["Bucle de escena"]
    A3["3 · Documentalista"] --> DEC{"¿Es un encuentro?"}
    DEC -->|sí| A5["5 · Especialista deportivo"]
    DEC -->|no| A4["4 · Escritor de escena"]
    A5 --> VD["Verificadores deterministas"]
    A4 --> VD
    VD -->|S1| A8a["8 · Reparador"]
    A8a --> VD
    VD -->|limpio| SIG{"¿Quedan escenas?"}
    SIG -->|sí| A3
  end

  SIG -->|no| CAP["Capítulo completo"]
  CAP --> A6["6 · Continuista"]
  A6 -->|defectos| A8b["8 · Reparador"]
  A8b --> A6
  A6 -->|limpio| A7["7 · Jurado x3"]
  A7 -->|bajo umbral| A8c["8 · Reparador"]
  A8c --> A6
  A7 -->|sobre umbral| A9["9 · Estilista"]
  A9 --> A6r["Reverificación"]
  A6r -->|limpio| A10["10 · Archivero"]

  A10 --> VAL{"¿Delta compatible?"}
  VAL -->|no| A11["11 · Árbitro"]
  A11 --> VAL
  VAL -->|sí| FZ2["Congelar capítulo · CAN-12"]

  FZ2 --> A12["12 · Supervisor"]
  A12 -->|métricas sanas| A2
  A12 -->|deriva o deuda| RPL["Replanificar tramo · PRO-12"]
  RPL --> A2

  A8c -.reintentos agotados.-> CU["Cuarentena · CAL-13"]
  CU --> RPL
```

### 7.2 Secuencia de un capítulo

```mermaid
sequenceDiagram
  autonumber
  participant O as Orquestador
  participant P as Planificador
  participant D as Documentalista
  participant E as Escritor
  participant S as Esp. deportivo
  participant C as Continuista
  participant J as Jurado
  participant R as Reparador
  participant Y as Estilista
  participant A as Archivero
  participant B as Árbitro
  participant V as Supervisor

  O->>P: tramo de escaleta del capítulo N
  P-->>O: especificaciones de escena 1..k

  loop por cada escena
    O->>D: especificación de escena
    D->>D: canon.query · state-at · knowledge-of · prose.retrieve
    D->>D: context.pack a 17.200 tokens + context.audit
    alt conflicto de hechos en el paquete
      D->>B: conflicto detectado
      B-->>D: hecho vigente según precedencia
    end
    D-->>O: paquete de contexto
    alt la escena es un encuentro
      O->>S: paquete + estado de plantilla
      S->>S: match.simulate
      S-->>O: prosa + cronología del encuentro
    else escena narrativa
      O->>E: paquete
      E-->>O: prosa de escena
    end
    O->>O: verificadores deterministas
    opt defecto S1
      O->>R: fragmento + defecto + evidencia
      R-->>O: fragmento corregido
    end
  end

  O->>C: capítulo completo + canon relevante
  C-->>O: informe de continuidad
  opt defectos
    O->>R: defectos agrupados
    R-->>O: capítulo corregido
    O->>C: reverificación
  end

  O->>J: capítulo + rúbricas · 3 instancias en paralelo · 31.500 tokens
  J-->>O: puntuaciones con evidencia y dispersión
  alt bajo umbral y reintentos disponibles
    O->>R: defectos S2 y S3
    R-->>O: capítulo corregido
  else reintentos agotados
    O->>V: cuarentena del capítulo
    V-->>O: tramo replanificado
  end

  O->>Y: capítulo aprobado
  Y-->>O: capítulo pulido + huella estilística

  O->>A: capítulo final
  A-->>O: delta canónico + resúmenes
  O->>B: validar delta contra canon
  alt contradicción
    B-->>O: arbitraje aplicado y registrado
  end
  O->>O: congelar capítulo y reindexar
  O->>V: métricas del capítulo
  V-->>O: continuar o replanificar
```

### 7.3 Bucle de reparación y cuarentena

Cómo se cierra un defecto sin que nadie apruebe nada.

```mermaid
stateDiagram-v2
  [*] --> Detectado
  Detectado --> Agrupado: defectos del mismo tipo y zona
  Agrupado --> Reparando: revise.targeted con evidencia
  Reparando --> Reverificando
  Reverificando --> Cerrado: defecto resuelto y sin regresiones
  Reverificando --> Agrupado: persiste, quedan reintentos
  Reverificando --> Regresion: aparecen defectos nuevos
  Regresion --> Revertido: se descarta la corrección
  Revertido --> Agrupado
  Agrupado --> Cuarentena: presupuesto de reintentos agotado · CAL-12
  Cuarentena --> Replanificando: replan.arc o scene.spec más estricta
  Replanificando --> [*]
  Cerrado --> [*]
```

**Presupuestos de reintento por defecto**: 3 a nivel de escena, 2 a nivel de capítulo, 1 replanificación de tramo. Al agotarse la tercera, se replanifica el arco completo. No hay cuarto nivel: si un arco falla dos veces, el problema está en la escaleta y se recalcula desde el Arquitecto.

### 7.4 Ejecución: el Orquestador como código

§7.1 a §7.3 dicen **qué pasa**. Esta sección dice **cómo se ejecuta**, que es lo que hace falta para escribir `backend/orchestration/`.

#### Un proceso, un bucle asíncrono

El Orquestador es un bucle `asyncio` en un solo proceso. No hay cola de trabajos ni workers.

El motivo es de dimensionamiento, no de gusto: una novela es una unidad aislada, no hay concurrencia entre tiradas, la persistencia es un fichero local, y el paralelismo real que hay que soportar son **tres llamadas simultáneas**, las del Jurado (§4.2). Un broker y un proceso más serían infraestructura para un problema que este sistema no tiene, y añadirían un modo de fallo nuevo a un ciclo que por PRO-11 debe terminar sin que nadie intervenga.

#### Reanudación por escena

La tirada persiste su punto de reanudación (PRO-14) en `run_state` al cerrar **cada escena**, no cada llamada.

| | |
|---|---|
| **Al arrancar** | Si hay un capítulo sin congelar, se reanuda desde la última escena cerrada |
| **Qué se descarta** | Todo borrador posterior a ese punto: puede estar a medias y no ha pasado ninguna puerta (PRO-I2) |
| **Qué se conserva** | Las escenas ya cerradas del capítulo y su cuenta de reintentos consumidos |

Por escena y no por llamada porque la escena **ya es** la unidad de reintento de §7.3: reanudar por ahí reaprovecha una frontera que el diseño tiene, en vez de inventar otra. Persistir cada llamada obligaría a serializar su paquete de contexto y multiplicaría la escritura sin comprar nada.

#### Admisión de llamadas: CTX-20 como semáforo

El techo de concurrencia de §4.1 se implementa como un **semáforo con contador de tokens**, no como un límite de llamadas simultáneas: lo que se cuenta son tokens, porque tres jueces y un Continuista ocupan cosas muy distintas.

```
admitir(llamada):
    si en_vuelo + presupuesto(llamada) <= 100.000:
        en_vuelo += presupuesto(llamada);  ejecutar
    si no:
        encolar en FIFO estricta, sin reordenar por hueco
al terminar(llamada):
    en_vuelo -= presupuesto(llamada);  admitir al primero de la cola
```

Dos reglas que no se negocian: **FIFO estricta**, porque reordenar por hueco mata de hambre al Arquitecto y al Continuista, que son las llamadas grandes; y **fallo cerrado**, si el presupuesto de una llamada no se puede estimar, no se admite.

#### Módulos de `backend/orchestration/`

| Módulo | Responsabilidad |
|---|---|
| `loop` | Los bucles de capítulo y de escena de §7.1 |
| `checkpoint` | Escribe y lee el punto de reanudación en `run_state` |
| `admission` | Contador de CTX-20, cola FIFO y fallo cerrado |
| `retries` | Presupuesto de reintentos y paso a cuarentena de §7.3 |
| `dispatch` | Llama al agente que toca y valida su salida contra el esquema antes de devolverla |

`dispatch` es el que concentra el riesgo: es la frontera de confianza donde el texto de un modelo se convierte en objeto tipado (VER-01). Todo lo que pase de ahí sin validar contamina el canon.

---

## 8. Cómo se sustituye cada decisión antes reservada a una persona

| Decisión | Sustituto autónomo |
|---|---|
| Aprobar la escaleta | Verificador estructural determinista: cobertura de arcos, resolución del doble arco en momentos distintos, curva de tensión monótona por acto, todos los setups con payoff planificado, reparto de palabras por capítulo. Más una pasada de jurado sobre la escaleta. |
| Resolver una contradicción de canon | Árbitro con la política de precedencia PRO-10: canon congelado > delta nuevo; brief > canon derivado; invariante duro > preferencia estética; hecho con payoff cobrado > hecho sin cobrar. |
| Autorizar un retcon | `retcon.propose` más regla dura: solo procede si el hecho afectado no ha sido cobrado en ningún payoff y el número de pasajes que habría que tocar es igual o menor que 3. En caso contrario se regenera el capítulo nuevo. |
| Cerrar un capítulo | Puertas automáticas con umbrales por dimensión (CAL-09). |
| Calibrar a los jueces | Conjunto dorado con defectos sembrados (CAL-10) ejecutado cada 5 capítulos, más dispersión del jurado (CAL-11) como señal de fiabilidad por veredicto. |
| Rechazar y parar | No existe. Cuarentena (CAL-13) más replanificación (PRO-12). La producción continúa con el siguiente capítulo y el tramo cuarentenado se rehace. |
| Decidir que la novela está terminada | Condición de cierre verificable: deuda narrativa cero, todos los arcos con estado resuelto, curva de tensión completada, longitud dentro del rango del brief. |

**Lo que se pierde y hay que compensar con medición**: el criterio de gusto. Un sistema autónomo puede garantizar coherencia, verosimilitud y ausencia de defectos, pero no puede decidir por sí mismo que una escena es memorable. La contramedida practicable es el conjunto dorado, que fija un suelo conocido, y la vigilancia de la huella estilística, que detecta el aplanamiento antes de que se acumule.

---

## 9. Control de calidad automático

Los métodos con los que se verifica este control — y el código que lo implementa — están en [`verification.md`](verification.md). Aquí solo se describe el mecanismo.

### 9.1 Verificadores deterministas

Coste despreciable, cero falsos positivos si están bien escritos. Se ejecutan siempre antes que cualquier juez:

- Cronología: fechas mencionadas frente al calendario; orden de eventos; duración de elipsis.
- Resultados y clasificación: el marcador narrado cuadra con `match.simulate`; la tabla recalculada coincide con lo afirmado.
- Estadísticas acumuladas: suma de encuentros narrados.
- Disponibilidad: nadie juega estando lesionado en esa fecha (DEP-I2).
- Nombres, alias y léxico del mundo.
- Restricciones formales: tiempo verbal, persona, POV único por escena, longitud.
- Repetición: n-gramas de 4 o más ya usados; frecuencia de términos proscritos.
- Conocimiento: menciones de hechos canónicos por personajes cuyo PER-10 no los incluye.

### 9.2 Jurado

Tres instancias con rúbricas distintas y semillas distintas. Reglas:

- Toda puntuación cita el fragmento que la justifica. Sin cita, se descarta.
- Contexto mínimo: escena, especificación y ficha de voz. Nunca el paquete del Escritor.
- Dispersión alta entre instancias invalida el veredicto y fuerza una verificación adicional en lugar de promediar. Promediar jueces que no se ponen de acuerdo produce un número sin significado.

### 9.3 Puertas

| Puerta | Condición de paso |
|---|---|
| Escena generada | Cero defectos S1 deterministas |
| Capítulo verificado | Cero S1, máximo 2 S2, continuidad y voz sobre umbral |
| Capítulo cerrado | Puertas anteriores más huella estilística dentro de tolerancia y delta canónico integrado |
| Cierre de acto | Deuda narrativa dentro del margen planificado; curva de tensión conforme |
| Cierre de obra | Deuda narrativa cero; todos los arcos resueltos; longitud en rango |

---

## 10. Escritura de canon

El punto donde el texto generado se convierte en verdad. Sin validación externa, el Árbitro es el único guardián.

```mermaid
sequenceDiagram
  participant A as Archivero
  participant V as Validador
  participant B as Árbitro
  participant C as Canon
  participant I as Índices

  A->>A: delta.extract sobre el capítulo aprobado
  A->>V: delta canónico propuesto · CAN-11
  V->>C: contrastar con canon vigente
  alt sin contradicción
    V->>C: aplicar eventos
    C->>C: recalcular proyecciones
    C->>I: reindexar prosa y regenerar resúmenes
  else contradicción
    V->>B: conflicto con hechos afectados
    B->>B: aplicar precedencia PRO-10
    alt el canon previo gana
      B->>V: rechazar delta y marcar capítulo para reparación
    else el delta gana y el retcon es admisible
      B->>C: aplicar retcon registrado · CAN-10
      B->>I: marcar pasajes afectados para reescritura
    end
  end
```

Reglas duras: el delta se propone y se valida, nunca se aplica en bruto; todo hecho guarda procedencia (MET-09) y capítulo de origen; todo arbitraje deja registro con la regla aplicada; la congelación es la única operación que cambia el canon.

---

## 11. Observabilidad

Por cada fragmento se guarda: versión del paquete de contexto, ocupación real en tokens por bloque, ocupación concurrente en el momento de admitir la llamada, tiempo en cola, agente, skill, parámetros, defectos, puntuaciones con evidencia y decisiones de arbitraje.

En un sistema sin supervisión externa, la observabilidad no es un extra: es el único mecanismo para detectar que algo se ha estado degradando durante diez capítulos.

| Métrica | Señal de alarma |
|---|---|
| Defectos S1 por 1.000 palabras | Tendencia creciente: el canon no llega al contexto |
| Tasa de reparación | Por encima del 30 %: escaleta o contexto insuficientes |
| Capítulos en cuarentena | Más de uno por acto: problema estructural, no local |
| Deriva de huella estilística | Desviación sostenida: pase de estilo y refresco de muestras |
| Deuda narrativa | Crece sin plan de cierre |
| Dispersión del jurado | Alta y creciente: rúbricas mal definidas |
| Ocupación real por bloque | Un bloque desplaza sistemáticamente a otro |
| Ocupación concurrente máxima (CTX-20) | Roza los 100.000 de forma sostenida, o la cola crece: el paralelismo está mal dimensionado |
| Aciertos sobre el conjunto dorado | Caída: los jueces han derivado |

---

## 12. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Envenenamiento de canon (CTX-13) | Alto y creciente: sin revisión externa se propaga sin freno | Validación de delta, procedencia obligatoria, arbitraje registrado, conjunto dorado |
| Jueces que derivan junto al generador | Alto y silencioso | Aislamiento, evidencia obligatoria, jurado con dispersión, conjunto dorado periódico |
| Aplanamiento estilístico | Alto | Huella estilística, proscripción dinámica, muestras modélicas rotativas |
| Bucle infinito de reparación | Medio | Presupuesto de reintentos y cuarentena, sin excepción |
| Convergencia a lo correcto pero anodino | Alto, propio de la autonomía total | Umbrales mínimos también en tensión y subtexto, no solo en continuidad |
| Continuista que no cabe en 100.000 tokens | Medio, aparece hacia el capítulo 20 | Resúmenes jerárquicos y recuperación filtrada por metadatos |
| Coste por capítulo | Medio | Determinista antes que modelo, escena como unidad de reintento, modelos distintos por rol |

---

## 13. Decisiones abiertas

1. Tamaño óptimo del bloque de prosa literal (4.500 tokens actuales) frente a su coste por escena.
2. Si el Continuista debe operar por capítulo o por par de capítulos al crecer la obra.
3. Número de instancias de jurado: tres es el mínimo para medir dispersión, pero triplica coste.
4. Umbral de dispersión que invalida un veredicto.
5. Si `match.simulate` debe modelar el encuentro minuto a minuto o solo sus hitos.
6. Punto a partir del cual conviene reescribir un capítulo en vez de repararlo.
7. Cómo se resuelve la mitad vectorial del índice de prosa sobre SQLite (§3): extensión vectorial, embeddings en tabla con cálculo en Python, o prescindir de lo semántico y quedarse en FTS5 más filtro por metadatos.

---

## 14. Orden de construcción sugerido

1. Canon estructurado + registro de eventos.
2. Especificación de escena y escaleta.
3. Documentalista con presupuesto fijo, sin recuperación semántica.
4. Escritor de escena + verificadores deterministas.
5. Archivero y ciclo de congelación.
6. Árbitro y política de precedencia. **Desde aquí el sistema ya es autónomo**: antes de este punto, cualquier conflicto lo detiene.
7. Resúmenes jerárquicos.
8. Recuperación híbrida.
9. Jurado, conjunto dorado y Estilista.
10. Supervisor, replanificación y métricas de salud.
11. Frontend de lectura y visualización.

El orden recorre **funcionalidades de §2.3**, no capas técnicas: los pasos 1 y 5 llenan `canon/`, el 2 `planning/`, el 3 `context/`, el 4 `generation/`, el 6 cierra `canon/`, el 9 `verification/`, el 10 `supervision/` y el 11 el frontend entero. Es la consecuencia práctica de organizar por funcionalidad: cada paso entrega una carpeta que funciona, no un estrato horizontal que todavía no hace nada.

Los pasos 1 a 6 producen una novela coherente sin intervención. Del 7 al 10 se gana escala y calidad, no viabilidad. El paso 11 está fuera del camino crítico por definición (§2.1) y solo tiene sentido cuando el paso 10 ya produce métricas que mostrar.
