# AGENTS.md

Guía de este repositorio para cualquier agente que trabaje en él, humano o automático. Léela entera antes de tocar nada. Es el único documento de trabajo: `CLAUDE.md` solo apunta aquí.

---

## 1. Qué es este proyecto

Un sistema **autónomo** de generación de novelas largas. Caso de referencia: épica deportiva. El sistema planifica, escribe, verifica, corrige, arbitra y cierra una novela completa **sin intervención externa en ningún punto del ciclo**.

Dos restricciones fijan todo el diseño:

- **Autonomía de extremo a extremo.** No hay aprobación manual, ni revisión de una persona, ni escalado. Cada decisión necesita una regla de precedencia, un umbral numérico o un agente responsable.
- **Ventana de contexto de 100.000 tokens** por llamada, entrada más salida, para cualquier agente.

La idea central del dominio: **una novela larga no es un texto largo, es un estado del mundo que evoluciona**. El texto es la proyección visible. El sistema gestiona el estado; la prosa es consecuencia.

---

## 2. Estado actual

| Fase | Estado |
|---|---|
| Ontología del dominio | ✅ Completa |
| Modelos y diagramas | ✅ Completos |
| Arquitectura, agentes y skills | ✅ Especificados |
| Estrategia de verificación | ✅ Completa |
| Implementación de agentes | ⛔ **No iniciada** |
| Implementación de skills | ⛔ No iniciada |
| Capa de memoria | ⛔ No iniciada |

