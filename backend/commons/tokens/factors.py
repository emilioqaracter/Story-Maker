"""Factores de seguridad del contador, uno por modelo.

`architecture.md` 4.8. `tiktoken` es el tokenizador de OpenAI e infracuenta a
Claude entre un 15 y un 20 % en prosa inglesa, y mas en espanol. El error va
siempre hacia abajo, que es la unica direccion que un techo no perdona, asi
que nada de lo que devuelve se usa crudo: se multiplica por el factor de aqui.

Un factor por modelo porque los tokenizadores de Claude difieren entre
generaciones hasta un 30 % sobre el mismo texto. Sin factor conocido, la
llamada no se admite (RNF-05).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

#: Punto de partida declarado, no medido. Sale del desvio documentado de
#: `tiktoken` sobre Claude: partiendo de un 25 % de infracuento para prosa en
#: espanol, recuperar la cuenta exige dividir por 0,75, que es 1,33.
#: El numero bueno lo da la calibracion de arranque, no esta constante.
DEFAULT_FACTOR = 1.35

#: Margen que se suma al ratio observado en la calibracion. Absorbe que la
#: muestra del brief no represente todos los registros de la obra.
CALIBRATION_MARGIN = 0.10


class UnknownModelError(RuntimeError):
    """El modelo de una llamada no tiene factor conocido.

    Es fallo cerrado: la llamada no se admite. Estimar con el factor de otro
    modelo seria exactamente el error que los factores por modelo evitan.
    """


class ModelFactors(BaseModel):
    """Registro de factores por identificador de modelo."""

    model_config = ConfigDict(frozen=False)

    factors: dict[str, float] = Field(default_factory=dict)

    def get(self, model_id: str) -> float:
        try:
            return self.factors[model_id]
        except KeyError:
            raise UnknownModelError(
                f"sin factor calibrado para {model_id!r}: la llamada no se admite"
            ) from None

    def set(self, model_id: str, factor: float) -> None:
        if factor < 1.0:
            raise ValueError(
                f"un factor menor que 1 haria que el estimador quedase por debajo: {factor}"
            )
        self.factors[model_id] = factor

    def has(self, model_id: str) -> bool:
        return model_id in self.factors
