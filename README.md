# Story-Maker

Un sistema que escribe novelas deportivas —la historia de un atleta— sin
contradecirse.

La novela es la excusa. **Lo que se está construyendo son las capas de control
sobre un modelo**: los filtros que deciden si lo que produjo un modelo entra o
no entra. La novela es el banco de pruebas porque es un dominio donde las
incoherencias se ven a simple vista: alguien que juega con la rodilla rota dos
escenas antes de que se la operen, un móvil en 1890, un final que llega en la
primera página.

> **El principio del que sale todo lo demás:**
> lo que se puede calcular no se recuerda.
> El modelo escribe, el código y otro modelo verifican.

El diseño completo y el porqué de cada decisión están en [SPEC.md](SPEC.md).
Esto es el mapa.

---

## 1. Cómo se usa

No hay un comando que escriba la novela. **Se lo pides a Claude Code**, en la
terminal o en el panel de la extensión de VS Code, escribiendo en lenguaje
natural:

```
> escribí una novela sobre un nadador que vuelve de una lesión, en 1975
> hacé una novela de boxeo ambientada en 1890
> seguí con books/marco-1990
```

Eso es todo. Al leer eso, Claude Code carga sus instrucciones
([`.claude/skills/`](.claude/skills/)) y arranca:

1. Si no hay libro todavía → sigue **`preparar-libro`**: deriva lo que puede de
   tu idea, manda a investigar la época, y te hace **una sola tanda de preguntas**
   sobre lo que de verdad cambia el libro. Si le dices "decidí vos", no pregunta.
2. Con el canon listo → sigue **`dirigir-novela`**: planifica, escribe escena por
   escena, las hace criticar, corrige lo que haga falta y compila el resultado.

Mientras trabaja te va diciendo una línea por escena aprobada y una por intento
fallido, con el motivo real. Al final tienes `books/<slug>/manuscript/novela.md`.

También se puede lanzar desde la interfaz web (§9), que por dentro hace
exactamente lo mismo.

---

## 2. La idea en una página

Un modelo escribiendo cuarenta escenas seguidas deriva: olvida en qué punto
está la historia, adelanta el final, mete un objeto que no existía. La
respuesta habitual es pedirle que "recuerde el contexto". Aquí la respuesta es
otra: **no se le pide que recuerde nada**.

**Lo que se puede derivar no se guarda.** En qué acto cae una escena no está
escrito en ningún sitio: se calcula por su fecha. Tampoco existe "el estado
actual" de un personaje: existen tramos con vigencia (`desde` / `hasta`), y el
estado a la fecha de una escena se calcula. Así no puede desincronizarse.

**El modelo nunca ve el canon crudo.** Antes de escribir, un script resuelve el
canon *a la fecha de esa escena* y lo entrega en prosa: quién está, cómo está
ese día, en qué acto estamos y qué se espera de él, qué no puede aparecer por
la época. El modelo no interpreta YAML ni calcula nada.

**Quien produce no es quien juzga.** El escritor escribe pero no decide si su
escena vale. Eso lo decide otro agente, con contexto limpio, que no ha visto los
intentos anteriores.

---

## 3. Las puertas: qué son y quién las abre

Una **puerta** es un punto donde el trabajo se para y alguien dice sí o no. No
es una formalidad: si dice que no, la escena vuelve atrás con los motivos y se
reescribe.

Hay dos tipos, y la diferencia importa:

### Puertas de hecho — las abre un script

Comprueban cosas que tienen una respuesta correcta y que se pueden contar o
comparar. No opinan sobre la novela. Un script las aplica siempre igual, cuesta
cero y no se discute.

| | Qué comprueba | Ejemplo de lo que caza |
|---|---|---|
| **G0** el canon | que la historia esté completa antes de escribir: hay protagonista, meta, obstáculo y precio; la época tiene su lista de anacronismos; el arco tiene sus tres actos; el plan cabe en el techo de palabras | "arco.yaml no declara `precio`" → sin precio no hay historia, hay un entrenamiento largo |
| **G1** los hechos | la escena cae dentro de la época y en orden; el protagonista no hace algo que su estado le impide; no aparece nada anacrónico; la forma (párrafos, líneas, palabras) | "Aparece 'móvil', que no existe en esta época" · "corrió, y el canon dice que está lesionado hasta el 12 de agosto" |
| **G4** la obra | los dos hilos quedan cerrados; los tres actos tienen escenas; la última escena cae en el desenlace; el libro no se pasa del techo | "El hilo H1 no lo cierra ninguna escena aprobada" |

