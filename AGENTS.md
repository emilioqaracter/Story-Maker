# AGENTS.md

Guía de este repositorio para cualquier agente que trabaje en él, humano o automático. Léela entera antes de tocar nada. Es el único documento de trabajo: `CLAUDE.md` solo apunta aquí.

---

## 1. Qué es este proyecto

Un sistema **autónomo** de generación de novelas largas. Caso de referencia: épica deportiva. El sistema planifica, escribe, verifica, corrige, arbitra y cierra una novela completa **sin intervención externa en ningún punto del ciclo**.

Dos restricciones fijan todo el diseño:

- **Autonomía de extremo a extremo.** No hay aprobación manual, ni revisión de una persona, ni escalado. Cada decisión necesita una regla de precedencia, un umbral numérico o un agente responsable.
- **Ventana de contexto de 100.000 tokens de entrada** por llamada, para cualquier agente **del sistema mientras escribe la novela**. Es un techo fijado por el proyecto, no un límite del proveedor: los modelos usados dan entre 200.000 y 1.000.000. La salida no cuenta contra él. Es cuánto cabe en una llamada, no cuánto mide la novela. No aplica al trabajo de crear el sistema, las specs ni la documentación.

**De un vistazo**

| | |
|---|---|
| **Ventana máxima de contexto** | **100.000 tokens de entrada** por llamada, techo propio del proyecto. La salida no cuenta (§5.3.2) |
| **Backend** — `backend/` | **Python + FastAPI** |
| **Frontend** — `frontend/` | **React** |
| **Persistencia** | **SQLite en local**, un fichero por novela |
| **Servicios externos** | **Claude**, único proveedor de modelo, y **Langfuse**, espejo de la traza local (`docs/architecture.md` §4.8 y §11) |
| **Verificación formal** | **Lean 4** sobre la cronología del canon y **TLA+** sobre el flujo (`docs/verification.md` §4.4 y §5.10) |
| **Intervención humana en la novela** | Ninguna (§5.3.1) |

La idea central del dominio: **una novela larga no es un texto largo, es un estado del mundo que evoluciona**. El texto es la proyección visible. El sistema gestiona el estado; la prosa es consecuencia.

---

## 2. Estado actual

| Fase | Estado |
|---|---|
| Ontología del dominio | ✅ Completa |
| Modelos y diagramas | ✅ Completos |
| Arquitectura, agentes y skills | ✅ Especificados |
| SRS del backend (`specs/`) | ✅ Versión 1 (`srs-backend-v1.md`, pasos 1 a 6) y versión 2 (`srs-backend-v2.md`, pasos 7 a 10 y retcon), y versión 3 (`srs-backend-v3.md`, T33 a T36): entrevista, versiones, fichas y solicitudes de cambio que el frontend exige. Versión 4 (`srs-backend-v4.md`, T37 a T53): Lean sobre la cronología, guardarraíl bloqueante, espejo en Langfuse, hecho × capítulo, hooks de Claude Code, Jurado con las dimensiones del encargo, TLA+ del flujo completo, evaluación del sistema y perfil de extensión `prueba`; construida salvo las tiradas de evaluación de T52 |
| SRS del frontend (`specs/`) | ✅ Versión 1 (`srs-frontend-v1.md`, paso 11): entrevista del brief, lectura por versiones, ficha de personajes y lugares, enmiendas al brief desde la lectura. Las rutas nuevas que exige las realiza `srs-backend-v3.md`. Su plan de implementación es `frontend/PLAN.md`, T26 a T32. Versión 2 (`srs-frontend-v2.md`, T54 a T58): ilustraciones deportivas de marca, elevación, libro en 3D al cerrar la obra y grafo en 3D, sin rutas nuevas |
| Estrategia de verificación | ✅ Completa |
| Implementación del backend | 🟡 Versiones 1 y 2 construidas, cableadas y en verde (T0 a T24). De la versión 4, T37 a T51 y T53 construidos, integrados y en verde (`python gate.py`, con Lean; TLC en CI al cambiar el modelo): TLA+ del flujo, verificadores endurecidos, Langfuse como espejo, guardarraíl, hecho × escena y cronología, Lean antes de congelar, brief, hooks de Claude Code y audit log, Jurado de nueve dimensiones con elementos obligatorios, validación visual, tabla de validadores en la puerta, herramientas de evaluación y perfil `prueba`. T52, las tiradas de evaluación, en curso. Faltan también las dos tiradas reales: la de T16, que produce `golden/v1-seed/`, y la de T24, que se compara con ella (`backend/PLAN.md` §1.7) |
| Implementación del frontend | ✅ T26 a T31 construidos y en verde (`node gate.mjs`): entrevista, lectura por versiones con marcas de cambio, ficha de personajes y lugares, solicitudes de cambio, estado, deuda y grafo. T32 con modelo real sobre una copia de la tirada real; la tirada entera de una novela encargada desde la entrevista depende de T16 (`frontend/PLAN.md`). Versión 2, T55 a T58, construida; las ilustraciones del catálogo las pone quien desarrolla en `frontend/commons/brand/art/` |
| Implementación del backend v3 | ✅ T34 a T36 construidos y en verde (`python gate.py`): `brief/`, versiones, fichas, lista de novelas y solicitudes aplicadas por el Orquestador |
| Agentes de modelo | ✅ Los trece con prompt o código y cableados en el motor real |
| Capa de memoria | ✅ Cinco almacenes en SQLite, memoria de trabajo, delta canónico validado al congelar y traza local por tirada |