**El repositorio está en fase de especificación.** No hay código. No crees agentes, skills ni esqueletos de implementación salvo que se pida de forma explícita.

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
├── backend/                  ← API y motor del sistema autónomo
└── frontend/                 ← visualización del estado narrativo
```

`backend/` y `frontend/` existen pero están **vacías**: solo contienen un `.gitkeep`, porque git no versiona directorios sin ficheros. Reservan el sitio y fijan el stack; el contenido llega cuando arranque la implementación (§2).

### 3.1 Stack por carpeta

| Carpeta | Stack | Responsabilidad |
|---|---|---|
| `backend/` | Python + FastAPI | Orquestador, agentes, skills, capa de memoria y canon. Todo lo especificado en `docs/architecture.md` |
| `frontend/` | React + Three.js | Interfaz de lectura y visualización del estado del mundo, del grafo canónico y de la curva de tensión |

Dos consecuencias que conviene tener claras desde ya:

- **El frontend no participa en el ciclo de generación.** Observa y muestra; no aprueba, no corrige, no desbloquea. Cualquier interacción que condicione al ciclo viola la restricción de autonomía (§5.3.1).
- **El backend es el único dueño del canon.** El frontend lee proyecciones del estado; no escribe en él (§5.3.3).

El reparto detallado, la frontera entre las dos mitades y su contrato están en `docs/architecture.md` §2.1 y §2.2.

---

## 4. Los tres documentos

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

18 métodos con ID `VER-NN`, repartidos en dos ejes: verificación de **producto**, que el código hace lo que dice, y de **proceso**, que el agente se comporta de forma fiable. Cada uno clasificado en TAIDU, con herramienta, límite y puerta. Incluye el registro de riesgo aceptado.

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

Un cambio conceptual toca los tres documentos o ninguno. La propagación no es opcional ni se deja para después: se entrega en el mismo cambio.

| Si cambias... | Actualiza también |
|---|---|
| Un término en `definitions.md` | Los diagramas que lo usan y las tablas que lo referencian |
| Un agente o skill en `architecture.md` | La matriz agente × skill y los flujos |
| Un método en `verification.md` | El mapa de métodos, la matriz método × artefacto y el registro de riesgo aceptado |
| Un presupuesto de tokens | La tabla por agente y el total de ocupación |
| El stack, el despliegue o la estructura de carpetas | §3 y §3.1 de este fichero, más `architecture.md` §2.1, §2.2 y el orden de construcción |

### 5.3 Restricciones que no se negocian

Estas seis restricciones acotan **el sistema que se especifica**, no el trabajo sobre este repositorio. La distinción importa y se desarrolla en §6: en el ciclo de generación de la novela no interviene ninguna persona; en la edición de la spec el autor eres tú, y el agente te interroga antes de tocar nada.

1. **Nada de intervención humana.** Si al diseñar aparece un paso de aprobación, revisión o confirmación manual **dentro del sistema**, es un error de diseño. Sustitúyelo por regla, umbral o agente.
2. **100.000 tokens es el techo.** Entrada ≤70.000, entrada más salida ≤85.000. Lo que no quepa se resuelve con jerarquía de resúmenes y recuperación selectiva, nunca con truncamiento.
3. **El canon es la fuente de verdad.** Ninguna propuesta puede hacer que la verdad viva solo en la prosa.
4. **Determinista antes que modelo.** Si algo se puede comprobar con código, no se le pregunta a un modelo.
5. **Evidencia obligatoria.** Cualquier veredicto sin cita localizable se descarta.
6. **Fallo cerrado.** Una comprobación que no puede ejecutarse cuenta como fallida.

### 5.4 Convenciones de escritura

- **Idioma: español** en la prosa. **Inglés** en identificadores técnicos, nombres de skills y claves de datos (`scene.write`, `canon.query`, `check.timeline`).
- Prosa directa, sin relleno. Frases cortas. Se evita el énfasis decorativo y las fórmulas de transición vacías.
- Tablas cuando hay más de dos atributos por elemento; listas solo para enumeraciones simples.
- Cada afirmación de diseño lleva su porqué cuando no es obvio. Una regla sin motivo se salta en la primera implementación.
- Cada documento de `docs/` abre con el bloque de referencias cruzadas a los otros dos. Si creas uno nuevo, incluye el bloque y añádelo al índice de §3 y §4.

### 5.5 Alcance: solo esta rama

La única fuente de información válida es el estado actual de la rama de trabajo (`v2`): este fichero y los tres documentos de `docs/`.

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

Hay tres clases de cambio en este repositorio y cada una tiene su proceso. El eje que las separa es el radio de impacto: un término mal puesto en `definitions.md` contamina los tres documentos y todo el código que venga después; un bug en una función no sale de su fichero.

| Proceso | Qué se toca | Radio de impacto |
|---|---|---|
| **A** | `definitions.md`, `domain-knowledge.md` | Máximo: la ontología la consume todo lo demás |
| **B** | `architecture.md`, `verification.md` | Alto: fija cómo se construye y cómo se comprueba |
| **C** | `backend/`, `frontend/` | Local, pero puede revelar que la spec está mal |

### 6.1 El interrogatorio previo es obligatorio y bloqueante

**Los tres procesos empiezan igual: el agente te interroga antes de editar nada.** Invoca la skill `grilling`, que abre una entrevista por rondas: cada pregunta numerada con la respuesta que el agente recomienda, y espera a que contestes antes de la siguiente ronda.

Detalle de implementación que importa: se invoca **`grilling`**, no `grill-me`. `grill-me` y `grill-with-docs` llevan `disable-model-invocation: true`, así que solo tú puedes lanzarlas con `/grill-me`; el agente no puede. En el proceso A se invoca además `domain-modeling`, que es la que trabaja terminología de dominio.

**Bloqueante sin excepciones.** Sin tus respuestas no se edita. Ni en documentación fundamental, ni en specs, ni en código, ni para cambios que parezcan triviales. El agente no puede proceder declarando supuestos: si no hay respuesta, no hay cambio.

Esto no contradice §5.3.1. La restricción de cero intervención humana rige **dentro del sistema que se especifica**, donde no hay a quién preguntar. Aquí estás tú, eres el autor de la spec, y preguntarte es lo contrario de un fallo de diseño.

| Plano | Quién decide | Regla |
|---|---|---|
| El ciclo de generación de la novela | El sistema, solo | Cero intervención humana. §5.3.1 |
| El trabajo sobre este repositorio | Tú | Interrogatorio previo obligatorio. §6.1 |

### 6.2 Proceso A · Documentación fundamental

Para `definitions.md` y `domain-knowledge.md`. Es el proceso más caro, porque es el único cuyo error no se nota hasta tres documentos más tarde.

1. **Interrogar.** `grilling` más `domain-modeling`. El agente debe sacarte, como mínimo: ¿es un término nuevo o el renombre de uno existente? ¿qué ID de qué familia le toca? ¿qué invariante verificable añade? ¿qué se rompe si no existe? ¿en qué se distingue del término vecino que ya está en el glosario? Bloqueante.
2. **Inventariar el impacto.** Antes de escribir, la lista completa de dónde se referencia ese ID: diagramas, tablas, métodos de `verification.md`, secciones de `architecture.md`.
3. **Editar y propagar en la misma entrega.** Un cambio de ontología toca los tres documentos o ninguno (§5.2). No se parte en dos entregas.
4. **Verificar.** Los diagramas Mermaid afectados renderizan (§5.7) y no queda ninguna referencia a un ID inexistente.
5. **Registrar.** Entrada de changelog con el porqué del cambio, no solo el qué.

**Nunca** se recicla ni se renumera un ID (§5.1). Retirar un término es marcarlo obsoleto con su sustituto, jamás borrarlo.

### 6.3 Proceso B · Specs

Para `architecture.md` y `verification.md`.

1. **Leer antes de preguntar.** Las secciones que indica §4.1 para esa tarea. El agente no te interroga sobre algo que el documento ya responde.
2. **Interrogar.** `grilling`. Preguntas obligadas: ¿qué decisión nueva introduce este cambio y quién es su dueño, regla de precedencia, umbral o agente? ¿de dónde sale cada número nuevo? ¿qué método de `verification.md` comprueba que funciona? ¿cabe en el presupuesto de tokens de su agente? Bloqueante.
3. **Editar quirúrgicamente** (§5.6) y propagar según la tabla de §5.2.
4. **Contrastar** con la Definición de terminado, §10.
5. **Registrar** en el changelog con su porqué.

Si durante el interrogatorio aparece un término que no está en `definitions.md`, se para y se ejecuta el proceso A. Colar vocabulario nuevo dentro de un cambio de spec es como se degrada una ontología.

### 6.4 Proceso C · Código

Para `backend/` y `frontend/`. Hoy no aplica: el repositorio está en fase de especificación (§2) y las dos carpetas están vacías.

1. **Comprobar que hay spec.** Ninguna línea de código sin una sección de `architecture.md` que la autorice. Si no la hay, se para y se ejecuta el proceso B.
2. **Interrogar.** `grilling`. Preguntas obligadas: ¿qué sección de la spec implementa esto? ¿qué método `VER-NN` lo verifica y de qué clase TAIDU es? ¿qué contrato cruza aquí, HTTP o agente a agente? ¿va en `backend/` o en `frontend/`, y respeta la frontera de `architecture.md` §2.2? Bloqueante.
3. **Elegir el método de verificación antes de escribir**, con el procedimiento de `verification.md` §8. Si no hay método, va al registro de riesgo aceptado antes de escribir el código, nunca después.
4. **Escribir la prueba o la propiedad primero** cuando el método sea VER-05 o VER-06.
5. **Pasar la puerta de CI**: VER-01, VER-02, VER-05, VER-06 y VER-08 en verde (VER-15).
6. **Sincronizar la documentación.** Ver §6.5. Es un paso del proceso, no una tarea aparte.

Si al implementar descubres que la spec está mal, **paras y ejecutas el proceso B**. No se corrige en el código dejando la spec mintiendo: así es como los documentos dejan de describir el sistema.

### 6.5 Sincronización inversa: el código actualiza los documentos

Todo cambio de código lanza una **ejecución de sincronización** que revisa y actualiza los documentos de contexto. Se despacha como subagente al cerrar el paso 5 del proceso C, y el cambio no se da por terminado hasta que vuelve.

| Qué revisa | Contra qué |
|---|---|
| ¿La estructura de carpetas real coincide con lo declarado? | §3 y `architecture.md` §2.1 |
| ¿Lo implementado hace lo que dice la sección que lo autorizó? | `architecture.md` |
| ¿Los métodos `VER-NN` que cubren ese artefacto siguen siendo los de la matriz? | `verification.md` §7 |
| ¿Apareció vocabulario nuevo en el código que no está en el glosario? | `definitions.md` |
| ¿Cambió el estado de alguna fila de §2 o algún paso de §8? | Este fichero |

La ejecución **informa y propone; no edita la ontología por su cuenta**. Si detecta que hace falta tocar `definitions.md`, eso dispara el proceso A con su interrogatorio, porque el proceso A es bloqueante y una sincronización automática no puede saltarse esa puerta.

**Por qué existe este paso**: la propagación de §5.2 va de la spec al código. Sin sincronización inversa la deriva ocurre en la otra dirección y nadie la ve: el código avanza, los documentos se quedan quietos, y a los dos meses la spec describe un sistema que ya no existe.

---

## 7. Los 13 agentes especificados

Referencia rápida. El detalle está en `docs/architecture.md` §6. **Ninguno está implementado.**

| # | Agente | Misión |
|---|---|---|
| 0 | Orquestador | Dirige el flujo y cuenta reintentos. Código, no modelo |
| 1 | Arquitecto narrativo | Arcos, doble arco, curva de tensión, escaleta |
| 2 | Planificador de capítulo | Especificaciones de escena |
| 3 | Documentalista | Ensambla el paquete de contexto. Código |
| 4 | Escritor de escena | Produce la prosa |
| 5 | Especialista deportivo | Resuelve y narra encuentros |
| 6 | Continuista | Verificación de continuidad |
| 7 | Jurado (×3) | Evalúa dimensiones subjetivas |
| 8 | Reparador | Corrección dirigida |
| 9 | Estilista | Pase de voz, poda y proscripción |
| 10 | Archivero | Extrae el delta canónico y resume |
| 11 | Árbitro | Resuelve conflictos por precedencia |
| 12 | Supervisor | Vigila deuda, tensión y deriva; replanifica |

Tres son los que suelen faltar en implementaciones ingenuas: **Archivero** (sin él el canon se queda atrás respecto al texto), **Árbitro** (sin él un conflicto detiene el sistema, porque no hay a quién preguntar) y **Supervisor** (sin él la novela pierde forma en el segundo acto sin que nada lo señale).

---

## 8. Orden de implementación previsto

1. Canon estructurado + registro de eventos
2. Especificación de escena y escaleta
3. Documentalista con presupuesto fijo
4. Escritor de escena + verificadores deterministas
5. Archivero y ciclo de congelación
6. Árbitro y política de precedencia ← **desde aquí el sistema es autónomo**
7. Resúmenes jerárquicos
8. Recuperación híbrida
9. Jurado, conjunto dorado y Estilista
10. Supervisor, replanificación y métricas
11. Frontend de lectura y visualización ← fuera del camino crítico

Los pasos 1 a 6 producen una novela coherente sin intervención. Del 7 al 10 se gana escala y calidad, no viabilidad. El 11 no afecta a ninguna de las dos cosas: el sistema termina una novela con el frontend apagado (`architecture.md` §2.1).

---

## 9. Cómo trabajar

- **Primero el interrogatorio de §6.1, siempre.** Es la única puerta que no se salta. Una vez respondido, ejecuta el cambio entero sin volver a pedir confirmación paso a paso.
- Toda pregunta va con la respuesta que recomiendas y su porqué. Devolver la pregunta en crudo traslada el trabajo en vez de hacerlo.
- Señala las inconsistencias que encuentres de paso, aunque estén fuera del encargo. No las arregles sin decirlo.
- Di lo que no hiciste y por qué. Un cambio incompleto anunciado es recuperable; uno silencioso, no.

---

## 10. Definición de terminado

Un cambio está listo cuando:

- [ ] Usa el vocabulario y los IDs de `definitions.md`
- [ ] Respeta las seis restricciones de §5.3
- [ ] Ha seguido el proceso de §6 que le corresponde, con su interrogatorio previo respondido
- [ ] Cabe en 100.000 tokens con el presupuesto de su agente
- [ ] Tiene un método de `verification.md` que compruebe que funciona, o consta en su registro de riesgo aceptado
- [ ] Los tres documentos de `docs/` siguen coherentes entre sí y con este fichero
- [ ] Los diagramas Mermaid afectados renderizan
- [ ] No ha introducido ningún paso de aprobación manual **dentro del sistema especificado** (§5.3, §6.1)
- [ ] Se apoya solo en el estado actual de esta rama, sin recuperar nada de versiones anteriores (§5.5)

---

## 11. Lo que no hay que hacer

- Crear agentes, skills o código de implementación sin petición explícita.
- Reescribir un documento entero por un cambio local.
- Introducir revisión humana **dentro del ciclo del sistema**, en cualquier forma. En el trabajo sobre el repositorio ocurre lo contrario: §6.1 es obligatorio.
- Editar documentación, spec o código sin haber pasado el interrogatorio de §6.1.
- Llenar la ventana de contexto porque quepa: 100.000 tokens es un techo, no un objetivo.
- Dar por buena una comprobación sin evidencia localizable.
