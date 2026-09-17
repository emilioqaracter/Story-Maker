# Story-Maker — Especificación técnica

**Versión 10.0** · 2026-09-17 · el porqué de cada decisión está en
[SPEC-FUNCIONAL.md](SPEC-FUNCIONAL.md). Esto es **cómo está hecho**: archivos,
formatos, scripts, reglas, contratos y traza.

---

## 1. Estructura del repositorio

```
.claude/
  agents/            6 agentes: planner, escritor, corrector, critic-continuity,
                     critic-quality, lector-capitulo
  skills/            6 skills: preparar-libro, dirigir-novela, resolver-canon,
                     escribir-escena, corregir-escena, formato-critica
  settings.json      permisos para los scripts del harness
harness/
  config.yaml        los numeros del sistema (§2)
  flujo.yaml         el ciclo declarado: quien, cuando, con que; lo lee la UI
  voz-base.md        el registro del genero; punto de partida de voz.md
  vista.py           lo que la UI muestra: sistema, actividad, expediente
  server.py          API local + UI estatica
  scripts/           los validadores, las puertas y los scripts del ciclo (§5)
books/<slug>/        una novela (§3)
tests/               una trampa por regla y por script
ui/                  interfaz React (Vite) sobre server.py
```

Los scripts reciben la ruta del libro como argumento. **No hay libro
«actual».** `.claude/` está en la raíz porque Claude Code descubre agentes y
skills ahí; conceptualmente es parte del harness.

---

## 2. Configuración

`harness/config.yaml`. Todo lo que tiene un número está aquí y nada lo repite.
Un libro puede pisar cualquier sección con su propio `books/<slug>/config.yaml`
(normalmente solo `estructura`).

```yaml
estructura:
  capitulos: 1
  escenas_por_capitulo: 3
  parrafos_por_escena: 3
  lineas_por_parrafo: 4
  palabras_por_linea: 12
tolerancia:
  lineas_por_parrafo: 0        # exacto
  palabras_por_linea: 3        # 12 +- 3
rubrica:
  dimensiones: [conflicto, voz, concrecion, frescura, avance]
  niveles: [0, 1, 2]
ciclo:
  intentos_max: 3
genero:
  actos: [planteamiento, desarrollo, desenlace]
  reparto: { planteamiento: 0.25, desarrollo: 0.50, desenlace: 0.25 }
  exige: { planteamiento: "...", desarrollo: "...", desenlace: "..." }
```

**Derivado, no guardado** (`Libro.forma`):

```
palabras_por_escena     = parrafos × lineas × palabras_por_linea         = 144
palabras_por_escena_max = parrafos × lineas × (palabras_por_linea + tol) = 180
escenas_totales         = capitulos × escenas_por_capitulo
```

No hay techo de palabras: V5 acota cada escena, así que el libro cabe por
construcción.

---

## 3. Los archivos de un libro

```
books/<slug>/
  config.yaml                    opcional: la estructura de ESTE libro
  context/                       EL CANON. Lo escribe crear_libro.py; lo cambia una persona
    premise.yaml
    arco.yaml
    characters/<clave>.yaml
    timeline.yaml                el ciclo solo toca resumen, beats y estado
    voz.md                       voz-base + muestra fija de la primera escena aprobada
  manuscript/
    chNN/SNNN.md                 la prosa
    chNN/SNNN.validation.json    la salida de G1
    chNN/SNNN.critique.json      la critica juntada
    chNN/SNNN.<rol>.prompt.md    el prompt exacto que recibio cada agente (no se versiona)
    chNN/capitulo.lector-capitulo.prompt.md
    novela.md                    el entregable
  reports/
    traza.jsonl                  la traza (§7)
    final.json                   la salida de G4
  state.json                     escena actual, intento, ultima aprobada
```

### `premise.yaml`

