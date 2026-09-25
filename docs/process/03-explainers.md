# 03 · Explainers

> Documentación de proceso · ver [`../../AGENTS.md`](../../AGENTS.md) para el índice completo.
> Relacionados: [definitions](../definitions.md) · [domain-knowledge](../domain-knowledge.md) · [architecture](../architecture.md) · [verification](../verification.md)

Un explainer por cada concepto del curso que este proyecto aplica. No repiten teoría: cada uno dice qué es el concepto en una frase propia, con qué mecanismo concreto vive aquí, qué fallo de este sistema evita, qué no garantiza y dónde se comprueba. Cuando un límite ya está escrito en [`verification.md`](../verification.md), se toma de allí y no se reformula.

Todos tienen la misma forma, para que se puedan comparar:

- **Qué es**, en una frase.
- **Cómo se aplica aquí**, con ficheros e IDs.
- **Por qué aquí**, el fallo que evita en este sistema.
- **Límite**, lo que no garantiza.
- **Dónde se comprueba**, método `VER-NN`, prueba o puerta.

Van ordenados por capa del harness: primero cómo se construye, después lo que entra, cómo se piensa, qué se recuerda, cómo se verifica, qué se prohíbe, cómo se evalúa, cómo se observa y cómo se cambia una obra ya escrita.

---

## Índice

