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

## Las cinco puertas

| Puerta | Quién la abre | Qué comprueba |
|---|---|---|
| G0 canon | `validate_canon.py` | V21, V13, V16, que el plan quepa |
| G1 hechos | `validate_scene.py` | V1-V9, V14-V16, V20 |
| G2 criterio | `gate_scene.py` | veto de continuidad + rúbrica con citas |
| G3 capítulo | **una persona** | lo lee |
| G4 obra | `validate_book.py` | V10-V12, V17-V19 + las tres condiciones |

G1 corre siempre antes que G2: es determinista y gratis, y filtrar ahí antes de
convocar dos críticos es lo que mantiene el ciclo barato.

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
python -m pytest tests -q          # 52 tests, sin red ni tokens
python demo.py                     # corre el harness entero y lo explica
python nuevo_libro.py              # entrevista y crea un libro
python crear_novela.py books/<slug> # encadena todo: escribe, critica, compila
```

Del ciclo, por partes:

```bash
python harness/scripts/run_scene.py      books/<slug> next
python harness/scripts/resolver_canon.py books/<slug> S001
python harness/scripts/validate_scene.py books/<slug> S001
python harness/scripts/gate_scene.py     books/<slug> S001
python harness/scripts/validate_book.py  books/<slug>
```

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
