# Spec 02: Contrato de agentes

Cada agente se define por: **entrada**, **salida**, **permisos** y **criterio de fallo**.
Implementación concreta en spec 09 (Claude Code) y spec 10 (OpenRouter).

## Matriz de permisos y runtime

| Agente | Runtime (D1/D1b) | Lee Store | Escribe Store | Escribe prosa |
|---|---|:--:|:--:|:--:|
| PREMISE_INTERVIEWER | subagente Claude | — | ① solo al congelar | — |
| RESEARCHER | subagente Claude + WebSearch | ① | ⑦ (revisión humana) | — |
| OUTLINER | subagente Claude | ①④⑦ | ② (propuesta) | — |
| PLANNER | subagente Claude | todo | — | — |
| DRAFTER | **OpenRouter `:free`** | empaquetado | — | ✔ |
| VALIDATOR | **script Python** | todo | — | — |
| CRITIC (4 lentes) | **subagentes Claude, en paralelo** | todo | — | — |
| REVISER | **OpenRouter** (int. 1-2) → Claude (int. 3) | todo | — | ✔ |
| LEDGER_WRITER | **script Python** | todo | ✔ **exclusivo** | — |

El reparto no es arbitrario: OpenRouter absorbe el **volumen** de tokens (prosa),
Claude aporta el **juicio** (plan y crítica), y los pasos con respuesta correcta
única son código. Ver spec 09 §1.

> Regla de oro: si dos agentes pudieran escribir el estado, el estado se corrompe.
> Solo `LEDGER_WRITER` escribe, y solo tras la aprobación.

---

## 1. PREMISE_INTERVIEWER
- **Entrada:** petición libre del usuario ("un futbolista en 1990").
- **Trabajo:** entrevista corta para resolver ambigüedades (país, nivel competitivo,
  tono, final buscado). Traduce intención en `hard_constraints` verificables.
- **Salida:** `premise.lock.yaml`, presentado al usuario para confirmación.
- **Fallo:** si el usuario no confirma, no se congela nada.

## 2. RESEARCHER  *(solo si `reality_mode != fiction`)*
- **Entrada:** `axis.sport`, `axis.era`.
- **Salida:** corpus de hechos verificables (calendario, resultados, contexto
  social), cada uno con `source` y `confidence`. Alimenta `fixed_events` y la regla P03.
- **Fallo:** un hecho sin fuente no entra al corpus; se marca como `fiction`.

## 3. OUTLINER
- **Entrada:** ①④ + corpus.
- **Salida:** `world-timeline.yaml` completo con todas las escenas en estado `planned`.
- **Gate:** antes de escribir prosa se ejecuta el **dry-run** (spec 04). Si el
  timeline es imposible, se replantea. Coste: casi cero.

## 4. PLANNER (por escena)
- **Entrada:** escena `planned` + contexto empaquetado.
- **Salida:** *beat sheet* de la escena: objetivo dramático, conflicto, giro,
  qué hechos nuevos establece, qué hilos toca.
- Separa el "qué pasa" del "cómo se escribe": mejora ambos.

## 5. DRAFTER
- **Entrada:** beat sheet + **paquete de contexto selectivo** (spec 03 §3).
- **Salida:** prosa de la escena + declaración estructurada de hechos nuevos
  (`proposed_facts`) que el ledger registrará si se aprueba.
- **Regla:** puede escribir tiempo relativo en la prosa ("la semana pasada"),
  pero sus `proposed_facts` van con fecha absoluta.

## 6. VALIDATOR
- Código, no LLM. Ver spec 04.

## 7. CRITIC (panel de 4 lentes)
- Ver spec 05. **No reescribe nunca**: solo diagnostica.

## 8. REVISER
- **Entrada:** prosa + findings del validador + findings del crítico.
- **Salida:** prosa corregida. Cambios **mínimos y quirúrgicos**: no reescribe
  de cero, para no introducir violaciones nuevas.
- **Fallo:** tras 3 iteraciones sin pasar, escala al humano.

## 9. LEDGER_WRITER
- **Entrada:** escena aprobada + `proposed_facts`.
- **Trabajo:** anexa al ledger, actualiza `state_timeline` y `knowledge` de los
  personajes presentes, avanza `clock.cursor`, abre/cierra hilos, marca la escena
  `approved`, hace commit.
- **Fallo:** si un `proposed_fact` contradice el canon existente, rechaza la
  escena y la devuelve al ciclo (última red de seguridad).

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial. Contrato de los 9 agentes y matriz de permisos con la regla de escritura exclusiva del LEDGER_WRITER. |
| 0.2 | 2026-09-15 | emilioqaracter | La matriz incorpora la columna de runtime (D1/D1b): reparto entre scripts, OpenRouter y subagentes de Claude Code. |
