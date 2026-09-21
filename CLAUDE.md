# CLAUDE.md

Instrucciones operativas para Claude Code en este repositorio.

> **Lee primero [`AGENTS.md`](AGENTS.md).** Contiene el contexto del proyecto, el índice de documentación y las reglas de trabajo. Este archivo no las repite: añade cómo operar sobre el repositorio.

---

## 1. Lo mínimo que hay que saber antes de actuar

- Proyecto: sistema **autónomo** de generación de novelas largas (épica deportiva como caso de referencia).
- **Fase de especificación. No hay código y no debe crearse** salvo petición explícita.
- Dos restricciones absolutas: **cero intervención humana** en el ciclo y **ventana de 100.000 tokens** por llamada.
- Documentación en [`docs/`](docs/): [definitions](docs/definitions.md) · [domain-knowledge](docs/domain-knowledge.md) · [architecture](docs/architecture.md) · [validations](docs/validations.md).

---

## 2. Qué leer según la tarea

No hace falta leerlo todo cada vez. Carga lo que corresponda:

| Tarea | Lee |
|---|---|
| Añadir o cambiar un término | `definitions.md` completo; los diagramas que lo usen |
| Cambiar un diagrama | `domain-knowledge.md` §1 y el diagrama concreto; `definitions.md` para los IDs |
| Tocar agentes, skills o contexto | `architecture.md` §4 a §7 |
| Tocar validaciones o umbrales | `validations.md` completo |
| Responder una duda de dominio | `definitions.md`; el resto solo si hace falta |

Si la tarea afecta a más de un documento, léelos todos antes de escribir nada. Editar uno y dejar los otros desalineados es el fallo más caro de este repositorio.

---

## 3. Reglas de edición

1. **Ediciones quirúrgicas.** Modifica solo lo que la tarea pide. No reescribas un documento entero para cambiar una tabla, ni reformatees secciones que no tocas.
2. **IDs estables.** Nunca renumeres, reasignes ni recicles un ID. Al retirar un término, márcalo como obsoleto con su sustituto.
3. **Propagación obligatoria.** Un cambio conceptual toca los cuatro documentos o ninguno. Consulta la tabla de `AGENTS.md` §5.2.
4. **Referencias por ID**, nunca por nombre, entre documentos.
5. **Sin frontera nueva sin dueño.** Si tu cambio introduce una decisión, dale regla de precedencia, umbral numérico o agente responsable. Si no puedes, el diseño no está terminado y hay que decirlo, no taparlo.
6. **Sin pasos manuales.** Si al diseñar te sale "revisar", "aprobar" o "confirmar" por parte de una persona, es un error. Sustitúyelo.
7. **Nada de inventar números.** Presupuestos de tokens, umbrales y severidades salen de los documentos. Si hace falta uno nuevo, decláralo como propuesta y explica de dónde sale.

---

## 4. Estilo de escritura

- **Español** en la prosa. **Inglés** en identificadores técnicos, nombres de skills y claves de datos (`scene.write`, `canon.query`, `check.timeline`).
- Frases cortas y directas. Sin relleno, sin énfasis decorativo, sin fórmulas de transición vacías.
- Tablas cuando hay más de dos atributos por elemento; listas solo para enumeraciones simples.
- Cada afirmación de diseño lleva su porqué cuando no es obvio. Una regla sin motivo se salta en la primera implementación.
- Cada documento de `docs/` abre con el bloque de referencias cruzadas a los otros tres. Si creas uno nuevo, incluye el bloque y añádelo al índice de `AGENTS.md` §3 y §4.

---

## 5. Mermaid

Los diagramas son parte del contenido, no decoración. Reglas para que rendericen:

- Etiquetas de nodo **siempre entre comillas**: `A["Escena · EST-08"]`.
- Nada de paréntesis, corchetes ni comillas dentro de las etiquetas.
- Un identificador no puede ser a la vez nodo y `subgraph`.
- En `erDiagram`, nombres de entidad en mayúsculas sin espacios y etiquetas de relación en una sola palabra con guiones bajos.
- Prefiere `graph TD`/`graph LR` y `stateDiagram-v2`. Evita tipos exóticos con soporte irregular.
- Comprueba mentalmente el diagrama antes de darlo por bueno: un diagrama roto es peor que ninguno, porque oculta la información en vez de mostrarla.

---

## 6. Trabajo autónomo

- Si la tarea es clara, hazla. No pidas confirmación para cada paso.
- Si hay ambigüedad real de diseño, plantea la opción que recomiendas y por qué, en lugar de devolver la pregunta en crudo.
- Señala las inconsistencias que encuentres de paso, aunque estén fuera del encargo. No las arregles sin decirlo.
- Di lo que no hiciste y por qué. Un cambio incompleto anunciado es recuperable; uno silencioso, no.

---

## 7. Definición de terminado

Un cambio está listo cuando:

- [ ] Usa el vocabulario y los IDs de `definitions.md`
- [ ] Respeta las seis restricciones de `AGENTS.md` §5.3
- [ ] Cabe en 100.000 tokens con el presupuesto de su agente
- [ ] Tiene una validación en `validations.md` que compruebe que funciona
- [ ] Los cuatro documentos siguen coherentes entre sí
- [ ] Los diagramas Mermaid afectados renderizan
- [ ] No ha introducido ningún paso de aprobación manual

---

## 8. Lo que no hay que hacer

- Crear agentes, skills o código de implementación sin petición explícita.
- Reescribir un documento entero por un cambio local.
- Introducir revisión humana en cualquier forma.
- Llenar la ventana de contexto porque quepa: 100.000 tokens es un techo, no un objetivo.
- Dar por buena una validación sin evidencia localizable.
