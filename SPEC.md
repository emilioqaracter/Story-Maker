# Story-Maker

Sistema que escribe una novela sobre un futbolista en 1990 sin contradecirse.

**Principio:** la coherencia factual se **calcula**, no se recuerda. Un LLM olvida
la edad del protagonista en el capítulo 12; un script no. El modelo escribe, el
código verifica.

**Stack:** Claude Code orquesta y critica · OpenRouter (modelos `:free`) escribe
la prosa · scripts Python validan.

---

## 1. Los archivos de contexto

Todo el estado vive en `context/`. Es la única fuente de verdad.

### `premise.yaml` — el eje, se escribe una vez y no se toca

```yaml
eje: "Un futbolista en 1990"
deporte: futbol
epoca: { desde: 1990-01-01, hasta: 1990-12-31 }
estilo: "Tercera persona, pasado, español rioplatense. Escenas de 800-1000 palabras."
prohibido: [VAR, celular, internet, redes sociales]
```

### `timeline.yaml` — cuándo pasa cada cosa

```yaml
escenas:
  - id: S001
    capitulo: 1
    fecha: 1990-01-08          # absoluta y obligatoria
    lugar: Rosario
    presentes: [marco, sofia]
    resumen: "Marco falla el penalti"
    estado: aprobada            # planificada | escrita | aprobada
```

### `characters/marco.yaml` — quién es y cómo cambia

Aquí está la clave del problema del cumpleaños: **lo que se puede calcular, no se guarda**.

```yaml
nombre: Marco Iriarte
nacimiento: 1962-03-14       # única fuente de la edad. NO existe el campo "edad".
club: Newells

estados:                     # el estado tiene vigencia, no es "el actual"
  - { desde: 1990-01-01, hasta: 1990-02-19, lesion: null }
  - { desde: 1990-02-20, hasta: 1990-04-05, lesion: rotura_fibrilar }

eventos_unicos:              # no pueden repetirse nunca
  - { fecha: 1990-02-20, que: lesion }
  - { fecha: 1990-04-12, que: boda }

sabe:                        # qué conoce y desde cuándo
  - { que: "el fichaje", desde: 1990-03-14 }
```

El cumpleaños **no se declara**: se deriva de `nacimiento`. Por eso no puede
ocurrir dos veces en el mismo año.

### `real-figures.yaml` — personas reales que pueden aparecer

Requisito único: tener artículo en Wikipedia. Lo verifica un script, no un criterio.

```yaml
- nombre: "Nombre Apellido"
  wikipedia: https://es.wikipedia.org/wiki/...
  nacimiento: 1960-10-30
  muerte: null
```

Las fechas salen del artículo, no las inventa el modelo.

---

## 2. El ciclo

```
  PLANIFICAR ──► ESCRIBIR ──► VALIDAR ──► CRITICAR ──► CORREGIR
   (Claude)     (OpenRouter)  (script)    (Claude)    (OpenRouter)
                                  │           │            │
                                  └───────────┴────────────┘
                                     máx. 3 intentos
                                          │
                                          ▼ aprobada
                                   guardar + commit
                                          │
                                   ¿fin de capítulo? ──► lo revisas tú
```

El validador corre **antes** que el crítico: es gratis, instantáneo y no falla.
Si a los 3 intentos no pasa, para y te pregunta.

---

## 3. El validador

Un script, sin LLM. Estas son las reglas que importan:

| # | Regla |
|---|---|
| V1 | Toda escena tiene fecha, y está dentro de la época de `premise.yaml` |
| V2 | Las fechas de un capítulo van hacia adelante (salvo flashback declarado) |
| V3 | La edad mencionada en la prosa coincide con la calculada desde `nacimiento` |
| V4 | **El cumpleaños no ocurre dos veces en el mismo año** |
| V5 | Un evento único no se repite |
| V6 | Nadie hace algo incompatible con su estado (jugar lesionado) |
| V7 | Nadie reacciona a algo que todavía no sabe |
| V8 | No aparecen palabras de la lista `prohibido` |
| V9 | Una persona real no aparece antes de nacer ni después de morir |

Salida:

```json
{"escena": "S014", "ok": false, "errores": [
  {"regla": "V4",
   "mensaje": "Se celebra el cumpleaños de Marco el 30-jun, pero nació el 14-mar (ya narrado en S007).",
   "arreglo": "Cambiar el motivo de la celebración, o mover la escena antes del 14-mar."}
]}
```

El mensaje tiene que decir qué está mal, cuál es la verdad y cómo arreglarlo.

**Detección en prosa:** V3, V7 y V8 necesitan leer texto libre. Regex para lo
obvio (palabras prohibidas, "X años"); para el resto, una llamada al modelo que
extrae afirmaciones y las compara **por código** contra el canon.

