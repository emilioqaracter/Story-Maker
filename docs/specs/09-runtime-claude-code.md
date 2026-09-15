# Spec 09: Runtime sobre Claude Code

**Decisión D1:** el harness es Claude Code. Sin servidor, sin framework, sin
orquestador propio. Subagentes para el juicio, scripts para el determinismo.

## 1. Regla de reparto

> **Si el paso tiene una respuesta correcta, es un script. Si requiere criterio, es un subagente.**

Esto importa más de lo que parece: la sesión principal de Claude Code es un LLM,
y un LLM conduciendo un bucle de 45 iteraciones deriva. Los pasos mecánicos
(validar, empaquetar contexto, escribir el ledger, commitear) **no** se le piden
al modelo: se invocan como scripts que devuelven JSON.

| Paso | Ejecutor | Motivo |
|---|---|---|
| Empaquetar contexto de la escena | `scripts/pack_context.py` | cálculo puro sobre YAML |
| Escribir prosa | **OpenRouter** vía `scripts/or_draft.py` | volumen de tokens (spec 10) |
| Validar | `scripts/validate.py` | 21 reglas deterministas (spec 04) |
| Criticar | **subagentes de Claude Code** | juicio literario y de continuidad |
| Revisar prosa | OpenRouter (int. 1-2) → Claude (int. 3) | escalada de calidad |
| Escribir el ledger + commit | `scripts/ledger.py` | mutación de estado, cero creatividad |
| Conducir el ciclo | sesión principal + skill | decide qué escena toca y cuándo parar |

## 2. Estructura del repo

```
Story-Maker/
├── .claude/
│   ├── agents/
│   │   ├── premise-interviewer.md
│   │   ├── outliner.md
│   │   ├── planner.md
│   │   ├── critic-continuity.md      L1  (veto)
│   │   ├── critic-sport.md           L2  (veto)
│   │   ├── critic-literary.md        L3  (rúbrica)
│   │   ├── critic-reader.md          L4  (señal)
│   │   └── reviser-escalated.md      solo intento 3
│   ├── skills/story-maker/SKILL.md   comandos del proyecto
│   └── settings.json                 permisos de Bash para los scripts
├── scripts/
│   ├── pack_context.py
│   ├── or_draft.py                   adaptador OpenRouter
│   ├── verify_figure.py              admisión de figuras reales (Wikipedia)
│   ├── validate.py
│   ├── ledger.py
│   └── run_scene.py                  ciclo completo de una escena
├── context/                          el Context Store (spec 01)
├── manuscript/
│   └── ch01/S001.md
└── docs/specs/
```

## 3. Ventaja gratis de los subagentes

Los subagentes de Claude Code tienen **contexto aislado** y solo devuelven su
mensaje final. Eso implementa por construcción dos reglas que la spec 05 pedía:

- **Las lentes no se ven entre sí** → no hay efecto manada.
- **El crítico no sabe el número de intento** → no hay aprobación complaciente.

Las 4 lentes se lanzan **en un solo mensaje, en paralelo**. Cada una devuelve su
veredicto en JSON; la sesión principal los funde.

```
        sesión principal (orquestador)
                    │
   ┌────────┬───────┴────────┬──────────┐   un solo mensaje,
   ▼        ▼                ▼          ▼   4 subagentes en paralelo
  L1       L2               L3         L4
continuity sport         literary    reader
   │        │                │          │
   └────────┴───────┬────────┴──────────┘
                    ▼
            merge → ¿veto? → scripts/run_scene.py continúa o revisa
```

**Limitación a respetar:** un subagente no lanza otros subagentes. El orquestador
es siempre la sesión principal. No diseñes jerarquías de tres niveles.

## 4. Ejemplo de subagente

`.claude/agents/critic-continuity.md`:

```markdown
---
name: critic-continuity
description: Lente L1. Detecta contradicciones de canon que el validador determinista no puede formalizar.
tools: Read, Grep
model: sonnet
---

Eres la lente de CONTINUIDAD de un panel crítico. NO reescribes: solo diagnosticas.

Recibes: la prosa de una escena y el canon ya resuelto a su fecha.

Busca únicamente:
- contradicciones implícitas con hechos del canon
- objetos, personajes o lugares que aparecen sin haber sido introducidos
- conocimiento que un personaje no podía tener en esa fecha
- cambios de carácter sin causa narrada

NO evalúes calidad literaria: no es tu trabajo, otra lente lo hace.
Máximo 5 hallazgos, ordenados por gravedad. Cada uno DEBE citar el fragmento exacto.

Devuelve SOLO este JSON, sin texto alrededor:
{"lens":"L1","veto":bool,"findings":[{"quote":"...","issue":"...","canon_ref":"...","fix":"..."}]}
```

## 5. Comandos de la skill

`.claude/skills/story-maker/SKILL.md` define el flujo de usuario:

| Comando | Qué hace |
|---|---|
| `/story init` | lanza `premise-interviewer`, congela `premise.lock.yaml` |
| `/story outline` | genera el timeline, verifica el elenco real (spec 11) y corre el dry-run |
| `/story figure <nombre>` | verifica una persona real en Wikipedia y propone su alta en ⑧ |
| `/story scene <id>` | ejecuta `run_scene.py` para una escena |
| `/story chapter <n>` | encadena escenas hasta el gate humano |
| `/story audit` | validación completa de la obra, no genera nada |
| `/story retcon <path> <valor>` | informe de impacto + cascada (spec 07) |

## 6. Permisos

`.claude/settings.json` debe permitir los scripts del proyecto para no pedir
confirmación en cada escena:

```json
{
  "permissions": {
    "allow": [
      "Bash(python scripts/validate.py:*)",
      "Bash(python scripts/pack_context.py:*)",
      "Bash(python scripts/or_draft.py:*)",
      "Bash(python scripts/ledger.py:*)",
      "Bash(python scripts/run_scene.py:*)",
      "Bash(python scripts/verify_figure.py:*)"
    ]
  }
}
```

La clave de OpenRouter vive **solo** en la variable de entorno `OPENROUTER_API_KEY`.
Nunca en `settings.json`, nunca en el repo. Añade `.env` a `.gitignore`.

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial (decisión D1). Regla de reparto script/subagente, estructura del repo, ejemplo de subagente crítico, comandos de la skill y permisos. |
| 0.2 | 2026-09-15 | emilioqaracter | Añadidos `verify_figure.py` y el comando `/story figure` derivados de la decisión D14 (spec 11). |
