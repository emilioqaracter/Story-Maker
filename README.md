# Story-Maker

Un sistema de agentes que escribe una **novela corta** y deja ver, paso a paso,
cómo la escribió.

La novela es la excusa. Lo que se está construyendo es un **sistema agéntico
observable**: unos agentes escriben, otros aprueban o rechazan, y todo lo que
se decide queda anotado con su motivo.

> Todo lo que se decide, lo decide un agente, y deja escrito por qué.

- [docs/SPEC-FUNCIONAL.md](docs/SPEC-FUNCIONAL.md): qué hace el sistema y por qué.
- [docs/SPEC-TECNICO.md](docs/SPEC-TECNICO.md): archivos, contratos y formatos.

## Cómo se usa

Se le pide a Claude Code, en la terminal o en VS Code:

```
> una novela sobre una ciclista que vuelve de una caída, unas 15.000 palabras
```

**La sesión de Claude Code es el orquestador.** Sigue la skill
`dirigir-novela`, despacha a los agentes, lee sus veredictos y aprueba los
capítulos que pasan. No hay ningún programa por debajo: el repositorio no tiene
una sola línea de código.

## Los cinco agentes

| Agente | Qué hace |
|---|---|
| **arquitecto** | convierte la idea y la longitud en el plan de la novela |
| **director** | dice qué toca ahora, cuando no está claro cómo seguir |
| **redactor** | escribe el capítulo, y lo reescribe si le dan luz roja |
| **revisor** | ¿está bien escrito este capítulo? |
| **verificador** | ¿encaja este capítulo en la historia? |

Ningún agente aprueba su propio trabajo, y Claude Code no puede decidir que un
capítulo está bien.

## El círculo de aprobación

Se repite una vez por capítulo. Dos luces verdes y el capítulo entra en la
novela. Una luz roja y vuelve al redactor con el motivo.

```
  REDACTOR ──► borrador ──► REVISOR ──► VERIFICADOR ──► el capítulo entra
      ▲                        │             │
      └──── luz roja ──────────┴─────────────┘
            y el motivo
```

Toda luz roja dice qué está mal, dónde con una cita, y qué cambiar, y le llega
al redactor entera, sin resumir. Un capítulo corregido vuelve a entrar por el
principio: las dos luces se piden de nuevo. A los tres intentos sin aprobar, el
capítulo se para y decide la persona.

## Ver lo que pasó

**El estado es la carpeta de la novela.** No hay contadores escondidos ni
archivo de estado:

```bash
ls books/<slug>/capitulos books/<slug>/decisiones
head -1 books/<slug>/decisiones/*.md
```

Un capítulo aprobado es el que no lleva `borrador` en el nombre. Cada juicio es
un archivo con su veredicto, su motivo y su hora, así que el historial de
decisiones no puede quedar incompleto: escribirlo **es** decidir.

Los nombres cuentan el camino solos: un intento con archivo de revisor y ninguno
de verificador es un borrador que no pasó de la primera puerta.

Hay una novela completa de ejemplo en `books/ciclista-2010/`.

Para los tiempos y los costes está **Langfuse**, con su plugin oficial para
Claude Code:

```bash
claude plugin marketplace add langfuse/Claude-Observability-Plugin
claude plugin install langfuse-observability@langfuse-observability
```

## Capas que se pueden apagar

| Capa | Qué aporta | Si se apaga |
|---|---|---|
| el plan | arquitecto y redactor | no hay novela |
| las decisiones en disco | qué se decidió y por qué | escribe a ciegas |
| el revisor | luz roja por cómo está escrito | entra todo |
| el verificador | luz roja por coherencia | los capítulos se contradicen |
| el director | el turno lo decide un agente | se decide leyendo la carpeta |
| Langfuse | tiempos, costes y comparar corridas | las decisiones siguen enteras |