```yaml
titulo: La ultima calle
eje: Una espaldista de 29 anos en su ultima temporada
deporte: natacion
lugar: Barcelona
epoca:
  desde: '1992-01-13'
  hasta: '1992-07-31'
  notas: opcional, una o dos frases        # NO hay lista de anacronismos
hilos:
- { id: H1, que: la plaza de maestra interina que pierde }
- { id: H2, que: la oferta del club para quedarse de entrenadora }
```

### `arco.yaml`

```yaml
protagonista: nuria                        # clave de characters/
meta: nadar los 200 espalda en los Juegos
obstaculo: la minima no baja y la plaza ya es de otra
precio: la plaza de maestra
actos:                                     # derivados de la epoca con genero.reparto
- { acto: planteamiento, desde: '1992-01-13' }
- { acto: desarrollo,    desde: '1992-03-03' }
- { acto: desenlace,     desde: '1992-06-11' }
```

### `characters/<clave>.yaml`

```yaml
nombre: Marco Iriarte
rol: mediocampista del club, en el ultimo ano de contrato
nacimiento: '1962-03-14'                   # opcional; la edad se calcula, no se guarda
estados:                                   # tramos con vigencia; no hay "estado actual"
- { desde: '1990-01-01', hasta: '1990-08-18', que: sano }
- { desde: '1990-08-19', hasta: '1990-11-24', que: lesionado,
    prohibe: [jugo, entreno, corrio, pateo] }   # lo que V4 no deja aparecer en ese tramo
- { desde: '1990-11-25', hasta: '1990-12-31', que: retirado }
```

`crear_libro.py` deja un solo tramo `en actividad`; los tramos con `prohibe`
los añade una persona.

### `timeline.yaml`

```yaml
escenas:
- id: S001
  capitulo: 1
  fecha: '1992-01-23'                      # absoluta; el acto se calcula de aqui
  lugar: Barcelona
  presentes: [nuria, marta, toni]          # claves de characters/
  resumen: una frase                       # plan: lo escribe guardar_plan.py
  beats: [tres momentos concretos]         # plan
  estado: planificada | escrita | aprobada # lo mueve run_scene.py
  cierra: []                               # que hilos resuelve; la penultima H1, la ultima H2
```

### `state.json`

```json
{"escena_actual": "S003", "intento": 1, "ultima_aprobada": "S002"}
```

### `SNNN.critique.json`

```json
{"escena": "S001",
 "veredicto": {"pasa": true, "motivo": "...", "mas_floja": {"dimension": "avance", "por_que": "..."}},
 "continuidad": {"veto": false, "hallazgos": [{"que": "...", "cita": "..."}]},
 "calidad": {"conflicto": {"nota": 1, "cita": "..."}, "voz": {...}, "concrecion": {...},
             "frescura": {...}, "avance": {...}}}
```

### Salida de toda puerta

```json
{"objeto": "S001", "ok": false, "puerta": "G1",
 "errores": [{"regla": "V4", "mensaje": "que esta mal y cual es la verdad.", "arreglo": "como salir de ahi."}],
 "...": "campos propios de cada puerta"}
```

Todas salen por `common.emitir()`: imprime, guarda si tiene destino y anota la
traza. Una puerta nueva no puede olvidarse de registrarse.

---

## 4. Las reglas

