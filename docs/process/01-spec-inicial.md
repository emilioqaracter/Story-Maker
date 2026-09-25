# 01 · Spec inicial

> Documentación de proceso · ver [`README.md`](README.md) para el índice de esta carpeta y [`../../AGENTS.md`](../../AGENTS.md) para el del repositorio.
> Relacionados: [definitions](../definitions.md) · [domain-knowledge](../domain-knowledge.md) · [architecture](../architecture.md) · [verification](../verification.md)
> Hermanos: [02-trade-offs](02-trade-offs.md) · [03-explainers](03-explainers.md) · [04-diagramas](04-diagramas.md) · [05-iteraciones](05-iteraciones.md) · [06-red-team](06-red-team.md)

Qué se decidió construir y por qué, antes de escribir código. No repite las especificaciones: resume su razonamiento y apunta por ID a donde vive cada decisión.

El lema de esta carpeta es «no se corrige el resultado, se corrige el razonamiento que llevó a él». Este documento es el punto de partida de ese razonamiento: si una decisión de hoy parece rara, aquí está la restricción de la que sale.

---

## 1. El problema

Una novela larga, personalizada para un destinatario, con la épica deportiva como caso de referencia. El sistema la planifica, la escribe, la verifica, la corrige, arbitra sus conflictos y la cierra **sin intervención externa en ningún punto del ciclo** (`AGENTS.md` §1).

Tres rasgos del encargo lo hacen difícil:

| Rasgo | Por qué complica | Dónde se trata |
|---|---|---|
| Larga | Una obra (EST-03) mide entre 80.000 y 200.000 palabras. No cabe entera en ninguna llamada, así que ningún agente la ve completa | `architecture.md` §4 |
| Personalizada | El brief (PRO-01) trae un destinatario, sus rasgos y sus recuerdos, que tienen que aparecer en la prosa y comprobarse | `srs-backend-v3.md` §4.1; `srs-backend-v4.md` D-95 |
| Deportiva | Los encuentros tienen reglas, marcadores y cronología verificables. Un error de signo en un partido es un defecto, no una licencia literaria | `definitions.md` §5; `architecture.md` §6 |

---

## 2. Las dos restricciones fundacionales

Todo el diseño sale de dos restricciones. Se fijaron antes de cualquier arquitectura, y cada decisión posterior se contrasta contra ellas.

### 2.1 Autonomía de extremo a extremo (PRO-11)

Nadie aprueba una escena, un capítulo, un veredicto ni un delta canónico. La única entrada humana es el encargo: el brief antes del ciclo y sus enmiendas después de una congelación (`architecture.md` §2.2; `verification.md` §5.5).

**Por qué.** Un sistema que se para a esperar a una persona no es autónomo: es un asistente con colas. La consecuencia de diseño es dura y se aplica en todas partes: **toda bifurcación necesita una regla de precedencia, un umbral numérico o un agente responsable** (`architecture.md` §1, principio 8). Donde falta, hay un agujero de diseño, no una espera.

De esta restricción salen piezas enteras:

- La política de arbitraje PRO-10 y el Árbitro, que resuelven contradicciones sin preguntar.
- La cuarentena CAL-13 con replanificación PRO-12, que sustituyen a «rechazar y parar» (`architecture.md` §1, principio 9).
- El conjunto dorado CAL-10 y la dispersión del jurado CAL-11, que sustituyen a la calibración manual.
- La exclusión de VER-13, la revisión humana en el bucle, del catálogo de verificación (`verification.md` §5.5).

La tabla completa de qué ocupa el lugar de cada decisión humana está en `architecture.md` §8.

### 2.2 Techo de 100.000 tokens de entrada por llamada (CTX-01)

Cada llamada de un agente del sistema, mientras escribe la novela, recibe como máximo 100.000 tokens de entrada. El techo tiene un segundo plano, el de concurrencia (CTX-20): la suma de lo que está en vuelo en el mismo instante tampoco pasa de 100.000.

**Por qué.** No es un límite del proveedor: los modelos que se usan ofrecen entre 200.000 y 1.000.000 (`architecture.md` §4.1). Es una decisión de calidad y de coste. La distracción (CTX-14) y la dilución de atención aparecen mucho antes de agotar la ventana, y en prosa el coste se paga en cada escena de cada capítulo.

`architecture.md` §4.1 deja escrito por qué se declara propio: una restricción etiquetada como física se salta en cuanto alguien descubre que el proveedor da diez veces más. Esta se sostiene por su motivo.

Tres matices que se fijaron desde el principio:

