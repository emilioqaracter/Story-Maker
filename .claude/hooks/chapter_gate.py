#!/usr/bin/env python
"""Hook `PostToolUse` de Claude Code: la puerta de un fichero de capitulo.

`specs/srs-backend-v4.md` RF-251, RI-66, RNF-56, D-92.

Cuando Claude Code escribe o edita un `*.chapter.md` o `*.chapter.txt`, este
script pasa el texto por **los mismos verificadores deterministas que usa el
motor** --`verification.checks`, `check.forbidden`-- y por la puerta de escena de
`verification.gates`: cero S1. No reimplementa ninguno: los importa de
`backend/`. Una segunda copia se desincronizaria de la primera a la tercera
vez que alguien tocara un verificador.

Actua sobre el trabajo de desarrollo, no sobre la novela: nunca corre dentro de
una tirada, y los `claude -p` del motor no cargan hooks (RI-62). Por eso no es
revision humana ni del sistema dentro del ciclo (AGENTS.md 5.3.1).

    # como hook: el JSON de Claude Code por la entrada estandar
    echo '{"tool_name":"Write","tool_input":{"file_path":"x.chapter.md"}}' | python chapter_gate.py

    # a mano, sobre un capitulo congelado, con el canon de su novela
    python chapter_gate.py --novel backend/runs-x/n.sqlite --chapter 3

    # un fichero suelto con el canon de una novela
    python chapter_gate.py --novel n.sqlite --file borrador.chapter.md

Salida: 0 si pasa o si el fichero no es de capitulo; 2 con los defectos y su
cita en la salida de error si no pasa. **Falla cerrado** (AGENTS.md 5.3.6): si no
puede importar el backend, leer el fichero o ejecutar un verificador, sale con 2.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: RI-66. Los ficheros sobre los que actua. Todo lo demas pasa sin mirar.
CHAPTER_SUFFIXES = (".chapter.md", ".chapter.txt")

#: Codigo de salida que Claude Code devuelve al agente con la salida de error.
BLOCK = 2

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"


def is_chapter(path: str) -> bool:
    return path.replace("\\", "/").lower().endswith(CHAPTER_SUFFIXES)


@dataclass(frozen=True)
class Canon:
    """Lo que el canon de una novela aporta a los verificadores.

    Sin novela, las listas van vacias (RF-251): una fecha explicita no se puede
    contrastar con un calendario que no hay y cuenta como fallo, que es el lado
    seguro (AGENTS.md 5.3.6).
    """

    allowed_dates: list[str] = field(default_factory=list)
    forbidden: tuple[Any, ...] = ()
    style_terms: list[str] = field(default_factory=list)


def _import_backend() -> None:
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))


def load_canon(novel: Path) -> Canon:
    """Las listas de la novela, leidas en solo lectura como en `verify_scene`."""
    from canon.db import connection
    from verification.checks import forbidden

    with connection.reader(novel) as con:
        fechas = [r["world_time"] for r in con.execute("SELECT DISTINCT world_time FROM event")]
        fechas += [
            r["world_time"] for r in con.execute("SELECT DISTINCT world_time FROM prose_scene")
        ]
        return Canon(
            allowed_dates=fechas,
            forbidden=forbidden.read_terms(con),
            style_terms=forbidden.read_style_terms(con),
        )


def chapter_scenes(novel: Path, chapter: int) -> list[tuple[str, str]] | None:
    """(escena, texto) del capitulo en la version vigente; `None` si no esta."""
    from canon import manuscript
    from canon.db import connection

    with connection.reader(novel) as con:
        escenas = manuscript.chapter_at(con, chapter, manuscript.current_version(con))
    if escenas is None:
        return None
    return [(e.scene_id, e.text) for e in escenas]


def defects_of(scenes: list[tuple[str, str]], canon: Canon) -> list[tuple[str, Any]]:
    """Los defectos deterministas, con la escena en la que salen.

    Por escena, lo que `verify_scene` mira en cada una; sobre el capitulo unido,
    `check.forbidden` otra vez, como la segunda red antes de congelar: un termino
    de varias palabras puede quedar partido entre dos escenas.
    """
    from verification.checks import deterministic as checks
    from verification.checks import forbidden

    out: list[tuple[str, Any]] = []
    for escena, texto in scenes:
        encontrados = []
        encontrados += checks.check_format(texto)
        encontrados += checks.check_timeline(texto, allowed_dates=canon.allowed_dates)
        encontrados += forbidden.check_forbidden(texto, terms=canon.forbidden)
        encontrados += checks.check_repetition(
            texto, frozen_ngrams=[], proscribed=canon.style_terms
        )
        out += [(escena, d) for d in encontrados]
    if len(scenes) > 1:
        unido = "\n\n".join(t for _, t in scenes)
        vistos = {(d.rule, d.evidence.quote) for _, d in out if d.kind == forbidden.KIND}
        out += [
            ("capitulo", d)
            for d in forbidden.check_forbidden(unido, terms=canon.forbidden)
            if (d.rule, d.evidence.quote) not in vistos
        ]
    return out


def gate(scenes: list[tuple[str, str]], canon: Canon) -> tuple[bool, list[str]]:
    """La puerta de escena de `verification.gates` sobre los defectos: cero S1."""
    from verification import gates

    defectos = defects_of(scenes, canon)
    resultado = gates.scene_gate([d for _, d in defectos])
    lineas = [
        f"{d.severity} {d.kind} [{escena}] «{d.evidence.quote}» @{d.evidence.offset}: {d.rule}"
        for escena, d in defectos
    ]
    return resultado.passed, [f"puerta de capitulo: {resultado.reason()}", *lineas]


def _hook_paths(payload: dict[str, Any]) -> list[str]:
    """Las rutas que toco la herramienta: `file_path`, o las de cada edicion."""
    entrada = payload.get("tool_input") or {}
    rutas = [entrada.get("file_path")]
    rutas += [e.get("file_path") for e in entrada.get("edits") or [] if isinstance(e, dict)]
    return [r for r in rutas if isinstance(r, str) and r]


def _resolve(path: str, cwd: str | None) -> Path:
    p = Path(path)
    return p if p.is_absolute() or not cwd else Path(cwd) / p


def _block(lines: list[str]) -> int:
    sys.stderr.write("\n".join(lines) + "\n")
    return BLOCK


def run(argv: list[str], stdin: str) -> int:
    parser = argparse.ArgumentParser(description="Puerta de un fichero de capitulo")
    parser.add_argument("--novel", type=Path, help="SQLite de la novela cuyo canon se usa")
    parser.add_argument("--chapter", type=int, help="Capitulo congelado a validar")
    parser.add_argument("--file", type=Path, help="Fichero de capitulo a validar")
    args = parser.parse_args(argv)

    _import_backend()
    canon = Canon() if args.novel is None else load_canon(args.novel)

    if args.chapter is not None:
        if args.novel is None:
            return _block(["--chapter necesita --novel"])
        escenas = chapter_scenes(args.novel, args.chapter)
        if escenas is None:
            return _block([f"el capitulo {args.chapter} no esta en {args.novel}"])
        ok, lineas = gate(escenas, canon)
        return 0 if ok else _block(lineas)

    if args.file is not None:
        rutas = [args.file]
    else:
        payload = json.loads(stdin) if stdin.strip() else {}
        if not isinstance(payload, dict):
            return _block(["la entrada del hook no es un objeto JSON"])
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
        rutas = [_resolve(r, cwd) for r in _hook_paths(payload) if is_chapter(r)]
    if not rutas:
        return 0

    bloqueos: list[str] = []
    for ruta in dict.fromkeys(rutas):
        texto = ruta.read_text(encoding="utf-8")
        ok, lineas = gate([(ruta.name, texto)], canon)
        if not ok:
            bloqueos += [f"{ruta}:", *lineas]
    return _block(bloqueos) if bloqueos else 0


def _read_stdin() -> str:
    """El JSON del hook, en UTF-8 aunque la consola de Windows diga otra cosa."""
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    return sys.stdin.buffer.read().decode("utf-8")


def main() -> int:
    # Claude Code lee la salida de error en UTF-8; la consola de Windows no lo es.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        return run(sys.argv[1:], _read_stdin())
    except SystemExit as exc:  # argparse: argumentos malos tambien bloquean
        return BLOCK if exc.code not in (0, None) else 0
    except Exception as exc:  # fallo cerrado (RNF-56)
        return _block([f"puerta de capitulo: no se pudo validar ({type(exc).__name__}: {exc})"])


if __name__ == "__main__":
    raise SystemExit(main())
