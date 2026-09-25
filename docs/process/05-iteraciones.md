# 05 · Iteraciones

> Documentación de proceso · ver [`README.md`](README.md) para el índice de esta carpeta y [`../../AGENTS.md`](../../AGENTS.md) para el del repositorio.
> Relacionados: [definitions](../definitions.md) · [domain-knowledge](../domain-knowledge.md) · [architecture](../architecture.md) · [verification](../verification.md)
> Hermanos: [01-spec-inicial](01-spec-inicial.md) · [02-trade-offs](02-trade-offs.md) · [03-explainers](03-explainers.md) · [04-diagramas](04-diagramas.md) · [06-red-team](06-red-team.md)

Registro de lo que cambió tras cada eval, tirada real, contraejemplo de TLC o comprobación de Lean, y por qué. No es un diario: cada entrada es una decisión con su causa y su efecto. El lema de la carpeta se lee aquí en su forma más literal: **no se corrige el resultado, se corrige el razonamiento que llevó a él**. Por eso la columna central de cada entrada es la causa raíz, el razonamiento que estaba mal, y no el síntoma.

**Los `IT-n` son anclas locales de este documento**, no IDs del glosario ni de las specs. Solo sirven para enlazar dentro de `docs/process/` (`README.md`, «Reglas de esta carpeta»). Todo lo demás se cita por su ID estable: `D-NN`, `RF-NN`, `VER-NN`.

**Cómo se lee cada entrada.**

| Columna | Qué dice |
|---|---|
| Disparador | Uno de: eval, tirada real, contraejemplo TLC, fallo Lean, puerta/coherence, tuning |
| Evidencia | El dato observado, con su número cuando la fuente lo da |
| Causa raíz | El razonamiento de diseño o de código que permitió el fallo |
| Cambio | La decisión o el arreglo, por su ID |
| Efecto medido | Lo que se midió después. «No consta» si ninguna fuente de la rama lo registra |
| Fuente | Dónde vive la evidencia en esta rama |

Las entradas van agrupadas por disparador y, dentro de cada grupo, en el orden lógico de construcción. Solo llevan fecha las que la toman de su fuente. Todo sale del estado actual de la rama (`AGENTS.md` §5.5). Los hashes de commit que aparecen son los que citan las propias fuentes, no una consulta al historial.

Los casos adversariales, como la inyección del brief 02 o la trampa temporal del brief 03, se cuentan en [06-red-team](06-red-team.md). Aquí solo aparecen cuando provocaron un cambio.

**Resumen**

| Disparador | Entradas |
|---|---|
| Eval | IT-1 a IT-5 |
| Tirada real | IT-6 a IT-22 |
| Contraejemplo TLC | IT-23 a IT-32 |
| Fallo Lean | IT-33 |
| Puerta/coherence | IT-34 y IT-35 |
| Tuning | IT-36 a IT-38 |

---

## 1. Eval

Las tiradas de evaluación de T52 (`specs/srs-backend-v4.md` RF-272), con el perfil `prueba` y el modelo `haiku`. Fallan a propósito y un fallo es un resultado (VER-10).

### IT-1 · Escenas de un párrafo donde el Jurado no puede anclar

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| eval | El primer `eval-01`, con escenas de 100 a 170 palabras sobre `69d605e`, corrió 44,2 min de reloj sin congelar el capítulo 1. Hubo 48 reintentos del juez por «cita(s) sin anclar» y 29 citas descartadas como `process.defect`. El juez hizo el 75 % de los tokens de entrada y el 87 % de los minutos de modelo, con 5,94 USD en 99 llamadas | Se dimensionó el perfil `prueba` pensando solo en la duración de la tirada, sin mirar lo que los consumidores de la escena necesitan de ella. Nueve citas de 8 o más palabras, únicas en la escena (`verification.md` §5.11), no caben en 150 palabras | [D-113](../../specs/srs-backend-v4.md): escena y capítulo de 400 a 600 palabras, obra de 1.200 a 1.800 | Con el perfil nuevo, un segundo intento dio 3 o 4 en todas las dimensiones con 0 citas descartadas, salvo `personalization` (IT-2) | [`aborted/eval-01-perfil-parrafo.md`](../../backend/evals/results/aborted/eval-01-perfil-parrafo.md); D-113 |