| Capa | Conceptos |
|---|---|
| **0 · Método** | [Harness engineering](#harness-engineering) · [Spec-driven development](#spec-driven-development) · [Clasificación TAIDU](#clasificación-taidu) |
| **1 · Entrada** | [Entrevista y brief estructurado](#entrevista-y-brief-estructurado) · [Texto no confiable y prompt injection](#texto-no-confiable-y-prompt-injection) |
| **2 · Contexto** | [Ingeniería de contexto y presupuesto de tokens](#ingeniería-de-contexto-y-presupuesto-de-tokens) · [Contador de tokens y prefijo cacheable](#contador-de-tokens-y-prefijo-cacheable) · [Techo de concurrencia y admisión](#techo-de-concurrencia-y-admisión) · [Aislamiento entre agentes](#aislamiento-entre-agentes) |
| **3 · Agentes** | [Multi-agente con orquestador como código](#multi-agente-con-orquestador-como-código) · [Structured output y validación con schema](#structured-output-y-validación-con-schema) · [Tool use y servidor de herramientas](#tool-use-y-servidor-de-herramientas) · [Retries con límite y cuarentena](#retries-con-límite-y-cuarentena) |
| **4 · Memoria** | [Cinco almacenes y estado derivado de eventos](#cinco-almacenes-y-estado-derivado-de-eventos) · [Resúmenes jerárquicos](#resúmenes-jerárquicos) · [Recuperación híbrida](#recuperación-híbrida) · [Memoria de trabajo, checkpoint y reanudación](#memoria-de-trabajo-checkpoint-y-reanudación) · [Congelación](#congelación) |
| **5 · Verificación** | [Validadores deterministas](#validadores-deterministas) · [Evidencia obligatoria y fallo cerrado](#evidencia-obligatoria-y-fallo-cerrado) · [LLM-as-judge: el Jurado](#llm-as-judge-el-jurado) · [Examen de comprensión sin contexto](#examen-de-comprensión-sin-contexto) · [Verificación formal de la historia con Lean 4](#verificación-formal-de-la-historia-con-lean-4) · [Model checking del sistema con TLA+ y TLC](#model-checking-del-sistema-con-tla-y-tlc) |
| **6 · Guardrails** | [Guardrail de palabras prohibidas](#guardrail-de-palabras-prohibidas) · [Policy engine y audit log](#policy-engine-y-audit-log) · [Hooks de Claude Code](#hooks-de-claude-code) · [Sandbox del proveedor](#sandbox-del-proveedor) |
| **7 · Evaluación** | [Evals del sistema](#evals-del-sistema) · [Red-teaming adversarial](#red-teaming-adversarial) · [Tuning con prompts versionados](#tuning-con-prompts-versionados) |
| **8 · Observabilidad** | [Observabilidad con Langfuse](#observabilidad-con-langfuse) |
| **9 · Cambio y lectura** | [Retcon, enmiendas y versiones](#retcon-enmiendas-y-versiones) · [Lectura interactiva con frontend observador](#lectura-interactiva-con-frontend-observador) · [Validación visual con MCP de navegador](#validación-visual-con-mcp-de-navegador) |

---

## Capa 0 · Método

### Harness engineering

- **Qué es.** Diseñar todo lo que rodea al modelo —qué ve, qué puede hacer, qué se comprueba de lo que devuelve y qué pasa cuando falla— de modo que la fiabilidad salga del andamiaje y no de la buena voluntad del modelo.
- **Cómo se aplica aquí.** El modelo es una pieza sustituible detrás de un puerto ([`backend/commons/provider/port.py`](../../backend/commons/provider/port.py)); todo lo demás es código: el Orquestador ([`backend/orchestration/loop.py`](../../backend/orchestration/loop.py)), el Documentalista que ensambla el paquete ([`backend/context/`](../../backend/context/)), la frontera de confianza ([`backend/orchestration/dispatch.py`](../../backend/orchestration/dispatch.py)), las puertas ([`backend/verification/gates.py`](../../backend/verification/gates.py)) y la escritura exclusiva de canon ([`backend/canon/freeze/freeze.py`](../../backend/canon/freeze/freeze.py)). De los trece agentes de [`architecture.md`](../architecture.md) §6, dos son código.
- **Por qué aquí.** PRO-11 prohíbe cualquier intervención humana en la revisión del texto. Sin persona que atrape un fallo, cada decisión necesita regla de precedencia, umbral o agente responsable ([`architecture.md`](../architecture.md) §1, principio 8). El harness es lo que convierte esa exigencia en mecanismo.
- **Límite.** Un harness completo garantiza que la novela es coherente con su canon y con sus reglas, no que sea buena. «Que la novela interese a un lector real» está en el registro de riesgo aceptado ([`verification.md`](../verification.md) §9).
- **Dónde se comprueba.** La puerta única [`backend/gate.py`](../../backend/gate.py), que corre VER-01, VER-02, VER-05, VER-06 y VER-08 (VER-15), y la prueba de diseño de [`architecture.md`](../architecture.md) §2.1: el sistema completa una novela con el frontend apagado.

### Spec-driven development

- **Qué es.** Ninguna línea de código existe sin un documento que la autorice, y los documentos se contrastan entre sí con código, no con una revisión cuando toque.
- **Cómo se aplica aquí.** Tres alturas: [`docs/`](../) dice qué es el sistema, [`specs/`](../../specs/) qué hace cada paso con requisitos `RF`, `RD`, `RI` y `RNF`, y [`backend/PLAN.md`](../../backend/PLAN.md) y [`frontend/PLAN.md`](../../frontend/PLAN.md) en qué orden se construye. Cada requisito cita su fuente en `docs/` y un único `VER-NN` ([`AGENTS.md`](../../AGENTS.md) §3.3). [`backend/coherence.py`](../../backend/coherence.py) corre dentro de la puerta y falla si un ID citado no existe, si un requisito no tiene método o tramo, si una sección de `architecture.md` no tiene fila en la matriz de cobertura, o si la tabla de validadores de [`architecture.md`](../architecture.md) §9.1 no casa con los `check.*` del código (`specs/srs-backend-v4.md` RF-268).
- **Por qué aquí.** El código de un sistema agéntico avanza más rápido que sus documentos. Sin contraste automático, la spec acaba describiendo un sistema que ya no existe, y los validadores que el resto del harness cree tener dejan de estar. El ciclo tiene además vuelta: la sincronización inversa de [`AGENTS.md`](../../AGENTS.md) §6.5 revisa los documentos tras cada cambio de código.
- **Límite.** `coherence.py` comprueba que los tres niveles hablan de lo mismo con los mismos nombres, no que lo escrito sea verdad ([`AGENTS.md`](../../AGENTS.md) §6.7).
- **Dónde se comprueba.** [`backend/test_coherence.py`](../../backend/test_coherence.py) y `python gate.py` (VER-15).

### Clasificación TAIDU

- **Qué es.** Cada cosa verificable recibe una sola clase según cómo se obtiene la confianza: Test, Analysis, Inspection, Demonstration o Unverifiable.
- **Cómo se aplica aquí.** Los veinte métodos de [`verification.md`](../verification.md) §3 llevan su clase, y la regla de asignación es de orden estricto: A antes que T antes que D antes que I (§2). La clase I se reserva para lo irreductiblemente subjetivo —tensión, subtexto, resonancia— y la U se declara por escrito en §9, con la señal que se vigila en su lugar. Tomar el anclaje de evidencia (VER-19) como A y no como I, o el examen de comprensión (VER-20) como T aunque use un modelo, sale de esta regla.
- **Por qué aquí.** Es la restricción «determinista antes que modelo» de [`AGENTS.md`](../../AGENTS.md) §5.3, punto 4, aplicada a la verificación. Sin clasificar, todo acaba en «que lo mire un juez», y un juez comparte modos de fallo con el generador.
- **Límite.** La clase dice cómo se obtiene la confianza, no cuánta hay ([`verification.md`](../verification.md) §2). Una clase A mal enunciada prueba con rigor la propiedad equivocada.
- **Dónde se comprueba.** La matriz método × artefacto de [`verification.md`](../verification.md) §7.1 y la de punto ciego × método de §7.2: todo límite declarado tiene otro método que lo tapa o una fila en §9.

---

## Capa 1 · Entrada

### Entrevista y brief estructurado

- **Qué es.** La única entrada humana del sistema se recoge por turnos y sale como un objeto validado, nunca como texto libre que otro agente tenga que interpretar.
- **Cómo se aplica aquí.** [`backend/brief/interview.py`](../../backend/brief/interview.py) aplica cada turno a un borrador tipado ([`backend/brief/draft.py`](../../backend/brief/draft.py), `Draft` y `Missing`) y devuelve el estado entero: qué falta, qué se contradice y qué hechos se proponen. Las preguntas van por plantilla, sin modelo ([`architecture.md`](../architecture.md) §2.3). Las contradicciones son reglas deterministas ([`backend/canon/brief_rules.py`](../../backend/canon/brief_rules.py), `specs/srs-backend-v3.md` RF-201 y RF-216), como un destinatario menor con un género o un tono de la lista adulta. El brief final es el modelo pydantic `Brief` de [`backend/canon/brief.py`](../../backend/canon/brief.py), con destinatario, género, tono, dedicatoria, prohibidas y perfil de extensión (PRO-15), y entra al canon como eventos con procedencia `brief` (MET-09).
- **Por qué aquí.** Un brief ambiguo se paga en cada escena de la obra, y cuando el ciclo arranca ya no hay a quién preguntar (PRO-11). La entrevista es el último momento en que preguntar es legítimo.
- **Límite.** Las reglas cubren las contradicciones enunciadas. Un tema prohibido no se detecta sin modelo: consta en [`verification.md`](../verification.md) §9.
- **Dónde se comprueba.** [`backend/brief/test_interview.py`](../../backend/brief/test_interview.py), [`backend/canon/test_brief_rules.py`](../../backend/canon/test_brief_rules.py) y [`backend/canon/test_brief.py`](../../backend/canon/test_brief.py): VER-05 y VER-06; RI-01 rechaza con 422 un brief con contradicción (VER-08).

### Texto no confiable y prompt injection

- **Qué es.** Todo texto que llega de fuera —la carta que pega quien encarga, una petición de cambio— es dato para el modelo, nunca instrucción, y nada de lo que el modelo saque de él entra solo.
- **Cómo se aplica aquí.** [`backend/brief/extract.py`](../../backend/brief/extract.py) (`brief.extract`) pone el texto libre en un bloque delimitado del paquete y no en la instrucción (`specs/srs-backend-v3.md` RNF-49); valida lo que devuelve con esquema; descarta toda cita que no aparece literal en el texto; y lo que queda son propuestas que solo entran si la persona las acepta (RF-217, RF-218). La interpretación de una enmienda, [`backend/brief/interpret.py`](../../backend/brief/interpret.py), sigue la misma regla. Un nombre que entra en todos los paquetes pasa por las mismas puertas que el resto del canon.
- **Por qué aquí.** El brief alimenta todos los paquetes de la obra. Una orden que se colara desde la carta se replicaría en cada llamada y acabaría en el canon, que es el fallo más caro del sistema: el envenenamiento (CTX-13).
- **Límite.** La contención es estructural —esquema, cita literal, aceptación explícita—, no un detector de inyecciones. Una propuesta legítima en forma pero falsa de contenido pasa si la persona la acepta. Y la campaña solo encuentra lo que buscó (VER-17, [`verification.md`](../verification.md) §5.9).
- **Dónde se comprueba.** [`backend/evals/adversarial/test_campaign.py`](../../backend/evals/adversarial/test_campaign.py) y la ejecución real documentada en [`backend/evals/results/adversarial-02.md`](../../backend/evals/results/adversarial-02.md): ninguna propuesta contiene la orden incrustada y el borrador no cambia sin aceptar. VER-17.

---

## Capa 2 · Contexto

### Ingeniería de contexto y presupuesto de tokens

- **Qué es.** Cada llamada recibe un paquete construido a propósito, con un presupuesto por bloque, en lugar de todo lo que quepa.
- **Cómo se aplica aquí.** El techo es propio del proyecto, 100.000 tokens de entrada por llamada (CTX-01), con el paquete ensamblado hasta 85.000 para dejar 15.000 a lo que añada un reintento, y 50.000 de salida como red de seguridad ([`architecture.md`](../architecture.md) §4.1). Cada agente tiene su presupuesto (§4.2) y su receta bloque a bloque (§4.9), implementadas en [`backend/context/packing/recipes.py`](../../backend/context/packing/recipes.py) y [`backend/context/packing/packet.py`](../../backend/context/packing/packet.py). Al desbordar se compacta por prioridad inversa (CTX-19): fragmentos, prosa previa, resúmenes y fichas secundarias, nunca anclas, conocimiento del POV ni la especificación de escena. [`backend/context/audit/audit.py`](../../backend/context/audit/audit.py) (`context.audit`) revisa el paquete antes de gastar la llamada.
- **Por qué aquí.** La distracción aparece mucho antes de agotar la ventana, y el coste se paga en cada escena de cada capítulo ([`architecture.md`](../architecture.md) §4.1). Sin presupuesto, el Continuista deja de caber en la ventana alrededor del capítulo 20 (§4.5).
- **Límite.** El presupuesto acota el tamaño, no la pertinencia: un paquete dentro de cupo puede traer la evidencia equivocada. Lo que no cabe se sustituye por resumen, nunca se trunca, así que el detalle perdido no se recupera en esa llamada.
- **Dónde se comprueba.** Propiedad de VER-06 «el paquete nunca supera 85.000 al ensamblarse, ni 100.000 al llamar contando el cupo de tirón», en [`backend/context/packing/test_packet.py`](../../backend/context/packing/test_packet.py) y [`backend/context/packing/test_recipes.py`](../../backend/context/packing/test_recipes.py); guardarraíl de techo por llamada de VER-12.

### Contador de tokens y prefijo cacheable

- **Qué es.** Un número que no se puede medir no es un techo: se estima antes de llamar, se mide después y la diferencia corrige al estimador.
- **Cómo se aplica aquí.** Un único contador en [`backend/commons/tokens/counter.py`](../../backend/commons/tokens/counter.py): `tiktoken` local por un factor por modelo ([`backend/commons/tokens/factors.py`](../../backend/commons/tokens/factors.py)), calibrado al arrancar ([`backend/commons/tokens/calibration.py`](../../backend/commons/tokens/calibration.py)) y contrastado con el `usage` real de cada respuesta, sumados sus tres campos de entrada ([`architecture.md`](../architecture.md) §4.8). El bloque 1 del paquete es el prefijo cacheable (CTX-23): idéntico en toda llamada del mismo agente y sin nada voluble delante, porque el caché casa por prefijo.
- **Por qué aquí.** No existe tokenizador local oficial para Claude, y `tiktoken` se queda corto siempre en la misma dirección, más en español. Sin corrección, el techo sería a veces no ser un techo. Y con la ventana real de Haiku 4.5 el colchón es estrecho: un desvío grande rompe la llamada (§4.8).
- **Límite.** El factor se calibra sobre una muestra, no sobre la obra: es riesgo aceptado declarado en [`architecture.md`](../architecture.md) §4.8. Cachear no libera ventana: lo servido desde caché ocupa igual.
- **Dónde se comprueba.** Propiedad de VER-06 «lo estimado por su factor nunca queda por debajo del `usage` real», en [`backend/commons/tokens/test_counter.py`](../../backend/commons/tokens/test_counter.py); la pareja estimado-real va a la traza de VER-09 y que el real supere al estimado es fallo de CI.

### Techo de concurrencia y admisión

- **Qué es.** El techo de tokens se aplica también a la suma de todo lo que está en vuelo a la vez, no solo a cada llamada.
- **Cómo se aplica aquí.** CTX-20 fija 100.000 tokens de entrada en vuelo, y el invariante CTX-I1 dice que nunca se superan, cupos de tirón (CTX-22) incluidos. [`backend/orchestration/admission.py`](../../backend/orchestration/admission.py) es un semáforo que cuenta tokens y no llamadas: reserva entrada más cupo de tirón entero al admitir, encola en FIFO estricta lo que no cabe, y no admite lo que no puede estimar ([`architecture.md`](../architecture.md) §7.4). La tabla `admission` de la memoria de trabajo guarda lo que está en vuelo y lo que espera.
- **Por qué aquí.** El paralelismo real son las tres instancias del Jurado. Admitir por lo que ocupa una llamada al empezar y dejarla crecer con herramientas rompe el techo sin que salte nada, y reordenar por hueco mataría de hambre a las llamadas grandes.
- **Límite.** Con el flujo de hoy el techo concurrente apenas muerde: es un guardarraíl para cuando el paralelismo crezca ([`architecture.md`](../architecture.md) §4.1). Depende de que la estimación sea por exceso, que es lo que vigila el contador.
- **Dónde se comprueba.** [`backend/orchestration/test_admission.py`](../../backend/orchestration/test_admission.py) con la propiedad de VER-06 sobre CTX-I1, y el invariante «nunca hay más de CTX-20 tokens en vuelo» del modelo TLA+ (VER-18).

### Aislamiento entre agentes

- **Qué es.** El contexto que generó un texto no lo juzga, y cada llamada empieza en una ventana limpia.
- **Cómo se aplica aquí.** El paquete se construye desde cero en [`backend/context/`](../../backend/context/) para cada llamada y nunca se muta ni se reutiliza (CTX-11, [`architecture.md`](../architecture.md) §4.7). El Escritor no ve defectos de otros capítulos, el Jurado no ve el paquete del Escritor y el Archivero no ve las rúbricas. La memoria de trabajo nunca entra en la ventana de un modelo (§3.2, regla 1). El `claude -p` del motor se lanza sin la configuración de quien lo ejecuta —ni `CLAUDE.md`, ni hooks, ni skills, ni servidores MCP— desde [`backend/commons/provider/claude_cli.py`](../../backend/commons/provider/claude_cli.py) (`specs/srs-backend-v4.md` RI-62).
- **Por qué aquí.** Un verificador que ve el razonamiento del generador aprueba lo que el generador creía haber hecho. Y un borrador rechazado que llegara al Escritor haría que el sistema aprendiera de su propio error.
- **Límite.** El aislamiento acota lo que cada agente ve, no cuántos corren a la vez, que es trabajo de CTX-20. Tampoco evita que dos modelos entiendan mal lo mismo: es el límite de VER-14.
- **Dónde se comprueba.** Propiedad de VER-06 «la fusión es determinista: el mismo canon produce el mismo paquete»; la lista fija de argumentos y entorno del CLI en [`backend/commons/provider/test_claude_cli.py`](../../backend/commons/provider/test_claude_cli.py) (VER-11).

---

## Capa 3 · Agentes

### Multi-agente con orquestador como código

- **Qué es.** El trabajo se reparte entre agentes con misión, contrato y criterio de salida propios, y quien los dirige no es un modelo.
- **Cómo se aplica aquí.** Trece agentes en [`architecture.md`](../architecture.md) §6, con sus contratos en §6.2. El Orquestador y el Documentalista son código; los once restantes corren sobre Claude Haiku 4.5 a través del CLI de Claude Code (§4.8). El Orquestador es un bucle síncrono en un proceso ([`backend/orchestration/loop.py`](../../backend/orchestration/loop.py)) que compone cada agente en [`backend/orchestration/engine.py`](../../backend/orchestration/engine.py). Los roles de la rúbrica son etiquetas sobre esos agentes en la traza exportada: `planner`, `writer`, `editor` e `interviewer` (§11). Tres agentes cubren lo que suele faltar: Archivero, Árbitro y Supervisor.
- **Por qué aquí.** Una novela no es un texto largo, es un estado del mundo que evoluciona ([`AGENTS.md`](../../AGENTS.md) §1). Un solo agente no cabe en 100.000 tokens con la obra entera, y un orquestador de modelo añadiría decisiones sin dueño a un ciclo que debe terminar solo.
- **Límite.** El reparto multiplica las fronteras donde un contrato puede romperse en silencio. VER-08 verifica la forma del contrato agente a agente, no el significado ([`verification.md`](../verification.md) §4.8).
- **Dónde se comprueba.** [`backend/orchestration/test_loop.py`](../../backend/orchestration/test_loop.py) y [`backend/orchestration/test_engine.py`](../../backend/orchestration/test_engine.py) con dobles deterministas (VER-05); el flujo modelado en TLA+ (VER-18).

### Structured output y validación con schema

- **Qué es.** Lo que devuelve un modelo es texto hasta que un esquema lo convierte en objeto; lo que no valida no entra.
- **Cómo se aplica aquí.** [`backend/orchestration/dispatch.py`](../../backend/orchestration/dispatch.py) es la frontera de confianza del sistema: valida cada salida con pydantic contra su esquema, aplica el tope de salida en código y no intenta remendar la respuesta. Una salida que no encaja cuenta como fallida y consume un reintento. Los esquemas de artefacto —especificación de escena en [`backend/commons/types/scene.py`](../../backend/commons/types/scene.py), rúbricas en [`backend/commons/types/rubrics.py`](../../backend/commons/types/rubrics.py), delta canónico CAN-11— son el contrato agente a agente, y el OpenAPI generado es el contrato HTTP ([`backend/openapi.json`](../../backend/openapi.json)).
- **Por qué aquí.** Todo lo que pase de `dispatch` sin validar contamina el canon, y no hay revisión humana detrás que lo detecte ([`architecture.md`](../architecture.md) §7.4). Remendar la salida esconde que el modelo entendió mal el encargo.
- **Límite.** VER-01 no dice nada sobre el contenido: un `chapter_number` bien tipado puede valer 47 en un libro de 30 capítulos. VER-08 verifica la forma, no el significado ([`verification.md`](../verification.md) §4.1 y §4.8).
- **Dónde se comprueba.** [`backend/orchestration/test_dispatch.py`](../../backend/orchestration/test_dispatch.py) y [`backend/orchestration/test_contract.py`](../../backend/orchestration/test_contract.py); VER-01 con `mypy --strict` y VER-08 en la puerta.

### Tool use y servidor de herramientas

- **Qué es.** Un agente puede pedir, durante su turno, información que no le llegó en el paquete, a través de herramientas cerradas, acotadas y de solo lectura.
- **Cómo se aplica aquí.** Hay dos herramientas (CTX-21): `context.budget`, que dice cuánto lleva ocupado, y `canon.lookup`, consulta acotada al canon y a la prosa congelada ([`architecture.md`](../architecture.md) §5.3). Las sirve [`backend/orchestration/tools/server.py`](../../backend/orchestration/tools/server.py), porque el Orquestador lleva el contador de la llamada. El puerto ofrece `complete_with_tools` solo a los agentes que las declaran en la matriz de §6.3; el CLI del motor corre con `--strict-mcp-config` y una configuración MCP vacía, así que las herramientas se piden con un protocolo JSON propio de [`backend/commons/provider/claude_cli.py`](../../backend/commons/provider/claude_cli.py) y no por MCP. `canon.lookup` mide antes de devolver, nunca trunca y etiqueta la procedencia de cada resultado. Ninguna herramienta escribe.
- **Por qué aquí.** El paquete empuja lo previsible; lo que el agente descubre que necesita después de leerlo solo se cubre tirando. Con escritura, la cadena herramienta más reparación sería un camino para reescribir canon congelado (VER-17, [`verification.md`](../verification.md) §5.9).
- **Límite.** El resultado es determinista; cuándo y cuántas veces se llama, no (§5.3). Una lista cerrada acota qué se pide, no si se pide lo pertinente. El MCP del repositorio es otra cosa: el de navegador de la validación visual, fuera del ciclo.
- **Dónde se comprueba.** [`backend/orchestration/tools/test_server.py`](../../backend/orchestration/tools/test_server.py): argumentos con tipos cambiados, claves de más o JSON malformado se rechazan sin coercionar (VER-12); cada llamada deja un registro `tool` en la traza y un span en Langfuse (VER-09).

### Retries con límite y cuarentena

- **Qué es.** Reintentar tiene tope, y cada nivel de la escalera cambia el diagnóstico en lugar de repetir lo mismo.
- **Cómo se aplica aquí.** [`backend/orchestration/retries.py`](../../backend/orchestration/retries.py): 3 intentos por escena, 2 por capítulo y 1 replanificación de tramo; agotado el último, se replanifica el arco ([`architecture.md`](../architecture.md) §7.3). CAL-12 fija el presupuesto y CAL-13 la cuarentena: la escena se rehace en su sitio con una especificación más estricta; el capítulo se rehace de inmediato y nunca se salta al siguiente. Si una escaleta no pasa `outline.check` tras sus intentos, la tirada para con `RunAbortedError` y su motivo en la traza.
- **Por qué aquí.** Sin tope hay bucle infinito de reparación; sin cambio de nivel, el tope solo retrasa el mismo fallo. Y saltarse un capítulo cuarentenado fabricaría una contradicción que ninguna puerta ve: el siguiente se escribiría sin su prosa ni su estado del mundo.
- **Límite.** La escalera garantiza que la tirada termina o para con motivo, no que termine bien. El número de reintentos es un presupuesto de coste, no una medida de calidad.
- **Dónde se comprueba.** [`backend/orchestration/test_loop.py`](../../backend/orchestration/test_loop.py) (VER-05) y el invariante TLA+ «los reintentos nunca superan la escalera de RF-18, tampoco sumando caídas» (VER-18), con el contraejemplo B4 de [`backend/orchestration/model/README.md`](../../backend/orchestration/model/README.md) §7.1.

---

## Capa 4 · Memoria

### Cinco almacenes y estado derivado de eventos

- **Qué es.** La memoria de largo plazo se separa por el tipo de pregunta que responde, y la verdad es un registro append-only del que todo lo demás se proyecta.
- **Cómo se aplica aquí.** Cinco almacenes lógicos en un solo SQLite por novela ([`architecture.md`](../architecture.md) §3.1, esquema en [`backend/canon/db/schema.sql`](../../backend/canon/db/schema.sql)): canon estructurado, registro de eventos ([`backend/canon/events/log.py`](../../backend/canon/events/log.py)), grafo de entidades con vigencia ([`backend/canon/graph/`](../../backend/canon/graph/)), índice de prosa ([`backend/canon/prose_index/`](../../backend/canon/prose_index/)) y resúmenes jerárquicos ([`backend/canon/summaries/`](../../backend/canon/summaries/)). El registro manda y las proyecciones se reconstruyen ([`backend/canon/projections/rebuild.py`](../../backend/canon/projections/rebuild.py)). Del índice se derivan hecho × escena (`fact_usage`, [`backend/canon/prose_index/usage.py`](../../backend/canon/prose_index/usage.py)) y la vista `chronology` ([`backend/canon/prose_index/chronology.py`](../../backend/canon/prose_index/chronology.py)), que alimenta a Lean.
- **Por qué aquí.** Unificarlo todo en un índice vectorial es el error estructural más frecuente ([`architecture.md`](../architecture.md) §3.1): «qué sabía el protagonista en la jornada 14» no se responde por similitud. Un fichero por novela hace la tirada reproducible: copiar el fichero es copiar el estado ([`AGENTS.md`](../../AGENTS.md) §3.2).
- **Límite.** El canon es tan bueno como los deltas que entran; su corrección la vigilan el Archivero, el Árbitro y la validación del delta, no el almacén.
- **Dónde se comprueba.** [`backend/canon/projections/test_rebuild.py`](../../backend/canon/projections/test_rebuild.py), [`backend/canon/prose_index/test_usage.py`](../../backend/canon/prose_index/test_usage.py) y [`backend/canon/prose_index/test_chronology.py`](../../backend/canon/prose_index/test_chronology.py) (VER-05, VER-06); [`backend/commons/test_sql_safety.py`](../../backend/commons/test_sql_safety.py) sobre las consultas (VER-02).

### Resúmenes jerárquicos

- **Qué es.** La obra se comprime en niveles —escena, capítulo, arco, obra— para que cualquier agente pueda tener delante lo que pasó sin releerlo todo.
- **Cómo se aplica aquí.** Se generan al congelar, nunca sobre la marcha, con `summarize.hierarchical` ([`backend/canon/summaries/levels.py`](../../backend/canon/summaries/levels.py)): 60 a 100 palabras por escena, 150 a 250 por capítulo construidas desde los de escena, 300 por arco y la obra regenerada cada 5 capítulos ([`architecture.md`](../architecture.md) §4.5). Se piden por nivel y rango, no por similitud (§3.1). En el perfil `prueba` cada resumen mide como mucho la mitad de lo que resume (`specs/srs-backend-v4.md` D-112).
- **Por qué aquí.** Es lo que mantiene la memoria completa dentro de 100.000 tokens cuando la novela pasa de 150.000 palabras. Sin jerarquía, el Continuista no cabe hacia el capítulo 20 ([`architecture.md`](../architecture.md) §4.5 y §12).
- **Límite.** Un resumen pierde detalle por construcción; lo que se perdió solo vuelve por la recuperación de fragmentos o por `canon.lookup`. Un resumen que invente un hecho no es canon, pero puede sesgar la escena siguiente.
- **Dónde se comprueba.** [`backend/canon/freeze/test_freeze.py`](../../backend/canon/freeze/test_freeze.py) (VER-05) y la medida de presupuesto del Continuista de `specs/srs-backend-v2.md` RNF-29.

### Recuperación híbrida

- **Qué es.** RAG con varias piernas que no compiten entre sí: lo que es verdad se pide por clave y lo que se escribió se busca por léxico y por semántica, y las dos búsquedas se fusionan por rangos.
- **Cómo se aplica aquí.** Cuatro piernas ([`architecture.md`](../architecture.md) §4.4, [`backend/context/retrieval/legs.py`](../../backend/context/retrieval/legs.py)): consulta al canon, grafo de entidades, FTS5 con BM25 sobre fragmentos (`prose_chunk_fts`) y vectores de `intfloat/multilingual-e5-large` calculados en local con `fastembed` ([`backend/commons/provider/embeddings.py`](../../backend/commons/provider/embeddings.py)). La consulta sale del canon y de la especificación de escena, sin modelo ([`backend/context/query/build.py`](../../backend/context/query/build.py)); las dos búsquedas de prosa se fusionan por rangos recíprocos ([`backend/context/retrieval/fusion.py`](../../backend/context/retrieval/fusion.py)) y se eligen por cupos —lugar, voz, promesa, espejo, libre— en [`backend/context/retrieval/quotas.py`](../../backend/context/retrieval/quotas.py). Cada fragmento lleva su procedencia; el fragmento nunca cruza la frontera de su escena.
- **Por qué aquí.** Solo la léxica acierta con nombres propios y solo la semántica encuentra la escena espejo que no comparte palabras (CTX-09). La procedencia es la contramedida contra el envenenamiento de contexto (CTX-13): sin etiqueta, la intención de un personaje se lee como hecho.
- **Límite.** La constante de fusión es 60 por venir del trabajo original, sin ajustar aquí ([`architecture.md`](../architecture.md) §13, decisión abierta 10). Un modelo E5 sin sus prefijos recupera peor sin error ni aviso (§4.8).
- **Dónde se comprueba.** [`backend/context/retrieval/test_fusion.py`](../../backend/context/retrieval/test_fusion.py) y [`backend/context/retrieval/test_legs.py`](../../backend/context/retrieval/test_legs.py) (VER-05, VER-06); el conjunto dorado de recuperación de [`backend/evals/retrieval_golden.py`](../../backend/evals/retrieval_golden.py) con [`backend/evals/test_retrieval.py`](../../backend/evals/test_retrieval.py) (VER-10).

### Memoria de trabajo, checkpoint y reanudación

- **Qué es.** Lo que todavía se está decidiendo vive aparte de lo que ya es verdad, y una caída retoma desde la última frontera cerrada sin rehacer trabajo validado ni reutilizar el que no lo está.
- **Cómo se aplica aquí.** La memoria de trabajo (PRO-13) son tablas `wm_*` en el mismo fichero —`run_state`, `draft`, `defect`, `verdict`, `admission`—, escritas solo por la fábrica de [`backend/commons/db/working_memory.py`](../../backend/commons/db/working_memory.py) ([`architecture.md`](../architecture.md) §3.2). El punto de reanudación (PRO-14) se guarda al cerrar cada escena en [`backend/orchestration/checkpoint.py`](../../backend/orchestration/checkpoint.py), con los reintentos consumidos y la escaleta vigente; al reanudar se descarta todo borrador posterior (PRO-I2) y un capítulo ya congelado no se reescribe (§7.4).
- **Por qué aquí.** Una tirada larga se cae, y sin estado en disco una caída en el capítulo 28 se lleva el capítulo entero. Si el punto no guardara los reintentos, cada caída regalaría una escalera nueva; si reutilizara borradores a medias, entraría texto que ninguna puerta aprobó.
- **Límite.** Reanudar por escena reaprovecha trabajo por escena, no por llamada: lo gastado en la escena interrumpida se vuelve a pagar. PRO-I2 se comprueba sobre el estado que deja la reanudación, no por construcción ([`verification.md`](../verification.md) §5.10).
- **Dónde se comprueba.** [`backend/orchestration/test_checkpoint.py`](../../backend/orchestration/test_checkpoint.py), con las pruebas que reproducen B1, B3, B4 y R1; [`backend/commons/db/test_working_memory.py`](../../backend/commons/db/test_working_memory.py) para PRO-I1; propiedad de VER-06 «reanudar produce el mismo capítulo que no caer»; invariantes de reanudación en TLA+ (VER-18).

### Congelación

- **Qué es.** El único momento en que el texto generado se convierte en verdad, hecho como una transacción que entra entera o no entra.
- **Cómo se aplica aquí.** La congelación (CAN-12) en [`backend/canon/freeze/freeze.py`](../../backend/canon/freeze/freeze.py) sigue el orden de [`architecture.md`](../architecture.md) §3.3: fuera de la transacción, cortar fragmentos, resumir y calcular vectores; dentro, aplicar el delta (CAN-11), recalcular proyecciones, indexar prosa y hecho × escena, escribir resúmenes, insertar la proscripción de estilo y purgar la memoria de trabajo (PRO-I1). Antes pasan dos redes que miran lo que va a entrar: `check.forbidden` sobre el capítulo entero y Lean sobre canon más delta (§10). El delta se valida en [`backend/canon/arbiter/entries.py`](../../backend/canon/arbiter/entries.py) y los conflictos van al Árbitro con la precedencia PRO-10 ([`backend/canon/arbiter/precedence.py`](../../backend/canon/arbiter/precedence.py)).
- **Por qué aquí.** El canon es la fuente de verdad ([`AGENTS.md`](../../AGENTS.md) §5.3.3). Si pudiera escribirse desde otro sitio, la amenaza propia del sistema —un agente reescribe un hecho para dejar de ser incoherente— quedaría abierta ([`verification.md`](../verification.md) §5.9).
- **Límite.** La congelación garantiza que entra lo validado y nada a medias, no que el delta sea verdad respecto a la prosa: un delta con la forma correcta y hechos falsos pasa los guardarraíles (VER-12).
- **Dónde se comprueba.** [`backend/canon/freeze/test_freeze.py`](../../backend/canon/freeze/test_freeze.py) y [`backend/canon/arbiter/test_precedence.py`](../../backend/canon/arbiter/test_precedence.py) (VER-05); invariantes TLA+ «nunca se escribe canon antes de congelar» y «ningún capítulo se congela dos veces» (VER-18).

---

## Capa 5 · Verificación

### Validadores deterministas

- **Qué es.** Todo lo que se puede comprobar con código se comprueba con código, antes que cualquier juez y con coste despreciable.
- **Cómo se aplica aquí.** Los verificadores de CAL-03 viven en [`backend/verification/checks/deterministic.py`](../../backend/verification/checks/deterministic.py): `check.timeline`, `check.format`, `check.lexicon` —nombres escritos exactamente como en el canon—, `check.knowledge`, `check.repetition`, `check.ledger` y `check.availability`, con la longitud de capítulo frente al perfil (PRO-15) en `check_chapter_length`. Aparte, `check.forbidden` ([`backend/verification/checks/forbidden.py`](../../backend/verification/checks/forbidden.py)) y `outline.check` ([`backend/planning/outline/check.py`](../../backend/planning/outline/check.py)), que exige que cada elemento obligatorio del destinatario tenga su cobro planificado. La tabla de [`architecture.md`](../architecture.md) §9.1 dice de cada uno dónde vive, dónde corre, su severidad y qué pasa si falla; las puertas de §9.3 están en [`backend/verification/gates.py`](../../backend/verification/gates.py).
- **Por qué aquí.** Un modelo no es fiable contando fechas ni comparando tildes, y cada falso negativo determinista acaba en canon. Es la restricción 4 de [`AGENTS.md`](../../AGENTS.md) §5.3.
- **Límite.** Solo cubren lo que alguien enunció como regla. Duración de elipsis y estadísticas acumuladas no tienen verificador propio y son riesgo aceptado ([`architecture.md`](../architecture.md) §9.1). Una palabra común al principio de frase puede dar un falso S1 de `check.lexicon` ([`verification.md`](../verification.md) §9).
- **Dónde se comprueba.** [`backend/verification/checks/test_deterministic.py`](../../backend/verification/checks/test_deterministic.py) y [`backend/verification/test_gates.py`](../../backend/verification/test_gates.py) (VER-05, VER-06); VER-07 con umbral propuesto de mutantes muertos sobre este módulo ([`verification.md`](../verification.md) §4.7); `coherence.py` contrasta la tabla con el código (RF-268).

### Evidencia obligatoria y fallo cerrado

- **Qué es.** Un veredicto sin cita localizable no vale nada, y una comprobación que no se puede ejecutar cuenta como fallida.
- **Cómo se aplica aquí.** `check.evidence` ([`backend/verification/checks/evidence.py`](../../backend/verification/checks/evidence.py)) exige que toda cita del Continuista, del Jurado y del Archivero aparezca literal, una sola vez y con 8 palabras o más en la escena que nombra, tras normalizar espacios, comillas y guiones de diálogo ([`verification.md`](../verification.md) §5.11). Una cita que no ancla descarta el veredicto como defecto de proceso, no del texto. El fallo cerrado atraviesa el sistema: sin `lake` la tirada no arranca, un modelo sin factor de contador no se admite, un embebedor que no carga impide empezar, y los dos hooks salen con 2 si no pueden evaluar.
- **Por qué aquí.** «Sin cita no hay defecto» como instrucción de prompt la cumple cualquier modelo inventándose la cita. Una cita falsa que acusa gasta reintentos en una escena sana; una que absuelve deja pasar un defecto hasta canon (§5.11). Y sin fallo cerrado, lo que no se ejecutó se lee como aprobado.
- **Límite.** Comprueba que la cita existe, jamás que sostenga lo que se afirma con ella; esa distancia está en [`verification.md`](../verification.md) §9.
- **Dónde se comprueba.** [`backend/verification/checks/test_evidence.py`](../../backend/verification/checks/test_evidence.py) (VER-19, clase A); la tasa de citas descartadas por instancia queda en la traza (VER-09).

### LLM-as-judge: el Jurado

- **Qué es.** Un modelo puntúa lo irreductiblemente subjetivo con rúbrica, justificación y cita, y varias instancias miden cuánto se fía uno de la nota.
- **Cómo se aplica aquí.** El Jurado (CAL-11) son tres instancias con las mismas rúbricas y semillas distintas ([`backend/verification/jury/verdict.py`](../../backend/verification/jury/verdict.py)), sobre nueve dimensiones de las rúbricas versión 2 ([`backend/commons/types/rubrics.py`](../../backend/commons/types/rubrics.py), `specs/srs-backend-v4.md` RF-257): continuidad, tono, arco, voz, ritmo y personalización, que son las de la entrega, más guía de estilo, subtexto y tema ([`architecture.md`](../architecture.md) §9.2). El nivel es la mediana con umbral 3; un rango de 2 niveles o más invalida el veredicto y fuerza otra ronda en vez de promediar (`specs/srs-backend-v2.md` D-39). Ve el capítulo, las rúbricas, las fichas de voz y el encargo como dato, nunca el paquete del Escritor.
- **Por qué aquí.** Tensión, subtexto y resonancia no tienen regla determinista ([`verification.md`](../verification.md) §2, regla 2), y sin persona que lea alguien tiene que juzgarlas. La dispersión es la señal de fiabilidad que sustituye a una segunda opinión humana.
- **Límite.** El verificador es otro modelo y comparte modos de fallo con el generador: detecta lo que el generador hizo mal, no lo que ambos entienden mal igual ([`verification.md`](../verification.md) §5.6). Por eso lo calibra el conjunto dorado (CAL-10, [`backend/verification/jury/golden.py`](../../backend/verification/jury/golden.py)).
- **Dónde se comprueba.** [`backend/verification/jury/test_jury.py`](../../backend/verification/jury/test_jury.py) y [`backend/verification/jury/test_rubrics_v2.py`](../../backend/verification/jury/test_rubrics_v2.py) (VER-05); VER-14 en línea; VER-19 sobre cada cita; VER-10 con el conjunto dorado y la lectura humana comparada.

### Examen de comprensión sin contexto

- **Qué es.** Un lector sin canon delante responde preguntas sobre el capítulo, y un solucionario hecho de antemano corrige sin juicio.
- **Cómo se aplica aquí.** [`backend/verification/quiz/build.py`](../../backend/verification/quiz/build.py) construye preguntas y solucionario desde la especificación de escena y el canon vigente, nunca desde el capítulo; `quiz.answer` ve solo el capítulo, sin prefijo cacheable ni fichas; [`backend/verification/quiz/grade.py`](../../backend/verification/quiz/grade.py) corrige. Cada respuesta errónea es un S2 en la puerta de capítulo, antes del Jurado ([`verification.md`](../verification.md) §5.12). Lo dispara el Orquestador en código, no un agente.
- **Por qué aquí.** Todo lo demás revisa con el canon delante, así que aprueba un capítulo coherente para quien ya sabe la respuesta y opaco para quien solo tiene el texto. Es el único método que ve que el hecho vive en el estado del mundo y no en la página.
- **Límite.** Mide que la información llegue, nunca que llegue bien contada: un capítulo plomizo y clarísimo saca un diez ([`verification.md`](../verification.md) §5.12).
- **Dónde se comprueba.** [`backend/verification/quiz/test_quiz.py`](../../backend/verification/quiz/test_quiz.py) (VER-20, clase T); el score `quiz.wrong` en Langfuse.

### Verificación formal de la historia con Lean 4

- **Qué es.** La cronología de la novela se exporta como hechos a Lean, y sus invariantes temporales se demuestran para todos los hechos a la vez, no se muestrean.
- **Cómo se aplica aquí.** [`backend/verification/formal/generate.py`](../../backend/verification/formal/generate.py) genera el fichero Lean desde la vista `chronology` del SQLite, de forma determinista, con eventos, instante, lugar, personajes presentes y fechas de nacimiento (`birth_date`; si falta, derivada de `age` y marcada como derivada, nunca inventada). El proyecto Lake en [`backend/verification/formal/lean/`](../../backend/verification/formal/lean/) define cuatro invariantes en [`StoryMaker/Invariants.lean`](../../backend/verification/formal/lean/StoryMaker/Invariants.lean): I1, nadie aparece antes de nacer y la edad cuadra; I2, nadie en dos lugares en el mismo instante; I3, ninguna vigencia termina antes de empezar; I4, nadie presente tras quedar excluido. `check.formal` corre `lake build` antes de cada congelación, retcon y enmienda, desde `loop.py:_approve_chapter` y [`backend/orchestration/amend.py`](../../backend/orchestration/amend.py) ([`architecture.md`](../architecture.md) §9.1). Un fallo es un S1 que vuelve a reparación; en una enmienda, la rechaza sin crear versión.
- **Por qué aquí.** La cronología es el único canon cuya coherencia se puede demostrar entera ([`verification.md`](../verification.md) §4.4). [`backend/evals/formal/CASOS.md`](../../backend/evals/formal/CASOS.md) documenta un caso, por mutación declarada como tal, que Lean refuta con I4 y que `check.timeline` y `check.availability` dejan pasar.
- **Límite.** Lean prueba los hechos exportados, no que la prosa los narre. Un recuerdo con fecha imposible dentro de una escena del presente no lo ve ([`verification.md`](../verification.md) §9).
- **Dónde se comprueba.** [`backend/verification/formal/test_generate.py`](../../backend/verification/formal/test_generate.py), [`backend/verification/formal/test_check.py`](../../backend/verification/formal/test_check.py) y [`backend/evals/formal/test_case.py`](../../backend/evals/formal/test_case.py); en la puerta, una fixture limpia que demuestra y otra sembrada que falla (VER-04).

### Model checking del sistema con TLA+ y TLC

- **Qué es.** El flujo de la tirada se modela como máquina de estados y un comprobador recorre todos los estados alcanzables buscando uno que rompa un invariante.
- **Cómo se aplica aquí.** [`backend/orchestration/model/run.tla`](../../backend/orchestration/model/run.tla) modela configuración, planificación, cada capítulo, caída y reanudación, enmiendas y publicación de versiones; [`chapter.tla`](../../backend/orchestration/model/chapter.tla) es el ciclo del capítulo como subacción. [`run.cfg`](../../backend/orchestration/model/run.cfg) fija un modelo pequeño —5 capítulos, 2 escenas, la escalera 3-2-1, una caída y una enmienda— con invariantes como `NeverPublishUngated`, `NoChapterDuplicated`, `NoChapterLost`, `ResumeOnlyClosed`, `PreviousVersionPreserved` y `RetriesWithinLimit`, y la vivacidad `GenerationTerminates`: toda generación acaba publicada o abortada. [`run_tlc.sh`](../../backend/orchestration/model/run_tlc.sh) guarda cada salida en `tlc/`. El [README](../../backend/orchestration/model/README.md) relaciona cada acción con su función del código (§4).
- **Por qué aquí.** Los fallos de flujo —recongelar tras una caída, perder la cuenta de reintentos— no salen en un test de ejemplo porque exigen una secuencia concreta. TLC encontró cuatro en el código, B1 a B4, cada uno con contraejemplo en `code-today/`, prueba que lo reproduce y arreglo (README §7.1). Cada invariante lo rompe al menos una mutación en `mutations/`, para descartar que sea vacuo.
- **Límite.** Prueba el flujo modelado, no el orquestador que lo implementa; esa distancia la cubre VER-05 ([`verification.md`](../verification.md) §5.10).
- **Dónde se comprueba.** VER-18, en CI al cambiar el modelo; salidas en [`backend/orchestration/model/tlc/`](../../backend/orchestration/model/tlc/).

---

## Capa 6 · Guardrails

### Guardrail de palabras prohibidas

- **Qué es.** Una lista de términos que no pueden aparecer se aplica en código sobre cada intento y sobre el capítulo entero, antes de aceptarlo.
- **Cómo se aplica aquí.** `check.forbidden` ([`backend/verification/checks/forbidden.py`](../../backend/verification/checks/forbidden.py)) es S1 en la puerta de escena y, sobre el capítulo entero, justo antes de congelar. Normaliza con [`backend/canon/normalize.py`](../../backend/canon/normalize.py) —NFKD, `casefold`, sin marcas combinantes—, compara por palabra completa y genera variantes simples: plurales en `-s` y `-es`, `z` final a `ces`, `o` y `a` finales (`specs/srs-backend-v4.md` RF-237). La lista vive en SQLite (POE-12) con tres niveles de guardarraíl: `global`, copiado de [`backend/canon/db/forbidden_global.txt`](../../backend/canon/db/forbidden_global.txt); `cliente`, de la entrevista; `novela`, de una solicitud de cambio (RF-239). Una coincidencia entra en la escalera de reintentos con el defecto y su cita; agotada, la tirada para con `RunAbortedError`, término y nivel (RF-238). Cada una deja `guardrail.match` en la traza y un score en Langfuse (RF-240).
- **Por qué aquí.** Quien encarga dice qué no quiere ver, y en un libro para una persona concreta una sola aparición es el fallo. Por subcadena, «mar» saltaría en «Marcos»; sin normalizar, «cabrón» escaparía como «cabron».
- **Límite.** Detecta la palabra, no el tema: un tema prohibido queda en [`verification.md`](../verification.md) §9. Plegar la «ñ» hace que «año» y «ano» normalicen igual, con un posible falso S1 que queda contado en la traza (§9).
- **Dónde se comprueba.** [`backend/verification/checks/test_forbidden.py`](../../backend/verification/checks/test_forbidden.py), con casos por nivel y de variante (VER-05, VER-06, VER-12); [`backend/commons/tracing/test_guardrail_export.py`](../../backend/commons/tracing/test_guardrail_export.py) para el score.

### Policy engine y audit log

- **Qué es.** Las decisiones de política se toman por reglas en orden, con un ganador siempre definido, y cada decisión queda en un registro que delata si alguien lo toca.
- **Cómo se aplica aquí.** Dentro del motor, la política es PRO-10 en [`backend/canon/arbiter/precedence.py`](../../backend/canon/arbiter/precedence.py): canon congelado sobre delta nuevo, brief sobre canon derivado, invariante duro sobre preferencia estética, hecho cobrado sobre hecho sin cobrar ([`architecture.md`](../architecture.md) §8). El audit log es la propia traza ([`backend/commons/tracing/trace.py`](../../backend/commons/tracing/trace.py)): cada registro lleva `prev_hash`, el hash del anterior, y `verify_chain` señala la primera línea editada, borrada, insertada o reordenada (`specs/srs-backend-v4.md` RF-253). Arbitraje, retcon, guardarraíl y verificación formal dejan decisión, regla e instante. Para el trabajo de desarrollo, [`.claude/hooks/policy.py`](../../.claude/hooks/policy.py) aplica cuatro reglas en orden y escribe su propia cadena en `.claude/audit/policy.jsonl`.
- **Por qué aquí.** Sin persona a quien preguntar, una política con empates o ciclos detiene el sistema. Y sin cadena, la traza que justifica cada decisión se podría retocar sin dejar rastro.
- **Límite.** La cadena no ve que se borren las últimas líneas ni el fichero entero, y el audit log de desarrollo es de cada máquina ([`verification.md`](../verification.md) §9). La traza informa una cadena rota, no para la tirada.
- **Dónde se comprueba.** [`backend/commons/tracing/test_trace.py`](../../backend/commons/tracing/test_trace.py) (VER-06 sobre la cadena), [`backend/canon/arbiter/test_precedence.py`](../../backend/canon/arbiter/test_precedence.py) (VER-05) y VER-04 sobre que PRO-10 es total y sin ciclos.

### Hooks de Claude Code

- **Qué es.** Guiones que Claude Code ejecuta antes o después de una herramienta del agente de desarrollo, para que las reglas del repositorio se cumplan sin depender de que el agente las recuerde.
- **Cómo se aplica aquí.** [`.claude/settings.json`](../../.claude/settings.json) declara dos. [`.claude/hooks/policy.py`](../../.claude/hooks/policy.py), en `PreToolUse` sobre `Write`, `Edit`, `MultiEdit`, `Read` y `Bash`, deniega escribir un `*.sqlite` de tiradas o del conjunto dorado, leer `.env*` o ficheros de claves y escribir un capítulo con términos de la lista global, y registra toda decisión (RF-252). [`.claude/hooks/chapter_gate.py`](../../.claude/hooks/chapter_gate.py), en `PostToolUse`, pasa todo `*.chapter.md` o `*.chapter.txt` por los verificadores reales de `backend/`, sin reimplementar ninguno, y devuelve los defectos al agente con código 2 (RF-251). Los dos fallan cerrados (RNF-56).
- **Por qué aquí.** El canon solo lo escribe la congelación ([`AGENTS.md`](../../AGENTS.md) §5.3.3), y una edición a mano de un SQLite sería verdad sin procedencia. Actúan sobre quien construye el sistema: los `claude -p` del motor no cargan hooks (RI-62), así que no introducen revisión humana en el ciclo.
- **Límite.** Sobre `Bash` las reglas son expresiones regulares sobre el texto del comando, y un comando ofuscado puede escapar ([`verification.md`](../verification.md) §9).
- **Dónde se comprueba.** [`backend/verification/test_policy_hook.py`](../../backend/verification/test_policy_hook.py) y [`backend/verification/test_chapter_hook.py`](../../backend/verification/test_chapter_hook.py) (VER-05, VER-12).

### Sandbox del proveedor

- **Qué es.** El proceso que llama al modelo corre con el mínimo de configuración, red y sistema de ficheros, para que una acción mala falle sin consecuencias.
- **Cómo se aplica aquí.** [`verification.md`](../verification.md) §5.3 fija el entorno: red solo hacia Claude y Langfuse, porque los embeddings son locales, sistema de ficheros acotado a la tirada y canon de solo lectura salvo para el Archivero. En el código, [`backend/commons/provider/claude_cli.py`](../../backend/commons/provider/claude_cli.py) lanza cada `claude -p` con `--setting-sources ""`, `--safe-mode`, `--strict-mcp-config` con configuración MCP vacía, sin variables `LANGFUSE_*` ni `OTEL_*` y con `MAX_THINKING_TOKENS=0` (`specs/srs-backend-v4.md` RI-62, D-133).
- **Por qué aquí.** El motor usa el CLI con la suscripción del autor. Sin estos recortes, un plugin o un hook de la máquina engancharía cada llamada de la novela y mandaría el brief a un servicio por una vía que nadie decidió ([`architecture.md`](../architecture.md) §4.8).
- **Límite.** Contiene el daño, no lo previene: un agente aislado puede escribir prosa incoherente con total libertad (§5.3).
- **Dónde se comprueba.** [`backend/commons/provider/test_claude_cli.py`](../../backend/commons/provider/test_claude_cli.py) fija la lista de argumentos y el entorno (VER-11).

---

## Capa 7 · Evaluación

### Evals del sistema

- **Qué es.** El sistema entero se mide contra un conjunto fijo de entradas y un método de puntuación, y el resultado se genera desde las trazas, nunca a mano.
- **Cómo se aplica aquí.** Cuatro piezas en [`backend/evals/`](../../backend/evals/) ([`verification.md`](../verification.md) §5.2). Cinco briefs versionados en [`evals/briefs/`](../../backend/evals/briefs/): semilla, adversarial, trampa temporal, destinatario menor con prohibiciones y dominio no deportivo. La tabla brief × verificador de [`evals/brief_table.py`](../../backend/evals/brief_table.py), una columna fija por validador, con resultado en [`evals/results/briefs.md`](../../backend/evals/results/briefs.md). El conjunto dorado de defectos sembrados (CAL-10), cada 5 capítulos, con cinco transformaciones deterministas sobre capítulos congelados. Y la lectura humana de una novela ya congelada con la rúbrica del Jurado, comparada por dimensión en [`evals/human_vs_jury.py`](../../backend/evals/human_vs_jury.py), sin umbral de acuerdo (`specs/srs-backend-v4.md` D-95).
- **Por qué aquí.** La calibración por revisión manual está prohibida dentro del ciclo (VER-13 excluido). Los evals son lo que la sustituye fuera: un Jurado que deja de ver lo sembrado ha derivado, y la lectura humana dice cuánto se separa su juicio del de una persona, sin tocar PRO-11 porque es sobre un artefacto cerrado.
- **Límite.** Un eval en verde dice que el sistema sigue haciendo lo que ese conjunto cubre, nunca que la novela sea buena ([`verification.md`](../verification.md) §5.2).
- **Dónde se comprueba.** [`backend/evals/test_brief_table.py`](../../backend/evals/test_brief_table.py), [`backend/evals/test_briefs.py`](../../backend/evals/test_briefs.py), [`backend/evals/test_temporal.py`](../../backend/evals/test_temporal.py) y [`backend/evals/test_human_vs_jury.py`](../../backend/evals/test_human_vs_jury.py) (VER-10); las tiradas reales son T52, en curso.

### Red-teaming adversarial

- **Qué es.** Buscar fallos a propósito bajo un modelo de amenaza, y dejar cada hallazgo como caso fijo para que no vuelva.
- **Cómo se aplica aquí.** [`verification.md`](../verification.md) §5.9 enumera los vectores: inyección en el brief, en su texto libre o en una enmienda; cadenas de herramientas que reescriben canon; deriva hacia la nota del Jurado; exfiltración por rutas construidas con salida de modelo; y envenenamiento de canon, la amenaza propia de este sistema. El brief [`02-adversarial.json`](../../backend/evals/briefs/02-adversarial.json) con su [texto libre](../../backend/evals/briefs/02-adversarial.texto-libre.txt) es el caso fijo, y [`evals/adversarial/real_02.py`](../../backend/evals/adversarial/real_02.py) su ejecución con el modelo real. Contra el envenenamiento la contramedida es estructural: escritura exclusiva del Archivero, arbitraje de todo delta y retcon que solo toca el hecho disputado ([`backend/canon/arbiter/retcon.py`](../../backend/canon/arbiter/retcon.py)).
- **Por qué aquí.** Tras un envenenamiento todo valida: el canon falso es coherente con la prosa que lo produjo. Solo un modelo de amenaza escrito de antemano obliga a cerrar ese camino antes de que ocurra.
- **Límite.** Solo encuentra lo que la campaña buscó, y la cobertura caduca en cuanto cambian los prompts o el modelo ([`verification.md`](../verification.md) §5.9).
- **Dónde se comprueba.** [`backend/evals/adversarial/test_campaign.py`](../../backend/evals/adversarial/test_campaign.py) y [`backend/canon/arbiter/test_retcon.py`](../../backend/canon/arbiter/test_retcon.py) (VER-17); resultado real en [`evals/results/adversarial-02.md`](../../backend/evals/results/adversarial-02.md).

### Tuning con prompts versionados

- **Qué es.** Cambiar un prompt es un despliegue: se versiona, se mide antes y después sobre la misma entrada, y la mejora se atribuye a una versión concreta.
- **Cómo se aplica aquí.** Cada agente tiene una `prompt_version`, el hash de su texto, que viaja en cada registro `call` de la traza; [`backend/orchestration/prompts_sync.py`](../../backend/orchestration/prompts_sync.py) la publica en Langfuse sin que la tirada lea nunca de allí (`specs/srs-backend-v4.md` D-86). [`backend/evals/compare.py`](../../backend/evals/compare.py) compara dos tiradas por defectos por 1.000 palabras, tasa de reparación, ocupación y dimensiones del Jurado, y dice qué versión usó cada agente. La iteración documentada es [`evals/results/tuning-01.md`](../../backend/evals/results/tuning-01.md): el brief semilla antes y después de cambiar los prompts del juez, el Especialista y el Arquitecto. La regla de promoción es VER-16: ninguna dimensión de CAL-01 puede empeorar.
- **Por qué aquí.** Tratar un prompt como una edición de texto es cómo se degrada un sistema agéntico sin que nadie sepa cuándo empezó ([`verification.md`](../verification.md) §5.8).
- **Límite.** Una comparación sobre un brief y un perfil corto detecta regresiones medibles; un aplanamiento estilístico lento cae por debajo del radar (§5.8, riesgo aceptado en §9).
- **Dónde se comprueba.** [`backend/evals/test_compare.py`](../../backend/evals/test_compare.py) y [`backend/orchestration/test_prompts_sync.py`](../../backend/orchestration/test_prompts_sync.py) (VER-10, VER-16).

---

## Capa 8 · Observabilidad

### Observabilidad con Langfuse

- **Qué es.** Toda ejecución deja una trayectoria consultable —qué entró, qué se llamó, cuánto costó, qué falló— porque en un sistema sin supervisión es el único modo de ver que algo se lleva diez capítulos degradando.
- **Cómo se aplica aquí.** La fuente de verdad es un JSONL append-only por novela, junto a su SQLite ([`backend/commons/tracing/trace.py`](../../backend/commons/tracing/trace.py)). Langfuse es su espejo ([`backend/commons/tracing/langfuse_export.py`](../../backend/commons/tracing/langfuse_export.py)), con un conductor en vivo y otro por lote que pliegan la misma función: una traza por generación —tirada, enmienda, solicitud de cambio o entrevista— con `session_id` igual a la novela; spans de capítulo y escena; una generation por llamada con nombre `<rol>.<agente>`, tokens, coste, latencia y prompt enlazado; un span por herramienta; y los resultados de verificadores, Jurado, Lean y guardarraíl como scores ([`architecture.md`](../architecture.md) §11). El coste es el equivalente de API que da el CLI, nunca calculado aquí.
- **Por qué aquí.** Sin traza no hay eval reproducible, ni diagnóstico de deriva, ni evidencia de un ataque ([`verification.md`](../verification.md) §5.1). Que el espejo no gobierne es deliberado: un fallo al exportar deja `export.failed` y la tirada sigue, porque parar una novela por no poder registrar una llamada daría a la observabilidad un poder que no le toca.
- **Límite.** Observa, no juzga: dice qué pasó, nunca si estuvo bien (§5.1). La ingestión solo admite generation, span y event, así que `retriever`, `tool`, `evaluator` y `guardrail` viajan como span con el tipo en metadatos ([`architecture.md`](../architecture.md) §11).
- **Dónde se comprueba.** [`backend/commons/tracing/test_langfuse_export.py`](../../backend/commons/tracing/test_langfuse_export.py) y [`backend/orchestration/test_observability.py`](../../backend/orchestration/test_observability.py): todo tipo de registro está clasificado como con score o sin él (VER-09).

---

## Capa 9 · Cambio y lectura

### Retcon, enmiendas y versiones

- **Qué es.** Una obra ya congelada se puede cambiar, pero solo por un proceso explícito que decide solo, toca lo mínimo y conserva lo que había.
- **Cómo se aplica aquí.** Dos caminos. El retcon (CAN-10), que el sistema se propone a sí mismo, lo propone el Árbitro y lo admite el código en [`backend/canon/arbiter/retcon.py`](../../backend/canon/arbiter/retcon.py): solo si el hecho no está cobrado en ningún payoff y hay 3 pasajes o menos que tocar ([`architecture.md`](../architecture.md) §8). La enmienda al brief, que pide quien encarga desde la lectura, la aplica [`backend/orchestration/amend.py`](../../backend/orchestration/amend.py) entre congelaciones: `amend.interpret` la traduce a exactamente una entidad y un atributo, el Orquestador localiza las escenas que usan el hecho por `fact_usage`, las repara con el hecho nuevo como canónico, las reverifica, pasa Lean y las recongela en una transacción ([`backend/canon/arbiter/refreeze.py`](../../backend/canon/arbiter/refreeze.py)). La versión anterior (PRO-08) se conserva entera.
- **Por qué aquí.** Sin regla, un cambio pedido obligaría a regenerar la novela o a que alguien decidiera qué tocar. Con procedencia `brief` gana al canon derivado por PRO-10, y si contradice un invariante duro se rechaza con su motivo en vez de elegir por quien pide.
- **Límite.** Solo se reescriben las escenas que nombran el hecho; una consecuencia narrativa indirecta que no lo nombre no se localiza. La regeneración pasa las mismas puertas que la escritura original, que tienen sus propios límites.
- **Dónde se comprueba.** [`backend/orchestration/test_amend.py`](../../backend/orchestration/test_amend.py), [`backend/orchestration/test_fact_usage.py`](../../backend/orchestration/test_fact_usage.py) y [`backend/canon/arbiter/test_retcon.py`](../../backend/canon/arbiter/test_retcon.py) (VER-05); invariantes TLA+ «lo que mostraba una versión al dejar de ser la vigente es lo que sigue mostrando» y «una enmienda solo se aplica entre congelaciones» (VER-18), con el contraejemplo B2.

### Lectura interactiva con frontend observador

- **Qué es.** La obra se lee por versiones, con índice, portada y ficha enlazada a los capítulos, desde una interfaz que muestra y encarga pero nunca aprueba.
- **Cómo se aplica aquí.** [`frontend/manuscript/`](../../frontend/manuscript/) sirve la lectura por versiones con marca de capítulos cambiados y la solicitud de cambio desde un fragmento o un hecho; [`frontend/story-bible/`](../../frontend/story-bible/) la ficha de personajes y lugares, derivada del canon y enlazada a donde aparece cada entrada; [`frontend/interview/`](../../frontend/interview/) la entrevista. El contrato es el OpenAPI que genera FastAPI, y el cliente del frontend se genera desde él ([`architecture.md`](../architecture.md) §2.2).
- **Por qué aquí.** Cualquier interacción que condicione el ciclo reintroduce por la puerta de atrás la aprobación manual que PRO-11 prohíbe (§2.1). Por eso lo único que entra por el frontend son encargos, y un encargo cambia lo que se pide, no revisa lo que se escribió.
- **Límite.** El frontend muestra proyecciones; su corrección depende de las del backend. VER-08 garantiza que un cambio incompatible rompe la compilación, no que la pantalla enseñe lo correcto.
- **Dónde se comprueba.** `node gate.mjs` en [`frontend/`](../../frontend/) con `tsc --strict`, `eslint` y `vitest` (VER-01, VER-02, VER-05); el contrato HTTP con `schemathesis` en [`backend/orchestration/test_contract.py`](../../backend/orchestration/test_contract.py) (VER-08).

### Validación visual con MCP de navegador

- **Qué es.** Un agente abre la novela en un navegador real, la recorre y comprueba lo que un test de componente no ve, y el mismo recorrido existe como guion repetible sin agente.
- **Cómo se aplica aquí.** [`.mcp.json`](../../.mcp.json) declara el MCP de navegador de Playwright para la demostración con agente; [`frontend/visual/tour.mjs`](../../frontend/visual/tour.mjs) es el recorrido repetible de portada, índice y ficha, sobre una novela sembrada sin modelo por [`frontend/visual/seed.py`](../../frontend/visual/seed.py). [`frontend/visual/verdict.ts`](../../frontend/visual/verdict.ts) decide qué pasa, qué falla y a qué mitad vuelve el fallo: de datos al backend, de presentación al frontend (`specs/srs-backend-v4.md` RF-267, RI-69).
- **Por qué aquí.** La portada con dedicatoria y el índice navegable son parte de lo que se entrega, y un fallo visual con los datos correctos no lo detecta ningún validador del backend. Enviar el fallo a la mitad que corresponde es la misma idea que devolver un defecto al rol que lo produjo.
- **Límite.** Un servidor MCP de proyecto lo aprueba la persona en una sesión interactiva; mientras no se apruebe, el recorrido se demuestra con el guion (RI-69). El recorrido solo mira lo que su guion nombra.
- **Dónde se comprueba.** [`frontend/visual/verdict.test.ts`](../../frontend/visual/verdict.test.ts), que corre en `node gate.mjs` (VER-05); el recorrido con navegador queda fuera de la puerta porque necesita Python, `uvicorn` y el navegador instalado.