| Matiz | Regla | Fuente |
|---|---|---|
| Solo cuenta la entrada | La salida no ocupa la ventana de quien la produce; tiene su propia red de seguridad en 50.000 | `architecture.md` §4.1 |
| El paquete se ensambla por debajo | Hasta 85.000, para dejar 15.000 a lo que añada un reintento sin rehacer el paquete | `AGENTS.md` §5.3 |
| Lo que no cabe no se trunca | Se resuelve con jerarquía de resúmenes, recuperación selectiva y aislamiento; al desbordar, compactación por prioridad inversa (CTX-19) | `definitions.md` §0; CTX-I1 |

El techo no aplica al trabajo de construir el sistema: leer los cuatro documentos enteros para hacer un cambio no viola nada (`AGENTS.md` §5.3).

### 2.3 Por qué las dos juntas obligan al diseño que hay

Por separado, cada restricción tiene salidas fáciles. Juntas, casi todas se cierran:

- Sin autonomía, una persona podría releer el manuscrito y detectar contradicciones. Con autonomía, lo tiene que hacer un agente.
- Sin techo, ese agente podría leer la obra entera. Con techo, no puede.

La única salida que queda es que **la verdad no viva en la prosa**, sino en una estructura consultable que cabe en trozos. Esa es la idea central.

---

## 3. La idea central: una novela larga es un estado del mundo que evoluciona

La regla de oro de `definitions.md` §0: una novela larga no es un texto largo, es un estado del mundo que evoluciona, y el texto es su proyección visible. El sistema gestiona el estado; la prosa es consecuencia.

Se convierte en principios de arquitectura (`architecture.md` §1):

| Principio | Qué significa | Por qué hace falta |
|---|---|---|
| El canon es la fuente de verdad (CAN-01) | Lo que no está en el canon no ha ocurrido | Si la verdad vive solo en los capítulos, cada llamada obliga a releerlo todo, y el techo lo impide |
| El estado se deriva de eventos | Registro append-only y proyecciones calculadas | Responde «qué era cierto en el capítulo 12» sin ambigüedad |
| Ningún capítulo se cierra sin su delta (CAN-11, CAN-I1) | Lo que un capítulo cambia en el mundo se extrae, valida e integra antes de congelar (CAN-12) | Sin eso, el capítulo siguiente trabaja contra un canon que ya no es verdad |
| El contexto se presupuesta (CTX-03) | Cada llamada recibe un paquete construido a propósito | Tener 100.000 tokens no es motivo para usarlos |
| Escena para generar, capítulo para controlar | EST-08 es la unidad de escritura; EST-07, la de las puertas | La escena cabe en una llamada; la coherencia se juzga sobre algo mayor |

De aquí salen los cinco almacenes de la capa de memoria —canon estructurado, registro de eventos, grafo de entidades, índice de prosa y resúmenes jerárquicos— y la persistencia en un fichero SQLite por novela (`architecture.md` §3; `AGENTS.md` §3.2). Un fichero por novela hace la tirada reproducible: copiar el fichero es copiar el estado completo.

Tres principios más completan el marco y responden a la autonomía, no al techo: lo verificable se verifica sin modelo, escritura y evaluación se aíslan, y el bloqueo se resuelve replanificando (`architecture.md` §1, principios 4, 5 y 9).

---

## 4. El orden en que se especificó

Antes de una línea de código se escribieron, en este orden, siete niveles de documento. Cada uno consume al anterior.

```mermaid
graph LR
  A["Ontología · definitions.md"] --> B["Modelos · domain-knowledge.md"]
  B --> C["Arquitectura · architecture.md"]
  C --> D["Verificación · verification.md"]
  D --> E["SRS por versión · specs"]
  E --> F["Planes · backend/PLAN.md y frontend/PLAN.md"]
  F --> G["Código · backend y frontend"]
```