### IT-2 · Una dimensión del Jurado sin nada contra lo que juzgar

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| eval | `01-semilla` no tiene destinatario. `personalization` salió 1, 3, sin nivel, 2 y sin nivel en cinco rondas, y bajo umbral en cuatro. Con D-113 aplicada, 1 en `personalization` y 3 o 4 en el resto | Se pedía puntuar las nueve dimensiones de RF-257 siempre, aunque el encargo no diera objeto a alguna. Un juicio sin objeto bloqueaba sin medir nada. A la semilla de T16, que tampoco tiene destinatario, le habría pasado lo mismo | [D-114](../../specs/srs-backend-v4.md): sin destinatario ni elementos no se juzga `personalization`, y sin tono no se juzga `tone`. La tabla por brief las marca «no aplica» | No consta una tirada posterior con esa medida aislada. En [`briefs.md`](../../backend/evals/results/briefs.md), `jury.personalization` sigue fallando en `02-adversarial`, que sí tiene destinatario | [`aborted/eval-01-perfil-parrafo.md`](../../backend/evals/results/aborted/eval-01-perfil-parrafo.md); D-114 |

### IT-3 · La replanificación se salía del perfil

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| eval | `eval-01` abortó a los 32 min: la replanificación del acto 2 devolvió dos veces capítulos y una obra fuera de `prueba` (`capitulo-fuera-de-rango`, `longitud-fuera-de-rango`), y la escalera acabó en `RunAbortedError` | La forma de la obra se daba por supuesta en la replanificación. Solo viajaba el rango de escena, dentro del esquema, y no el número de capítulos del tramo ni el presupuesto de palabras | [D-129](../../specs/srs-backend-v4.md): `replan.arc` recibe los capítulos, las escenas, el rango de palabras y lo que puede sumar el tramo | En la tirada «después» de [`tuning-01.md`](../../backend/evals/results/tuning-01.md) hubo 1 replanificación, frente a 4 en la de antes, y ninguna cuarentena | D-129; `tuning-01.md` |

### IT-4 · Un hecho sobre una entidad que nadie creó

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| eval | `eval-02` se estrelló al congelar el capítulo 1 con `FOREIGN KEY constraint failed` en la proyección de `attribute.set` | Se validaba el delta solo contra contradicciones con el canon. Un hecho sobre una entidad inexistente no contradice nada, así que pasaba y la clave ajena tumbaba la tirada entera | [D-130](../../specs/srs-backend-v4.md): la puerta 1 del Árbitro descarta ese hecho como S2 `unknown-entity`, lo registra como `process.defect` del Archivero y congela el resto | No consta. El mismo razonamiento reapareció por otro camino, el elenco, en IT-21 | D-130; tabla de hallazgos de `tuning-01.md` |

### IT-5 · Cinco briefs en paralelo: ninguno cierra

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| eval | Cinco tiradas sobre `8deed8d`, el 2026-09-24, con tope común de 30 min (RNF-58). `04-menor` y `05-no-deportivo` abortan en la escaleta con `doble-arco-colapsado` en los 2 intentos. `01-semilla` cae con un `ValueError` porque el Planificador no especifica `c1e1`. `03-temporal` cae con `OutputValidationError` tras JSON inválido del juez. `02-adversarial` agota el tope en el Jurado | Dos razonamientos distintos. Uno: una salida del modelo que no encaja se comprobaba después de la llamada y acababa en excepción, no en reintento. Otro, en la escaleta: con 3 escenas, el Arquitecto funde el arco exterior y el interior | En esta serie, ninguno: se registran como hallazgos abiertos. La salida que no encaja la corrigió después D-134, a partir de otra tirada (IT-18). `doble-arco-colapsado` sigue abierto | Las tiradas cuentan como fallo y no pasan en falso (`AGENTS.md` §5.3.6). La trampa de `03-temporal` la cazó `check.timeline` con 3 S1, detallada en [06-red-team](06-red-team.md) | [`briefs.md`](../../backend/evals/results/briefs.md); [`briefs-lectura.md`](../../backend/evals/results/briefs-lectura.md) |

---

## 2. Tirada real

Tiradas con el modelo real fuera de la serie de evaluación: las del bloque 1 del plan y las de los perfiles `breve` y `corta`.

### IT-6 · El esquema de salida en el lugar que el modelo lee menos

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | En la primera tirada real, con el esquema en el prompt de sistema, Haiku devolvía markdown o claves inventadas | Se colocó el esquema donde manda la convención, el sistema, sin tener en cuenta que el CLI antepone su andamiaje y que lo último que se lee es lo que más pesa (CTX-16) | [D-62](../../specs/srs-backend-v1.md): el esquema viaja con `--json-schema`, `dispatch` lo revalida y su texto va al final de la entrada | No consta en cifras. El coste es un turno más y el andamiaje dos veces, que `harness_tokens` declara | D-62 |

