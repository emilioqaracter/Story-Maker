# Spec 01: Context Store

Fuente única de verdad. Ningún agente salvo `LEDGER_WRITER` escribe aquí.
Cada escritura aprobada = 1 commit de git (`scene(S014): approved`).

```
context/
├── premise.lock.yaml      ①  EJE INMUTABLE            [solo-lectura tras congelar]
├── world-timeline.yaml    ②  consistencia temporal de la historia
├── characters/
│   ├── marco.yaml         ③  consistencia temporal por personaje
│   └── sofia.yaml
├── style.md               ④  voz, POV, registro
├── canon-ledger.jsonl     ⑤  hechos establecidos (append-only)
├── open-threads.yaml      ⑥  hilos abiertos y su deadline
├── research-corpus.yaml   ⑦  hechos REALES verificados      [congelado tras revisión humana]
└── real-figures.yaml      ⑧  personas reales admitidas      [append-only, verificado vs Wikipedia]
```

---

## ① `premise.lock.yaml` — el eje

Escrito una sola vez por `PREMISE_INTERVIEWER`. **Inmutable**: modificarlo exige
acción humana explícita y dispara revalidación de toda la obra.

```yaml
premise_id: pr_1990_futbol
locked_at: 2026-09-15
schema_version: 1

axis:
  user_request: "Quiero que sea un futbolista en 1990"   # literal del usuario
  sport: football
  era: { start: 1990-01-01, end: 1990-12-31 }
  protagonist_role: player
  reality_mode: hybrid        # hybrid | fiction | historical   (D3)

hard_constraints:             # verificables por código -> error duro
  - { id: HC1, type: date_range,  rule: "toda escena en 1988-06..1991-06" }
  - { id: HC2, type: anachronism, rule: "sin tecnología posterior a 1990" }
  - { id: HC3, type: role,        rule: "el protagonista es jugador en activo" }

anachronism_blocklist: [VAR, smartphone, WhatsApp, redes sociales, GPS, email]

soft_intent:                  # no verificable -> guía al crítico literario
  themes: [ambición, lesión, clase social]
  ending_shape: agridulce
```

---

## ② `world-timeline.yaml` — temporalidad de la historia

```yaml
clock:
  story_start: 1990-01-08
  story_end:   1990-07-20
  cursor: 1990-03-02          # última fecha narrada; solo avanza

fixed_events:                 # anclas del mundo; no se mueven
  - { id: WE01, date: 1990-06-08, label: "Inicio del Mundial de Italia", source: real }
  - { id: WE02, date: 1990-03-11, label: "Derbi de invierno", source: fiction }

scenes:
  - id: S001
    chapter: 1
    date: 1990-01-08          # ABSOLUTA Y OBLIGATORIA
    duration_hours: 3
    location: Rosario
    pov: marco
    present: [marco, sofia]
    summary: "Marco falla el penalti en el amistoso"
    establishes: [F001, F002] # ids del canon-ledger
    status: approved          # planned | drafted | approved
```

**Invariantes** (ver spec 04): fechas monótonas por capítulo, sin solapes de
escenas con el mismo personaje, toda escena dentro de `era`.

---

## ③ `characters/<id>.yaml` — temporalidad del personaje

Resuelve el problema del cumpleaños duplicado y el de "reacciona a lo que aún no sabe".

```yaml
id: marco
name: Marco Iriarte
schema_version: 1

immutables:                   # nunca cambian; contradecirlos = error duro
  birth_date: 1962-03-14      # ÚNICA fuente de edad. El campo `age` está PROHIBIDO.
  birthplace: Rosario
  dominant_foot: left

state_timeline:               # estado CON VIGENCIA, no "estado actual"
  - from: 1990-01-01
    to:   1990-02-19
    club: Newells
    injury: null
    morale: bajo
  - from: 1990-02-20
    to:   1990-05-10
    club: Newells
    injury: { type: rotura_fibrilar, recovers_on: 1990-04-05 }
    morale: hundido

life_events:                  # ÚNICOS: no pueden repetirse jamás
  - { id: LE1, date: 1990-02-20, type: lesion, unique: true, scene: S008 }
  - { id: LE2, date: 1990-04-12, type: boda,   unique: true, scene: S019 }

recurring_events:             # DERIVADOS, nunca declarados a mano
  - { type: birthday, derived_from: immutables.birth_date, cadence: annual }

knowledge:                    # qué sabe y DESDE CUÁNDO
  - { fact_id: F014, since: 1990-03-14, via: S007 }

relationships:
  - { with: sofia, type: pareja, since: 1988-09-01, until: null }
```