**El repositorio está cerrando el backend: las versiones 1 a 4 tienen el código completo, y faltan las tiradas reales que lo demuestran: T16 y T24, y las de evaluación de T52, en curso.** El plan de lo que falta, con su orden y sus puertas, es `backend/PLAN.md`. No crees agentes, skills ni código fuera de ese plan salvo que se pida de forma explícita.

---

## 3. Estructura del repositorio

Es un **monorepo**: backend y frontend viven en la misma raíz, junto a la especificación.

```
.
├── AGENTS.md                 ← estás aquí: guía de trabajo, reglas e índice
├── CLAUDE.md                 ← una línea que apunta a este fichero
├── docs/
│   ├── definitions.md        ← ontología: qué existe en el dominio
│   ├── domain-knowledge.md   ← modelos visuales de esa ontología
│   ├── architecture.md       ← cómo se construye el sistema
│   └── verification.md       ← cómo se verifica el código y la salida de los agentes
├── .mcp.json                 ← MCP de navegador de la validación visual; su guion repetible es frontend/visual/
├── .claude/settings.json     ← hooks de Claude Code del trabajo de desarrollo
├── .claude/hooks/            ← sus guiones: validación de capítulo y política, con audit log en .claude/audit/
├── .claude/skills/           ← reglas de este repositorio, ejecutables
│   ├── grill-me/             ← proceso: interrogatorio previo, §6.1
│   ├── verification-sheet/   ← proceso: produce verification.md
│   ├── fastapi/              ← tecnología: backend
│   ├── react/                ← tecnología: frontend
│   └── sqlite/               ← tecnología: persistencia
├── specs/                    ← un SRS por versión del backend: ver §3.3
├── backend/                  ← API y motor del sistema autónomo
└── frontend/                 ← visualización del estado narrativo
```

`backend/` tiene el código de las versiones 1 a 4 (§2). `frontend/` tiene la versión 1 entera (§2), con su plan en `frontend/PLAN.md`. El paso 11 está fuera del camino crítico (§8).

### 3.1 Stack por carpeta

| Carpeta | Stack | Responsabilidad |
|---|---|---|
| `backend/` | Python + FastAPI | Orquestador, agentes, skills, capa de memoria y canon. Todo lo especificado en `docs/architecture.md` |
| `frontend/` | React | Entrevista del brief, lectura del manuscrito por versiones con ficha de personajes y lugares, enmiendas al brief desde la lectura, y visualización del estado del mundo, del grafo canónico y de la curva de tensión. `frontend/visual/` es la validación visual repetible, que no es una vista |

**Las dos se organizan por funcionalidad, no por capa técnica.** Cada funcionalidad es una carpeta con todo lo suyo dentro y lo compartido vive en `commons/`; en el frontend, además, **no se usa Feature-Sliced Design**. El reparto concreto, con las tres reglas que impiden que degenere, está en `docs/architecture.md` §2.3.

Dos consecuencias que conviene tener claras desde ya:

- **El frontend no participa en el ciclo de generación.** Observa y muestra; no aprueba, no corrige, no desbloquea. Cualquier interacción que condicione al ciclo viola la restricción de autonomía (§5.3.1). Lo único que entra por él son encargos —el brief y sus enmiendas—, y un encargo cambia lo que se pide, no revisa lo que se escribió (`docs/architecture.md` §2.2).
- **El backend es el único dueño del canon.** El frontend lee proyecciones del estado; no escribe en él (§5.3.3).

### 3.2 Persistencia

**SQLite en local.** Los cinco almacenes de la capa de memoria (`architecture.md` §3) viven en SQLite, con un fichero por novela.

Por qué encaja con este sistema y no es una decisión provisional:

- **Una novela es una unidad aislada.** No hay concurrencia entre tiradas ni escritura desde varios procesos a la vez: el Archivero es el único que escribe canon, y solo al congelar un capítulo. Es el caso de uso donde SQLite es mejor, no donde se le tolera.
- **Un fichero por novela hace la tirada reproducible.** Copiar el fichero es copiar el estado completo, lo que vale tanto para depurar como para el conjunto dorado (CAL-10) y para los evals de VER-10.
- **Sin servidor no hay una pieza más que pueda fallar** en un ciclo que debe terminar sin que nadie intervenga.

El reparto detallado, la frontera entre las dos mitades y su contrato están en `docs/architecture.md` §2.1 y §2.2.

### 3.3 `specs/`

