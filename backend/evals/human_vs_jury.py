"""La lectura humana frente al Jurado, por dimension. RF-271, D-95, D-39. VER-10.

`specs/srs-backend-v4.md` §4.14; `docs/verification.md` §5.5. Cruza el fichero
de lectura humana (RD-48, validado con su esquema) con el **ultimo veredicto
aprobado del Jurado de cada capitulo**, el que dejo congelar el capitulo: el
registro `jury` de la traza con `passed` verdadero, y de el el nivel resultante
de cada dimension, que es la mediana de las tres instancias (RF-131).

Por dimension: capitulos comparados, media humana, media del Jurado, diferencia
media absoluta y los capitulos con diferencia de 2 niveles o mas, que es el
rango que ya invalida un veredicto del Jurado (D-39). Debajo, el detalle
capitulo x dimension con la diferencia firmada, humano menos Jurado.

**Sin umbral de acuerdo.** Ninguna cifra de aqui aprueba ni suspende nada: un
umbral seria un numero sin origen (D-95). La tabla informa; la lectura de lo
que significa se escribe a mano debajo, separada, en `human-vs-jury.md`.

    python -m evals.human_vs_jury --human evals/human/<novela>.json \\
        --trace evals/results/traces/<novela>.json \\
        --out evals/results/human-vs-jury.md [--novel <copia>.sqlite] [--check]

`--trace` acepta la traza JSONL o su extracto de `brief_table.py`. Con
`--novel`, la lectura se valida entera, citas incluidas, antes de comparar.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from commons.tracing.trace import TraceRecord
from evals.brief_table import load_records
from evals.human_template import HumanReading, load, problems
from verification.jury.verdict import INVALID_SPREAD

#: Marca que separa lo generado de la lectura escrita a mano. Regenerar
#: conserva lo que haya debajo.
MANUAL = "<!-- lectura a mano: debajo de esta linea no se regenera -->"


def approved_levels(records: Sequence[TraceRecord]) -> dict[int, dict[str, int | None]]:
    """Por capitulo, los niveles del ultimo `jury` con `passed` verdadero."""
    out: dict[int, dict[str, int | None]] = {}
    for r in records:
        if r.kind != "jury" or r.fields.get("passed") is not True:
            continue
        capitulo, niveles = r.fields.get("chapter"), r.fields.get("levels")
        if not isinstance(capitulo, int) or not isinstance(niveles, dict):
            continue
        out[capitulo] = {
            str(d): (n if isinstance(n, int) and not isinstance(n, bool) else None)
            for d, n in niveles.items()
        }
    return out


@dataclass(frozen=True)
class Pair:
    chapter: int
    dimension: str
    human: int
    jury: int

    @property
    def diff(self) -> int:
        return self.human - self.jury


@dataclass(frozen=True)
class Comparison:
    dimensions: tuple[str, ...]
    pairs: tuple[Pair, ...]
    without_verdict: tuple[int, ...]
    without_level: tuple[tuple[int, str], ...]

    def of(self, dimension: str) -> list[Pair]:
        return [p for p in self.pairs if p.dimension == dimension]


def compare(reading: HumanReading, records: Sequence[TraceRecord]) -> Comparison:
    jurado = approved_levels(records)
    dims = tuple(r.dimension.value for r in reading.rubrics.rubrics)
    pares: list[Pair] = []
    sin_veredicto: list[int] = []
    sin_nivel: list[tuple[int, str]] = []
    for ch in sorted(reading.chapters, key=lambda c: c.chapter):
        niveles = jurado.get(ch.chapter)
        if niveles is None:
            sin_veredicto.append(ch.chapter)
            continue
        for s in sorted(ch.scores, key=lambda x: dims.index(x.dimension.value)):
            nivel = niveles.get(s.dimension.value)
            if nivel is None:
                sin_nivel.append((ch.chapter, s.dimension.value))
                continue
            pares.append(Pair(ch.chapter, s.dimension.value, s.level, nivel))
    return Comparison(dims, tuple(pares), tuple(sin_veredicto), tuple(sin_nivel))


def _mean(values: Sequence[int]) -> str:
    return f"{sum(values) / len(values):.2f}" if values else "—"


def render(reading: HumanReading, comparison: Comparison) -> str:
    lineas = [
        "# Lectura humana frente al Jurado (LLM-as-judge)",
        "",
        f"Novela `{reading.novel}`, version {reading.manuscript_version} del manuscrito, "
        f"leida por {reading.reviewer} con las rubricas version {reading.rubrics.version}. "
        "Generada por `python -m evals.human_vs_jury` (RF-271): no se edita a mano.",
        "",
        "El Jurado es el ultimo veredicto aprobado de cada capitulo. Sin umbral de "
        f"acuerdo (D-95); una diferencia de {INVALID_SPREAD} o mas es el rango que ya "
        "invalida un veredicto del Jurado (D-39).",
        "",
        "| Dimension | Capitulos | Media humana | Media del Jurado "
        f"| Diferencia media absoluta | Capitulos con diferencia de {INVALID_SPREAD} o mas |",
        "|---|---|---|---|---|---|",
    ]
    for d in comparison.dimensions:
        propios = comparison.of(d)
        lejos = [str(p.chapter) for p in propios if abs(p.diff) >= INVALID_SPREAD]
        lineas.append(
            f"| `{d}` | {len(propios)} | {_mean([p.human for p in propios])} "
            f"| {_mean([p.jury for p in propios])} | {_mean([abs(p.diff) for p in propios])} "
            f"| {', '.join(lejos) or 'ninguno'} |"
        )
    lineas += [
        "",
        "## Por capitulo",
        "",
        "| Capitulo | Dimension | Humano | Jurado | Diferencia |",
        "|---|---|---|---|---|",
    ]
    lineas += [
        f"| {p.chapter} | `{p.dimension}` | {p.human} | {p.jury} | {p.diff:+d} |"
        for p in comparison.pairs
    ]
    if comparison.without_verdict or comparison.without_level:
        lineas += ["", "## Fuera de la comparacion", ""]
        lineas += [
            f"- Capitulo {n}: sin veredicto aprobado del Jurado en la traza."
            for n in comparison.without_verdict
        ]
        lineas += [
            f"- Capitulo {n}, `{d}`: el veredicto aprobado no tiene nivel de esa dimension."
            for n, d in comparison.without_level
        ]
    return "\n".join(lineas) + "\n"


def _with_manual(body: str, previous: str | None) -> str:
    """Lo generado, mas la lectura a mano que ya hubiera debajo de la marca."""
    if previous is None or MANUAL not in previous:
        return body
    return body + "\n" + MANUAL + previous.split(MANUAL, 1)[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lectura humana frente al Jurado (RF-271).")
    parser.add_argument("--human", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path, help="Traza JSONL o su extracto")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--novel", type=Path, help="Copia del .sqlite, para validar las citas")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    try:
        lectura = load(args.human)
    except ValidationError as exc:
        sys.stderr.write(f"{args.human} no cumple el esquema:\n{exc}\n")
        return 1
    fallos = problems(lectura, args.novel)
    if fallos:
        sys.stderr.write("la lectura humana no es valida:\n" + "".join(f"- {f}\n" for f in fallos))
        return 1
    previo = args.out.read_text(encoding="utf-8") if args.out.exists() else None
    cuerpo = _with_manual(render(lectura, compare(lectura, load_records(args.trace))), previo)
    if args.check:
        if previo != cuerpo:
            sys.stderr.write(f"{args.out} no es lo que se genera desde su entrada\n")
            return 1
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(cuerpo, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
