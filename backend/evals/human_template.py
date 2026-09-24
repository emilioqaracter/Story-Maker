"""La plantilla de lectura humana y su esquema. RF-270, RD-48, D-95. VER-10 con VER-05.

`specs/srs-backend-v4.md` §4.14 y §5; `docs/verification.md` §5.5. Una persona
lee una novela **ya congelada** y la puntua con las mismas dimensiones y los
mismos niveles que el Jurado. Es un eval sobre un artefacto cerrado, fuera del
ciclo: no aprueba, no corrige y no entra en ninguna tirada (`AGENTS.md` §5.3.1).

La plantilla sale del **conjunto de rubricas vigente de la novela** --la ultima
version de `document_version` de tipo `rubrics`, la misma que leyo el Jurado--,
nunca de una lista escrita aqui: si las rubricas ganan dimensiones, la
plantilla las gana sin tocar este fichero. Las rubricas van copiadas dentro del
fichero, con su version, para que la persona lea los cinco niveles y para que
la validacion detecte una plantilla generada con otras.

El fichero relleno, `evals/human/<novela>.json` (RD-48), lleva por capitulo y
dimension el nivel, la escena, la cita y la justificacion: el esquema de la
puntuacion del Jurado (`verification/jury/prompts.py`, `Score`), con la
justificacion obligatoria y sin campos de mas. Al revisor, solo por su papel.

    python -m evals.human_template template --novel <copia>.sqlite --id <novela> \\
        --out evals/human/<novela>.json [--check]
    python -m evals.human_template validate --reading evals/human/<novela>.json \\
        [--novel <copia>.sqlite]

La plantilla recien generada **no valida**: tiene los niveles vacios. Valida
cuando la persona la ha rellenado entera.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from canon import manuscript
from canon.db import connection
from commons.types.rubrics import DEFAULT_RUBRICS, RubricSet
from commons.types.rubrics import loads as load_rubrics
from verification.checks import evidence
from verification.jury.prompts import Score

#: El papel del revisor: minusculas, cifras y espacios. Un nombre propio lleva
#: mayuscula y no pasa; es la forma barata de que no entre uno por descuido.
ROLE = r"^[a-z][a-z0-9 _-]*$"

INSTRUCTIONS = (
    "Lectura humana fuera del ciclo: la novela ya esta congelada y esta lectura no la "
    "cambia. Por cada capitulo y cada dimension, un nivel del 1 al 5 con la rubrica de "
    "este mismo fichero (el 3 es cumple), la escena que lo justifica, una cita literal "
    f"de esa escena de al menos {evidence.MIN_QUOTE_WORDS} palabras que aparezca una sola "
    "vez, y la justificacion. El revisor va por su papel, nunca por su nombre."
)


class HumanScore(Score):
    """La puntuacion del Jurado, con la justificacion obligatoria."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    justification: str = Field(min_length=1)


class HumanChapter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chapter: int = Field(ge=1)
    scenes: tuple[str, ...] = Field(min_length=1, description="Escenas del capitulo leido")
    scores: tuple[HumanScore, ...]