---

## 4. El crítico

Dos subagentes de Claude Code, en paralelo. **No reescriben: solo diagnostican.**

| Lente | Busca | Poder |
|---|---|---|
| **Continuidad** | contradicciones que el validador no puede formalizar: objetos que aparecen de la nada, cambios de carácter sin causa, conocimiento inferido | **veta** |
| **Calidad** | escena sin conflicto, diálogo expositivo, clichés, ritmo plano | puntúa 1-10, bloquea si < 6 |

Dos detalles que importan:

- Los subagentes de Claude Code tienen contexto aislado, así que **no se ven entre
  sí** (no hay efecto manada) y **no saben en qué intento van** (no aprueban por
  cansancio). Sale gratis.
- El feedback tiene que citar el fragmento exacto. "Mejora el ritmo" es inútil;
  "los párrafos 3-5 frenan la escena" es accionable.

Sobre personas reales, la lente de continuidad veta una sola cosa: atribuirles
conducta deshonrosa o delictiva que no esté documentada.

---

## 5. OpenRouter

**El límite que condiciona todo:** los modelos `:free` dan ~50 peticiones/día sin
créditos (~1000/día si cargas $10 una vez). Una novela de 45 escenas necesita
~100-145 llamadas. **No cabe en un día.**

Por eso:
- El ciclo guarda estado en disco y **se puede reanudar** al día siguiente.
- Respeta los 429 con backoff, sin reintentar en bucle.
- El validador filtra antes de gastar llamadas.

**Cargar $10 en OpenRouter es la mejor decisión coste/beneficio del proyecto:**
convierte tres semanas en una tarde.

### Cómo se le habla a un modelo débil

| Regla | Por qué |
|---|---|
| Una tarea por llamada | pedir prosa + JSON a la vez rompe una de las dos |
| El contexto va **ya resuelto, en prosa** | "Marco, 28 años, lesionado hasta el 5 de abril" — nunca YAML que deba interpretar |
| Prompt corto y rígido | los matices se pierden en modelos pequeños |
| Parseo tolerante | envuelven el JSON en ```` ``` ````, añaden preámbulos |

Los modelos `:free` rotan y desaparecen: la lista va en un YAML con orden de
fallback, nunca cableada en el código.

```yaml
escritor:  { modelos: [a:free, b:free], temperatura: 0.85 }
corrector: { modelos: [a:free], temperatura: 0.4 }
```

**Escalada:** intentos 1-2 en OpenRouter → intento 3 lo corrige Claude → intento 4
te pregunta. El modelo gratis hace el volumen; Claude entra solo donde falla.

`OPENROUTER_API_KEY` va en el entorno. Nunca en el repo.

---

## 6. Estructura

```
Story-Maker/
├── SPEC.md
├── .claude/
│   ├── agents/
│   │   ├── planner.md
│   │   ├── critic-continuity.md
│   │   └── critic-quality.md
│   └── settings.json          permisos para los scripts
├── scripts/
│   ├── draft.py               llama a OpenRouter
│   ├── validate.py            las 9 reglas
│   └── run_scene.py           conduce el ciclo de una escena
├── context/
│   ├── premise.yaml
│   ├── timeline.yaml
│   ├── characters/marco.yaml
│   └── real-figures.yaml
└── manuscript/
    └── ch01/S001.md
```

**Regla de reparto:** si el paso tiene una respuesta correcta, es un script; si
requiere criterio, es un subagente. El ciclo lo conduce `run_scene.py`, no el
modelo — un LLM iterando 45 veces deriva.

Un commit de git por escena aprobada. Si algo se descarrila, `git revert` y se
regenera desde ahí.

---

## 7. Decidido

| Qué | Valor |
|---|---|
| Unidad de trabajo | escena; tú apruebas al cerrar cada capítulo |
| Realismo | protagonista ficticio, mundo real (Mundial 90, clubes) |
| Personas reales | permitidas si tienen Wikipedia |
| Formato | español, ~40k palabras, ~45 escenas |
| Crítico | veta continuidad, aconseja en calidad |

## 8. Pendiente

- Qué modelos `:free` concretos usar (rotan; elegir al arrancar).
- Si cargar $10 en OpenRouter o generar por lotes durante varios días.
- Cómo se decide que la novela terminó.

## 9. Por dónde empezar

1. **10 escenas-trampa** con errores plantados (cumpleaños repetido, edad mal,
   jugar lesionado) y los errores que el validador debería detectar.
2. **`validate.py`**, probado contra ese fixture. Sin LLM, sin red, sin cuota.
3. **`draft.py`** con una escena de juguete, para medir la cuota real.
4. Recién entonces, los subagentes y el ciclo completo.
