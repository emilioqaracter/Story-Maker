---
name: dirigir-novela
description: Dirige el ciclo entero de una novela de punta a punta, sin intervencion humana - crea el canon, investiga, planifica, escribe, critica, corrige y compila. Usala cuando pidan escribir una novela, seguir un libro empezado o correr el harness completo.
---

# Dirigir una novela

Vos llevas el ciclo. No hay script conductor y no hay nadie a quien preguntar:
desde la idea hasta `novela.md`, las decisiones son tuyas.

**Lo que NO es tuyo es el criterio de aceptacion.** Vos decidis que hacer a
continuacion; si lo hecho vale lo dice otro. Desde la v9.0 ese otro es, segun
el caso, un script o **otro agente**:

- Los **hechos** los comprueba un script y no se discuten: la epoca, el estado
  del protagonista, la forma. G1 y G0.
- El **criterio** lo pone la lente de calidad, que devuelve `pasa` con motivo.
  G2 releva ese veredicto; no lo recalcula y vos tampoco.

Lo que ninguna de las dos cosas admite es que **vos** decidas que una escena
esta bien. Escribis, medis y acatas.

> Vos elegis el camino. El veredicto no lo pones vos.

## Las cuatro reglas que no se rompen

1. **Ninguna puerta la abris vos.** Nunca escribas "la escena esta bien, sigo".
   Corres el script, lees su JSON y acatas su `ok`. Si no te gusta el veredicto
   —lo diga el script o la lente de calidad— el camino es corregir la escena,
   no convocar otra vez al critico a ver si esta vez dice que si.
2. **El canon no se toca.** Ni para desatascar, ni para que una escena pase, ni
   cuando G4 no abre. Si la prosa contradice el canon, se cambia la prosa. Lo
   unico que se replanifica son los `beats` y el `resumen` de una escena, que es
   plan y no canon. El arco —meta, obstaculo, precio y los tres actos— no se
   toca nunca desde aqui.
3. **Los archivos los escriben los scripts.** Lo unico que guardas vos es la
   prosa y la critica de una escena, que son `.md` y `.json` sueltos. El canon,
   el plan y el estado van **siempre** por `guardar_plan.py`, `crear_libro.py` o
   `run_scene.py`. Nunca edites a mano `timeline.yaml`, `state.json` ni nada de
   `context/`: un ':' sin comillas en un YAML deja el canon ilegible y el fallo
   aparece tres pasos despues disfrazado de otra cosa.
4. **Cada llamada a un subagente va limpia.** Un agente por Task, con todo lo
   que necesita en su prompt. Los dos criticos no se ven entre si, no saben en
   que intento van, y no leen la critica del intento anterior.

## Lo que corres y lo que delegas

| Paso | Como |
|---|---|
| resolver el canon a una fecha | `python harness/scripts/run_scene.py <libro> contexto <SID>` |
| que toca ahora | `run_scene.py <libro> next` |
| G0 canon | `validate_canon.py <libro>` |
| G1 hechos | `validate_scene.py <libro> <SID>` |
| G2 rubrica | `gate_scene.py <libro> <SID>` |
| G3 capitulo | `gate_chapter.py <libro> <N>` (la lectura por stdin) |
| G4 obra | `validate_book.py <libro>` |
| aprobar | `run_scene.py <libro> aprobar <SID>` |
| compilar | `compilar.py <libro>` |
| crear el libro | `crear_libro.py <json>` (ver skill `preparar-libro`) |
| guardar epoca o beats | `guardar_plan.py <libro> epoca\|beats` (JSON por stdin) |
| escribir / corregir / criticar / planificar / investigar / leer | subagentes (Task) |

Todo lo que tiene una respuesta correcta es un script. Todo lo que pide
criterio es un subagente. Si dudas de cual es cual: si dos personas razonables
darian la misma respuesta, es un script.

## El recorrido

### 0. El libro, la epoca y G0

Si te dan `books/<slug>` con el canon hecho, salta al paso 1.

Si te dan una idea, **eso es otra skill**: segui `preparar-libro`, que convierte
la idea en un canon que abre G0 — deriva lo derivable, manda al `researcher` a
por la epoca y pregunta una sola vez lo que de verdad cambia el libro. Volve
aca con G0 abierto.

Si el libro existe pero `context/epoca.yaml` no tiene `prohibido`, tambien es
`preparar-libro`: le falta el arranque.

**Sin G0 abierto no se escribe una sola linea de prosa.**

### 1. Planificar

Si hay escenas sin `beats`, Task al agente `planner` con la meta, el obstaculo,
el precio, los hilos y las escenas pendientes **con el acto de cada una**
(`validate_canon.py` te lo devuelve en `actos`). El acto no lo elige el planner:
se calcula por la fecha. Devuelve
`resumen` y `beats`. **No los escribas vos**: van por
`python harness/scripts/guardar_plan.py <libro> beats` (JSON por stdin), que
solo toca esos dos campos y solo de las escenas que el plan nombra.