### Campos derivados (calculados, nunca persistidos)

| Derivado | Fórmula |
|---|---|
| `age_at(d)` | años completos entre `birth_date` y `d` |
| `birthday_in(year)` | `birth_date` con el año sustituido |
| `state_at(d)` | tramo de `state_timeline` que contiene `d` |
| `knows(f, d)` | existe entrada en `knowledge` con `since <= d` |

---

## ④ `style.md`

POV y persona, tiempo verbal, registro, longitud objetivo de escena, tics a evitar,
y una muestra de 200 palabras como referencia de voz.

## ⑤ `canon-ledger.jsonl` — append-only, con procedencia

```jsonl
{"id":"F001","scene":"S001","date":"1990-01-08","fact":"Marco es zurdo","type":"immutable"}
{"id":"F014","scene":"S007","date":"1990-03-14","fact":"Sofia conoce el fichaje","type":"knowledge","who":"sofia"}
{"id":"F021","scene":"S011","date":"1990-04-02","fact":"El vestuario huele a eucalipto","type":"detail"}
```

`type`: `immutable` | `state` | `knowledge` | `detail` | `world`.
Nunca se edita una línea existente: se anexa una corrección con `supersedes`.

## ⑥ `open-threads.yaml`

```yaml
threads:
  - id: T01
    opened_in: S003
    description: "La carta sin abrir del padre"
    must_close_by_chapter: 9
    status: open        # open | closed | abandoned (con justificación)
```

## ⑦ `research-corpus.yaml` — hechos reales verificados (D6)

Generado una vez por `RESEARCHER`, **revisado por un humano** y congelado.
A partir de ahí es la única autoridad para la regla P03: el DRAFTER no puede
afirmar nada marcado `source: real` que no esté aquí.

```yaml
corpus_id: football_1990
sport: football
frozen_at: 2026-09-15
reviewed_by: human            # sin esto, el corpus no se puede usar

facts:
  - id: R001
    date: 1990-06-08
    claim: "Arranca la Copa del Mundo en Italia"
    confidence: high
    source: "referencia aportada en la revisión"
  - id: R014
    date_range: [1990-01-01, 1990-06-01]
    claim: "No existe la sustitución por conmoción ni el VAR"
    type: rule_of_the_era

gaps:                          # lo que el corpus NO cubre
  - "Calendario completo de la liga argentina 1990"
    # -> cualquier afirmación en esta zona debe marcarse `source: fiction`
```

El bloque `gaps` es tan importante como `facts`: declara explícitamente dónde
el sistema **no sabe**, y obliga a etiquetar esa zona como ficción en vez de inventar.

## ⑧ `real-figures.yaml` — personas reales admitidas (D14)

Registro de las figuras públicas que pueden aparecer. Admisión por Wikipedia,
verificada por script. Esquema completo, niveles de interacción y reglas del
grupo R en la **spec 11**.

```yaml
figures:
  - id: rf_ejemplo
    display_name: "Nombre Apellido"
    wikipedia: { url: "...", revision_id: 123456789, verified_at: 2026-09-15 }
    birth_date: 1960-10-30
    death_date: null
    status: living                 # living | deceased
    max_interaction: backdrop      # mention | backdrop | interaction | intimate
```

A diferencia de `characters/*.yaml`, aquí **nada se inventa**: las fechas y la
trayectoria se extraen del artículo verificado, no las escribe un modelo.

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial. Archivos ① a ⑥, esquemas YAML y tabla de campos derivados. |
| 0.2 | 2026-09-15 | emilioqaracter | Añadido ⑦ research-corpus.yaml (decisión D6), con su bloque `gaps` para declarar explícitamente lo que el sistema no sabe. |
| 0.3 | 2026-09-15 | emilioqaracter | Añadido ⑧ real-figures.yaml (decisión D14): registro de personas reales admitidas, con esquema detallado en la spec 11. |