### IT-7 · El examen suspendía respuestas correctas

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | El examen dio por falladas 5 de 6 respuestas correctas | Se exigía el nombre completo de la clave, que mide la memoria del lector para los apellidos y no si la información llegó a la página (RF-112) | [D-64](../../specs/srs-backend-v2.md): basta la clave entera o una palabra distintiva suya, de tres letras o más | No consta | [`backend/PLAN.md`](../../backend/PLAN.md) §1.4; D-64 |

### IT-8 · Citas del Jurado descartadas por la forma de copiar

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | El Jurado descartó 15 puntuaciones y `pacing` se quedó sin nivel en todas las rondas | Dos supuestos. Se confundía la forma de copiar (« / » entre párrafos, puntos suspensivos tipográficos) con la de leer. Y se exigía anclar en la escena nombrada, cuando el ritmo se juzga sobre el capítulo | [D-65](../../specs/srs-backend-v2.md), que normaliza esas marcas, y [D-66](../../specs/srs-backend-v2.md), que ancla en la única escena del capítulo que contiene la cita. El prompt del juez exige copia literal de 8 a 25 palabras | No consta aislado: la segunda tirada falló por otra forma de cita (IT-15) | `PLAN.md` §1.4; D-65; D-66 |

### IT-9 · El reintento repetía la misma llamada

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | Tres intentos de escena seguidos, los tres en presente | El reintento no llevaba el defecto del intento anterior, así que era la misma llamada otra vez. El código se apartaba de `architecture.md` §4.1 | El reintento lleva el defecto y su evidencia | No consta | `PLAN.md` §1.4 |

### IT-10 · Una fecha que no era una fecha

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | `check.timeline` marcaba «1 de esta» como fecha | La expresión aceptaba cualquier palabra tras «de». Un verificador determinista puede ser demasiado generoso y no saberlo | Solo se aceptan nombres de mes | No consta | `PLAN.md` §1.4 |

### IT-11 · Un fallo del proveedor tumbaba la tirada entera

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | La tirada cayó entera cuando el CLI salió con error en una llamada del Jurado | El fallo del proveedor no se capturaba y subía hasta el bucle, aunque `architecture.md` §4.8 lo trata como intermitente y reintentable | Consume un intento del presupuesto de la llamada, [D-70](../../specs/srs-backend-v2.md): tres, compartidos con la salida que no valida. Agotado, sube y la tirada se reanuda por RF-20 | No consta | `PLAN.md` §1.4; D-70 |

### IT-12 · El Continuista juzgaba estilo

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | El Continuista marcó como S1 cuatro adjetivos que la guía de estilo prohíbe | Se confió en que el prompt bastaba para acotar el ámbito del agente. CAL-06 pone el estilo en S3 y su dueño es el Estilista | RF-51 llevado a código: el prompt enumera los ámbitos de continuidad y el anclaje descarta lo que cae fuera como defecto de proceso (RF-111) | No consta | `PLAN.md` §1.4 |

### IT-13 · Deriva declarada al empezar la obra

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | El Supervisor declaró deriva tras el capítulo 1 por «recuperaciones degradadas» | Se definió «degradado» como pierna semántica vacía. Al empezar la obra no hay prosa que recuperar, así que la señal saltaba siempre | Degradado es que la pierna no pudo ejecutarse, como dicen `architecture.md` §4.4 y §11 | No consta | `PLAN.md` §1.4 |

### IT-14 · Un presupuesto de reintentos para toda la obra

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | El capítulo 2 dio por agotada su primera escena al primer fallo | El presupuesto era uno para la obra, y cada escena heredaba los intentos de la anterior | Presupuesto nuevo por capítulo, y contador de escena a cero al empezar cada escena y al entrar en la puerta de capítulo (RF-18, `architecture.md` §7.3) | No consta | `PLAN.md` §1.4 |

Tras IT-9 a IT-14, la tirada se archivó en `runs-golden/intento-1/` y se relanzó con las correcciones (`PLAN.md` §1.4).

### IT-15 · Un fallo del juez gastaba la escalera del texto

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | La segunda tirada abortó en el capítulo 1: en la última ronda se descartaron 18 de 30 puntuaciones, con cuatro dimensiones sin nivel | Una cita descartada contaba como defecto del texto, y el Reparador arreglaba lo que no estaba roto. RF-111 dice que es un fallo de proceso | [D-71](../../specs/srs-backend-v2.md): la cita que no ancla vuelve al juez con su motivo y consume un intento del presupuesto de la llamada de D-70 | No consta aislado. El anclaje siguió siendo el coste dominante del Jurado (IT-1, IT-36) | `PLAN.md` §1.4; D-71 |

