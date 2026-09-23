"""`check.forbidden`. El guardarrail de palabras prohibidas.

RF-236 a RF-240, D-90, D-91. `architecture.md` §9.1 y §9.3.

Una prohibida del encargo contradice lo que se pidio, y el brief gana sobre el
canon derivado (PRO-10): es un invariante duro, no estetica, y por eso es **S1**.
Con S2 una tirada medida congelo ocho fragmentos con la palabra dentro. Lo
estetico --los n-gramas repetidos de POE-12, nivel `estilo`-- se queda en
`check.repetition`, y ninguna prohibida pasa por alli: una sola fuente.

Donde corre, y por que en dos sitios:

- En `verify_scene`, **en cada intento** de escena, y por eso tambien tras
  reparar, pulir o reescribir por retcon o enmienda. Una coincidencia bloquea la
  escena y el reintento lleva el defecto con su cita.
- Otra vez **sobre el capitulo entero justo antes de congelar**
  (`orchestration/loop.py`). Es la segunda red: un borrador reanudado no pasa por
  `verify_scene`, y un termino de varias palabras puede quedar partido entre dos
  escenas. Ahi una coincidencia vuelve a reparacion, nunca a la congelacion.

La coincidencia --normalizacion, palabra completa, variantes-- es la de
`canon/normalize.py`, que comparten el guardarrail y las reglas del brief
(RF-237). Se reexporta aqui para quien la busque junto al verificador.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from canon.brief import FORBIDDEN_LEVELS, STYLE_LEVEL, ForbiddenLevel
from canon.normalize import Occurrence, normalize, occurrences, pattern, scan, tokens, variants
from commons.types.primitives import Defect, Evidence, Severity

__all__ = [
    "FORBIDDEN_LEVELS",
    "KIND",
    "ForbiddenTerm",
    "Occurrence",
    "check_forbidden",
    "describe",
    "normalize",
    "occurrences",
    "read_style_terms",
    "read_terms",
    "rule_for",
    "variants",
]

KIND = "check.forbidden"


class ForbiddenTerm(BaseModel):
    """Una prohibida con el nivel del que viene (D-91)."""

    model_config = ConfigDict(frozen=True)

    term: str = Field(min_length=1)
    level: ForbiddenLevel


def rule_for(term: str, level: str) -> str:
    """La regla del defecto. Lleva termino y nivel en una forma que `describe` lee.

    El defecto es un `Defect` corriente (CAL-05), sin campos propios; la traza
    (`guardrail.match`) y el motivo de un aborto necesitan el termino y el nivel,
    y los sacan de aqui en vez de volver a buscar.
    """
    return f"«{term}» esta prohibida en el nivel {level}"


_RULE = re.compile(r"^«(?P<term>.+)» esta prohibida en el nivel (?P<level>global|cliente|novela)$")


def describe(defect: Defect) -> ForbiddenTerm | None:
    """El termino y el nivel de un defecto de `check.forbidden`; `None` si no lo es."""
    if defect.kind != KIND:
        return None
    m = _RULE.match(defect.rule)
    if m is None:
        return None
    return ForbiddenTerm(term=m.group("term"), level=m.group("level"))  # type: ignore[arg-type]


def check_forbidden(text: str, *, terms: Sequence[ForbiddenTerm]) -> list[Defect]:
    """Un S1 por coincidencia, con termino, nivel, cita y desplazamiento (RF-236).

    Cada aparicion es un defecto: el Reparador tiene que quitarlas todas, y una
    sola que se le escape volveria a parar el capitulo en el siguiente intento.
    """
    if not terms:
        return []
    toks = tokens(text)
    out: list[Defect] = []
    for t in terms:
        for occ in scan(text, toks, pattern(t.term)):
            out.append(
                Defect(
                    kind=KIND,
                    severity=Severity.S1,
                    evidence=Evidence(quote=occ.quote, offset=occ.offset),
                    rule=rule_for(t.term, t.level),
                )
            )
    return sorted(out, key=lambda d: d.evidence.offset)


def _has_level(con: sqlite3.Connection) -> bool:
    return any(str(r[1]) == "level" for r in con.execute("PRAGMA table_info(proscribed)"))


def read_terms(con: sqlite3.Connection) -> tuple[ForbiddenTerm, ...]:
    """Las prohibidas de los tres niveles del guardarrail, la global primero.

    Lee con cualquier conexion, tambien la de solo lectura. Un fichero anterior a
    la migracion 4 --que se abre en lectura y por eso no ha migrado-- se lee como
    la migracion lo dejaria: lo que prohibio el brief es `cliente`.
    """
    if not _has_level(con):
        rows = con.execute("SELECT term FROM proscribed WHERE kind = 'brief' ORDER BY term")
        return tuple(ForbiddenTerm(term=r["term"], level="cliente") for r in rows)
    rows = con.execute(
        "SELECT term, level FROM proscribed WHERE level IN (?, ?, ?) "
        "ORDER BY CASE level WHEN 'global' THEN 0 WHEN 'cliente' THEN 1 ELSE 2 END, term",
        FORBIDDEN_LEVELS,
    )
    return tuple(ForbiddenTerm(term=r["term"], level=r["level"]) for r in rows)


def read_style_terms(con: sqlite3.Connection) -> list[str]:
    """Lo proscrito por estilo (POE-12): lo que `check.repetition` sigue mirando."""
    if not _has_level(con):
        rows = con.execute("SELECT term FROM proscribed WHERE kind <> 'brief'")
    else:
        rows = con.execute("SELECT term FROM proscribed WHERE level = ?", (STYLE_LEVEL,))
    return [r["term"] for r in rows]
