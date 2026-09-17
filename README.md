# Story-Maker

Un sistema que escribe **novelas deportivas cortas** —la historia de un
atleta, en tres actos— sin contradecirse, y que deja ver por dentro cómo lo
hizo.

La novela es la excusa. **Lo que se está construyendo son las capas de control
sobre un modelo**: las puertas que deciden si lo que produjo un modelo entra o
no entra, el criterio con evidencia que las abre, y la traza que cuenta después
qué pasó y por qué.

> Lo que se puede calcular no se recuerda. El modelo escribe; el código y otro
> modelo verifican.

- [SPEC-FUNCIONAL.md](SPEC-FUNCIONAL.md): qué hace el sistema y por qué.
- [SPEC-TECNICO.md](SPEC-TECNICO.md): archivos, scripts, reglas, contratos, traza.
- [CLAUDE.md](CLAUDE.md): lo que hace falta saber para trabajar en el repo.

## Cómo se usa

Se le pide a **Claude Code**, en la terminal o en VS Code:

```
> escribí una novela sobre un nadador que vuelve de una lesión, en 1975
> seguí con books/nuria-1992
```

Si no hay libro, sigue `preparar-libro` (decide y pregunta una sola vez); con el
canon listo sigue `dirigir-novela` (planifica, escribe, critica, corrige,
compila). Al final: `books/<slug>/manuscript/novela.md` y una traza en
`books/<slug>/reports/traza.jsonl`.

## Quién hace qué

| Pieza | Qué hace | Quién decide |
|---|---|---|
| **planner** | reparte la historia en escenas: resumen y tres beats | un script comprueba que no falte ninguno |
| **escritor** / **corrector** | la prosa; el corrector toca solo lo señalado | no deciden nada |
| **critic-continuity** | contradicciones con el canon; un hallazgo veta | **decide** (veta) |
| **critic-quality** | si la escena entra, con motivo; la rúbrica con cita | **decide** |
| **lector-capitulo** | lo que solo se ve leyendo el capítulo seguido | el script aplica sus hallazgos |
| **G0 · G1 · G4** | canon, hechos y forma, obra | scripts, siete reglas |

Cada agente corre con contexto limpio y recibe el canon **resuelto a la fecha
de su escena**, en prosa, dentro de un prompt que arma un script. Ningún agente
escribe archivos.

## Ver cómo funcionó

```bash
python harness/scripts/traza.py books/<slug>
```

Y con interfaz (`cd ui && npm install && npm run build`, luego
`python harness/server.py`): el mapa del sistema, la línea de tiempo de puertas
y agentes, y el expediente de cada novela escena por escena. Todo del disco.

## Correrlo a mano

```bash
pip install -r requirements.txt
python -m pytest tests -q                       # sin red ni tokens
python harness/scripts/comprobar_sistema.py
```

Los comandos del ciclo, uno por uno, están en [CLAUDE.md](CLAUDE.md).

## Estructura

```
.claude/         6 agentes y 6 skills
harness/         config.yaml · flujo.yaml · voz-base.md · vista.py · server.py · scripts/
books/<slug>/    context/ (el canon) · manuscript/ · reports/ · state.json
tests/           una trampa por regla y por script
ui/              React sobre harness/server.py
```

Langfuse es opcional: `cp .env.example .env` con tus claves y `reportar.py`
manda una traza por escena con la rúbrica como scores. Sin claves, no pasa nada.