Los cuatro documentos de `docs/` dicen **qué sistema es** y por qué. Una spec dice **qué hace exactamente un paso de construcción**, con qué contrato y cómo se comprueba. No repite la arquitectura: la refina hasta el punto en que se puede escribir código.

| Regla | Valor |
|---|---|
| **Qué justifica una spec** | Una **versión del backend o del frontend**: un tramo del orden de construcción de `architecture.md` §14 que se entrega junto. La versión 1 del backend son los pasos 1 a 6, los que producen una novela coherente sin intervención (§8); la versión 1 del frontend es el paso 11 |
| **Nombre** | `specs/srs-<mitad>-vN.md`, con `<mitad>` igual a `backend` o `frontend`; un solo fichero por versión, en formato SRS. Los IDs de requisito, decisión y tramo son únicos en toda la carpeta: cada spec continúa la numeración donde la anterior terminó |
| **Estructura** | Introducción con alcance; descripción general; requisitos de interfaces (`RI-NN`), funcionales por funcionalidad (`RF-NN`), de datos (`RD-NN`) y no funcionales (`RNF-NN`), cada uno con su fuente en `docs/` y su método `VER-NN`; matriz requisito × método; fuera de alcance; decisiones tomadas; decisiones abiertas; trazabilidad con los IDs de `definitions.md` |
| **Proceso** | **B** (§6.3), el mismo que `architecture.md` y `verification.md`, con el mismo umbral y el mismo interrogatorio |

Dos límites que no se cruzan desde una spec:

- **Una spec no introduce vocabulario ni números.** Todo término viene de `definitions.md` y todo número de `architecture.md`. Si hace falta uno nuevo, se para y se ejecuta el proceso A o B sobre el documento que corresponda, antes de seguir con la spec.
- **Si al escribirla se descubre que la arquitectura está mal, se corrige `architecture.md` en la misma entrega.** La spec nunca contradice a la arquitectura en silencio: así es como los documentos dejan de describir un solo sistema.

Cada requisito tiene exactamente un `VER-NN` principal que lo comprueba, o consta en el registro de riesgo aceptado de `verification.md` §9. Los IDs `RF`, `RD`, `RI` y `RNF` son estables dentro de su SRS y no se reciclan.

---

## 4. Los cuatro documentos

Están pensados para leerse en este orden. Cada uno depende del anterior.

### [`docs/definitions.md`](docs/definitions.md) · Ontología

Glosario con identificadores estables agrupados en diez capas: metamodelo (`MET`), estructura narrativa (`EST`), personajes (`PER`), mundo (`MUN`), subdominio deportivo (`DEP`), poética (`POE`), canon (`CAN`), contexto (`CTX`), calidad (`CAL`) y proceso (`PRO`). Incluye invariantes verificables.

**Consúltalo cuando**: necesites saber qué significa un término o qué ID usar.

### [`docs/domain-knowledge.md`](docs/domain-knowledge.md) · Modelos

16 diagramas Mermaid: mapa de capas, árbol estructural, modelo entidad-relación del núcleo, anatomía de escena, árboles por capa, ciclo setup-payoff, ciclo de vida del capítulo y mapa de modos de fallo.

**Consúltalo cuando**: necesites entender cómo se relacionan las entidades o qué causa un tipo de defecto.

### [`docs/architecture.md`](docs/architecture.md) · Arquitectura

Reparto físico del monorepo, capa de memoria en cinco almacenes, ingeniería de contexto con presupuestos en tokens, catálogo de skills, catálogo de 13 agentes, flujos del sistema y política de arbitraje.

**Consúltalo cuando**: vayas a implementar cualquier componente o necesites saber qué agente hace qué.

### [`docs/verification.md`](docs/verification.md) · Verificación

20 métodos con ID `VER-NN`, repartidos en dos ejes: verificación de **producto**, que el código hace lo que dice, y de **proceso**, que el agente se comporta de forma fiable. Cada uno clasificado en TAIDU, con herramienta, límite y puerta. Incluye el registro de riesgo aceptado.

**Consúltalo cuando**: vayas a escribir código o un test, o necesites saber con qué método se comprueba un artefacto y qué garantía da.

### 4.1 Qué leer según la tarea

No hace falta leerlo todo cada vez. Carga lo que corresponda:

| Tarea | Lee |
|---|---|
| Añadir o cambiar un término | `definitions.md` completo; los diagramas que lo usen |
| Cambiar un diagrama | `domain-knowledge.md` §1 y el diagrama concreto; `definitions.md` para los IDs |
| Tocar agentes, skills o contexto | `architecture.md` §4 a §7 |
| Tocar estructura, stack o despliegue | `architecture.md` §2 y §3; §3.1 de este fichero |
| Tocar verificación, tests o umbrales | `verification.md` completo |
| Escribir o cambiar un SRS de `specs/` | `architecture.md` completo; `verification.md` §7 y §8; §3.3 de este fichero |
| Responder una duda de dominio | `definitions.md`; el resto solo si hace falta |