class HumanReading(BaseModel):
    """RD-48. El fichero de lectura humana de una novela."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    novel: str = Field(min_length=1)
    reviewer: str = Field(pattern=ROLE, description="Papel del revisor, nunca su nombre")
    manuscript_version: int = Field(ge=1, description="Version del manuscrito leida")
    instructions: str
    rubrics: RubricSet
    chapters: tuple[HumanChapter, ...] = Field(min_length=1)


# ------------------------------------------------------------------ lectura


def current_rubrics(con: sqlite3.Connection) -> RubricSet:
    """La version de las rubricas que guarda el fichero: la que leyo el Jurado
    (`orchestration/engine.py`, `_rubrics`, RNF-37)."""
    row = con.execute(
        "SELECT body FROM document_version WHERE doc_kind = 'rubrics' ORDER BY version DESC LIMIT 1"
    ).fetchone()
    return load_rubrics(row["body"]) if row else DEFAULT_RUBRICS


def _chapters(con: sqlite3.Connection, version: int) -> dict[int, dict[str, str]]:
    """Por capitulo de la version, sus escenas en orden con su texto."""
    out: dict[int, dict[str, str]] = {}
    for n in manuscript.chapters_in(con, version):
        escenas = manuscript.chapter_at(con, n, version) or []
        out[n] = {s.scene_id: s.text for s in escenas}
    return out


# ------------------------------------------------------------------ plantilla


def template(novel: Path, novel_id: str, *, reviewer: str = "revisor 1", version: int = 1) -> str:
    """La plantilla, como texto: la misma novela da el mismo fichero."""
    with connection.reader(novel) as con:
        rubricas = current_rubrics(con)
        capitulos = _chapters(con, version)
    if not capitulos:
        raise ValueError(f"{novel} no tiene capitulos congelados en la version {version}")
    cuerpo = {
        "novel": novel_id,
        "reviewer": reviewer,
        "manuscript_version": version,
        "instructions": INSTRUCTIONS,
        "rubrics": rubricas.model_dump(mode="json"),
        "chapters": [
            {
                "chapter": n,
                "scenes": list(escenas),
                "scores": [
                    {
                        "dimension": r.dimension.value,
                        "level": None,
                        "scene": "",
                        "quote": "",
                        "justification": "",
                    }
                    for r in rubricas.rubrics
                ],
            }
            for n, escenas in sorted(capitulos.items())
        ],
    }
    return json.dumps(cuerpo, ensure_ascii=False, indent=1) + "\n"


# ------------------------------------------------------------------ validacion


def load(path: Path) -> HumanReading:
    return HumanReading.model_validate_json(path.read_text(encoding="utf-8"))


def problems(reading: HumanReading, novel: Path | None = None) -> list[str]:
    """Lo que el esquema no expresa. Vacio es valido.

    Sin novela: una puntuacion por dimension de las rubricas del fichero y por
    capitulo, y la escena citada es del capitulo. Con la novela, ademas: las
    rubricas son las vigentes, los capitulos y escenas son los de la version
    leida, y cada cita ancla literal y unica en su escena, la misma regla que
    descarta una cita del Jurado (RF-129).
    """
    out: list[str] = []
    dims = [r.dimension for r in reading.rubrics.rubrics]
    repetidos = [n for n, c in Counter(ch.chapter for ch in reading.chapters).items() if c > 1]
    out += [f"capitulo {n}: aparece mas de una vez" for n in repetidos]
    for ch in reading.chapters:
        vistas = Counter(s.dimension for s in ch.scores)
        out += [f"capitulo {ch.chapter}: falta {d.value}" for d in dims if d not in vistas]
        out += [f"capitulo {ch.chapter}: {d.value} repetida" for d, c in vistas.items() if c > 1]
        out += [
            f"capitulo {ch.chapter}: {d.value} no esta en las rubricas del fichero"
            for d in vistas
            if d not in dims
        ]
        out += [
            f"capitulo {ch.chapter}: {s.dimension.value} cita la escena {s.scene}, que no es suya"
            for s in ch.scores
            if s.scene not in ch.scenes
        ]
    if novel is None:
        return out

    with connection.reader(novel) as con:
        vigentes = current_rubrics(con)
        capitulos = _chapters(con, reading.manuscript_version)
    if reading.rubrics != vigentes:
        out.append(
            f"las rubricas del fichero (version {reading.rubrics.version}) no son las "
            f"vigentes de la novela (version {vigentes.version})"
        )
    leidos = {ch.chapter for ch in reading.chapters}
    out += [f"capitulo {n}: congelado y sin leer" for n in sorted(set(capitulos) - leidos)]
    out += [f"capitulo {n}: no esta en la novela" for n in sorted(leidos - set(capitulos))]
    for ch in reading.chapters:
        textos = capitulos.get(ch.chapter)
        if textos is None:
            continue
        if tuple(textos) != ch.scenes:
            out.append(f"capitulo {ch.chapter}: sus escenas no son las de la novela")
        for s in ch.scores:
            texto = textos.get(s.scene)
            if texto is not None and evidence.anchor(texto, s.quote) is None:
                out.append(
                    f"capitulo {ch.chapter}: la cita de {s.dimension.value} no ancla "
                    f"literal y unica en {s.scene}"
                )
    return out


# ------------------------------------------------------------------ comando


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plantilla y validacion de la lectura humana.")
    sub = parser.add_subparsers(dest="command", required=True)
    tp = sub.add_parser("template", help="Genera la plantilla de una novela congelada")
    tp.add_argument("--novel", required=True, type=Path, help="Copia del .sqlite de la novela")
    tp.add_argument("--id", required=True, help="Nombre de la novela en evals/human/")
    tp.add_argument("--out", required=True, type=Path)
    tp.add_argument("--reviewer", default="revisor 1")
    tp.add_argument("--version", type=int, default=1)
    tp.add_argument("--check", action="store_true")
    va = sub.add_parser("validate", help="Valida un fichero relleno contra su esquema")
    va.add_argument("--reading", required=True, type=Path)
    va.add_argument("--novel", type=Path)
    args = parser.parse_args(argv)

    if args.command == "template":
        cuerpo = template(args.novel, args.id, reviewer=args.reviewer, version=args.version)
        if args.check:
            igual = args.out.exists() and args.out.read_text(encoding="utf-8") == cuerpo
            if not igual:
                sys.stderr.write(f"{args.out} no es lo que se genera desde su novela\n")
            return 0 if igual else 1
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(cuerpo, encoding="utf-8", newline="\n")
        return 0

    try:
        lectura = load(args.reading)
    except ValidationError as exc:
        sys.stderr.write(f"{args.reading} no cumple el esquema:\n{exc}\n")
        return 1
    fallos = problems(lectura, args.novel)
    for f in fallos:
        sys.stderr.write(f"- {f}\n")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