### IT-16 · El CLI anonimiza dentro del sistema

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | En T32, el CLI aplicó las instrucciones de la organización sobre datos personales dentro de la extracción: anonimizó nombres propios del texto libre y añadió una nota de privacidad detrás del JSON. La extracción entera se tumbaba | Se supuso que la salida del modelo sería solo el JSON pedido y que un fallo de formato afectaba a toda la respuesta | Se lee el primer objeto JSON y cada hecho se valida por separado. Lo alterado no ancla en el texto y se descarta, como pide RF-217 | La extracción con modelo real funciona y una solicitud de cambio real se aplicó sobre una copia de la tirada. El riesgo sigue abierto en `frontend/PLAN.md` §6 | [`frontend/PLAN.md`](../../frontend/PLAN.md), T32 |

### IT-17 · El razonamiento por defecto del CLI

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | En la primera tirada `breve`, cada llamada del juez escribió de 7.000 a 13.000 tokens para un JSON de unos 1.500 y tardó de 70 a 130 s. El Jurado se llevaba unos 15 min por capítulo | Se asumió el comportamiento por defecto del transporte. El CLI activa el razonamiento y lo cobra como salida, sin que nada del sistema dependa de él: lo que un agente produce ya lo comprueba un verificador | [D-133](../../specs/srs-backend-v4.md): `MAX_THINKING_TOKENS=0` para todos los agentes del motor (RI-62) | En una llamada mínima, la salida bajó de 347 a 213 tokens y el tiempo de 4,3 a 2,9 s. El traspaso da de 5 a 25 s por llamada de Haiku | D-133; [`.claude/handoff/2026-09-24.md`](../../.claude/handoff/2026-09-24.md) |

### IT-18 · Una especificación que no encaja paraba la tirada

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | En la primera tirada `breve` sin razonamiento, el Planificador devolvió un JSON válido sin la clave `c1e1`, y la tirada paró con un `ValueError` en el capítulo 1. Es el mismo hallazgo que `01-semilla` en IT-5 | La comprobación corría después de la llamada, fuera del camino de reintento. Un fallo corregible del modelo gastaba la novela en vez de un intento | [D-134](../../specs/srs-backend-v4.md): lo rechaza el modelo de salida que `dispatch` exige (`plan_model`), así que es un reintento con su motivo (RI-18) | No consta | D-134 |

### IT-19 · El Escritor entregaba corto

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | Con 1.250 palabras pedidas por escena, el Escritor entregó 768, 883, 972 y 1.004. En 10 capítulos la obra quedaría en unas 9.500, fuera del rango de cierre de 11.250 a 13.750 (RF-23), y cada capítulo corto gasta uno de los dos S2 de la puerta | Se pedía la longitud como objetivo aproximado, «en torno a», sin decir el suelo que el perfil exige | [D-135](../../specs/srs-backend-v4.md): el prompt del Escritor lleva el mínimo de escena del perfil como mínimo que no se baja | No consta | D-135 |

### IT-20 · La tirada `breve` que no congelaba: el modo permisivo

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | La tirada `breve` del 2026-09-24 pasó unos 45 min, en cuatro invocaciones, sin congelar el capítulo 1. El Continuista marcaba en cada pase un S1 `continuity.place` que venía de la propia especificación, y el Reparador cerró 0 defectos. Hubo hasta 25 llamadas al juez en 2 min, con `voice` y `theme` sin nivel. Acabó en `RunAbortedError` porque la replanificación comprobó la escaleta `breve` contra `novela`: 10 `capitulo-fuera-de-rango` | Dos razonamientos. Uno era un error: la replanificación por cuarentena no pasaba el perfil del brief. El otro fue la respuesta: para que la tirada terminara, se rebajaron las puertas en vez de arreglar lo que producía el defecto | [D-136](../../specs/srs-backend-v4.md): `lenient` en `breve` y `prueba`, y en `corta` desde D-139. Solo bloquean los S1 `check.*`, y cada degradación queda en la traza (RF-284). En el mismo cambio, la replanificación pasa el perfil y el rango del brief. [D-137](../../specs/srs-backend-v4.md) lleva el perfil a la entrevista | La primera tirada `prueba` con el modo abortó igual en la escaleta (`doble-arco-colapsado`), y el Jurado dejó sin nivel 8 de 9 dimensiones. En esa sesión, una tirada `prueba` cerró en unos 11 min, con 54 llamadas y 1,75 USD ([D-138](../../specs/srs-backend-v4.md)). **Revertido por D-142** (IT-38), salvo el arreglo de la replanificación | D-136; D-138; `.claude/handoff/2026-09-24.md` |