Si la tarea afecta a más de un documento, léelos todos antes de escribir nada. Editar uno y dejar los otros desalineados es el fallo más caro de este repositorio.

---

## 5. Reglas de trabajo en el repositorio

### 5.1 Identificadores

- Los IDs (`EST-07`, `CTX-13`, `VER-08`) son **estables**. Nunca se reasignan, se renumeran ni se reciclan.
- Al retirar un término, se marca como obsoleto con su sustituto. No se borra.
- Al añadir uno, se usa el siguiente número libre de su familia.
- Las referencias cruzadas entre documentos van siempre por ID, nunca por nombre.

### 5.2 Coherencia entre documentos

Un cambio conceptual toca los cuatro documentos o ninguno. La propagación no es opcional ni se deja para después: se entrega en el mismo cambio.

| Si cambias... | Actualiza también |
|---|---|
| Un término en `definitions.md` | Los diagramas que lo usan y las tablas que lo referencian |
| Un agente o skill en `architecture.md` | La matriz agente × skill y los flujos |
| Un método en `verification.md` | El mapa de métodos, la matriz método × artefacto y el registro de riesgo aceptado |
| Un presupuesto de tokens | La tabla por agente y el total de ocupación |
| El stack, el despliegue o la estructura de carpetas | §3 y §3.1 de este fichero, más `architecture.md` §2.1, §2.2 y el orden de construcción |
| Una sección de `architecture.md` que un SRS refina | Los requisitos de `specs/srs-backend-vN.md` que la citan como fuente |
| Un requisito de un SRS o un tramo del plan | La matriz de cobertura de `backend/PLAN.md` §7. `backend/coherence.py` lo comprueba en la puerta (§6.7) |

### 5.3 Restricciones que no se negocian

Estas seis restricciones acotan **el sistema que se especifica**, no el trabajo de construirlo. Las dos que más se malinterpretan:

- **El agente pregunta para crear y desarrollar; cero intervención humana en la revisión del texto durante la creación de la novela** (§6.1).
- **Los 100.000 tokens son el contexto que puede tener un agente del sistema en cada llamada mientras escribe la novela** (§5.3.2). No son la longitud de la novela, que es mucho mayor, ni un techo para el trabajo sobre este repositorio. Leer los cuatro documentos enteros para hacer un cambio bien no viola nada.

1. **Nada de intervención humana en la revisión del texto.** Si al diseñar aparece una persona que aprueba, revisa o confirma una escena, un capítulo, un veredicto o un delta canónico, es un error de diseño. Sustitúyelo por regla, umbral o agente.
2. **100.000 tokens de entrada es el techo de cada llamada del sistema al redactar**, y lo fija este proyecto, no el proveedor. Un paquete se ensambla hasta 85.000, dejando 15.000 para lo que añada un reintento. La salida no cuenta contra el techo, pero tiene su propia red de seguridad en 50.000. Lo que no quepa se resuelve con jerarquía de resúmenes y recuperación selectiva, nunca con truncamiento.
3. **El canon es la fuente de verdad.** Ninguna propuesta puede hacer que la verdad viva solo en la prosa.
4. **Determinista antes que modelo.** Si algo se puede comprobar con código, no se le pregunta a un modelo.
5. **Evidencia obligatoria.** Cualquier veredicto sin cita localizable se descarta.
6. **Fallo cerrado.** Una comprobación que no puede ejecutarse cuenta como fallida.

### 5.4 Convenciones de escritura

- **Idioma: español** en la prosa. **Inglés** en identificadores técnicos, nombres de skills y claves de datos (`scene.write`, `canon.query`, `check.timeline`).
- Prosa directa, sin relleno. Frases cortas. Se evita el énfasis decorativo y las fórmulas de transición vacías.
- Tablas cuando hay más de dos atributos por elemento; listas solo para enumeraciones simples.
- Cada afirmación de diseño lleva su porqué cuando no es obvio. Una regla sin motivo se salta en la primera implementación.
- Cada documento de `docs/` abre con el bloque de referencias cruzadas a los otros tres. Si creas uno nuevo, incluye el bloque y añádelo al índice de §3 y §4.

### 5.5 Alcance: solo esta rama

La única fuente de información válida es el estado actual de la rama de trabajo (`v2-oneshot`): este fichero y los cuatro documentos de `docs/`.

- **No se consulta el historial de git**, ni ramas anteriores, ni commits previos, ni ficheros borrados.
- **No se reintroduce** nada que existiera en una versión anterior por el hecho de haber existido. Si algo hace falta, se justifica desde cero contra los documentos de hoy.
- Las especificaciones describen **solo el sistema de hoy**. No llevan notas de lo que se quitó, ni comparativas con versiones pasadas, ni arqueología.
- Si un documento cita algo que ya no está en la rama, es una inconsistencia: se señala y se corrige, no se rescata el original.

**Por qué**: el proyecto arrancó de cero en esta rama. Arrastrar decisiones de versiones anteriores reintroduce restricciones que ya no aplican y hace que los documentos dejen de describir un sistema único y coherente.