| Regla | Qué comprueba | Puerta | Función | Trampa en `tests/` |
|---|---|---|---|---|
| **V1** premisa | `deporte`, `lugar`; `epoca.desde <= hasta`; exactamente 2 hilos con `id` y `que` | G0 | `validate_canon.v1_premisa` | `test_v1_*` |
| **V2** arco | protagonista con ficha; `meta`, `obstaculo`, `precio`; tres actos en orden con fechas crecientes; cada acto con ≥1 escena si hay ≥3 escenas | G0 | `validate_canon.v2_arco` | `test_v2_*` |
| **V3** timeline | tantas escenas como `escenas_totales`; ids únicos; capítulo en rango; cada escena con fecha dentro de la época, sin retroceder dentro de su capítulo, y con presentes que existen | G0 (todas) y G1 (la escena) | `validate_canon.v3_timeline`, `v3_escena` | `test_v3_*` |
| **V4** estado | ningún término de `prohibe` del tramo vigente de un presente aparece en la prosa (palabra completa, sin tildes ni mayúsculas) | G1 | `validate_scene.v4_estado` | `test_v4_*` |
| **V5** forma | `parrafos_por_escena` párrafos; `lineas_por_parrafo` líneas cada uno; cada línea `palabras_por_linea ± tolerancia` | G1 | `validate_scene.v5_forma` | `test_v5_*` |
| **V6** hilos | cada hilo declarado lo cierra exactamente una escena aprobada; ninguna escena cierra un hilo no declarado | G4 | `validate_book.v6_hilos` | `test_v6_*` |
| **V7** actos | los tres actos tienen escena aprobada; la última aprobada (por fecha) cae en el desenlace. No se exige con menos de 3 escenas | G4 | `validate_book.v7_actos` | `test_v7_*` |

Y las comprobaciones de las puertas de criterio, que no son reglas sobre el
canon sino sobre **la utilizabilidad del juicio**:

| Id | Qué | Puerta |
|---|---|---|
| `G2/traza` | la crítica es posterior a la prosa (mtime) | G2 |
| `G2/veredicto` | existe `pasa` y trae `motivo` | G2 |
| `G2/criterio` | el crítico dijo `pasa: false`; su motivo viaja como error para el corrector | G2 |
| `G2/mas_floja` | `mas_floja.dimension` existe en la rúbrica y trae `por_que` | G2 |
| `G2/continuidad` | cada hallazgo cierra; un `veto: true` sin hallazgos también | G2 |
| `G2/rubrica` | nota en `niveles`; toda nota con cita | G2 |
| `G3/completo` | todas las escenas del capítulo aprobadas | G3 |
| `G3/lectura` | todo hallazgo con cita, y la cita aparece en el capítulo | G3 |
| `G3/capitulo` | un hallazgo con `bloquea: true` | G3 |
| `G4/completo` | quedan escenas sin aprobar | G4 |

Correspondencia con la numeración anterior (para leer trazas viejas):
V1 ← V13 (época) y V21 (intake); V2 ← V16; V3 ← V1, V2 y `plan_cabe`;
V4 ← V6; V5 ← V14 y V15; V6 ← V10 y V11; V7 ← V17 y V18. Retiradas: V3, V4,
V5, V7, V8, V9, V12, V19, V20 y el regulador.

---

## 5. Los scripts

Todos en `harness/scripts/`. Todos imprimen JSON. Todos reciben la ruta del
libro. Código y comentarios en español sin tildes (la consola de Windows viene
en cp1252). Los que leen stdin lo reconfiguran a UTF-8 por la misma razón.

