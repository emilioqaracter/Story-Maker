"""La tabla brief x verificador, generada desde las trazas. RF-269, D-95. VER-10.

`specs/srs-backend-v4.md` §4.14. Una fila por tirada del conjunto de cinco
briefs (RF-250) y una columna por verificador, con tres valores posibles:

- **pasó**: el verificador corrio en la tirada y no marco nada;
- **falló (n)**: marco `n` veces, contando todos los intentos --una trampa que
  `check.timeline` caza en el primer intento y el Reparador arregla sigue siendo
  una trampa cazada, y es lo que la tabla tiene que enseñar--;
- **no aplica**: la tirada no le dio nada que verificar, como `check.ledger` en
  un brief sin encuentros.

Debajo, una fila por tirada con su commit, la fecha de su primer registro, el
cierre y la `prompt_version` de cada agente que llamo al modelo.

**Nunca a mano.** Las trazas de las tiradas viven en `runs-*/`, fuera de git,
asi que la tabla se genera desde **extractos versionados**: un JSON por tirada
con los registros que la tabla, `human_vs_jury.py` y una auditoria necesitan, y
el commit sobre el que corrio, que la traza no lleva. La misma entrada da el
mismo fichero byte a byte: nada depende del reloj ni de la maquina.

Dos comandos, que son los que usa T52:

    python -m evals.brief_table extract --brief 03-temporal \\
        --trace runs-evals/03-temporal.trace.jsonl --commit <sha> \\
        --out evals/results/traces/03-temporal.json
    python -m evals.brief_table table --extracts evals/results/traces \\
        --out evals/results/briefs.md [--check]

Con `--check` no escribe: compara lo que generaria con lo que hay y sale con 1
si difieren, que es como se demuestra que la tabla versionada se regenera.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from commons.tracing.trace import Trace, TraceRecord
from commons.types.rubrics import Dimension
from verification.continuity.review import in_scope
from verification.jury.verdict import THRESHOLD

# ------------------------------------------------------------------ extractos

#: Los registros que se conservan de una traza, y de cada uno los campos. `None`
#: conserva todos. De `outline.check` se quita la escaleta, que no es un
#: resultado de verificador y es lo que mas pesa; de `call`, todo lo que no dice
#: con que prompt se llamo.
KEPT: dict[str, frozenset[str] | None] = {
    "outline.check": frozenset({"defects", "passed", "messages"}),
    "scene.attempt": None,
    "chapter.gate": None,
    "quiz": None,
    "jury": None,
    "guardrail.match": None,
    "formal.lean": None,
    "chapter.frozen": None,
    "work.close": None,
    "call": frozenset({"agent", "prompt_version", "model", "ok"}),
}

_COMMIT = r"^[0-9a-f]{7,40}$"


class RunExtract(BaseModel):
    """Lo versionado de una tirada: su brief, su commit y sus registros."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    brief: str = Field(min_length=1, description="Nombre del brief, sin extension: 03-temporal")
    commit: str = Field(pattern=_COMMIT, description="Commit sobre el que corrio la tirada")
    source: str = Field(description="Nombre del fichero de traza del que sale, sin ruta")
    records: tuple[TraceRecord, ...]


def _keep(record: TraceRecord) -> TraceRecord | None:
    if record.kind not in KEPT:
        return None
    campos = KEPT[record.kind]
    if campos is None:
        return record
    return record.model_copy(
        update={"fields": {k: v for k, v in record.fields.items() if k in campos}}
    )


def extract(brief: str, trace_path: Path, commit: str) -> RunExtract:
    """El extracto de una traza JSONL. Falla si la traza no existe o esta vacia:
    una tabla con una fila sin registros diria «no aplica» donde no se midio."""
    if not trace_path.exists():
        raise FileNotFoundError(f"no existe la traza {trace_path}")
    registros = [r for r in (_keep(x) for x in Trace(trace_path).read()) if r is not None]
    if not registros:
        raise ValueError(f"la traza {trace_path} no tiene registros que medir")
    return RunExtract(brief=brief, commit=commit, source=trace_path.name, records=tuple(registros))


def dumps(run: RunExtract) -> str:
    return run.model_dump_json(indent=1) + "\n"


def load_records(path: Path) -> list[TraceRecord]:
    """Los registros de una traza JSONL o de un extracto. Lo usa tambien
    `human_vs_jury.py`, que lee el Jurado de cualquiera de los dos."""
    if path.suffix == ".json":
        return list(RunExtract.model_validate_json(path.read_text(encoding="utf-8")).records)
    return list(Trace(path).read())


def load_extracts(folder: Path) -> list[RunExtract]:
    runs = [
        RunExtract.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted(folder.glob("*.json"))
    ]
    if not runs:
        raise ValueError(f"no hay extractos en {folder}")
    return sorted(runs, key=lambda r: r.brief)