### 5.6 Cómo se edita

1. **Ediciones quirúrgicas.** Modifica solo lo que la tarea pide. No reescribas un documento entero para cambiar una tabla, ni reformatees secciones que no tocas.
2. **Numeración de secciones estable.** Otros documentos referencian secciones por número. Antes de renumerar, comprueba quién apunta ahí.
3. **Sin frontera nueva sin dueño.** Si tu cambio introduce una decisión, dale regla de precedencia, umbral numérico o agente responsable. Si no puedes, el diseño no está terminado y hay que decirlo, no taparlo.
4. **Sin pasos manuales.** Si al diseñar te sale «revisar», «aprobar» o «confirmar» por parte de una persona, es un error. Sustitúyelo.
5. **Nada de inventar números.** Presupuestos de tokens, umbrales y severidades salen de los documentos. Si hace falta uno nuevo, decláralo como propuesta y explica de dónde sale.

### 5.7 Mermaid

Los diagramas son parte del contenido, no decoración. Reglas para que rendericen:

- Etiquetas de nodo **siempre entre comillas**: `A["Escena · EST-08"]`.
- Nada de paréntesis, corchetes ni comillas dentro de las etiquetas.
- Un identificador no puede ser a la vez nodo y `subgraph`.
- En `erDiagram`, nombres de entidad en mayúsculas sin espacios y etiquetas de relación en una sola palabra con guiones bajos.
- Prefiere `graph TD` o `graph LR` y `stateDiagram-v2`. Evita tipos exóticos con soporte irregular.
- Comprueba mentalmente el diagrama antes de darlo por bueno: un diagrama roto es peor que ninguno, porque oculta la información en vez de mostrarla.

---

## 6. Procesos de cambio

Hay tres clases de cambio en este repositorio y cada una tiene su proceso. El eje que las separa es el radio de impacto: un término mal puesto en `definitions.md` contamina los cuatro documentos y todo el código que venga después; un bug en una función no sale de su fichero.

| Proceso | Qué se toca | Radio de impacto | Detalle |
|---|---|---|---|
| **A** | `definitions.md`, `domain-knowledge.md` | Máximo: la ontología la consume todo lo demás | §6.2 |
| **B** | `architecture.md`, `verification.md`, `specs/` | Alto: fija cómo se construye y cómo se comprueba | §6.3 |
| **C** | `backend/`, `frontend/` | Local, pero puede revelar que la spec está mal | §6.4 |

Los tres procesos se describen en §6.2 a §6.4, que son su **única** fuente: no hay una skill que los repita, y por eso no hace falta regla de desempate.

En `.claude/skills/` viven cinco skills, que hacen otra cosa:

| Skill | Qué hace |
|---|---|
| `grill-me` | Lanza el interrogatorio previo de §6.1. Solo la puedes invocar tú, con `/grill-me` |
| `verification-sheet` | Produce `verification.md` desde un context seed: catálogo de métodos, TAIDU y riesgo aceptado |
| `fastapi` | Cómo se escribe `backend/` |
| `react` | Cómo se escribe `frontend/` |
| `sqlite` | Cómo se guarda el estado |

Las tres de tecnología dicen **cómo escribir**; este documento dice **qué pasos seguir** y **si procede**.

### 6.1 El interrogatorio previo

**Los tres procesos empiezan igual: si el cambio cruza el umbral, el agente te interroga antes de editar nada.** Invoca la skill `grilling`, que abre una entrevista por rondas: cada pregunta numerada con la respuesta que el agente recomienda, y espera a que contestes antes de la siguiente ronda.

Detalle de implementación que importa: se invoca **`grilling`**, no `grill-me`. `grill-me` lleva `disable-model-invocation: true`, así que solo tú puedes lanzarla con `/grill-me`; el agente no puede. En el proceso A se invoca además `domain-modeling`, que es la que trabaja terminología de dominio.

**Bloqueante cuando el cambio cruza el umbral.** El umbral es este, y es el mismo en los tres procesos:

> El cambio **introduce una decisión con dueño, un número nuevo, un ID nuevo o una frontera nueva**.

Si lo cruza, sin tus respuestas no se edita: el agente no puede proceder declarando supuestos. Si no lo cruza — una errata, un enlace roto, un reformateo, renombrar un fichero — se hace y se dice, sin entrevista.

Un solo criterio gobierna las dos puertas: **si un cambio merece quedar registrado como decisión, merece que te pregunten antes de tomarla.** Dos criterios distintos para lo mismo se desincronizan a la tercera vez que alguien los aplica.

El interrogatorio no tiene tope de preguntas, por diseño de la skill: termina cuando no queda ninguna decisión sin resolver y tú lo confirmas. Si se alarga más de lo que el cambio merece, la salida es decirlo en lenguaje natural, no un contador.

Esto no contradice §5.3.1, porque son dos momentos distintos de la vida del sistema:

| Momento | Qué se decide | Quién decide |
|---|---|---|
| **Crear y desarrollar el sistema** | Qué término entra en la ontología, qué agente hace qué, qué método lo verifica, qué código se escribe | **Tú.** El agente pregunta antes de decidir. §6.1 |
| **Generar la novela** | Si una escena pasa, si un veredicto vale, si un delta entra en canon | **El sistema, solo.** Cero intervención humana en la revisión del texto. §5.3.1 |

Dicho corto: **el agente pregunta para crear y desarrollar; nadie revisa el texto mientras la novela se escribe.**

Cuando el sistema está generando no hay a quién preguntar, y por eso toda decisión necesita regla de precedencia, umbral o agente responsable. Mientras se construye sí hay a quién preguntar: tú eres el autor de la spec, y consultarte es lo contrario de un fallo de diseño.

### 6.2 Proceso A · Documentación fundamental

Para `definitions.md` y `domain-knowledge.md`. Es el proceso más caro, porque es el único cuyo error no se nota hasta tres documentos más tarde.

1. **Interrogar.** `grilling` más `domain-modeling`. El agente debe sacarte, como mínimo: ¿es un término nuevo o el renombre de uno existente? ¿qué ID de qué familia le toca? ¿qué invariante verificable añade? ¿qué se rompe si no existe? ¿en qué se distingue del término vecino que ya está en el glosario? Bloqueante si cruza el umbral de §6.1.
2. **Inventariar el impacto.** Antes de escribir, la lista completa de dónde se referencia ese ID: diagramas, tablas, métodos de `verification.md`, secciones de `architecture.md`.
3. **Editar y propagar en la misma entrega.** Un cambio de ontología toca los cuatro documentos o ninguno (§5.2). No se parte en dos entregas.
4. **Verificar.** Los diagramas Mermaid afectados renderizan (§5.7) y no queda ninguna referencia a un ID inexistente.

**Nunca** se recicla ni se renumera un ID (§5.1). Retirar un término es marcarlo obsoleto con su sustituto, jamás borrarlo.

### 6.3 Proceso B · Specs

Para `architecture.md`, `verification.md` y las specs de `specs/` (§3.3).

1. **Leer antes de preguntar.** Las secciones que indica §4.1 para esa tarea. El agente no te interroga sobre algo que el documento ya responde.
2. **Interrogar.** `grilling`. Preguntas obligadas: ¿qué decisión nueva introduce este cambio y quién es su dueño, regla de precedencia, umbral o agente? ¿de dónde sale cada número nuevo? ¿qué método de `verification.md` comprueba que funciona? ¿cabe en el presupuesto de tokens de su agente? Bloqueante si cruza el umbral de §6.1.
3. **Editar quirúrgicamente** (§5.6) y propagar según la tabla de §5.2.
4. **Contrastar** con la Definición de terminado, §10.

Si durante el interrogatorio aparece un término que no está en `definitions.md`, se para y se ejecuta el proceso A. Colar vocabulario nuevo dentro de un cambio de spec es como se degrada una ontología.

### 6.4 Proceso C · Código

Para `backend/` y `frontend/`. Aplica a `backend/` y a `frontend/` (§2).

1. **Comprobar que hay spec.** Ninguna línea de código sin una sección de `architecture.md` que la autorice. Si no la hay, se para y se ejecuta el proceso B.
2. **Interrogar.** `grilling`. Preguntas obligadas: ¿qué sección de la spec implementa esto? ¿qué método `VER-NN` lo verifica y de qué clase TAIDU es? ¿qué contrato cruza aquí, HTTP o agente a agente? ¿va en `backend/` o en `frontend/`, y respeta la frontera de `architecture.md` §2.2? Bloqueante si cruza el umbral de §6.1.
3. **Elegir el método de verificación antes de escribir**, con el procedimiento de `verification.md` §8. Si no hay método, va al registro de riesgo aceptado antes de escribir el código, nunca después.
4. **Escribir la prueba o la propiedad primero** cuando el método sea VER-05 o VER-06.
5. **Pasar la puerta de CI**: VER-01, VER-02, VER-05, VER-06 y VER-08 en verde (VER-15).
6. **Sincronizar la documentación**, con el procedimiento de §6.5. Es un paso del proceso, no una tarea aparte.

Durante los seis pasos rige §6.6: lo que cruza el umbral se para y se avisa, lo que no, se resuelve.

Si al implementar descubres que la spec está mal, **paras y ejecutas el proceso B**. No se corrige en el código dejando la spec mintiendo: así es como los documentos dejan de describir el sistema.

### 6.5 Sincronización inversa: el código actualiza los documentos

Todo cambio de código lanza una **ejecución de sincronización** que revisa y actualiza los documentos de contexto. Se despacha como subagente al cerrar el paso 5 del proceso C, y el cambio no se da por terminado hasta que vuelve.

