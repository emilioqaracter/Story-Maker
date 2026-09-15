# Story-Maker — Spec 00: Visión general

**Versión:** 0.4 (borrador) · **Fecha:** 2026-09-15 · **Estado:** en diseño

## 1. Propósito

Harness agéntico que genera novelas de temática deportiva manteniendo
consistencia de canon, temporal y de personajes a lo largo de toda la obra.

## 2. Decisiones fundacionales (cerradas)

| ID | Decisión | Valor |
|----|----------|-------|
| D1 | Stack | **Claude Code**: subagentes (`.claude/agents/`) + skill + scripts. Sin infra propia. |
| D1b | Motor de prosa | **OpenRouter, modelos `:free`**, invocado por script desde Bash (spec 10). Claude no escribe la novela. |
| D2 | Unidad de generación | **Escena**, con *gate* de aprobación humana al cerrar cada capítulo. |
| D3 | Relación con la realidad | **Híbrido**: protagonista y trama ficticios, mundo deportivo real (competiciones, calendario, clubes). |
| D4 | Autoridad del crítico | **Veto duro** en canon/continuidad/temporalidad; **consultivo** en calidad literaria (con umbral configurable). |
| D5 | Alcance deportivo | **Fútbol primero**, con `sport` modelado como plugin extensible. |
| D6 | Research | **Corpus curado**: generado una vez, revisado por humano, congelado. Toda verificación va contra él. |
| D7 | Retcon | **Permitido con revalidación en cascada** (spec 07). |
| D8 | Formato objetivo | Español, novela corta: ~40k palabras, 10-12 capítulos, ~45 escenas. |
| D14 | Personajes reales | **Permitidos**, con un único requisito de admisión: tener perfil en Wikipedia (spec 11). |

## 3. Principio rector

> La consistencia factual se **calcula**, no se recuerda.
> El LLM juzga únicamente lo que el código no puede verificar.

Corolarios:
- Toda fecha en el estado es absoluta (ISO-8601). "La semana pasada" solo existe en la prosa.
- Ningún dato derivable se almacena (la edad se calcula desde `birth_date`).
- Un único agente tiene permiso de escritura sobre el Context Store.

## 4. Flujo de alto nivel

```
Usuario ──► [PREMISE INTERVIEWER] ──► premise.lock.yaml (CONGELADO)
                                            │
                                            ▼
                              [OUTLINER] ──► world-timeline.yaml
                                            │  (dry-run: valida el
                                            │   timeline completo
                                            │   antes de escribir prosa)
                                            ▼
        ┌────────────────── CICLO POR ESCENA ───────────────────┐
        │  PLANNER ─► DRAFTER ─► VALIDATOR ─► CRITIC ─► REVISER │
        │                        (código)     (LLM)      ▲      │
        │                            │          │        │      │
        │                            └──────────┴────────┘      │
        │                              máx. 3 iteraciones       │
        └───────────────────────┬───────────────────────────────┘
                                ▼ aprobada
                         [LEDGER WRITER] ──► actualiza Context Store
                                ▼
                     ¿fin de capítulo? ──► GATE HUMANO
```

## 5. Índice de specs

| Archivo | Contenido |
|---|---|
| `01-context-store.md` | Los 6 archivos de contexto y sus esquemas |
| `02-agents.md` | Contrato de cada agente (entrada/salida/permisos) |
| `03-loop.md` | Máquina de estados, reintentos, gates, presupuestos |
| `04-validators.md` | Reglas deterministas de continuidad y temporalidad |
| `05-critic-rubric.md` | Panel crítico y rúbrica de evaluación |
| `06-open-questions.md` | Decisiones pendientes |
| `07-retcon.md` | Revalidación en cascada al cambiar canon aprobado |
| `08-sport-plugin.md` | Contrato del módulo de deporte (fútbol como primera implementación) |
| `09-runtime-claude-code.md` | Mapeo a subagentes, skill y scripts; quién corre dónde |
| `10-openrouter.md` | Adaptador de modelos, límites del tier gratuito, prompting para modelos débiles |
| `11-real-figures.md` | Personajes reales: admisión por Wikipedia y niveles de interacción |

## 6. Convención de versionado

Todo documento de `docs/specs/` termina con un **Historial de revisiones**. Reglas:

- El historial se actualiza **en el mismo commit** que el cambio que documenta.
  Una spec modificada sin línea nueva de historial es un cambio incompleto.
- Numeración `0.x` mientras el diseño esté abierto; `1.0` cuando se implemente.
- Una entrada por cambio sustantivo. Correcciones de estilo o tipografía no
  generan versión nueva.
- Cuando un cambio cierra o revisa una decisión, la entrada **cita su ID** (D1, D7…)
  para poder rastrear el porqué desde cualquier documento.
- La versión de esta portada refleja el estado del **conjunto** de specs, no solo
  el de este archivo.

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial. Decisiones D1-D4, principio rector, flujo de alto nivel e índice de specs. |
| 0.2 | 2026-09-15 | emilioqaracter | Cierre de la ronda 2: decisiones D5-D8. Añadidas al índice las specs 07 (retcon) y 08 (plugin de deporte). |
| 0.3 | 2026-09-15 | emilioqaracter | D1 redefinida: el harness pasa a ser Claude Code. Nueva D1b: la prosa se genera con OpenRouter. Añadidas al índice las specs 09 y 10. |
| 0.4 | 2026-09-15 | emilioqaracter | Cierre de D14: personajes reales admitidos con criterio Wikipedia. Añadida al índice la spec 11. Incorporada la convención de versionado de documentos. |
