"""`run_lean`: genera la cronologia, la compila y dice que fallo. RF-245, RNF-55, D-88.

Fallo cerrado (`AGENTS.md` §5.3.6): no encontrar `lake`, no poder exportar un
hecho, no compilar o agotar el tope de tiempo cuentan como fallo, nunca como
paso, y nunca salen de aqui como excepcion. Un fallo que se escapa como
excepcion lo acaba tratando alguien como «no se pudo comprobar», que es la
puerta abierta.

El resultado, `LeanResult`, es lo que T46 convierte en el defecto S1
`check.formal`: el teorema que falla y las filas de origen de cada hecho que lo
rompe. La cita la pone quien llama, que es quien tiene la prosa.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import subprocess  # nosec B404 - lake con lista de argumentos, sin shell
import time
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from canon.db import connection
from canon.events.log import InstantCollisionError
from commons.types.primitives import Defect, Evidence, Severity
from verification.formal.generate import (
    CHRONOLOGY,
    PENDING,
    THEOREMS,
    Chronicle,
    FormalExportError,
    Pending,
    read_chronicle,
    render,
    theorem_lines,
    write,
)

#: El proyecto Lake: tipos, invariantes y fixtures.
PROJECT = Path(__file__).resolve().parent / "lean"

#: RNF-55 (propuesta): el mismo tope que una llamada al proveedor, el
#: `timeout_s` del CLI en `commons/provider/claude_cli.py`.
LAKE_TIMEOUT_S = 600

#: Lo que se guarda de la salida de Lake en el resultado: lo ultimo, que es
#: donde estan los errores.
_OUTPUT_TAIL = 4000

KIND = "check.formal"

_ERROR = re.compile(r"^error: (?P<path>.+?\.lean):(?P<line>\d+):(?P<col>\d+): (?P<msg>.*)$")
#: Lo que dice Lean cuando `decide` calcula la proposicion y sale falsa. Otro
#: error en la linea de un teorema --un tope de recursion, por ejemplo-- no
#: demuestra que la invariante se rompa: dice que no se pudo decidir.
_REFUTED = "proved that the proposition"


class Origin(BaseModel):
    """Una fila del canon, o de lo que va a entrar, que produjo un hecho."""

    model_config = ConfigDict(frozen=True)

    table: str
    key: tuple[str, ...]
    pending: bool = False

    @classmethod
    def parse(cls, raw: str) -> Origin:
        pending = raw.startswith(PENDING)
        body = raw[len(PENDING) :] if pending else raw
        table, _, key = body.partition("[")
        return cls(table=table, key=tuple(str(k) for k in json.loads("[" + key)), pending=pending)

    def __str__(self) -> str:
        return (PENDING if self.pending else "") + self.table + json.dumps(
            list(self.key), ensure_ascii=False
        )


class Violation(BaseModel):
    """Un hecho, o un par de hechos, que rompe una invariante."""

    model_config = ConfigDict(frozen=True)

    invariant: str
    theorem: str
    sources: tuple[Origin, ...]


class LeanResult(BaseModel):
    """Lo que devuelve `run_lean`. `passed` es falso salvo demostracion."""

    model_config = ConfigDict(frozen=True)

    passed: bool
    reason: str = Field(description="Vacio si paso; si no, por que no")
    failed_theorems: tuple[str, ...] = ()
    violations: tuple[Violation, ...] = ()
    output: str = ""
    elapsed_s: float = 0.0

    @property
    def rule(self) -> str:
        """La regla del defecto S1: teorema y filas de origen (RF-254)."""
        if self.passed:
            return ""
        if not self.violations:
            return f"{KIND}: {self.reason}"
        parts = [
            f"{v.theorem}: " + " y ".join(str(s) for s in v.sources) for v in self.violations
        ]
        return f"{KIND}: " + "; ".join(parts)

    def scenes(self) -> tuple[str, ...]:
        """Escenas implicadas, en orden: donde busca la cita quien llama."""
        found: list[str] = []
        for v in self.violations:
            for s in v.sources:
                if s.table == CHRONOLOGY and s.key[0] not in found:
                    found.append(s.key[0])
        return tuple(found)

    def entities(self) -> tuple[str, ...]:
        """Entidades implicadas: la de cada presencia y la de cada atributo."""
        found: list[str] = []
        for v in self.violations:
            for s in v.sources:
                ent = s.key[1] if s.table == CHRONOLOGY else s.key[0]
                if ent not in found:
                    found.append(ent)
        return tuple(found)

    def to_defect(self, evidence: Evidence) -> Defect:
        """El S1 `check.formal`. La cita la da quien tiene la prosa (RF-254)."""
        if self.passed:
            raise ValueError("una cronologia demostrada no es un defecto")
        return Defect(kind=KIND, severity=Severity.S1, evidence=evidence, rule=self.rule)


def find_lake() -> str | None:
    """`lake` en el PATH o, si no, donde lo deja `elan` en esta maquina."""
    found = shutil.which("lake")
    if found:
        return found
    for name in ("lake.exe", "lake"):
        candidate = Path.home() / ".elan" / "bin" / name
        if candidate.is_file():
            return str(candidate)
    return None


class _Run(BaseModel):
    returncode: int | None
    output: str
    reason: str = ""


def _lake(
    args: Sequence[str], *, lake: Sequence[str] | None, project: Path, timeout_s: float
) -> _Run:
    command = list(lake) if lake is not None else None
    if command is None:
        found = find_lake()
        if found is None:
            return _Run(returncode=None, output="", reason="lake no esta instalado (elan)")
        command = [found]
    try:
        # Lista de argumentos y sin shell: nada del canon llega a la linea de comandos.
        done = subprocess.run(  # nosec B603
            [*command, *args],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        out = _text(exc.stdout) + _text(exc.stderr)
        return _Run(returncode=None, output=out, reason=f"lake agoto el tope de {timeout_s:g} s")
    except OSError as exc:
        return _Run(returncode=None, output="", reason=f"lake no se pudo ejecutar: {exc}")
    return _Run(returncode=done.returncode, output=done.stdout + done.stderr)


def _text(raw: str | bytes | None) -> str:
    if raw is None:
        return ""
    return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw


def parse_build(
    output: str, theorems: dict[int, str], file: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Teoremas refutados y errores que no son la refutacion de un teorema.

    Un teorema falla cuando Lean dice, en su linea de `file`, que `decide`
    calculo la proposicion y es falsa. Cualquier otro error --en otro fichero,
    en otra linea o de otra clase-- es que no se pudo decidir, y eso no es una
    invariante rota: tambien cuenta como fallo, pero no se atribuye a ninguna.
    """
    failed: list[str] = []
    other: list[str] = []
    for line in output.splitlines():
        m = _ERROR.match(line.strip())
        if m is None:
            continue
        here = Path(m.group("path")).as_posix().endswith(file)
        theorem = theorems.get(int(m.group("line"))) if here else None
        if theorem is None or _REFUTED not in m.group("msg"):
            other.append(line.strip())
        elif theorem not in failed:
            failed.append(theorem)
    return tuple(failed), tuple(other)