### Puertas de criterio — las abre un agente

Comprueban cosas que no se pueden contar: si la escena funciona, si está en el
momento correcto de la historia, si contradice algo que no es formalizable.
**Aquí decide un modelo**, y el script solo comprueba que su decisión sea
utilizable.

| | Quién decide | Qué mira |
|---|---|---|
| **G2** la escena | el agente `critic-quality` devuelve `pasa: true/false` con motivo, y `critic-continuity` puede vetar con una cita | ¿pasa algo que le importe al protagonista? ¿está en su acto? ¿hace lo que pedía el plan? ¿contradice el canon? |
| **G3** el capítulo | el agente `lector-capitulo` señala lo que solo se ve leyendo seguido | repeticiones entre escenas, saltos, promesas plantadas y no recogidas |

**Qué comprueba el script en G2**, ya que no decide: que haya veredicto, que
traiga motivo (sin motivo el corrector no sabe qué tocar), que las notas de la
rúbrica citen el texto, y que la crítica **no sea más vieja que la prosa** — una
crítica rancia describe un texto que ya no existe, y aprobar con ella es
aprobar a ciegas.

### La rúbrica

Cinco dimensiones, cada una 0, 1 o 2. **Ya no decide nada**: es la medida que
permite comparar una corrida con otra y una versión del prompt con la
siguiente. Toda nota exige cita textual, el 2 incluido — si solo se exigiera
evidencia para las notas bajas, el camino más cómodo sería poner 2 en todo.

| Dimensión | 0 | 1 | 2 |
|---|---|---|---|
| conflicto | no pasa nada: termina como empezó | hay tensión, se resuelve sin costo | algo cambia y tiene precio |
| voz | podría haberlo escrito cualquiera | correcto pero neutro | suena a este libro y a este personaje |
| concreción | se nombran emociones | mezcla mostrar y explicar | la acción y el detalle físico llevan el peso |
| frescura | cliché o frases hechas | alguna muletilla | limpio |
| avance | el protagonista termina donde empezó | se mueve, pero nada le cuesta | algo cambia para él, y paga por ello |

---

## 4. El canon: qué es y qué se comprueba

El **canon** es el expediente del libro: quién es el protagonista, qué quiere,
qué se lo impide, qué le va a costar, en qué época transcurre, qué escenas hay.
Son los YAML de `books/<slug>/context/`, y **solo los cambia una persona**. Si
una escena contradice el canon, se cambia la escena.

Esa regla existe porque un ciclo que puede editar el canon para que su texto
pase deja de validar nada: cuando algo no cuadra, cambia el expediente y todo
"cuadra".

| Archivo | Qué contiene | ¿Regla dura? |
|---|---|---|
| `arco.yaml` | protagonista, **meta**, **obstáculo**, **precio**, y los tres actos con su fecha de inicio | sí: sin los tres primeros, G0 no abre |
| `premise.yaml` | deporte, lugar, época, los dos hilos | sí |
| `characters/*.yaml` | nombre, rol, y **estados con vigencia** (`lesionado desde X hasta Y`) | sí: es lo que sostiene un arco de recuperación |
| `epoca.yaml` | `prohibido` (lo que no existía) y `notas` (cómo se vivía) | sí, pero **cualitativa** |
| `timeline.yaml` | las escenas con su fecha, lugar, resumen y beats | el plan sí se puede replanificar |

**Lo que dejó de ser regla dura** (v9.0): la edad a la fecha, el cumpleaños, lo
que cada personaje sabe, las figuras reales y el calendario deportivo. No eran
malas reglas; eran demasiada precisión. La época ahora se pide **coherente, no
exhaustiva**: que en 1800 no haya móviles y en 2010 sí haya internet, no qué día
se jugó cada partido. Lo que el canon sigue sabiendo llega igual al escritor en
el contexto resuelto, y las contradicciones que queden son trabajo del crítico
de continuidad, que para eso lee.

---

## 5. La estructura: tres actos

