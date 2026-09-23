"""De la salida del Continuista a defectos con cita anclada.

RF-51, RF-110, RF-111, RI-19. La cita **no se acepta por declarada**: se ancla
con `check.evidence` sobre el texto del capitulo. La que no ancla invalida su
defecto sin evaluarlo y queda como defecto de proceso del Continuista, que no
consume reintento del capitulo ni detiene nada.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from commons.types.primitives import Defect, Severity
from verification.checks import evidence

#: RF-51. Los ambitos de continuidad, los de la regla 1 del prompt. Lo que el
#: modelo devuelva fuera de aqui --estilo, ritmo, voz-- no es suyo: tiene
#: dueno (Estilista, Jurado) y severidad propia (CAL-06, S3), y como S1 del
#: Continuista tumbaria la puerta por algo que no contradice ningun hecho.
SCOPES = frozenset(
    {
        "fact",
        "time",
        "knowledge",
        "competence",
        "state",
        "identity",
        "place",
        "pov",
        "arc",
        "character",
    }
)


def in_scope(kind: str) -> bool:
    return kind.removeprefix("continuity.") in SCOPES


class ProposedDefect(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str = Field(min_length=1)
    severity: Severity
    quote: str = Field(min_length=1)
    rule: str = Field(min_length=1)


class Review(BaseModel):
    model_config = ConfigDict(frozen=True)

    defects: tuple[ProposedDefect, ...] = Field(default_factory=tuple)


class Anchored(BaseModel):
    """Lo que queda tras anclar: defectos validos y descartes por cita."""

    model_config = ConfigDict(frozen=True)

    defects: tuple[Defect, ...]
    discarded: tuple[str, ...] = Field(
        default_factory=tuple, description="Citas que no anclaron: defecto de proceso del emisor"
    )


def parse(raw: str) -> Review:
    return Review.model_validate_json(raw)


def anchor_all(review: Review, chapter_text: str) -> Anchored:
    """Ancla cada cita. Lo que no ancla, fuera; y consta (RF-111).

    Un defecto fuera de los ambitos de continuidad se descarta igual y consta
    igual: es un fallo del emisor, no del texto.
    """
    validos: list[Defect] = []
    descartes: list[str] = []
    for prop in review.defects:
        if not in_scope(prop.kind):
            descartes.append(f"[fuera de ambito: {prop.kind}] {prop.quote}")
            continue
        ev = evidence.anchor(chapter_text, prop.quote)
        if ev is None:
            descartes.append(prop.quote)
            continue
        validos.append(Defect(kind=prop.kind, severity=prop.severity, evidence=ev, rule=prop.rule))
    return Anchored(defects=tuple(validos), discarded=tuple(descartes))


def scene_offsets(texts: Sequence[str], separator: str = "\n\n") -> list[int]:
    """Donde empieza cada escena dentro del texto del capitulo unido.

    Es lo que permite devolver un defecto del Continuista --que cita el capitulo
    entero-- a la escena que hay que reparar.
    """
    offsets: list[int] = []
    pos = 0
    for i, t in enumerate(texts):
        offsets.append(pos)
        pos += len(t) + (len(separator) if i < len(texts) - 1 else 0)
    return offsets


def scene_of(offset: int, offsets: Sequence[int]) -> int:
    """Indice de la escena que contiene la posicion."""
    idx = 0
    for i, start in enumerate(offsets):
        if offset >= start:
            idx = i
    return idx