### 2. El bucle, escena por escena

`run_scene.py <libro> next` te dice que toca. Repeti hasta que diga `cerrar`.

Para cada escena:

1. **Contexto**: `run_scene.py <libro> contexto <SID>`. Eso, y solo eso, es lo
   que sabe el escritor. No le pases el canon crudo ni otras escenas.
2. **Escribir**: Task a `escritor` con el contexto resuelto y `context/voz.md`.
   Si es una correccion, Task a `corrector` con la escena actual y los errores
   tal cual salieron del validador — con su regla, su mensaje y su arreglo.
   Guarda la prosa que devuelve en `manuscript/chNN/SNNN.md`.
3. **G1**: `validate_scene.py`. Si cierra, volve al paso 2 con esos errores.
   Es determinista y gratis: filtra aca antes de gastar dos criticos.
4. **Criticar**: dos Task **separados**, `critic-continuity` y `critic-quality`,
   cada uno con la escena y el canon resuelto. La de calidad devuelve el
   **veredicto** (`pasa` + motivo): es quien decide. Junta las dos respuestas en
   `manuscript/chNN/SNNN.critique.json` con la forma que pide la skill
   `formato-critica`.

   Al critico de calidad pasale **el acto** de la escena y que se espera de el:
   sin eso no puede juzgar si la escena llega tarde o temprano.
5. **G2**: `gate_scene.py`. Releva el veredicto y comprueba que la critica sea
   legitima (que hable del texto actual, que el motivo exista, que las notas
   citen). Si cierra, volve al paso 2 con esos errores.
6. **Aprobar**: `run_scene.py <libro> aprobar <SID>`.
7. Si al aprobar te avisa que **cierra un capitulo**, hace G3 (abajo).

### 3. G3 — el capitulo

Task a `lector-capitulo` con las escenas del capitulo **seguidas**. Devuelve
hallazgos con cita. Pasaselos a `gate_chapter.py <libro> <N>` por stdin.

Si cierra, las escenas que senala vuelven al bucle: `run_scene.py <libro>
intento <SID>` para que cuente el intento, y de ahi al paso 2 con esos errores.

### 4. G4 — la obra

`validate_book.py`. Si no abre, mira **que** condicion falla:

- Un hilo sin cerrar (V10), un acto sin escenas (V17) o una ultima escena que
  no cae en el desenlace (V18): es un problema de **plan**, no de canon.
  Replanifica las escenas que aun no estan aprobadas para que cierren lo que
  falta, y volve al bucle. Si ya estan todas aprobadas, la ultima es la que
  tiene que cambiar: `run_scene.py <libro> intento <SID>` y corregila.
- El techo (C2): contrae las escenas que queden.

### 5. Compilar

`compilar.py <libro>` y decis donde quedo y cuantas palabras tiene.

## Cuando algo se atasca

`intentos_max` (3 por defecto, en `harness/config.yaml`) es por escena. Cuando
se agota, **no pares a preguntar**. En orden:

1. **Replanifica la escena**: Task al `planner` solo para ese `SID`, diciendole
   que los beats actuales no se pudieron escribir sin romper la rubrica.
   Guarda los beats nuevos y `run_scene.py <libro> intento <SID>` para volver a
   contar desde ahi. Esto se hace **una vez por escena**.
2. Si despues de replanificar vuelve a agotarse, **para de verdad**: deja el
   libro como esta y explica que escena, que puerta y con que error. Insistir
   mas es quemar tokens en el mismo muro. Eso no es pedir permiso, es informar.

Un fallo que se repite en todas las escenas (todas cierran G1 por forma, por
ejemplo) no se arregla reintentando: mira el contexto que les llegas pasando.
Antes de tocar un prompt, comproba que el dato llego.

## Al terminar

Deci en cinco lineas: cuantas escenas, y **una linea por intento fallido con su
motivo real** ("S002 intento 1: el critico rechazo, el protagonista no decide
nada"). Sin volcar los JSON. Despues, donde quedo el entregable.

Mientras trabajas, lo mismo: una linea por escena cuando se aprueba y una por
intento que falla, con el motivo. Ni silencio ni volcado.

**Antes de terminar, corre `python harness/scripts/reportar.py <libro>`.** Manda
a Langfuse una traza por escena, con sus intentos, sus puertas y la rubrica como
scores. Si no hay claves configuradas no hace nada y no molesta.

`reports/traza.jsonl` lo escriben las propias puertas al emitir su veredicto, no
vos: ahi queda lo que hizo el codigo. Lo que hizo el modelo lo cuenta Langfuse.