### IT-21 · El elenco nombraba a quien no existe

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | La tirada `corta` del 2026-09-24 congeló el capítulo 1 y paró al congelar el 2 con `IntegrityError: FOREIGN KEY constraint failed`. El delta estaba limpio y el POV existía | El elenco del Planificador no se contrastaba con el canon, aunque EST-I1 dice que son identificadores del estado del mundo. Era el único camino a `entity` sin filtrar: D-130 había cerrado el del delta, no este | [D-140](../../specs/srs-backend-v4.md): `parse` filtra el elenco a las entidades del canon y conserva el POV. Como red, `_freeze` deja fuera de los presentes lo que nadie crea, con `process.defect` del Planificador. Vale en todos los perfiles | No consta. El traspaso propone reanudar esa novela como prueba real | D-140; `.claude/handoff/2026-09-24.md` |

### IT-22 · Un hecho mal formado del Archivero tumbaba la tirada

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tirada real | La misma tirada `corta` paró porque el Archivero devolvió 3 veces un `relation.set` sin `kind`, y `_call` lanzó `OutputValidationError` sin capturar | En modo permisivo se supuso que bastaba con relajar las puertas. Una salida mal formada seguía siendo una excepción | D-141, solo en el traspaso y en los comentarios del código (`canon/archivist/extract.py`, `orchestration/engine.py`): en modo permisivo se descartan los hechos mal formados, y los agentes devuelven un valor seguro al agotar sus reintentos. **No tiene fila en `specs/`** | No consta. Hay tests de unidad del parseo; falta el test con el motor. Tras D-142 ningún perfil activa el modo permisivo | `.claude/handoff/2026-09-24.md` |

---

## 3. Contraejemplo TLC

El modelo de VER-18 (`docs/verification.md` §5.10) está en [`backend/orchestration/model/`](../../backend/orchestration/model/README.md). Hay dos clases de contraejemplo: los que corrigieron el modelo y los que encontraron fallos del código al modelarlo. Las mutaciones M1 a M4 no son iteraciones. Son la prueba de que cada invariante detecta lo que debe, y constan en su README, §7.2.

### IT-23 · Una guarda del modelo que el código no tenía

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| contraejemplo TLC | `chapter.tla` tenía `retcons < SceneAttempts`, y el código no cuenta retcons | Se modeló lo que el sistema debería hacer, no lo que el código hace. Un modelo más estricto que el código prueba otro sistema | Se quitó la guarda, se añadió `RetconPartial`, y `RetconsBounded` prueba que la cota la da la escalera: como mucho 9 por capítulo | `chapter` sin error: 2.636 estados generados, 1.831 distintos | [README del modelo](../../backend/orchestration/model/README.md) §6 y §7.3 |

### IT-24 · Un invariante cierto por construcción

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| contraejemplo TLC | `ResumeOnlyClosed == lastClosed <= scene` no podía fallar | Se escribió el invariante sobre variables que la propia acción mantiene, así que era vacuo | Se retiró de `chapter.tla` y se redefinió en `run.tla` sobre los borradores y el punto que reutiliza `Resume` (PRO-I2) | M4, `checkpoint.save` sin el borrado de borradores posteriores, da contraejemplo: el invariante ya no es vacuo | README §7.2 y §7.3 |

### IT-25 · Tamaño y evaluación del modelo de la tirada

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| contraejemplo TLC | Error de evaluación de TLC en `PlanPasses`: `freezes` aplicado a 0. Además, `run.tla` crecía unas 26 veces por capítulo: 163.336 estados distintos con 2 capítulos, 4.281.495 con 3, y con 5 no terminó en diez minutos | Una disyunción no es un condicional para TLC. Y se exploraban reescrituras por retcon que no cambian nada de lo que miran los invariantes | Un `IF` en `PlanPasses`, y tres reducciones: la reescritura conserva la marca de puertas, no hay retcon sobre congelados con la versión 1 vigente, y no se explora una segunda reescritura en la misma versión | `run` con 5 capítulos: 508.470 estados distintos, profundidad 242, 51 s, sin error. 510.546 con `PlanAttempts = 3` | README §3 y §7.3 |

### IT-26 · B1: una caída tras congelar recongela el capítulo

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| contraejemplo TLC | Falla `NoChapterDuplicated`: `Freeze`, `Crash` antes de `SaveNext`, `Resume` y `freezes[1] = 2`. En Python, `chapter.frozen` sale para `[1, 1, 2]` | Se supuso que congelar y avanzar el punto eran un solo paso. Entre los dos corren la puerta de acto, el Supervisor y el conjunto dorado, todos con llamadas a modelo, y `write_index` hace `INSERT OR REPLACE` | `ResumeSkipsFrozen`, en `91a1457`: un capítulo con prosa congelada no se reescribe y sigue desde su puerta de acto. Se descartó escribir N+1 en la transacción de la congelación, porque saltaría esa puerta | `test_b1_…`: `chapter.frozen` para `[1, 2]` y un solo evento del capítulo 1. `run.cfg` sin error | [`tlc/code-today_b1_double_freeze.txt`](../../backend/orchestration/model/tlc/code-today_b1_double_freeze.txt); README §7.1 |

