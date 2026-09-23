"""Las puertas de calidad de la version 1.

RF-22, D-06, CAL-07, CAL-09. `architecture.md` §9.3. Dos puertas por capitulo:

- **Escena generada**: cero defectos S1 deterministas.
- **Capitulo verificado**: cero S1 y **maximo 2 S2** del Continuista y del
  examen de comprension. Es la puerta de §9.3 sin su componente de voz, que
  llega con el Jurado (D-06).

Son funciones puras sobre listas de defectos: la puerta no sabe de agentes ni
de reintentos, solo cuenta. Quien decide que hacer cuando no pasa es la
escalera de `orchestration/retries`.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from commons.types.primitives import Defect, Severity

#: D-06. Maximo de S2 que un capitulo verificado tolera. Sale de §9.3.
CHAPTER_MAX_S2 = 2


class GateResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    s1: int = Field(ge=0)
    s2: int = Field(ge=0)
    s3: int = Field(ge=0)

    def reason(self) -> str:
        if self.passed:
            return "pasa"
        partes = []
        if self.s1:
            partes.append(f"{self.s1} S1")
        if self.s2 > CHAPTER_MAX_S2:
            partes.append(f"{self.s2} S2 sobre un maximo de {CHAPTER_MAX_S2}")
        return "no pasa: " + ", ".join(partes)


def _count(defects: Sequence[Defect]) -> tuple[int, int, int]:
    s1 = sum(1 for d in defects if d.severity is Severity.S1)
    s2 = sum(1 for d in defects if d.severity is Severity.S2)
    s3 = sum(1 for d in defects if d.severity is Severity.S3)
    return s1, s2, s3


def scene_gate(defects: Sequence[Defect]) -> GateResult:
    """Escena generada: cero S1."""
    s1, s2, s3 = _count(defects)
    return GateResult(passed=s1 == 0, s1=s1, s2=s2, s3=s3)


def chapter_gate(defects: Sequence[Defect]) -> GateResult:
    """Capitulo verificado: cero S1, maximo 2 S2."""
    s1, s2, s3 = _count(defects)
    return GateResult(passed=s1 == 0 and s2 <= CHAPTER_MAX_S2, s1=s1, s2=s2, s3=s3)