| Script | Uso | Qué hace | Efectos |
|---|---|---|---|
| `comprobar_sistema.py` | `comprobar_sistema.py` | los 6 agentes y las 6 skills existen y su frontmatter carga | — |
| `crear_libro.py` | `crear_libro.py <libro.json>` | deriva y escribe el canon; corre G0 | crea `books/<slug>/`; traza G0 |
| `validate_canon.py` | `validate_canon.py <libro>` | **G0**: V1, V2, V3; devuelve `actos` y `sin_beats` | traza |
| `guardar_plan.py` | `guardar_plan.py <libro> < plan.json` | guarda `resumen` y `beats`; rechaza escenas sin tres beats | `timeline.yaml` |
| `run_scene.py` | `next` · `aprobar <SID>` · `intento <SID>` · `estado` · `reset` | el estado del ciclo (§6) | `state.json`, `timeline.yaml`, `voz.md` |
| `resolver_canon.py` | `resolver_canon.py <libro> <SID>` | el canon resuelto a la fecha, en prosa | — |
| `empaquetar.py` | `empaquetar.py <libro> <SID\|chN> <rol> [--errores f.json]` | arma el prompt del agente y lo deja en un archivo | `*.prompt.md`; traza `agente/inicio` |
| `guardar_prosa.py` | `guardar_prosa.py <libro> <SID> --de <rol> < prosa` | limpia preámbulo y fences, comprueba la forma, guarda | `SNNN.md`; traza `agente/fin` |
| `validate_scene.py` | `validate_scene.py <libro> <SID>` | **G1**: V3, V4, V5 | `SNNN.validation.json`; traza |
| `guardar_critica.py` | `guardar_critica.py <libro> <SID> --continuidad a --calidad b` | parsea las dos respuestas crudas, exige veredicto y `mas_floja`, junta y guarda | `SNNN.critique.json`; traza `agente/fin` ×2 |
| `gate_scene.py` | `gate_scene.py <libro> <SID>` | **G2** | traza |
| `gate_chapter.py` | `gate_chapter.py <libro> <N> < lectura.json` | **G3** | traza `agente/fin` (lector) + puerta |
| `validate_book.py` | `validate_book.py <libro>` | **G4**: completo, V6, V7 | `reports/final.json`; traza |
| `compilar.py` | `compilar.py <libro>` | concatena las aprobadas | `manuscript/novela.md`; traza |
| `traza.py` | `traza.py <libro> [--json]` | resume la traza (§7) | — |
| `reportar.py` | `reportar.py <libro>` | espejo opcional en Langfuse | red, si hay claves |

Módulos compartidos: `common.py` (carga, `Libro`, derivaciones, `Error`,
`emitir`), `parseo.py` (`limpiar_prosa`, `extraer_json`), `traza.py`.

### `run_scene.py next`

Devuelve `accion`:

| `accion` | Cuándo | Qué hace el orquestador |
|---|---|---|
| `planificar` | la primera escena pendiente no tiene tres beats | Task al planner → `guardar_plan.py` |
| `escribir` | pendiente sin prosa en disco | `empaquetar.py ... escritor` |
| `corregir` | pendiente con prosa | `empaquetar.py ... corrector` |
| `parar` | `intento >= ciclo.intentos_max` | replanificar una vez; si no, parar e informar |
| `cerrar` | ninguna pendiente y G4 abriría | `validate_book.py`, `compilar.py`, `traza.py` |
| `revisar` | ninguna pendiente y G4 no abriría | mirar `condiciones` y replanificar |

`aprobar <SID>` vuelve a correr G1 y G2 antes de marcar la escena: el estado
no se mueve sin las puertas abiertas. Con la primera aprobada fija `voz.md`
(dos párrafos de muestra bajo `## Muestra fija`; no se regenera). `reset`
borra prosa, críticas, prompts, estado, traza y entregable, devuelve `voz.md` a
la base y **no toca el canon ni los beats**.

---

## 6. Los contratos de los agentes

El **método** vive en `.claude/agents/<rol>.md` (Claude Code lo carga solo).
Los **datos** van en el prompt que arma `empaquetar.py`. El orquestador lanza
un Task con la instrucción literal que devuelve `empaquetar.py`: «Lee
`books/<slug>/manuscript/chNN/SNNN.<rol>.prompt.md` y haz tu trabajo».