### IT-27 · B2: un retcon cambia una versión ya publicada

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| contraejemplo TLC | Falla `PreviousVersionPreserved`: con la versión 2 creada, un retcon del capítulo 2 reescribe una escena del 1 y la vista de la versión 1 cambia | Se guardaba historial solo en la enmienda, como si ella fuera la única que reescribe. `text_at` devuelve el texto vigente de toda escena sin historial | `RetconKeepsHistory`, en `91a1457`: `refreeze.commit` guarda lo que ven las versiones no vigentes en **toda** recongelación (RD-34, PRO-08) | `test_b2_…`: la versión 1 muestra `v1` y la 2 marca las escenas como cambiadas | [`tlc/code-today_b2_retcon_history.txt`](../../backend/orchestration/model/tlc/code-today_b2_retcon_history.txt); README §7.1 |

### IT-28 · B3: una escena bloqueada entra en el canon tras una caída

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| contraejemplo TLC | Falla `ResumeOnlyClosed` y, por consecuencia, `NeverPublishUngated`: una escena agota la escalera, `Crash`, `Resume` la reutiliza con `scenesOk = FALSE`, y el capítulo congela | Se trató «escrita» como «cerrada». El punto avanzaba con el borrador de una escena bloqueante, y al reanudar se reutilizaba como si hubiera pasado su puerta (PRO-I2) | `CheckpointOnlyPassed`, en `91a1457`: el punto cubre solo un prefijo de escenas que pasaron. La cuarentena devuelve el punto al principio del capítulo | `test_b3_…`: la segunda tirada reescribe la escena, no pasa y aborta sin congelar | [`tlc/code-today_b3_checkpoint.txt`](../../backend/orchestration/model/tlc/code-today_b3_checkpoint.txt), [`b3_blocked_scene_frozen`](../../backend/orchestration/model/tlc/code-today_b3_blocked_scene_frozen.txt); README §7.1 |

### IT-29 · B4: la reanudación regalaba una escalera entera

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| contraejemplo TLC | Falla `RetriesWithinLimit`: tras `Crash` y `Resume` con `chapterAttempts = 0`, `spentCh = 2` con `ChapterAttempts = 2`. La liveness aguantaba igual: 920.140 estados distintos | Contradicción silenciosa entre código y arquitectura. `architecture.md` §7.4 pide conservar los reintentos consumidos, y `run` creaba un `Budget()` nuevo por capítulo | `ResumeKeepsBudget`, en `91a1457`: gana §7.4. `wm_run_state` guarda `chapter_attempts` y `arc_replans` (migración 6) | `test_b4_…`: una sola reespecificación de escena antes de replanificar, y no dos | [`tlc/code-today_b4_budget.txt`](../../backend/orchestration/model/tlc/code-today_b4_budget.txt), [`b4_budget_liveness`](../../backend/orchestration/model/tlc/code-today_b4_budget_liveness.txt); README §7.1 |

### IT-30 · R1: la reanudación replanificaba desde el brief

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| contraejemplo TLC | **Sin contraejemplo formal.** El modelo no tiene el contenido de la escaleta, así que no puede verlo. Salió al modelar el código, junto a B1 a B4 | Se reanudaba desde el brief, como si la escaleta vigente fuera derivable de él. Una replanificación del Supervisor se perdía con la caída | En `91a1457`: `wm_run_state.outline` guarda la escaleta vigente, y `_run_chapters` solo planifica si no hay ninguna | `test_r1_…`: el Arquitecto se llama una vez, no dos, y el capítulo 2 se escribe con la escaleta replanificada | README §6 y §7.1 |

### IT-31 · Un literal fuera de RF-18

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| contraejemplo TLC | Al cuadrar el modelo con el código, `_plan_with_gate` abortaba con `arc_replans > 2`, y el modelo necesitaba `PlanAttempts = 3` | Un número escrito a mano en vez de leído de la constante del presupuesto (`AGENTS.md` §5.6.5) | En `91a1457`, `retries.ARC_REPLANS`: la escaleta tiene 2 intentos, como `_replan`, y `PlanAttempts` pasa a 2 en todas las configuraciones | `run.cfg` sin error con `PlanAttempts = 2` | README §3, §6 y §7.1 |