| Qué revisa | Contra qué |
|---|---|
| ¿La estructura de carpetas real coincide con lo declarado? | §3 y `architecture.md` §2.1 |
| ¿Lo implementado hace lo que dice la sección que lo autorizó? | `architecture.md` |
| ¿Los métodos `VER-NN` que cubren ese artefacto siguen siendo los de la matriz? | `verification.md` §7 |
| ¿Apareció vocabulario nuevo en el código que no está en el glosario? | `definitions.md` |
| ¿Cambió el estado de alguna fila de §2? | Este fichero |
| ¿Cambió algún paso del orden de construcción? | `architecture.md` §14 |

La ejecución **informa y propone; no edita la ontología por su cuenta**. Si detecta que hace falta tocar `definitions.md`, eso dispara el proceso A con su interrogatorio, porque el proceso A es bloqueante y una sincronización automática no puede saltarse esa puerta.

**Por qué existe este paso**: la propagación de §5.2 va de la spec al código. Sin sincronización inversa la deriva ocurre en la otra dirección y nadie la ve: el código avanza, los documentos se quedan quietos, y a los dos meses la spec describe un sistema que ya no existe.

### 6.6 Escalado durante la implementación

§6.1 dice cuándo preguntar **antes** de empezar. Esta sección dice cuándo parar **a mitad**, que es un momento distinto: el interrogatorio ya pasó, el trabajo está en marcha, y aparece algo que no estaba previsto.

**La regla, en una línea: si el problema cruza el umbral de §6.1, se para y se avisa. Si no lo cruza, se resuelve con el mayor esfuerzo posible y se cuenta después.**

El umbral es el mismo a propósito, y no uno nuevo. §6.1 ya lo dice de la otra puerta: dos criterios distintos para lo mismo se desincronizan a la tercera vez que alguien los aplica. Si algo merece quedar registrado como decisión, merece que te avisen antes de tomarla —da igual que aparezca al planificar o al compilar.

| Se para y se avisa | Se resuelve y se cuenta |
|---|---|
| Hace falta un número, un ID o un término que no existe | Un test falla, el código no compila, una librería se comporta distinto de lo esperado |
| Aparece una frontera nueva sin dueño: dos componentes podrían hacer lo mismo y nada dice cuál | La spec no cubre un detalle, pero solo hay una lectura coherente con los cuatro documentos |
| La spec está mal o se contradice: eso dispara el proceso B (§6.3), no un parche en el código | Nombres, ergonomía, orden de los ficheros, rendimiento |
| Dos documentos se contradicen y arreglarlo exige elegir cuál gana | Una dependencia no instala y hay alternativa dentro del stack fijado |
| La decisión es cara de deshacer: destruye datos, o fuerza a reindexar la novela entera | Cualquier cosa recuperable editando código |
| Cumplirla obligaría a saltarse una de las seis restricciones de §5.3 | Refactorizar algo que ya funciona para que quepa lo siguiente |

**Parar no es parar del todo.** Se sigue con todo lo que no dependa de la respuesta, y la pregunta se hace en el momento en que de verdad bloquea, no al descubrirla. Quedarse quieto esperando una respuesta que afecta a un tramo de ocho es desperdiciar los otros siete.

**Cómo se avisa**, porque un aviso sin esto traslada el trabajo en vez de hacerlo:

1. **Qué está bloqueado** y qué no, en una línea.
2. **Qué se hizo antes de parar**, para que no haya que reconstruirlo.
3. **Las salidas posibles**, con la recomendada primera y su porqué.
4. **Qué se sigue construyendo** mientras tanto.

**Al terminar se dice lo que se resolvió por cuenta propia.** Un problema del lado derecho de la tabla se arregla sin preguntar, pero no en silencio: si se eligió entre dos lecturas posibles, eso consta en el informe final aunque no mereciera una interrupción. Un cambio incompleto anunciado es recuperable; uno silencioso, no (§9).

### 6.7 El ciclo docs → spec → plan, y quién lo comprueba

Los tres niveles de documento describen un solo sistema desde tres alturas: `docs/` dice qué es, `specs/` qué hace exactamente cada paso, `backend/PLAN.md` en qué orden y con qué ficheros se construye. Se desalinean en silencio si nadie los contrasta, así que el contraste es **código en la puerta**, no una revisión.

`backend/coherence.py` corre dentro de `gate.py` en cada cambio y falla la puerta si encuentra:

