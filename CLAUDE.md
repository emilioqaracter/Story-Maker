# Story-Maker

Harness que escribe novelas románticas ambientadas en el deporte. El diseño
completo y el porqué de cada decisión están en [SPEC.md](SPEC.md); esto es lo
que hace falta saber para trabajar en el repo.

**De qué se trata en realidad:** esto no es un generador de texto, es un banco
de pruebas para **capas de control sobre un modelo**. La novela es la excusa;
lo que se está construyendo son las puertas, los validadores y las rúbricas que
deciden si lo que produjo un modelo entra o no entra.

## El principio

> La coherencia factual se **calcula**, no se recuerda. El modelo escribe, el
> código verifica.

De ahí sale todo lo demás. Si un dato se puede derivar, no se guarda: no existe
un campo `edad`, existe `nacimiento`. No existe «el estado actual» de un
personaje, existen tramos con vigencia.

## Reglas que no se rompen

Estas no son preferencias de estilo. Cada una está porque su ausencia rompió
algo, y está documentada con su fecha en el historial del SPEC.

1. **Ningún agente abre su propia puerta.** El escritor no decide si escribió
   bien; el crítico no decide si la escena pasa; el planificador no decide si su
   plan cabe. Emiten algo estructurado y un script aplica un umbral escrito.

2. **Ningún agente escribe archivos.** Devuelven prosa o JSON y el script los
   guarda. Un agente escribiendo YAML mete un `:` sin comillas y deja el canon
   ilegible; y pedirle que cree un archivo abre una superficie de permisos que
   falla en silencio. Hay un solo dueño del estado: el código.

3. **El prompt a `claude -p` viaja por stdin, nunca como argumento.** En Windows
   `claude` es un shim `.cmd` y cmd.exe corta el argumento en el primer salto de
   línea. Con argv el modelo recibe un prompt vacío y contesta «no me llegó
   ninguna escena» — y esa queja termina escrita como si fuera prosa.

4. **El canon solo lo cambia una persona.** Si una escena contradice el canon,
   se cambia la escena. Un ciclo que puede editar el canon para que su texto
   pase deja de validar nada.

5. **Toda nota de la rúbrica exige cita**, el 2 incluido. Exigir evidencia solo
   donde la nota baja deja abierto el camino cómodo: poner 2 en todo sin mirar.

6. **Todo error dice qué está mal, cuál es la verdad y cómo se arregla.** Un
   error sin `arreglo` no es accionable y no sirve.

## Políticas de contexto

Los seis fallos típicos y qué hace el harness con cada uno (detalle en §8 del
SPEC). Un validador no salva a un modelo al que nunca le dijeron lo que
necesitaba.

| Fallo | Política |
|---|---|
| Relleno de contexto | ningún paso recibe un archivo del canon, recibe la resolución a su fecha |
| Prerrequisitos invisibles | si no está escrito en el canon, no existe |
| Borradores rancios | contexto limpio por llamada; una crítica más vieja que la prosa no abre G2 |
| Vaivén de altitud | ante un fallo se cambia la regla o el dato, nunca el nivel del prompt |
| Depurar solo el prompt | antes de tocar un prompt, comprobar que el dato llegó |
| Métricas silenciosas | ninguna puerta abre sin evidencia citable |

Las cuatro formas de manejar el contexto, y para qué sirve cada una acá:

- **Escribir** — canon, `state.json`, beats, traza, un commit por escena. Nada
  vive solo en la conversación.
- **Aislar** — un proceso nuevo por llamada; las dos lentes no se ven entre sí
  ni saben en qué intento van.
- **Seleccionar** — `resolver-canon` manda solo lo que aplica a esa fecha.
- **Comprimir** — el canon llega en prosa resuelta, nunca en YAML crudo.

> Escribir para no olvidar, aislar para no contaminar, seleccionar para no
> ahogar, comprimir para no interpretar.

## Las cinco puertas

| Puerta | Quién la abre | Qué comprueba |
|---|---|---|
| G0 canon | `validate_canon.py` | V21, V13, V16, que el plan quepa |
| G1 hechos | `validate_scene.py` | V1-V9, V14-V16, V20 |
| G2 criterio | `gate_scene.py` | veto de continuidad + rúbrica con citas + crítica al día |
| G3 capítulo | **una persona** | lo lee |
| G4 obra | `validate_book.py` | V10-V12, V17-V19 + las tres condiciones |