| Rol | Secciones del prompt | Devuelve | Lo guarda | Traza `fin` |
|---|---|---|---|---|
| `escritor` | VOZ · CANON resuelto · LO QUE PASO ANTES · FORMA · cierre «solo prosa» | prosa | `guardar_prosa.py --de escritor` | `chars`, `forma_ok`, `recortado` |
| `corrector` | LA ESCENA ACTUAL · errores con `arreglo` (del `--errores` o de la última puerta que cerró sobre la escena o su capítulo) · CANON · FORMA | prosa entera | `guardar_prosa.py --de corrector` | idem |
| `critic-continuity` | LA ESCENA · CANON · LO QUE PASO ANTES · formato | `{"continuidad": {"veto", "hallazgos": [{"que", "cita"}]}}` | `guardar_critica.py` | `hallazgos` |
| `critic-quality` | LA ESCENA · EL ACTO y lo que se le pide · CANON · LO QUE PASO ANTES · VOZ · formato | `{"veredicto": {"pasa", "motivo", "mas_floja": {"dimension", "por_que"}}, "calidad": {dim: {"nota", "cita"}}}` | `guardar_critica.py` | `pasa`, `mas_floja` |
| `lector-capitulo` | las escenas del capítulo seguidas · contexto del arco · formato | `{"hallazgos": [{"que", "cita", "escena", "bloquea"}]}` | `gate_chapter.py` (por stdin) | `hallazgos` |
| `planner` | lo arma el orquestador: meta, obstáculo, precio, hilos, época, escenas con fecha, acto y `cierra` | `{"escenas": [{"id", "resumen", "beats": [3]}]}` | `guardar_plan.py` | — |

Los scripts que guardan **toleran** preámbulos y bloques de código
(`parseo.py`): la salida del modelo se limpia, no se confía en que obedezca.
Y **rechazan** lo que no sirve con `ok: false` y un `arreglo` que dice a quién
volver a pedir qué.

---

## 7. La traza

`books/<slug>/reports/traza.jsonl`. Append-only; nunca se lee para escribir;
un JSON por línea; la escritura nunca tumba una puerta.

### Eventos

```json
{"t": "2026-09-17T10:19:32", "paso": "G1", "ms": 0, "tipo": "puerta", "agente": "G1",
 "ok": true, "errores": [], "escena": "S001", "palabras": 154, "suma": null, "mas_floja": null}

{"t": "...", "paso": "agente", "ms": 0, "tipo": "agente", "fase": "inicio",
 "agente": "escritor", "escena": "S001", "intento": 1, "chars": 6581}

{"t": "...", "paso": "agente", "ms": 146756, "tipo": "agente", "fase": "fin",
 "agente": "escritor", "escena": "S001", "chars": 802, "forma_ok": true, "recortado": false}
```

- `puerta`: lo escribe `common.emitir()` con el JSON de la puerta. `escena` es
  `SNNN`, `chNN`, `canon`, `obra` o `novela.md`.
- `agente/inicio`: lo escribe `empaquetar.py`. `intento` sale de `state.json`.
- `agente/fin`: lo escribe el script que guarda la respuesta. `ms` se calcula
  buscando hacia atrás el último `inicio` del mismo agente sobre la misma
  escena.

### Derivaciones (`traza.resumen`)

- **intentos de una escena** = pasadas por G1 sobre esa escena.
- **llamadas a agentes** = eventos `fin`; **tiempo en agentes** = suma de sus `ms`.
- **por puerta**: aplicadas y cerradas.

### Lecturas

- `traza.py <libro>`: informe en texto (cabecera, por agente, por puerta, por
  escena con cada evento y cada error, puertas del libro y de los capítulos).
- `traza.py <libro> --json`: el `resumen`.
- `vista.actividad(desde)`: los eventos de todos los libros desde una hora,
  para la UI.
- `vista.dossier(libro)`: por escena, puertas y agentes cruzados con la
  crítica y el timeline.
- `reportar.py`: en Langfuse, una sesión por libro; un span `producir-escena`
  por escena; un `evaluator` por pasada de G1 (`validar-hechos`) y G2
  (`evaluar-rubrica`); scores `intentos`, `veredicto`, `mas-floja`,
  `rubrica-<dim>` y `rubrica`.

---

## 8. El servidor y la UI

`python harness/server.py` sirve en `http://127.0.0.1:8770` la UI construida
(`ui/dist`) y la API. No recarga código: reiniciar tras tocar Python.