Toda novela sigue el reparto clásico, y el acto de cada escena **se calcula**
por su fecha (25% / 50% / 25% de la ventana temporal del libro).

| Acto | Qué tiene que pasar ahí |
|---|---|
| **planteamiento** | queda claro quién es el protagonista, qué quiere y qué se lo impide |
| **desarrollo** | el obstáculo aprieta y el precio sube: algo se pierde por el camino |
| **desenlace** | la meta se resuelve —consiguiéndola o no— y cuesta lo que se anunció |

El escritor recibe en su contexto en qué acto está y qué se espera de él. G4
comprueba que los tres tengan escenas y que la última caiga en el desenlace. Un
libro de menos de tres escenas no puede cubrir tres actos, y el harness deja de
exigirlo: una regla que no se puede cumplir no es una regla.

---

## 6. Los agentes: quién es cada uno

Viven en [`.claude/agents/`](.claude/agents/). Cada uno corre en **su propio
proceso, con contexto limpio**: los dos críticos no se ven entre sí, no saben en
qué intento van y no leen la crítica anterior. Eso evita que una crítica
arrastre a la siguiente.

| Agente | Cuándo entra | Qué hace | Qué **no** hace | Skills |
|---|---|---|---|---|
| **researcher** | una vez, al arrancar | averigua qué no existía en esa época y cómo se vivía entonces | no busca calendarios ni fechas de competiciones; no escribe archivos | `epoca` |
| **planner** | al arrancar, y cuando una escena se atasca | reparte la historia en escenas: resumen + 3 beats, respetando el acto de cada una | no escribe prosa, no elige el acto (se calcula), no toca el canon | `resolver-canon` |
| **escritor** | cada escena, primer intento | redacta la escena desde el canon resuelto y la voz del libro | no escribe el archivo, no juzga su escena | `escribir-escena`, `epoca` |
| **corrector** | cada intento a partir del 2º | reescribe **solo** lo que señalan los errores | no reescribe lo que ya pasó, no cambia el canon | `corregir-escena` |
| **critic-continuity** | cada intento, tras G1 | busca contradicciones con el canon que un script no puede formalizar, y **veta** | no reescribe, no puntúa | `formato-critica` |
| **critic-quality** | cada intento, tras G1 | **decide si la escena entra** y puntúa la rúbrica con cita | no reescribe, no toca el canon | `formato-critica` |
| **lector-capitulo** | al cerrar un capítulo | lee las escenas seguidas y señala lo que solo se ve así | no repite el trabajo de G1/G2, no decide si el capítulo pasa | — |

El **orquestador** (Claude Code) no está en la lista porque no es un subagente:
es quien los despacha.

### Por qué dos críticos y no uno

Son dos criterios incompatibles. La continuidad es binaria —hay contradicción o
no la hay— y **veta**: un solo hallazgo cierra la puerta. La calidad es gradual
y decide en conjunto. Mezclarlas haría que una escena bien escrita compensara
una contradicción, que es justo lo que no puede pasar.

---

## 7. Las skills: qué es cada una

Una skill es el manual de un trabajo concreto. Se carga cuando ese trabajo
toca, y no antes. Viven en [`.claude/skills/`](.claude/skills/).

| Skill | Para quién | Qué contiene |
|---|---|---|
| **preparar-libro** | el orquestador | cómo convertir una idea en un canon que abre G0: los tres cubos (lo que se calcula / se averigua / se decide) y cuándo está justificado preguntar |
| **dirigir-novela** | el orquestador | el recorrido entero, qué correr y qué delegar, las reglas que no se rompen, y qué hacer cuando algo se atasca |
| **resolver-canon** | planner, y cualquiera antes de escribir | cómo se entrega el canon resuelto a una fecha, en prosa |
| **escribir-escena** | escritor | la voz: tercera persona, pasado, un solo punto de vista, la emoción no se nombra, el deporte como oficio |
| **corregir-escena** | corrector | la regla del bisturí: tocar solo lo señalado |
| **formato-critica** | los dos críticos | el JSON exacto del veredicto, el veto y la rúbrica |
| **epoca** | researcher, escritor, críticos | cómo hacer que el año se note sin explicarlo |

---

## 8. El recorrido completo