def parse_report(stdout: str) -> tuple[Violation, ...]:
    """Las lineas `I1\\torigen\\torigen` que imprime el fichero en modo informe."""
    found: list[Violation] = []
    for line in stdout.splitlines():
        inv, *sources = line.rstrip("\r").split("\t")
        if inv not in THEOREMS or not sources:
            continue
        try:
            origins = tuple(Origin.parse(s) for s in sources)
        except ValueError:
            # No es una linea del informe. El teorema sigue contando como
            # fallido: lo que se pierde es la fila, no el fallo.
            continue
        found.append(Violation(invariant=inv, theorem=THEOREMS[inv], sources=origins))
    return tuple(found)


def _module_path(project: Path, module: str) -> Path:
    return project.joinpath(*module.split(".")).with_suffix(".lean")


def prove(
    chronicle: Chronicle,
    *,
    module: str | None = None,
    build: Sequence[str] | None = None,
    keep: bool = False,
    project: Path = PROJECT,
    lake: Sequence[str] | None = None,
    timeout_s: float = LAKE_TIMEOUT_S,
) -> LeanResult:
    """Escribe la cronologia como `module`, la compila y, si falla, pregunta por que.

    Sin `module`, el nombre sale del contenido: dos cronologias distintas no
    pisan el mismo fichero, y la misma dos veces escribe el mismo. `build` son
    los argumentos de Lake: `build <module>` si no se dan. Con `keep` el
    fichero se queda, que es lo que hacen las fixtures versionadas.
    """
    start = time.monotonic()
    text = render(chronicle)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    module = module or f"Generated.C{digest}"
    source = _module_path(project, module)
    report = _module_path(project, f"Generated.R{digest}")
    written: list[Path] = []

    def done(
        passed: bool,
        reason: str,
        *,
        failed_theorems: tuple[str, ...] = (),
        violations: tuple[Violation, ...] = (),
        output: str = "",
    ) -> LeanResult:
        return LeanResult(
            passed=passed,
            reason=reason,
            failed_theorems=failed_theorems,
            violations=violations,
            output=output,
            elapsed_s=round(time.monotonic() - start, 3),
        )

    try:
        if not source.exists() or source.read_text(encoding="utf-8") != text:
            write(source, text)
            if not keep:
                written.append(source)
        args = list(build) if build is not None else ["build", module]
        built = _lake(args, lake=lake, project=project, timeout_s=timeout_s)
        tail = built.output[-_OUTPUT_TAIL:]
        if built.returncode is None:
            return done(False, built.reason, output=tail)
        if built.returncode == 0:
            return done(True, "", output=tail)

        failed, other = parse_build(
            built.output, theorem_lines(text), source.relative_to(project).as_posix()
        )
        if other or not failed:
            return done(False, "la cronologia no compila", failed_theorems=failed, output=tail)

        write(report, render(chronicle, report=True))
        written.append(report)
        explained = _lake(
            ["env", "lean", "--run", str(report.relative_to(project))],
            lake=lake,
            project=project,
            timeout_s=timeout_s,
        )
        violations = tuple(v for v in parse_report(explained.output) if v.theorem in failed)
        return done(
            False,
            "falla " + ", ".join(failed),
            failed_theorems=failed,
            violations=violations,
            output=tail,
        )
    except OSError as exc:
        return done(False, f"no se pudo escribir la cronologia: {exc}")
    finally:
        for path in written:
            path.unlink(missing_ok=True)


def run_lean(
    novel: Path,
    pending: Pending | None = None,
    *,
    project: Path = PROJECT,
    lake: Sequence[str] | None = None,
    timeout_s: float = LAKE_TIMEOUT_S,
) -> LeanResult:
    """La cronologia del canon mas lo que va a entrar, demostrada o no (RF-245).

    `lake` sustituye al ejecutable, como lista de argumentos: lo usan las
    pruebas. Sin el, se busca con `find_lake`.
    """
    try:
        with connection.reader(novel) as con:
            chronicle = read_chronicle(con, pending)
    except (
        FormalExportError,
        InstantCollisionError,
        sqlite3.Error,
        connection.SchemaVersionError,
        OSError,
    ) as exc:
        return LeanResult(passed=False, reason=f"no se pudo exportar la cronologia: {exc}")
    return prove(chronicle, project=project, lake=lake, timeout_s=timeout_s)
