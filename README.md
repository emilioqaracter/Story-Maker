# Story-Maker

Harness que escribe novelas románticas ambientadas en el deporte, sin
contradecirse. El diseño completo está en [SPEC.md](SPEC.md); esto es cómo se
corre.

**Principio:** la coherencia factual se calcula, no se recuerda. El modelo
escribe, el código verifica.

## Instalación

```bash
pip install -r requirements.txt
python -m pytest tests -q          # 47 escenas-trampa, sin red ni tokens
```

## El perfil v1

La versión actual **no escribe una novela: escribe un documento de 3 párrafos de
4 líneas** (144 palabras). Está fijado en `harness/config.yaml` y es a propósito:
recorre el mismo camino completo y produce los mismos JSON que una novela entera,
pero cabe en una pantalla. Los contratos se fijan con el caso chico.

Para subir la escala se tocan cuatro números en `harness/config.yaml`. Nada más.

## Empezar

```bash
python nuevo_libro.py     # te pregunta todo y crea el libro
python demo.py            # corre el harness entero sobre los libros de ejemplo
```

`nuevo_libro.py` te pide primero la forma del documento (perfil, o los cinco
numeros a mano) y despues las doce preguntas de la historia. Escribe el canon
entero y corre G0. Lo que no puede hacer, y te lo dice al terminar: investigar la
epoca y escribir la prosa, que necesitan agentes.

## Arrancar un libro a mano

```
1. interviewer   12 preguntas fijas          -> context/intake.json
2. researcher    época y calendario, 1 vez   -> epoca.yaml, calendario.yaml
3. planner       deriva el canon y planifica -> premise, characters, relacion, timeline
4. validate_canon.py                          -> G0: si no abre, no se escribe nada
```

## El ciclo, por escena

```bash
python harness/scripts/run_scene.py    books/marco-1990 next        # qué toca
python harness/scripts/resolver_canon.py books/marco-1990 S001      # el canon en prosa
#   -> escribir-escena (subagente)  ->  manuscript/ch01/S001.md
python harness/scripts/validate_scene.py books/marco-1990 S001      # G1
#   -> critic-continuity + critic-quality  ->  S001.critique.json
python harness/scripts/gate_scene.py   books/marco-1990 S001        # G2
python harness/scripts/run_scene.py    books/marco-1990 aprobar S001
```

## Cerrar

```bash
python harness/scripts/validate_book.py books/marco-1990   # G4: las tres condiciones
python harness/scripts/compilar.py      books/marco-1990   # -> manuscript/novela.md
```

## Las cinco puertas

| Puerta | Quién la abre | Si no abre |
|---|---|---|
| G0 canon | `validate_canon.py` | no se escribe una línea |
| G1 hechos | `validate_scene.py` | vuelve a corregir, sin gastar crítica |
| G2 criterio | `gate_scene.py` | vuelve a corregir |
| G3 capítulo | **vos** | parás y decidís |
| G4 obra | `validate_book.py` | sigue produciendo, o pregunta |

**Ningún agente abre su propia puerta.** El crítico puntúa una rúbrica con cita
obligatoria; quien suma y compara contra el umbral es un script.

## Un libro nuevo

```bash
mkdir -p books/<slug>/context/characters books/<slug>/manuscript books/<slug>/reports
```

Los scripts reciben la ruta del libro como argumento: no hay libro «actual».
`harness/` y `.claude/` valen para todos; `books/<slug>/` es una novela concreta.
