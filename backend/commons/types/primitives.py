"""Tipos primitivos que cruzan todas las funcionalidades.

Fuente: `docs/definitions.md`. Cada enumeracion realiza un ID del glosario y
no admite valores fuera de el: un `provenance` libre es como el canon deja de
ser comprobable.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --------------------------------------------------------------------- MET-09

class Provenance(StrEnum):
    """MET-09. De donde viene un hecho canonico.

    Cerrada a proposito: RD-01 exige que la columna solo admita estos cuatro,
    y la precedencia PRO-10 se apoya en poder distinguirlos.
    """

    BRIEF = "brief"
    PROSE = "prose"
    DERIVED = "derived"
    ARBITRATION = "arbitration"


# --------------------------------------------------------------------- CAL-06

class Severity(StrEnum):
    """CAL-06. Gravedad de un defecto.

    S1 contradice el canon y bloquea cualquier puerta. S2 degrada la calidad
    sin contradecir. S3 es preferencia estetica.
    """

    S1 = "S1"
    S2 = "S2"
    S3 = "S3"


# --------------------------------------------------------------------- CTX

class BlockProvenance(StrEnum):
    """De donde sale un bloque de paquete de contexto.

    Es la contramedida contra CTX-13: sin la etiqueta, un fragmento de prosa
    que describia una intencion se lee igual que un hecho canonico.
    """

    CANON = "canon"
    FROZEN_PROSE = "frozen_prose"
    PLAN = "plan"


class Quota(StrEnum):
    """Cupos del bloque de recuperacion (architecture.md 4.4)."""

    PLACE = "place"
    VOICE = "voice"
    PROMISE = "promise"
    MIRROR = "mirror"
    FREE = "free"


# --------------------------------------------------------------- MUN-05, D-07

#: Publico porque las rutas HTTP lo declaran en su contrato. Mientras la regla
#: vivio solo aqui, el esquema prometia aceptar cualquier texto y la ruta
#: rechazaba casi todos.
ISO_INSTANT_PATTERN = r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?$"

_ISO_DATE = re.compile(ISO_INSTANT_PATTERN)


class WorldTime(BaseModel):
    """MUN-05. Instante de mundo.

    ISO 8601 mas `seq` de desempate (D-07). Se ordena por la tupla
    `(stamp, seq)`, que ordena lexicograficamente igual que cronologicamente:
    por eso el formato es fijo y se valida.
    """

    model_config = ConfigDict(frozen=True)

    stamp: str = Field(description="ISO 8601: YYYY-MM-DD, opcionalmente con hora")
    seq: int = Field(default=0, ge=0, description="Desempate dentro del mismo instante")

    @model_validator(mode="after")
    def _check_format(self) -> Self:
        if not _ISO_DATE.match(self.stamp):
            raise ValueError(f"instante de mundo no es ISO 8601: {self.stamp!r}")
        return self

    def __lt__(self, other: WorldTime) -> bool:
        return (self.stamp, self.seq) < (other.stamp, other.seq)

    def __le__(self, other: WorldTime) -> bool:
        return (self.stamp, self.seq) <= (other.stamp, other.seq)


# --------------------------------------------------------------------- CAL-05

class Evidence(BaseModel):
    """Cita localizable. Sin esto un veredicto se descarta (RI-19)."""

    model_config = ConfigDict(frozen=True)

    quote: str = Field(min_length=1, description="Fragmento textual citado")
    offset: int = Field(ge=0, description="Posicion de inicio en el texto juzgado")

    @model_validator(mode="after")
    def _non_empty(self) -> Self:
        if not self.quote.strip():
            raise ValueError("una cita en blanco no es evidencia")
        return self


class Defect(BaseModel):
    """CAL-05. Informe de un defecto.

    Contrato de spec 3.5: tipo, severidad, fragmento citado con posicion, y la
    regla o hecho canonico violado.
    """

    model_config = ConfigDict(frozen=True)

    kind: str = Field(min_length=1, description="Verificador que lo emite: check.timeline, ...")
    severity: Severity
    evidence: Evidence
    rule: str = Field(min_length=1, description="Regla o hecho canonico violado")