G1 corre siempre antes que G2: es determinista y gratis, y filtrar ahí antes de
convocar dos críticos es lo que mantiene el ciclo barato.

## Ver como funciono

`reports/traza.jsonl` guarda un evento por paso: agente, fase, escena, intento,
duracion, tokens reales y costo, y las puertas con **sus errores**. Se escribe
en el momento, no al final: si el ciclo se corta, lo que paso hasta ahi queda.

En la UI es la pestana «Como funciono» de cada libro. Los tokens salen de
`claude -p --output-format json`, no de una estimacion.

`harness/flujo.yaml` declara el flujo entero: quien trabaja, en que orden, con
que skill, que herramientas y contra que regla. La ventana «Flujo de trabajo»
lo muestra al lado de la traza real. Si agregas o mueves un paso del ciclo,
actualizalo ahi: es lo que evita que la pantalla cuente otra historia.

**El servidor no recarga codigo.** Si tocas `harness/server.py` o los scripts,
reinicialo. La UI avisa si detecta un servidor viejo.

## Ver como funciono

`reports/traza.jsonl` guarda un evento por paso: agente, fase, escena, intento,
duracion, tokens reales y costo, y las puertas con **sus errores**. Se escribe
en el momento, no al final: si el ciclo se corta, lo que paso hasta ahi queda.

En la UI es la pestana «Como funciono» de cada libro. Los tokens salen de
`claude -p --output-format json`, no de una estimacion.

## Estructura

```
.claude/     agentes y skills      \  el harness: vale para todos los libros
harness/     config y scripts      /
books/<slug>/  context · manuscript · reports · state.json   una novela
tests/       una escena-trampa por regla
```

Los scripts reciben la ruta del libro como argumento. **No hay libro «actual».**

## Comandos

```bash
python -m pytest tests -q          # 56 tests, sin red ni tokens
python demo.py                     # corre el harness entero y lo explica
python nuevo_libro.py              # entrevista y crea un libro
python crear_novela.py books/<slug> # encadena todo: escribe, critica, compila
```

Con interfaz:

```bash
cd ui && npm install && npm run build     # una vez
python harness/server.py                  # http://127.0.0.1:8770
```

En desarrollo, `python harness/server.py` y `cd ui && npm run dev` en paralelo:
Vite sirve en :5273 y proxea `/api` al servidor.

La UI no decide nada. Crea el canon y lanza los mismos scripts; las puertas
siguen siendo de ellos. `harness/server.py` es un envoltorio delgado sobre
`harness/scripts/` y sobre `nuevo_libro.py`: no hay dos caminos para lo mismo.

Del ciclo, por partes:

```bash
python harness/scripts/run_scene.py      books/<slug> next
python harness/scripts/resolver_canon.py books/<slug> S001
python harness/scripts/validate_scene.py books/<slug> S001
python harness/scripts/gate_scene.py     books/<slug> S001
python harness/scripts/validate_book.py  books/<slug>
python harness/scripts/run_scene.py      books/<slug> reset   # volver a empezar
```

`reset` devuelve el libro al punto de partida sin tocar `context/`: borra la
prosa, las criticas, el estado y el entregable. El canon no se toca nunca.

## Al trabajar acá

- **Cada cambio del SPEC se registra en su historial (§15), en la misma
  entrega.** Con versión, fecha, qué cambió y **por qué**. El log de git guarda
  el qué; el porqué de una decisión de diseño solo vive ahí.
- Los tests primero cuando se agrega una regla: escribir la escena-trampa,
  verla fallar, después implementar.
- El código y los comentarios van en español, sin tildes en el código fuente
  (la consola de Windows viene en cp1252 y los rompe). La prosa de las novelas
  sí lleva tildes.
- Si una regla nueva no tiene su trampa en `tests/test_reglas.py`, no está
  comprobada.

## Lo que NO está en el camino crítico

La investigación por internet (`researcher`) es opcional: si `epoca.yaml` ya
tiene anacronismos, `crear_novela.py` no la toca. Un libro con el canon escrito
a mano va derecho al ciclo de redacción, que es lo que importa que funcione.
