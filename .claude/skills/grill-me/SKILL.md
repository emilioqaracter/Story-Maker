---
name: grill-me
description: "Interrogatorio previo de Story-Maker. Entrevista por rondas antes de tocar la ontología, una spec o el código, según AGENTS.md §6.1."
disable-model-invocation: true
---

# Interrogatorio previo

Lanza la entrevista por rondas de `AGENTS.md` §6.1. Solo la persona puede invocarla, con `/grill-me`.

Llama a la skill `grilling` para el protocolo de la entrevista. Lo de abajo es lo que este repositorio añade encima.

## 1. Comprobar el umbral

> El cambio **introduce una decisión con dueño, un número nuevo, un ID nuevo o una frontera nueva**.

Si lo cruza, sin respuestas no se edita: no se procede declarando supuestos. Si no lo cruza —errata, enlace roto, reformateo, renombrar un fichero— se hace y se dice, sin entrevista.

Añadir o retirar un término siempre lo cruza. Cambiar la redacción de una definición sin cambiar lo que designa, no.

## 2. Preguntar según lo que se toca

`AGENTS.md` §6.2, §6.3 y §6.4 fijan las preguntas obligadas de cada proceso. Cárgalas antes de la primera ronda.

| Si tocas | Proceso | Lee antes |
|---|---|---|
| `definitions.md`, `domain-knowledge.md` | A | `AGENTS.md` §6.2 · invoca además `domain-modeling` |
| `architecture.md`, `verification.md` | B | `AGENTS.md` §6.3 y §4.1 |
| `backend/`, `frontend/` | C | `AGENTS.md` §6.4 y `verification.md` §8 |

**Leer antes de preguntar.** No interrogues sobre algo que el documento ya responde: es la forma más rápida de gastar la paciencia de quien contesta.

## 3. Reglas de este repositorio durante la entrevista

- **Toda pregunta va con la respuesta que recomiendas y su porqué** (`AGENTS.md` §9). Devolver la pregunta en crudo traslada el trabajo en vez de hacerlo.
- **Nada de inventar números.** Presupuestos, umbrales y severidades salen de los documentos. Uno nuevo se declara como propuesta y se explica de dónde sale.
- **Sin frontera nueva sin dueño.** Si el cambio introduce una decisión, necesita regla de precedencia, umbral numérico o agente responsable. Si no puedes dárselo, el diseño no está terminado: dilo, no lo tapes.
- **Si aparece un término que no está en `definitions.md`, para y ejecuta el proceso A.** Colar vocabulario nuevo dentro de un cambio de spec es como se degrada una ontología.
- Prosa en **español**; identificadores técnicos en inglés (`scene.write`, `canon.query`).

## 4. Al terminar

No edites hasta que la persona confirme que hay entendimiento compartido. Después, ejecuta el cambio entero sin volver a pedir confirmación paso a paso, y ciérralo contra la Definición de terminado de `AGENTS.md` §10.