### IT-32 · Tres fallos vistos al arreglar B1 a B4 y no tocados

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| contraejemplo TLC | Salieron al arreglar B1 a B4, fuera del alcance del modelo. `_work_closes` usa `report.words`, que tras reanudar cuenta solo esa invocación. `_current_texts` une fragmentos sin quitar el solape, mientras la historia sí lo quita. La especificación reescrita por `respec` no se guarda | El mismo patrón que B1 a B4: estado que vive en memoria de una invocación y se trata como si sobreviviera a la caída | Ninguno todavía. Se asignan por proceso C al dueño de cada fichero | No consta | [`backend/PLAN.md`](../../backend/PLAN.md), tabla de riesgos; README §6 |

---

## 4. Fallo Lean

### IT-33 · Ninguna tirada real dio un fallo de Lean

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| fallo Lean | **No hubo un fallo real.** Las cinco comprobaciones de `formal.lean` en las trazas de `eval-01` (capítulos 1 a 3), `eval-02` (capítulo 1) y `eval-01-umbral3` (capítulo 1) demostraron la cronología en 1,0 a 1,3 s. En la serie de cinco briefs, `check.formal` no llegó a correr: ningún capítulo congeló | No aplica: no hubo razonamiento que corregir. El caso que pide VER-04 se construyó como mutación declarada: un personaje excluido desde una fecha vuelve a estar presente en una escena posterior, y la prosa no nombra ninguna fecha | Ninguno en el motor. Se versiona el caso en `evals/formal/test_case.py`: Lean refuta `i4_absent_after_exclusion` con sus dos filas de origen, y `check.timeline` y `check.availability` pasan sobre la misma prosa | La fixture sembrada falla en sus cuatro teoremas, I1 a I4, y la limpia se demuestra en 2,9 s (`last-build.txt`, 2026-09-23) | [`evals/formal/CASOS.md`](../../backend/evals/formal/CASOS.md); [`last-build.txt`](../../backend/verification/formal/lean/last-build.txt) |

---

## 5. Puerta/coherence

### IT-34 · Dónde se comprueba `lake` y qué S1 da un hecho no exportable

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| puerta/coherence | No consta un fallo observado. D-107 lo registra como «fijado al construirse» la puerta formal | [D-88](../../specs/srs-backend-v4.md) comprobaba `lake` al arrancar la aplicación, lo que habría dejado sin lectura a quien no tiene Lean. Un fallo de `run_lean` sin filas de origen no tenía cita localizable | [D-107](../../specs/srs-backend-v4.md): `lake` se comprueba al componer el motor. El fallo sin filas es S1 `check.formal`, con la fila como evidencia en la primera escena. Sin `lake`, el paso de Lean de `gate.py` falla | La puerta exige Lean (`CASOS.md`, última línea) | D-88; D-107 |

### IT-35 · Numeración reservada fuera de `specs/`

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| puerta/coherence | `.claude/auditoria-entrega/2026-09-24/plan-cierre.md` reservaba D-133 a D-141 y RF-284 a RF-289 para otras decisiones, que ya no coinciden con `specs/` | Un documento de trabajo fuera del ciclo docs → spec → plan que `coherence.py` contrasta (`AGENTS.md` §6.7) asignaba IDs por su cuenta | Regla del traspaso: antes de numerar, se mira `specs/`. D-142 se tomó con esa regla | No consta que el plan de cierre se haya corregido | `.claude/handoff/2026-09-24.md`, punto 5 |

---

## 6. Tuning

### IT-36 · tuning-01: el Jurado y el Especialista en `prueba`

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tuning | En `eval-01-umbral3`, el capítulo 2 agotaba la escalera: el encuentro suspendía 3 intentos por `check.ledger` S1, porque la prosa daba marcadores parciales en cifras. Terminaba en cuarentena y replanificación | El prompt del Especialista no decía la forma que `check.ledger` comprueba, y el del juez dejaba recortar o unir frases. A la vez se decidió que en una tirada de prueba se mide el ciclo, no la calidad | [D-128](../../specs/srs-backend-v4.md): juez `7fe707a80eb1` → `742b19fab78d`, cita de una sola frase; Especialista `e74fc875b5f6` → `41fcc6dfbad0`, resultado en la forma de `check.ledger`; Arquitecto `4466609c77c5` → `dac47a65d9f1` (D-129). En `prueba`, mediana 2 y cita de 5 palabras | Capítulos congelados de 1 a 3 de 3. Defectos por 1.000 palabras de 13,2 a 4,2. Cuarentenas de 1 a 0 y replanificaciones de 4 a 1. **No mejoró**: reintentos del juez de 10 a 41, y coste de 2,77 a 6,54 USD (2,18 por capítulo). La tirada no cerró la obra | [`tuning-01.md`](../../backend/evals/results/tuning-01.md), [`tuning-01.json`](../../backend/evals/results/tuning-01.json) |

