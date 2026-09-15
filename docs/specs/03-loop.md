# Spec 03: Ciclo de ejecución

## 1. Máquina de estados de una escena

```
  planned
     │ PLANNER
     ▼
  beat_sheet ──► DRAFTER ──► drafted
                                │
                                ▼
                          ┌───────────┐
                          │ VALIDATOR │ (código, ~0 coste)
                          └─────┬─────┘
                       ERROR    │    limpio
                   ┌────────────┴──────────────┐
                   ▼                           ▼
              needs_revision            ┌────────────┐
                   ▲                    │   CRITIC   │ (4 lentes en paralelo)
                   │                    └──────┬─────┘
                   │           veto canon      │      ok / warn
                   ├───────────────────────────┤
                   │                           ▼
              [REVISER]                score_lit < umbral ?
                   │                     sí │        │ no
                   └────────────────────────┘        ▼
                   (attempt++, máx 3)            approved
                                                     │
                            ┌────────────────────────┘
                            ▼
                     [LEDGER_WRITER] ──► commit
                            │
                            ▼
                   ¿última escena del capítulo?
                            │ sí
                            ▼
                    ╔═══════════════════╗
                    ║   GATE HUMANO     ║  (D2)
                    ║ aprobar / revisar ║
                    ║ / rehacer capítulo║
                    ╚═══════════════════╝
```

Si `attempt > 3` → estado `escalated`, el ciclo se detiene y pregunta al humano.
Nunca hay bucle infinito.

## 2. Presupuestos y guardarraíles

| Guardarraíl | Valor por defecto | Motivo |
|---|---|---|
| `max_revisions_per_scene` | 3 | evita loop de coste |
| `max_tokens_per_chapter` | configurable | corta descarrilamientos caros |
| `critic_blind_to_attempt` | true | si el crítico sabe que es el intento 3, aprueba por complacencia |
| `checkpoint` | commit por escena aprobada | rollback gratis |
| `seed / log de cada llamada` | siempre | sin esto no se puede depurar el cap. 12 |

## 3. Empaquetado selectivo de contexto (context packing)

El `DRAFTER` **nunca** recibe la novela entera. Recibe:

```
┌─ SIEMPRE ────────────────────────────────────┐
│ premise.lock.yaml  (completo, es corto)      │
│ style.md                                     │
├─ VENTANA ────────────────────────────────────┤
│ resumen de las 2 escenas anteriores          │
│ texto completo de la escena anterior         │
│ beat sheet de la escena siguiente            │
├─ SELECTIVO ──────────────────────────────────┤
│ ficha de los personajes en `scene.present`   │
│   → con estado RESUELTO a scene.date:        │
│     "Marco, 28 años, lesionado hasta 04-05"  │
│ hechos del ledger que los involucran         │
│ hilos abiertos que vencen en este capítulo   │
└──────────────────────────────────────────────┘
```

> Clave: al DRAFTER se le entrega el estado **ya resuelto a la fecha de la escena**,
> no el YAML crudo. No debe calcular edades ni interpretar rangos: si lo hace, se equivoca.

## 4. Modos de ejecución

| Modo | Uso |
|---|---|
| `outline` | genera y valida solo el timeline (dry-run) |
| `scene <id>` | genera una escena concreta |
| `chapter <n>` | genera hasta el gate humano del capítulo n |
| `revalidate` | re-ejecuta el validador sobre toda la obra (tras cambiar canon) |
| `audit` | informe de coherencia global sin generar nada |

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial. Máquina de estados de la escena, guardarraíles de presupuesto, empaquetado selectivo de contexto y modos de ejecución. |