| Nivel | Qué fija | Por qué va en este puesto |
|---|---|---|
| Ontología | Qué existe: términos con ID estable en diez familias, e invariantes | Todo lo demás habla con su vocabulario. Un término mal puesto contamina los cuatro documentos y todo el código posterior (`AGENTS.md` §6) |
| Modelos | Cómo se relacionan las entidades y qué causa cada defecto | Hace visible lo que el glosario enumera; no añade términos |
| Arquitectura | Cómo se construye: memoria, contexto, skills, 13 agentes, flujos, arbitraje, orden de construcción | Necesita el vocabulario cerrado para asignar dueños |
| Verificación | Con qué método (VER-01 a VER-20) se comprueba cada artefacto, en dos ejes, con clase TAIDU y riesgo aceptado | Hay que saber qué se construye antes de decidir cómo se comprueba; y sin personas, la verificación es la única fuente de confianza (`verification.md`, introducción) |
| SRS por versión | Qué hace exactamente cada tramo, con requisitos RF, RD, RI y RNF, cada uno con su fuente y su VER-NN | Refina la arquitectura hasta poder escribir código, sin introducir términos ni números (`AGENTS.md` §3.3) |
| Planes | En qué orden, con qué ficheros y con qué puerta por tramo | No añaden requisitos: bajan el SRS a trabajo ordenado |
| Código | La realización | Es el nivel de menor radio de impacto |

**El criterio del orden es el radio de impacto** (`AGENTS.md` §6). Lo más caro de equivocar va primero, porque su error no se nota hasta tres documentos más tarde. Por eso cada nivel tiene su proceso de cambio: A para la ontología y los modelos, B para arquitectura, verificación y specs, C para el código, y los tres empiezan con el mismo interrogatorio cuando el cambio cruza el umbral de §6.1.

**La regla de corrección va en el sentido contrario.** Si al bajar un nivel se descubre que el de arriba está mal, se para y se corrige el de arriba en la misma entrega (`AGENTS.md` §3.3 y §6.4). La spec nunca contradice a la arquitectura en silencio, y el plan nunca contradice a la spec. `backend/coherence.py` comprueba en la puerta que los tres niveles hablan de las mismas cosas con los mismos nombres (`AGENTS.md` §6.7).

---

## 5. Qué entraba en la versión 1

La versión 1 del backend son los pasos 1 a 6 de `architecture.md` §14: **el sistema mínimo autónomo**, del brief al manuscrito congelado sin que nadie apruebe nada ([`srs-backend-v1.md`](../../specs/srs-backend-v1.md) §1.2; D-02).

| Paso | Qué entrega | Carpeta |
|---|---|---|
| 1 | Canon estructurado, registro de eventos y grafo de entidades | `canon/` |
| 2 | Escaleta y especificación de escena | `planning/` |
| 3 | Documentalista completo: recetas de paquete y recuperación híbrida | `context/` |
| 4 | Escritor, Especialista deportivo, verificadores deterministas, Continuista y Reparador | `generation/`, `verification/` |
| 5 | Archivero y ciclo de congelación | `canon/` |
| 6 | Árbitro y política de precedencia | `canon/` |

**Por qué esta frontera.** El paso 6 es el umbral de la autonomía: antes de él, cualquier conflicto de canon detiene el sistema (`architecture.md` §14). Los pasos 1 a 6 compran viabilidad; lo que viene después compra escala y calidad.

Participan diez de los trece agentes. Quedan fuera el Jurado, el Estilista y el Supervisor, y eso tiene un coste declarado: la versión 1 garantiza coherencia factual, temporal y deportiva, no calidad literaria medida (`srs-backend-v1.md` §1.2).

Tres decisiones de alcance merecen su porqué:

| D | Decisión | Por qué |
|---|---|---|
| D-03 | Continuista, Reparador y Especialista deportivo dentro | El bucle de `architecture.md` §7.1 no cierra sin ellos: sin Reparador no hay regeneración dirigida, sin `match.simulate` los verificadores deportivos no tienen contra qué comprobar |
| D-10 | Recuperación híbrida completa, con sus dos piernas | Separarla obligaría a escribir dos veces la fusión y los cupos, que es el grueso del trabajo. Al paso 8 le queda medir, no construir |
| D-05 | Sin retcon: el canon congelado siempre gana | Retconear exige reescribir prosa congelada, la mitad cara de `architecture.md` §10 |

Sin Jurado, la versión 1 fija su propia puerta de capítulo: cero S1 y máximo 2 S2 del Continuista (D-06). Sin Supervisor, replanifican el Planificador por escena y el Arquitecto por tramo (D-04).

El plan del SRS baja los seis pasos a nueve tramos, T0 a T8 (`srs-backend-v1.md` §11). Se aparta de §14 en dos puntos, los dos con motivo: `commons/` se adelanta a todo porque todas las funcionalidades importan de él, y `canon/` se parte en lectura, escritura y arbitraje porque leer hace falta desde el tramo 1 y escribir no hasta tener qué escribir (§11.1). `backend/PLAN.md` continúa desde T9 para cerrar la versión 1 con una tirada real, T16.

---

## 6. Qué se dejó para después, y por qué

