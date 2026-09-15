# Spec 04: Validadores deterministas

Se ejecutan **antes** del crítico LLM. Son gratis, instantáneos y fiables al 100%.
Filtran el ruido para que el crítico gaste juicio solo en lo que no se puede calcular.

## Severidades

| Nivel | Efecto |
|---|---|
| `ERROR` | Bloquea. Va a REVISER con la regla violada. |
| `WARN`  | No bloquea; se adjunta al contexto del crítico. |
| `INFO`  | Solo log. |

---

## Catálogo de reglas

### Grupo T — Temporalidad de la historia
| ID | Regla | Sev |
|---|---|---|
| T01 | Toda escena tiene `date` absoluta y válida | ERROR |
| T02 | `date` dentro de `premise.axis.era` (HC1) | ERROR |
| T03 | Las escenas de un capítulo son cronológicamente monótonas salvo `flashback: true` | ERROR |
| T04 | Un flashback declara `frame_date` (cuándo se recuerda) y `event_date` | ERROR |
| T05 | Ningún personaje aparece en dos escenas solapadas en el tiempo | ERROR |
| T06 | El viaje entre localizaciones consecutivas es factible en el tiempo transcurrido | WARN |
| T07 | La escena no contradice un `fixed_event` del mundo | ERROR |

### Grupo C — Temporalidad del personaje
| ID | Regla | Sev |
|---|---|---|
| C01 | Toda edad mencionada en prosa coincide con `age_at(scene.date)` | ERROR |
| C02 | **Un `recurring_event` anual no ocurre dos veces en el mismo año** | ERROR |
| C03 | Un `life_event` con `unique: true` aparece una sola vez en toda la obra | ERROR |
| C04 | La acción es compatible con `state_at(date)` (p. ej. no juega lesionado) | ERROR |
| C05 | El personaje no reacciona a un hecho F si `knows(F, date)` es falso | ERROR |
| C06 | Un personaje muerto no aparece después de su `death_date` | ERROR |
| C07 | Las relaciones citadas están vigentes (`since <= date < until`) | ERROR |
| C08 | La escena no contradice ningún `immutable` | ERROR |

### Grupo P — Premisa
| ID | Regla | Sev |
|---|---|---|
| P01 | Ningún término del `anachronism_blocklist` aparece en la prosa | ERROR |
| P02 | El rol del protagonista se mantiene (HC3) | ERROR |
| P03 | Los hechos marcados `source: real` coinciden con el corpus del RESEARCHER | ERROR |

### Grupo R — Personajes reales (spec 11)
| ID | Regla | Sev |
|---|---|---|
| R01 | Toda persona real nombrada está dada de alta en ⑧ (verificada en Wikipedia) | ERROR |
| R02 | La escena no supera el `max_interaction` de esa figura | ERROR |
| R03 | No aparece antes de `birth_date` ni después de `death_date` | ERROR |
| R04 | Su actividad es compatible con su `real_timeline` documentada | ERROR |
| R05 | Todo hecho atribuido con `source: real` existe en el corpus ⑦ | ERROR |
| R06 | Conducta deshonrosa o delictiva no documentada en ⑦ | ERROR |
| R07 | Ninguna escena gira **sobre** una figura real (son marco, no protagonistas) | WARN |

### Grupo S — Estructura
| ID | Regla | Sev |
|---|---|---|
| S01 | Longitud de escena dentro del rango de `style.md` ±25% | WARN |
| S02 | El POV de la prosa es el declarado en la escena | ERROR |
| S03 | Todo `open_thread` vencido está cerrado | ERROR |

---

## Formato de salida

```json
{
  "scene_id": "S014",
  "passed": false,
  "findings": [
    {
      "rule": "C02",
      "severity": "ERROR",
      "message": "Se celebra el cumpleanos de Marco el 1990-06-30, pero birth_date=1962-03-14 lo situa el 1990-03-14 (ya narrado en S007). Un evento anual no puede repetirse en el mismo ano.",
      "evidence": {
        "span": [412, 470],
        "source_of_truth": "characters/marco.yaml#immutables.birth_date"
      },
      "fix_hint": "Sustituir la celebracion por otro motivo, o mover la escena antes del 1990-03-14."
    }
  ]
}
```

Todo `message` debe ser **accionable**: qué se violó, cuál es la verdad,
dónde vive esa verdad y qué haría falta para arreglarlo.

## Detección en prosa

Las reglas C01, C05, P01 y R01 requieren extraer afirmaciones del texto libre.
Dos capas:

1. **Determinista**: regex y listas (blocklist de anacronismos, patrones de edad
   "X años", menciones de cumpleaños/aniversario). Barato, alta precisión.
2. **Extractor asistido**: un paso LLM que convierte la prosa en aserciones
   estructuradas (`{sujeto, predicado, fecha}`), que luego se comparan **por código**
   contra el canon. El LLM extrae; el código juzga.

## Dry-run de outline

Antes de escribir una sola palabra de prosa, los grupos **T** y **C** se ejecutan
sobre el `world-timeline.yaml` completo. Detecta timelines imposibles a coste cero.

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial. Catálogo de 21 reglas (grupos T, C, P, S), formato de findings, estrategia de detección en prosa y dry-run de outline. |
| 0.2 | 2026-09-15 | emilioqaracter | Añadido el grupo R (R01-R07) para personajes reales, derivado de la decisión D14 y detallado en la spec 11. El catálogo pasa a 28 reglas. |