```
IDEA
 └─ preparar-libro
     ├─ exprime la idea y decide meta / obstáculo / precio
     ├─ pregunta UNA vez solo lo que cambia el libro
     ├─ crear_libro.py    → escribe el canon (arco de 3 actos incluido)
     ├─ researcher        → qué no existía y cómo se vivía
     └─ guardar_plan.py   → lo guarda (el agente no escribe YAML)

 └─ G0  validate_canon.py ─── script. Si no abre, se para aquí

 └─ planner → guardar_plan.py ─── resumen y beats, por acto

 └─ POR CADA ESCENA (hasta 3 intentos):
     ├─ run_scene.py contexto  → el canon resuelto: quién, cómo está, qué acto
     ├─ escritor / corrector   → la prosa
     ├─ G1  validate_scene.py  → script: hechos y forma
     ├─ critic-continuity ┐
     ├─ critic-quality    ┘    → dos llamadas separadas, contexto aislado
     ├─ G2  gate_scene.py      → releva el veredicto del crítico
     └─ run_scene.py aprobar

 └─ AL CERRAR UN CAPÍTULO: lector-capitulo → G3 gate_chapter.py
 └─ G4  validate_book.py ─── los tres actos, los hilos, el techo
 └─ compilar.py ──────────── novela.md
 └─ reportar.py ──────────── manda a Langfuse la vista por escena
```

[`harness/flujo.yaml`](harness/flujo.yaml) declara esto mismo en un YAML que la
UI lee y compara contra lo que realmente corrió. Si se añade o mueve un paso,
se actualiza ahí.

---

## 9. El repositorio

```
.claude/           el sistema agéntico
  agents/          7 agentes (§6)
  skills/          7 skills (§7)
  settings.json    permisos y TRACE_TO_LANGFUSE

harness/           el código que juzga. Vale para todos los libros
  config.yaml      la forma del documento, la rúbrica y los tres actos
  flujo.yaml       el flujo declarado, para la UI
  voz-base.md      el registro del género, punto de partida de voz.md
  derivaciones.py  lo que se calcula: claves, actos, fechas, perfiles
  server.py        API local para la UI
  scripts/         los validadores y las puertas

books/<slug>/      una novela
  context/         el canon
  manuscript/      la prosa, sus validaciones y sus críticas
  reports/         la traza y el informe final
  state.json       en qué escena va y cuántos intentos lleva

tests/             una escena-trampa por regla (55, sin red ni tokens)
ui/                interfaz React sobre harness/server.py
```

| Script | Qué hace |
|---|---|
| `common.py` | carga el canon y deriva. **Todos los validadores salen por `emitir()`**, que imprime, guarda y deja traza: una puerta nueva no puede olvidarse de registrarse |
| `run_scene.py` | conduce el estado: qué toca, el canon resuelto, contar intentos, aprobar, `reset` |
| `validate_canon.py` `validate_scene.py` `gate_scene.py` `gate_chapter.py` `validate_book.py` | G0, G1, G2, G3, G4 |
| `compilar.py` | concatena las escenas aprobadas en `novela.md` |
| `crear_libro.py` | crea un libro desde un JSON, sin preguntar nada |
| `guardar_plan.py` | guarda lo que devuelven researcher y planner. **Existe para que ningún agente escriba YAML** |
| `traza.py` | el registro append-only de lo que hizo el código |
| `reportar.py` | manda a Langfuse la vista por escena |

---

## 10. Ver cómo funcionó (Langfuse)

Dos registros que responden preguntas distintas.

**`books/<slug>/reports/traza.jsonl` — lo que hizo el código.** Un evento por
puerta: cuál, si abrió, y **con qué errores** si no. Lo escribe cada validador
al emitir su JSON. Se escribe en el momento: si el ciclo se corta, lo que pasó
hasta ahí queda.

**Langfuse — lo que hizo el modelo.** Dos vistas complementarias:

- **Por conversación**, vía el hook oficial de Claude Code: cada turno con sus
  tool calls, tokens y coste. Cuenta *cómo trabajó el agente*.
- **Por novela**, vía `reportar.py`: una sesión por libro, una traza
  `producir-escena` por escena con sus intentos y sus puertas, y **scores** con
  el veredicto y las cinco dimensiones de la rúbrica. Cuenta *cómo salió el
  libro*, y es lo que permite comparar corridas entre sí.

### Configurarlo