# ------------------------------------------------------------------ celdas

PASSED = "pasó"
NOT_APPLICABLE = "no aplica"


@dataclass(frozen=True)
class Cell:
    applies: bool
    failures: int = 0

    def render(self) -> str:
        if not self.applies:
            return NOT_APPLICABLE
        return f"falló ({self.failures})" if self.failures else PASSED


def _defect_kinds(records: Sequence[TraceRecord]) -> list[str]:
    """Cada defecto que un verificador marco, por su `kind`, en escena y capitulo.

    `scene.attempt` los lleva como `kind:severidad`; `chapter.gate`, como
    `severidad:kind: regla «cita»`. Las coincidencias de `check.forbidden` en la
    segunda red, justo antes de congelar, solo constan como `guardrail.match`
    de etapa `congelacion`: las de escena ya van en su intento.
    """
    out: list[str] = []
    for r in records:
        if r.kind == "scene.attempt":
            out += [str(d).rsplit(":", 1)[0] for d in _list(r.fields.get("defects"))]
        elif r.kind == "chapter.gate":
            partes = [str(d).split(":", 2) for d in _list(r.fields.get("defects"))]
            out += [p[1].strip() for p in partes if len(p) == 3]
        elif r.kind == "guardrail.match" and r.fields.get("stage") == "congelacion":
            out.append("check.forbidden")
    return out


def _list(value: JsonValue | None) -> list[JsonValue]:
    return list(value) if isinstance(value, list) else []


#: Los verificadores de escena, que corren en todo intento (`verify_scene`), y
#: los que solo corren en una escena de encuentro (`verify_match`). Una columna
#: por cada uno, aunque no marque nada: es lo que permite escribir «pasó».
SCENE_CHECKS = (
    "check.format",
    "check.timeline",
    "check.forbidden",
    "check.repetition",
    "check.lexicon",
    "check.knowledge",
)
MATCH_CHECKS = ("check.ledger", "check.availability")


@dataclass(frozen=True)
class Column:
    name: str
    cell: Callable[[Sequence[TraceRecord], Sequence[str]], Cell]


def _of(records: Sequence[TraceRecord], kind: str) -> list[TraceRecord]:
    return [r for r in records if r.kind == kind]


def _count(kinds: Sequence[str], kind: str) -> int:
    return sum(1 for k in kinds if k == kind)


def _scene_check(kind: str, *, match_only: bool) -> Column:
    def cell(records: Sequence[TraceRecord], kinds: Sequence[str]) -> Cell:
        intentos = _of(records, "scene.attempt")
        if match_only:
            intentos = [r for r in intentos if r.fields.get("is_match") is True]
        return Cell(applies=bool(intentos), failures=_count(kinds, kind))

    return Column(kind, cell)


def _outline(records: Sequence[TraceRecord], _k: Sequence[str]) -> Cell:
    propios = _of(records, "outline.check")
    return Cell(bool(propios), sum(1 for r in propios if r.fields.get("passed") is False))


def _formal(records: Sequence[TraceRecord], kinds: Sequence[str]) -> Cell:
    """`formal.lean` deja un registro por ejecucion (RF-254); sin ninguno, cuenta
    lo que haya llegado como defecto `check.formal`, si llego."""
    propios = _of(records, "formal.lean")
    if propios:
        return Cell(True, sum(1 for r in propios if r.fields.get("passed") is False))
    n = _count(kinds, "check.formal")
    return Cell(bool(n), n)


def _continuity(records: Sequence[TraceRecord], kinds: Sequence[str]) -> Cell:
    return Cell(bool(_of(records, "chapter.gate")), sum(1 for k in kinds if in_scope(k)))


def _quiz(records: Sequence[TraceRecord], _k: Sequence[str]) -> Cell:
    propios = [r for r in _of(records, "quiz") if _int(r.fields.get("questions")) > 0]
    return Cell(bool(propios), sum(_int(r.fields.get("wrong")) for r in propios))


def _int(value: JsonValue | None) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _jury(dimension: Dimension) -> Column:
    """Una columna por dimension de las rubricas vigentes. Cuenta los veredictos
    en que la dimension quedo sin nivel o bajo el umbral (D-39)."""

    def cell(records: Sequence[TraceRecord], _k: Sequence[str]) -> Cell:
        niveles: list[JsonValue] = []
        for r in _of(records, "jury"):
            propios = r.fields.get("levels")
            if isinstance(propios, dict) and dimension.value in propios:
                niveles.append(propios[dimension.value])
        fallos = sum(1 for n in niveles if not isinstance(n, int) or n < THRESHOLD)
        return Cell(bool(niveles), fallos)

    return Column(f"jury.{dimension.value}", cell)


