"""Compila las dos fixtures de Lean: la puerta de RF-246.

    python -m verification.formal.fixtures            # comprueba y compila
    python -m verification.formal.fixtures --write    # regenera los .lean versionados
    python -m verification.formal.fixtures --record   # guarda la salida en lean/last-build.txt

Pasa solo si las dos cronologias versionadas son las que genera hoy el canon de
su fixture, si `lake build` compila la limpia y si `lake build Seeded` falla en
sus cuatro teoremas, con las filas de `SEEDED`, y en ningun otro sitio. Sin
`lake`, falla: la puerta cierra (`specs/srs-backend-v4.md` §7.2).
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess  # nosec B404 - git con lista de argumentos, sin shell
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from canon.db import connection
from verification.formal.check import LeanResult, prove
from verification.formal.fixtures import (
    CLEAN_FILE,
    LEAN,
    SEEDED,
    SEEDED_FILE,
    SEEDED_TARGET,
    build,
)
from verification.formal.generate import Chronicle, read_chronicle, render, write

RECORD = LEAN / "last-build.txt"


def _chronicles() -> tuple[Chronicle, Chronicle]:
    with tempfile.TemporaryDirectory() as tmp:
        out = []
        for seeded in (False, True):
            path = build(Path(tmp) / f"{'seeded' if seeded else 'clean'}.sqlite", seeded=seeded)
            with connection.reader(path) as con:
                out.append(read_chronicle(con))
    return out[0], out[1]


def _judge_seeded(result: LeanResult) -> list[str]:
    """Lo que no cuadra con `SEEDED`. Vacio si falla justo donde debe."""
    problems: list[str] = []
    if result.passed:
        return ["la fixture sembrada compila: sus incoherencias no se detectan"]
    if set(result.failed_theorems) != set(SEEDED) or not result.reason.startswith("falla"):
        problems.append(
            f"la sembrada falla en {sorted(result.failed_theorems)} ({result.reason}), "
            f"y tiene que fallar en {sorted(SEEDED)} y en nada mas"
        )
    for theorem, expected in SEEDED.items():
        found = {
            tuple(str(s) for s in v.sources) for v in result.violations if v.theorem == theorem
        }
        if found != set(expected):
            problems.append(f"{theorem}: filas {sorted(found)}, esperadas {sorted(expected)}")
    return problems


def _commit() -> str:
    git = shutil.which("git")
    if git is None:
        return "desconocido (git no esta en el PATH)"
    # Argumentos constantes; nada del exterior.
    head = subprocess.run(  # nosec B603
        [git, "rev-parse", "HEAD"], capture_output=True, text=True, cwd=LEAN
    ).stdout.strip()
    # El propio registro no cuenta: es lo que se esta escribiendo.
    dirty = subprocess.run(  # nosec B603
        [git, "status", "--porcelain", "--", ".", f":!{RECORD.name}"],
        capture_output=True,
        text=True,
        cwd=LEAN,
    ).stdout.strip()
    return head + (" con cambios sin commitear en lean/" if dirty else "")


def _record(clean: LeanResult, seeded: LeanResult) -> None:
    now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    lines = [
        "Ultima ejecucion real de las fixtures de Lean (specs/srs-backend-v4.md RF-246, D-88).",
        "Se escribe con `python -m verification.formal.fixtures --record`.",
        "",
        f"commit: {_commit()}",
        f"fecha:  {now}",
        "",
        f"== lake build (fixture limpia): {'pasa' if clean.passed else 'FALLA'}"
        f" en {clean.elapsed_s:.1f} s",
        clean.output.rstrip(),
        "",
        f"== lake build {SEEDED_TARGET} (fixture sembrada): "
        f"{'falla en ' + ', '.join(seeded.failed_theorems) if not seeded.passed else 'PASA'}"
        f" en {seeded.elapsed_s:.1f} s",
        seeded.output.rstrip(),
        "",
        "== filas de origen de cada teorema que falla",
        *[f"{v.theorem}: " + " y ".join(str(s) for s in v.sources) for v in seeded.violations],
        "",
    ]
    write(RECORD, "\n".join(lines))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="regenera los .lean versionados")
    parser.add_argument("--record", action="store_true", help="guarda la salida real")
    args = parser.parse_args(argv)

    clean, seeded = _chronicles()
    texts = {CLEAN_FILE: render(clean), SEEDED_FILE: render(seeded)}
    if args.write:
        for path, text in texts.items():
            write(path, text)
    stale = [
        p.relative_to(LEAN).as_posix()
        for p, t in texts.items()
        if not p.exists() or p.read_text(encoding="utf-8") != t
    ]
    if stale:
        print(
            f"cronologia versionada desactualizada: {', '.join(stale)}. "
            "Regenerala con `python -m verification.formal.fixtures --write`"
        )
        return 1

    clean_result = prove(clean, module="StoryMaker.Fixture", build=["build"], keep=True)
    seeded_result = prove(
        seeded, module=SEEDED_TARGET, build=["build", SEEDED_TARGET], keep=True
    )
    if args.record:
        _record(clean_result, seeded_result)

    problems: list[str] = []
    if not clean_result.passed:
        problems.append(f"la fixture limpia no pasa: {clean_result.reason}")
        problems.append(clean_result.output[-1500:])
    problems += _judge_seeded(seeded_result)
    if problems:
        print("\n".join(problems))
        return 1
    print(
        f"lean: limpia demostrada en {clean_result.elapsed_s:.1f} s; sembrada refutada en "
        f"{', '.join(seeded_result.failed_theorems)} en {seeded_result.elapsed_s:.1f} s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