```bash
cp .env.example .env     # y pega tus claves de Langfuse
```

`.env` está en `.gitignore` y no se commitea. Para la vista por conversación,
además, el hook: está documentado en
[langfuse.com/integrations/developer-tools/claude-code](https://langfuse.com/integrations/developer-tools/claude-code),
se instala en `~/.claude/hooks/langfuse_hook.py` y se activa con
`TRACE_TO_LANGFUSE` en `.claude/settings.json` (ya está puesto).

Todo esto es **opcional**: sin claves, el harness corre igual y no se entera.

---

## 11. Correrlo a mano

```bash
pip install -r requirements.txt
python -m pytest tests -q          # 55 escenas-trampa, sin red ni tokens
```

Las piezas sueltas, por si hace falta:

```bash
python harness/scripts/run_scene.py      books/<slug> next
python harness/scripts/run_scene.py      books/<slug> contexto S001
python harness/scripts/validate_scene.py books/<slug> S001
python harness/scripts/gate_scene.py     books/<slug> S001
python harness/scripts/gate_chapter.py   books/<slug> 1      # la lectura por stdin
python harness/scripts/validate_book.py  books/<slug>
python harness/scripts/reportar.py       books/<slug>
python harness/scripts/run_scene.py      books/<slug> reset  # volver a empezar
```

`reset` devuelve el libro al punto de partida sin tocar `context/`.

Con interfaz:

```bash
cd ui && npm install && npm run build
python harness/server.py                  # http://127.0.0.1:8770
```

La UI no decide nada: crea el canon y lanza a Claude Code con la misma skill.

---

## 12. Las reglas que no se rompen

Cada una está porque su ausencia rompió algo, y está documentada con su fecha
en el historial del SPEC (§16).

1. **Nadie abre su propia puerta.** Quien escribe no decide si lo escrito vale.
   El crítico decide, pero sobre el trabajo de otro y sin ver los intentos
   anteriores.
2. **Ningún agente escribe el canon.** Devuelven prosa o JSON y un script lo
   guarda. Un agente escribiendo YAML mete un `:` sin comillas y deja el canon
   ilegible; el fallo aparece tres pasos después disfrazado de otra cosa.
3. **El prompt a `claude -p` viaja por stdin, nunca como argumento.** En
   Windows `claude` es un shim `.cmd` y cmd.exe corta el argumento en el primer
   salto de línea.
4. **El canon solo lo cambia una persona.** Si una escena lo contradice, se
   cambia la escena. Lo único replanificable son los `beats`, que son plan.
5. **Toda nota de la rúbrica exige cita**, el 2 incluido.
6. **Todo error dice qué está mal, cuál es la verdad y cómo se arregla.** Un
   error sin `arreglo` no es accionable.

### Las políticas de contexto

| Fallo | Política |
|---|---|
| relleno de contexto | ningún paso recibe un archivo del canon: recibe la resolución a su fecha |
| prerrequisitos invisibles | si no está escrito en el canon, no existe |
| borradores rancios | contexto limpio por llamada; una crítica más vieja que la prosa no abre G2 |
| vaivén de altitud | ante un fallo se cambia la regla o el dato, nunca el nivel del prompt |
| depurar solo el prompt | antes de tocar un prompt, comprobar que el dato llegó |
| métricas silenciosas | ninguna puerta abre sin evidencia citable |

> Escribir para no olvidar, aislar para no contaminar, seleccionar para no
> ahogar, comprimir para no interpretar.

---

## 13. Si vas a tocar algo

- **Cada cambio del SPEC se registra en su historial (§16), en la misma
  entrega**, con versión, fecha, qué cambió y **por qué**. El log de git guarda
  el qué; el porqué de una decisión solo vive ahí.
- **Los tests primero** al agregar una regla: escribir la escena-trampa, verla
  fallar, después implementar. Si una regla no tiene su trampa en
  `tests/test_reglas.py`, no está comprobada.
- Código y comentarios **en español, sin tildes en el código fuente** (la
  consola de Windows viene en cp1252 y los rompe). La prosa de las novelas sí
  lleva tildes.
- Si agregas o mueves un paso del ciclo, actualiza `harness/flujo.yaml`.
- **El servidor no recarga código.** Si tocas `harness/server.py` o los
  scripts, reinícialo.