| Método | Ruta | Devuelve |
|---|---|---|
| GET | `/api/config` | versión, `estructura`, `tolerancia`, `rubrica`, `ciclo`, `genero`, `perfiles` |
| GET | `/api/sistema` | `vista.sistema()`: agentes, skills, puertas, flujo |
| GET | `/api/actividad?desde=ISO` | `vista.actividad()` |
| GET | `/api/books` · `/api/books/<slug>` | estado de los libros / de uno |
| GET | `/api/books/<slug>/dossier` · `/traza` · `/novela` · `/log` | expediente · eventos + resumen · el entregable · el log del ciclo lanzado |
| POST | `/api/books` | `crear_libro.crear(json)` |
| POST | `/api/books/<slug>/run` · `/reset` · `/validar` | lanza `claude -p` con `dirigir-novela` en sesión limpia · `run_scene.py reset` · `validate_book.py` |

La UI (`ui/src/`) tiene tres vistas: `Sistema.jsx`, `Actividad.jsx`,
`Libros.jsx`. Naranja lo que actúa (agentes), pizarra lo que juzga (puertas).
Desarrollo: `python harness/server.py` y `cd ui && npm run dev` (Vite en :5273
proxea `/api`).

---

## 9. Tests

```bash
python -m pytest tests -q
```

Sin red ni tokens. El fixture es `books/marco-1990` (una escena aprobada, con
crítica), copiado a un temporal por test.

- `tests/test_reglas.py`: una trampa por regla (V1-V7) y por comprobación de
  G2, G3 y G4; el caso bueno; que todo error sea accionable; que el
  frontmatter de agentes y skills cargue.
- `tests/test_ciclo.py`: los scripts que rodean a los agentes (`parseo`,
  `guardar_*`, `empaquetar`, `resolver_canon`, `run_scene`, `traza`,
  `crear_libro`, `comprobar_sistema`).

Al añadir una regla: escribir la trampa, verla fallar, implementar. Si una
regla no tiene su trampa, no está comprobada.

---

## 10. Convenciones

- Código y comentarios en español, **sin tildes en el código fuente**. La
  prosa de las novelas sí lleva tildes.
- Todo script imprime JSON con `ok` y `errores`; cada error trae `regla`,
  `mensaje` (termina en punto) y `arreglo`.
- Los scripts que leen stdin lo reconfiguran a UTF-8.
- El prompt a `claude -p` viaja por stdin, nunca como argumento.
- Si se agrega o mueve un paso del ciclo, se actualiza `harness/flujo.yaml`.
- Cada cambio de especificación se registra en el historial del documento
  que toca, en la misma entrega, con su porqué.

---

## 11. Historial técnico

| Versión | Fecha | Cambio |
|---|---|---|
| **10.0** | 2026-09-17 | Reglas renumeradas V1-V7 (§4 trae la correspondencia). Eliminados: `researcher.md`, skills `epoca` y `analizar-traza`, `epoca.yaml`, `intake.json`, `derivaciones.py` (absorbido por `crear_libro.py`), `sistema.py` y `dossier.py` (fundidos en `vista.py`, solo disco), la lectura de Langfuse en la UI, `Informes.jsx`/`md.js`, `reports/`, `Novelas.drawio`, `books/prueba-*` y `books/ruben-2015`. `resolver_canon.py` pasa a ser el dueño de `contexto()`. `run_scene.py` pierde el regulador y el subcomando `contexto`; `next` devuelve `planificar`. `guardar_plan.py` solo guarda beats. `traza.py` gana `informe()` y CLI. `crear_libro.py` toma un JSON de decisiones y deja de depender de `server.py`. `state.json` queda con tres campos. `timeline.yaml` pierde `flashback` y `palabras`; `characters/*.yaml` pierde `eventos_unicos`, `sabe`, `club`. `premise.yaml` pierde `estilo` y `pregunta_dramatica` y gana `epoca.notas`. Los `*.prompt.md` dejan de versionarse. Tests reescritos. |