def _work_close(records: Sequence[TraceRecord], _k: Sequence[str]) -> Cell:
    """Siempre aplica. Sin `work.close` la comprobacion de cierre no corrio, y
    una comprobacion que no corre cuenta como fallida (`AGENTS.md` §5.3)."""
    cierres = _of(records, "work.close")
    return Cell(True, 0 if cierres and cierres[-1].fields.get("closed") is True else 1)


def columns() -> list[Column]:
    """El orden de la tabla: el de la tirada. Las del Jurado salen de
    `commons/types/rubrics.py`, no de una lista de aqui."""
    return [
        Column("outline.check", _outline),
        *(_scene_check(k, match_only=False) for k in SCENE_CHECKS),
        *(_scene_check(k, match_only=True) for k in MATCH_CHECKS),
        Column("check.formal", _formal),
        Column("continuity", _continuity),
        Column("quiz", _quiz),
        *(_jury(d) for d in Dimension),
        Column("work.close", _work_close),
    ]


def _extra_columns(runs: Iterable[RunExtract], known: set[str]) -> list[Column]:
    """Un verificador que marca y no tiene columna gana la suya: la tabla no
    esconde un `kind` nuevo por no estar en la lista."""
    vistos = sorted(
        {
            k
            for run in runs
            for k in _defect_kinds(run.records)
            if k not in known and not in_scope(k) and k != "quiz"
        }
    )
    return [_scene_check(k, match_only=False) for k in vistos]


# ------------------------------------------------------------------ la tabla


def _prompt_versions(records: Sequence[TraceRecord]) -> str:
    por_agente: dict[str, set[str]] = {}
    for r in _of(records, "call"):
        agente, version = r.fields.get("agent"), r.fields.get("prompt_version")
        if isinstance(agente, str) and isinstance(version, str):
            por_agente.setdefault(agente, set()).add(version)
    if not por_agente:
        return "sin llamadas a modelo"
    return ", ".join(f"`{a}={'/'.join(sorted(v))}`" for a, v in sorted(por_agente.items()))


def _closing(records: Sequence[TraceRecord]) -> str:
    cierres = _of(records, "work.close")
    if not cierres:
        return "sin work.close"
    f = cierres[-1].fields
    motivo = str(f.get("reason") or "").replace("|", "/").replace("\n", " ")
    estado = "cerró" if f.get("closed") is True else "no cerró"
    return f"{estado}: {motivo[:120]}" if motivo else estado


def render(runs: Sequence[RunExtract]) -> str:
    cols = columns()
    cols += _extra_columns(runs, {c.name for c in cols})
    lineas = [
        "# Tabla por brief",
        "",
        "Generada por `python -m evals.brief_table table` desde los extractos de las "
        "trazas (RF-269). No se edita a mano: se regenera.",
        "",
        "«falló (n)» cuenta cada vez que el verificador marco, en todos los intentos; "
        "«no aplica», que la tirada no le dio nada que verificar.",
        "",
        "| Brief | " + " | ".join(f"`{c.name}`" for c in cols) + " |",
        "|---|" + "---|" * len(cols),
    ]
    for run in runs:
        kinds = _defect_kinds(run.records)
        celdas = [c.cell(run.records, kinds).render() for c in cols]
        lineas.append(f"| {run.brief} | " + " | ".join(celdas) + " |")
    lineas += [
        "",
        "## Tiradas",
        "",
        "| Brief | Commit | Fecha | Cierre | `prompt_version` por agente |",
        "|---|---|---|---|---|",
    ]
    for run in runs:
        fecha = run.records[0].at[:10] if run.records else ""
        lineas.append(
            f"| {run.brief} | `{run.commit}` | {fecha} | {_closing(run.records)} "
            f"| {_prompt_versions(run.records)} |"
        )
    return "\n".join(lineas) + "\n"


# ------------------------------------------------------------------ comando


def _write_or_check(out: Path, body: str, *, check: bool) -> int:
    if check:
        actual = out.read_text(encoding="utf-8") if out.exists() else None
        if actual != body:
            sys.stderr.write(f"{out} no es lo que se genera desde su entrada\n")
            return 1
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8", newline="\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tabla brief x verificador (RF-269).")
    sub = parser.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("extract", help="Extracto versionable de una traza")
    ex.add_argument("--brief", required=True)
    ex.add_argument("--trace", required=True, type=Path)
    ex.add_argument("--commit", required=True)
    ex.add_argument("--out", required=True, type=Path)
    ex.add_argument("--check", action="store_true")
    tb = sub.add_parser("table", help="La tabla desde una carpeta de extractos")
    tb.add_argument("--extracts", required=True, type=Path)
    tb.add_argument("--out", required=True, type=Path)
    tb.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "extract":
        body = dumps(extract(args.brief, args.trace, args.commit))
    else:
        body = render(load_extracts(args.extracts))
    return _write_or_check(args.out, body, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