Cada versión posterior tiene su SRS y su porqué. La numeración de requisitos, decisiones y tramos continúa de una a otra, para que un ID signifique una sola cosa en toda la carpeta (`srs-frontend-v1.md` D-55).

| Versión | SRS | Qué añade | Por qué no entró antes |
|---|---|---|---|
| Backend v2 | [`srs-backend-v2.md`](../../specs/srs-backend-v2.md) | Pasos 7 a 10: resúmenes de arco y de obra, afinado de la recuperación, Jurado de tres instancias con conjunto dorado, Estilista con huella, Supervisor con replanificación por deriva. Y el retcon CAN-10. Entran los trece agentes | Compran escala y calidad, no viabilidad. Pulir calidad sobre un canon que todavía no evoluciona es trabajo perdido (`backend/PLAN.md`, introducción). El retcon espera a tener Estilista, para que la reescritura no rompa la voz, y Jurado, para medir que no la empeoró (D-43) |
| Frontend v1 | [`srs-frontend-v1.md`](../../specs/srs-frontend-v1.md) | Paso 11: entrevista del brief, lectura web por versiones, ficha de personajes y lugares, solicitud de cambio desde la lectura, vistas de estado | Está fuera del camino crítico por diseño: el sistema completa una novela con el frontend apagado (`architecture.md` §2.1; RNF-39) |
| Backend v3 | [`srs-backend-v3.md`](../../specs/srs-backend-v3.md) | Las rutas que el frontend exige: brief extendido, entrevista en `brief/`, versiones con manifiesto, fichas, lista de novelas y solicitudes aplicadas por el Orquestador | Las pide el frontend v1 en su §8.2; antes, solo se podía encargar con un brief en JSON y leer con un cliente HTTP |
| Backend v4 | [`srs-backend-v4.md`](../../specs/srs-backend-v4.md) | No añade paso: endurece los existentes. Lean 4 sobre la cronología, guardarraíl de prohibidas bloqueante, Langfuse como espejo de la traza, hecho × escena, hooks de Claude Code con audit log, Jurado de nueve dimensiones con elementos obligatorios, TLA+ del flujo completo, evaluación con cinco briefs y perfiles de extensión cortos (PRO-15) | Cierra huecos que las versiones anteriores dejaban pasar o no dejaban rastro (su §1.1). Necesita un sistema completo sobre el que endurecer |
| Frontend v2 | [`srs-frontend-v2.md`](../../specs/srs-frontend-v2.md) | Ilustraciones de marca, elevación, libro en 3D al cerrar la obra y grafo en 3D | Solo presentación: ninguna ruta, escritura ni control nuevos |

Dos decisiones de la v1 del frontend fijaron la forma de todo lo que vino después:

- **Una solicitud de cambio es una enmienda al brief** (D-48): un hecho con procedencia `brief` (MET-09) que gana sobre el canon derivado por PRO-10 y se aplica como retcon. Es un encargo, no una revisión, y por eso no rompe PRO-11.
- **La entrevista no es un agente 14º** (D-49): son llamadas de modelo despachadas en código. Los trece agentes son los del ciclo de la novela, y la entrevista ocurre antes.

---

## 7. Qué quedó fuera de alcance

Cada SRS tiene su tabla de fuera de alcance, en su §8. Lo que se repite entre versiones dice más del diseño que cualquier fila suelta:

| Qué | Motivo | Fuente |
|---|---|---|
| Cualquier aprobación, rechazo o desbloqueo humano del ciclo | Contradice PRO-11 | `srs-frontend-v1.md` §1.2; `verification.md` §5.5 |
| Edición directa del texto por el lector | Sería revisión humana del texto. Lo que existe es pedir un cambio de hecho, que el sistema escribe solo | `srs-frontend-v1.md` §8.1 |
| Hooks que actúen dentro de una tirada | Serían revisión del texto por la puerta de atrás | `srs-backend-v4.md` §8 |
| Leer configuración de Langfuse durante una tirada | Metería la red en el camino crítico: la observabilidad observa, no gobierna | `srs-backend-v4.md` D-86 |
| Debate entre agentes | El Árbitro decide por regla, más barato y reproducible | `srs-backend-v2.md` §8 |
| Modelos distintos por agente | El puerto lo permite, pero elegir exige medir antes. Hoy los once agentes de modelo corren sobre el mismo | `srs-backend-v2.md` §8; `architecture.md` §13, nº 8 |
| Preguntas de la entrevista generadas por modelo | Determinista antes que modelo: qué falta ya lo sabe el código | `srs-backend-v3.md` D-73 |
| Deshacer una enmienda | Se pide otra: cada versión tiene una sola causa | `srs-backend-v3.md` §8 |
| Un proveedor de imagen | Claude sigue siendo el único proveedor de modelo del sistema | `srs-frontend-v2.md` D-115 |
| Autenticación y multiusuario | El sistema es local, un fichero por novela | `srs-frontend-v1.md` §1.2 |