### IT-37 · El conjunto dorado del cierre agotaba el tope

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tuning | La tirada «después» de IT-36 congeló el capítulo 3 y agotó su tope de 60 min sin `work.close`. El conjunto dorado del cierre hizo 41 llamadas al juez en 16 min: 5 casos por 3 jueces, más 22 correcciones de cita | Se atribuyó el problema al número de casos, no al coste por caso del juez | [D-131](../../specs/srs-backend-v4.md): `golden_cases`, con 1 caso en `prueba` | No consta. **Revertido por D-142** (IT-38) | D-131; `tuning-01.md` |

### IT-38 · Reversión de las rebajas

| Disparador | Evidencia | Causa raíz | Cambio | Efecto medido | Fuente |
|---|---|---|---|---|---|
| tuning | Con D-128, D-131 y D-136 las tiradas cortas terminaban, pero congelando capítulos con defectos declarados (`scene.forced`, `chapter.forced`, `replan.kept`) | Se corrigió el resultado, que la tirada termine, en vez del razonamiento. Una obra que cierra con las puertas rebajadas no demuestra que el ciclo escriba bien. Es la decisión de quien encarga el sistema | [D-142](../../specs/srs-backend-v4.md): mediana 3, citas de 8 a 25 palabras, 5 casos dorados y `lenient = False` en todos los perfiles. Se quedan los prompts de D-128, la replanificación con el perfil de D-136, D-130 y D-140. Una obra cierra solo por RF-23 | No consta todavía una tirada estricta de un perfil corto | D-142; `architecture.md` §9.3 |

---

## 7. Patrones

Qué razonamiento erróneo se repitió, y qué regla del repositorio lo previene hoy.

| Patrón | Entradas | Qué lo previene hoy |
|---|---|---|
| **Tratar un fallo del agente como fallo del texto.** Una cita que no ancla, una dimensión sin objeto o un juicio de estilo del Continuista gastaban la escalera del texto | IT-1, IT-2, IT-8, IT-12, IT-15 | RF-111: un fallo de proceso no es un defecto del texto. D-71 lo devuelve al agente con su motivo. `AGENTS.md` §5.3.5: sin cita localizable no hay veredicto |
| **Excepción donde tocaba reintento.** Un error del proveedor, una salida sin la clave esperada o un hecho mal formado paraban la tirada entera | IT-5, IT-11, IT-18, IT-22 | D-70 y RI-18: toda salida que no encaja consume un intento de la llamada. D-134: la forma se valida en el modelo de salida de `dispatch`, no después. La tirada no pasa en falso: `AGENTS.md` §5.3.6 |
| **Un número o un perfil implícito.** El literal `> 2`, la replanificación contra `novela`, la longitud «en torno a» o el rango de escena como única forma | IT-3, IT-19, IT-20, IT-31 | D-105: todo consumidor de un rango lo lee del perfil. `AGENTS.md` §5.6.5: nada de inventar números |
| **Dato del modelo no contrastado con el canon.** Hechos y elencos sobre entidades que no existen llegaban a la clave ajena | IT-4, IT-21 | D-130 y D-140: se descarta con su motivo, en todos los perfiles. `AGENTS.md` §5.3.3: el canon es la fuente de verdad. EST-I1 |
| **Estado de una invocación tratado como persistente.** Punto, presupuesto, escaleta o longitud que no sobrevivían a la caída | IT-26, IT-28, IT-29, IT-30, IT-32 | PRO-I2 y RNF-08: reanudar da lo mismo que no caer. VER-18, con `run.tla` y `code-today/` en la puerta de CI al cambiar el modelo |
| **Contradicción silenciosa entre código y arquitectura.** El código hacía otra cosa que `architecture.md` y nadie lo veía | IT-9, IT-13, IT-29 | `AGENTS.md` §6.4: si la spec está mal se ejecuta el proceso B, no un parche. `backend/coherence.py` (§6.7) contrasta lo que es texto, pero no el comportamiento |
| **Modelo o invariante que prueba otro sistema.** Una guarda que el código no tiene, o un invariante cierto por construcción | IT-23, IT-24 | Mutaciones M1 a M4 en `model/mutations/`: cada invariante debe dar contraejemplo cuando se rompe lo que protege. La tabla acción TLA+ ↔ código del README del modelo, §4 |
| **Rebajar el filtro en vez de arreglar lo que produce el texto.** Umbral más bajo, menos casos dorados, modo permisivo | IT-20, IT-36, IT-37, IT-38 | D-142: el sistema es estricto en todos los perfiles, y si un filtro bloquea se arregla lo que produce el texto. Las correcciones que se quedaron son las que cambian al productor: los prompts de D-128, D-129, D-133, D-135 y D-140 |
