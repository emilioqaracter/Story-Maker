# Rama `legado` — el conductor en Python

**Esta rama esta congelada.** El desarrollo sigue en `main`.

Aqui vive el sistema tal como era hasta el 16 de septiembre de 2026: el ciclo lo
conducia un bucle de Python y las novelas eran romances deportivos de pareja.
Se aparto entera, sin borrar nada, el dia que Claude Code paso a orquestar.

## Que hay aqui que no esta en `main`

| | Que hacia |
|---|---|
| `crear_novela.py` | el conductor: un `while` que preguntaba a `run_scene.py` que tocaba, llamaba a `claude -p` para cada paso de criterio y aplicaba las puertas |
| `demo.py` | corria el harness entero sobre dos libros de ejemplo y lo iba explicando |
| `nuevo_libro.py` | la entrevista de doce preguntas fijas por terminal |
| `books/` | ocho libros de ejemplo, todos con canon de pareja |
| el canon de pareja | `relacion.yaml` con cinco etapas (desconocidos, atraccion, intimidad, ruptura, union), `calendario.yaml` con fechas exactas de competicion, `real-figures.yaml` |
| las reglas duras que se fueron | V3 edad a la fecha, V4 cumpleanos, V7 lo que cada personaje sabe, V9 figuras reales, V20 hito del calendario |
| G2 aritmetica | el critico daba cinco notas, el script sumaba y comparaba contra un umbral |

## Por que se aparto

Un bucle determinista es reproducible pero es tonto: ante un fallo repetido solo
sabe reintentar el mismo camino tres veces y parar. El conductor agentico puede
leer el error, replanificar la escena y cambiar de estrategia.

Lo que **no** se movio al cambiar de conductor es quien acepta: las puertas de
hecho siguen siendo scripts en `main`. Se cambio quien elige el camino, no quien
pone el liston.

## Para que sirve tenerla

Para comparar. Es el mismo flujo, con las mismas puertas, corrido de forma
determinista: si alguna vez hay que responder «¿esto lo hace mejor el agente o
el bucle?», la respuesta esta a un `git checkout` de distancia.

    git checkout legado
    python demo.py
    python crear_novela.py books/marco-1990

No aceptes parches aqui: si algo de esto hace falta otra vez, se porta a `main`.