Las decisiones que siguen abiertas, con su efecto en cada versión, están en `architecture.md` §13 y en el §10 de cada SRS.

---

## 8. Criterios de éxito

Se fijaron antes del código, en tres alturas. Ninguno es «compila»: todos piden evidencia ejecutable.

### 8.1 La puerta de cada cambio

| Criterio | Fuente |
|---|---|
| VER-01, VER-02, VER-05, VER-06 y VER-08 en verde antes de llegar a la rama principal | VER-15; `srs-backend-v1.md` §7.2 |
| Cada requisito con exactamente un VER-NN principal, o en el registro de riesgo aceptado antes de escribir su código | `AGENTS.md` §3.3 y §6.4; `verification.md` §9 |
| Docs, specs y planes coherentes, comprobado por código | `backend/coherence.py`; `AGENTS.md` §6.7 |
| Fallo cerrado: una comprobación que no corre cuenta como fallida | `AGENTS.md` §5.3; `verification.md` §2 |

### 8.2 La puerta de cada tramo

Cada tramo de los planes tiene una puerta propia, y **un tramo no empieza hasta que el anterior la pasa** (`srs-backend-v1.md` §11). La puerta comprueba una propiedad de la que depende el siguiente: descubrir en el tramo 6 que las proyecciones no eran reconstruibles obligaría a rehacer todo lo que se apoyó en ellas.

### 8.3 La definición de terminado de cada versión

| Versión | El criterio que de verdad cuenta | Fuente |
|---|---|---|
| Backend v1 | Una tirada completa va del brief al cierre de obra sin intervención (RNF-03), y copiar el fichero de la novela devuelve las mismas proyecciones y la misma recuperación (RD-12) | `srs-backend-v1.md` §11.2 |
| Backend v2 | Una tirada real con los trece agentes cierra la obra sin intervención y ninguna dimensión de CAL-01 queda por debajo de la semilla de la v1 | `srs-backend-v2.md` §11.1 |
| Backend v3 | El OpenAPI declara las rutas que pide el frontend y el frontend compila contra él | `srs-backend-v3.md` §11.1 |
| Backend v4 | Ningún camino congela o publica sin pasar `check.forbidden` y `run_lean`, y una novela real tiene su sesión en Langfuse | `srs-backend-v4.md` §11.1 |
| Frontend v1 | Una persona encarga una novela, la lee y pide un cambio sin cliente HTTP y sin que nadie apruebe nada (RNF-38), y el sistema sigue terminando una novela con el frontend apagado (RNF-39) | `srs-frontend-v1.md` §11.1 |

`srs-backend-v1.md` §11.2 lo dice sin rodeos: los demás criterios comprueban que el camino existe; la tirada sin intervención comprueba que funciona.

A la fecha de este documento, esa comprobación es lo que falta. El código de las versiones 1 a 4 está construido y en verde, pero la tirada real de T16, que produce `golden/v1-seed/`, la de T24, que se compara con ella, y las tiradas de evaluación de T52 siguen pendientes o en curso (`AGENTS.md` §2; `backend/PLAN.md` §1.7). Por tanto, la versión 1 todavía no cumple su propia definición de terminado.

### 8.4 La definición de terminado de cualquier cambio

La lista de `AGENTS.md` §10 aplica a todo, sea documento o código: vocabulario de `definitions.md`, las seis restricciones de §5.3, el proceso que corresponde con su interrogatorio, el techo de 100.000 respetado, un método de verificación o riesgo aceptado, los cuatro documentos coherentes, los diagramas renderizando, ningún paso de aprobación manual dentro del sistema y nada recuperado de versiones anteriores.

---

## 9. Qué leer después

| Tema | Documento |
|---|---|
| Compromisos entre alternativas | [02-trade-offs](02-trade-offs.md) |
| Explicaciones de piezas concretas | [03-explainers](03-explainers.md) |
| Diagramas del proceso | [04-diagramas](04-diagramas.md) |
| Iteraciones | [05-iteraciones](05-iteraciones.md) |
| Red team | [06-red-team](06-red-team.md) |
