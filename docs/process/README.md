# docs/process

> Documentación de proceso · ver [`../../AGENTS.md`](../../AGENTS.md) para el índice completo.
> Relacionados: [definitions](../definitions.md) · [domain-knowledge](../domain-knowledge.md) · [architecture](../architecture.md) · [verification](../verification.md)

Los cuatro documentos de `docs/` dicen **qué sistema es**. Esta carpeta dice **cómo se llegó a él**: qué se decidió, con qué opciones delante, qué lo hizo cambiar y qué se intentó romper.

Regla de fondo: **no se corrige el resultado, se corrige el razonamiento que llevó a él.** Cuando una tirada, una eval, TLC o Lean encontraron un fallo, el arreglo no se queda en el síntoma. Se corrige la decisión o la spec que lo permitió, y aquí consta la causa y el efecto.

## Índice

| Documento | Qué responde |
|---|---|
| [01-spec-inicial.md](01-spec-inicial.md) | Qué se decidió construir y por qué, antes de escribir código |
| [02-trade-offs.md](02-trade-offs.md) | Cada decisión de diseño relevante como decisión: opciones, criterios, elección y coste aceptado |
| [03-explainers.md](03-explainers.md) | Un explainer breve por cada concepto del curso aplicado en el proyecto |
| [04-diagramas.md](04-diagramas.md) | Arquitectura del harness, máquina de estados de TLA+, esquema SQLite y tabla de validadores con su punto de ejecución |
| [05-iteraciones.md](05-iteraciones.md) | Qué cambió tras cada eval, tirada o contraejemplo de TLC o Lean, y por qué |
| [06-red-team.md](06-red-team.md) | Casos adversariales probados, qué validador los detectó o no, y cómo se resolvió |

## Reglas de esta carpeta

- **No es fuente de verdad del diseño.** Si algo de aquí contradice a `docs/`, `specs/` o el código, lo que manda es el documento de mayor altura. Esta carpeta se corrige para que coincida con ellos, nunca al revés (`AGENTS.md` §6.7).
- **No introduce IDs de dominio.** Las anclas locales `TO-n`, `IT-n` y `RT-n` solo sirven para enlazar dentro de la carpeta. Todo lo demás se cita por su ID estable: `D-NN`, `RF-NN`, `VER-NN`, `CTX-NN`.
- **Solo el estado actual de la rama** (`AGENTS.md` §5.5). Lo que se cuenta sale de los documentos, los resultados de eval y el código de hoy, no del historial de git.