| Qué comprueba | Entre qué |
|---|---|
| Todo `RF`, `RD`, `RI`, `RNF` y `D` citado existe, y ninguno se define dos veces | `specs/*.md` ↔ `backend/PLAN.md` |
| Todo requisito cita un `VER-NN` que existe | `specs/*.md` ↔ `docs/verification.md` |
| Toda sección `§N.N` citada de `architecture.md`, `verification.md` o este fichero existe | `specs/*.md`, `backend/PLAN.md` ↔ `docs/`, `AGENTS.md` |
| Todo ID de dominio citado existe en el glosario | `specs/*.md` ↔ `docs/definitions.md` |
| Todo requisito aparece en la matriz requisito × método de su SRS | `specs/*.md` §7.1 |
| Todo requisito está asignado a un tramo, y en `frontend/PLAN.md` al mismo que le da su SRS | `specs/*.md` §11 o `backend/PLAN.md`; `frontend/PLAN.md` y su §7.2 |
| Toda sección de `architecture.md` tiene fila en la matriz de cobertura de cada plan | `docs/architecture.md` ↔ `backend/PLAN.md` §7 y `frontend/PLAN.md` §7.1 |
| Todo paquete de `backend/` y toda carpeta de `frontend/` están declarados en el reparto físico | `backend/`, `frontend/` ↔ `architecture.md` §2.3 |
| Todo `kind` `check.*` que asigna el código y todo módulo validador —un `verification/checks/<x>.py` cuyo docstring abre con `` `check.<x>` ``— tienen fila en la tabla de validadores; todo `check.*` de una fila existe en el código y toda fila dice dónde corre; y la tabla por brief tiene una columna fija por cada validador de la puerta de escena o de la escena de encuentro, ni una más ni una menos | `architecture.md` §9.1 ↔ `backend/` y `backend/evals/brief_table.py` (`specs/srs-backend-v4.md` RF-268) |
| Ningún número de tramo se define dos veces | `specs/*.md` §11 ↔ `backend/PLAN.md` |

**Qué hacer cuando falla.** Lo que la puerta señala es una desalineación, y la dirección de la corrección la fija §3.3: la spec nunca contradice a la arquitectura en silencio, y el plan nunca contradice a la spec. Se corrige el documento de menor altura, salvo que al hacerlo se descubra que el de mayor altura está mal: entonces se ejecuta el proceso A o B que corresponda y se propagan los tres en la misma entrega.

**Qué no comprueba.** Que lo escrito sea verdad. Comprueba que los tres documentos hablan de las mismas cosas con los mismos nombres, que es la condición para que alguien pueda comprobar lo demás.

---

## 7. Los 13 agentes especificados

El catálogo completo —misión, skills principales, criterio de salida y contrato de entrada y salida— está en [`docs/architecture.md`](docs/architecture.md) §6 y §6.2. **No se repite aquí**: dos copias de la misma tabla garantizan que una se quede atrás.

El estado de implementación de cada uno está en §2 y, tramo a tramo, en `backend/PLAN.md`.

---

## 8. Orden de implementación previsto

Los once pasos, con su justificación y con qué funcionalidad de `architecture.md` §2.3 llena cada uno, están en [`docs/architecture.md`](docs/architecture.md) §14.

Lo único que conviene retener aquí: **los pasos 1 a 6 producen una novela coherente sin intervención**. Del 7 al 10 se gana escala y calidad, no viabilidad, y el 11 —el frontend— está fuera del camino crítico por diseño (§3.1).

---

## 9. Cómo trabajar

- **Si el cambio cruza el umbral de §6.1, primero el interrogatorio.** Es la única puerta que no se salta. Una vez respondido, ejecuta el cambio entero sin volver a pedir confirmación paso a paso. Si no lo cruza, hazlo y dilo.
- Toda pregunta va con la respuesta que recomiendas y su porqué. Devolver la pregunta en crudo traslada el trabajo en vez de hacerlo.
- Señala las inconsistencias que encuentres de paso, aunque estén fuera del encargo. No las arregles sin decirlo.
- Di lo que no hiciste y por qué. Un cambio incompleto anunciado es recuperable; uno silencioso, no.

---

## 10. Definición de terminado

Un cambio está listo cuando:

- [ ] Usa el vocabulario y los IDs de `definitions.md`
- [ ] Respeta las seis restricciones de §5.3
- [ ] Ha seguido el proceso de §6 que le corresponde y, si cruza el umbral, su interrogatorio previo está respondido
- [ ] Si toca un agente o un paquete de contexto del sistema, cabe en 100.000 tokens de entrada contando su cupo de herramientas
- [ ] Tiene un método de `verification.md` que compruebe que funciona, o consta en su registro de riesgo aceptado
- [ ] Los cuatro documentos de `docs/` siguen coherentes entre sí y con este fichero
- [ ] Los diagramas Mermaid afectados renderizan
- [ ] No ha introducido ningún paso de aprobación manual **dentro del sistema especificado** (§5.3, §6.1)
- [ ] Se apoya solo en el estado actual de esta rama, sin recuperar nada de versiones anteriores (§5.5)

---

## 11. Lo que no hay que hacer

- Crear agentes, skills o código de implementación sin petición explícita.
- Reescribir un documento entero por un cambio local.
- Introducir revisión humana del texto en el ciclo de generación, en cualquier forma. En el trabajo de crear y desarrollar ocurre lo contrario: preguntar es obligatorio (§6.1).
- Editar documentación, spec o código saltándose el interrogatorio de §6.1 cuando el cambio cruza su umbral.
- Diseñar un paquete de contexto que llene la ventana porque quepa: en cada llamada del sistema, 100.000 tokens es un techo, no un objetivo. Para trabajar sobre el repositorio no hay techo: lee lo que haga falta.
- Dar por buena una comprobación sin evidencia localizable.
