"""La especificacion de escena, artefacto compartido.

RF-28 a RF-30, EST-I1. Vive en `commons/` y no en `planning/` porque **cruza
funcionalidades**: la produce `planning/`, y la consumen `context/` para armar
la consulta y `generation/` para escribir. Ese es exactamente el criterio de
entrada a `commons/`: se baja algo cuando lo usan dos, no cuando parece que
podria usarse.

Mientras vivio en `planning/`, `context/` tenia que importar de una
funcionalidad hermana, que es justo lo que la regla de los tres pisos prohibe.
Lo destapo la comprobacion de fronteras en cuanto se escribio el primer modulo
de recuperacion.

EST-I1 se impone al construir y no en un verificador posterior: una escena sin
POV unico o sin cambio de valor no es una especificacion mala, es un objeto que
no deberia poder existir.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commons.types.primitives import WorldTime


class SceneFunction(StrEnum):
    """EST-14. Rol de la escena en el arco.

    Cerrada porque el cupo de espejo de la recuperacion busca escenas con la
    misma funcion: si el conjunto fuera libre, dos escenas equivalentes con
    nombres distintos nunca se encontrarian.
    """

    ESTABLISH = "establecer"
    COMPLICATE = "complicar"
    REVEAL = "revelar"
    DECIDE = "decidir"
    CULMINATE = "culminar"
    ASSIMILATE = "asimilar"


class SceneIdentity(BaseModel):
    """Bloque 1. Donde y cuando ocurre, y quien la cuenta."""

    model_config = ConfigDict(frozen=True)

    scene_id: str = Field(min_length=1)
    chapter: int = Field(ge=1, description="EST-I1: exactamente uno")
    ordinal: int = Field(ge=1)
    pov: str = Field(min_length=1, description="EST-I1: exactamente uno")
    place: str = Field(min_length=1)
    world_time: WorldTime


class DramaticFunction(BaseModel):
    """Bloque 2. Que hace esta escena por la obra."""

    model_config = ConfigDict(frozen=True)

    function: SceneFunction
    value_change: str = Field(min_length=1, description="EST-13")
    arcs: tuple[str, ...] = Field(default_factory=tuple)
    objective: str = Field(min_length=1, description="Que quiere el POV aqui")
    obstacle: str = Field(min_length=1, description="Que se lo impide")


class SceneContent(BaseModel):
    """Bloque 3. Con que se escribe."""

    model_config = ConfigDict(frozen=True)

    cast: tuple[str, ...] = Field(min_length=1, description="Elenco activo")
    beats: tuple[str, ...] = Field(min_length=1, description="Los pasos de la escena")
    setups_to_plant: tuple[str, ...] = Field(default_factory=tuple)
    setups_to_pay: tuple[str, ...] = Field(default_factory=tuple)


class ExpectedOutput(BaseModel):
    """Bloque 4. Que tiene que haber cambiado al terminar."""

    model_config = ConfigDict(frozen=True)

    target_words: int = Field(gt=0)
    ends_with: str = Field(min_length=1, description="Estado al cerrar la escena")


class SceneConstraints(BaseModel):
    """Bloque 5. Lo que no se puede hacer."""

    model_config = ConfigDict(frozen=True)

    tense: str = Field(default="pasado")
    person: str = Field(default="tercera")
    forbidden: tuple[str, ...] = Field(
        default_factory=tuple, description="Terminos proscritos vigentes (POE-12)"
    )
    facts_unknown_to_pov: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Hechos canonicos que el POV NO sabe todavia (PER-10)",
    )


class SceneSpec(BaseModel):
    """La especificacion completa. Es el encargo que recibe el Escritor."""

    model_config = ConfigDict(frozen=True)

    identity: SceneIdentity
    function: DramaticFunction
    content: SceneContent
    output: ExpectedOutput
    constraints: SceneConstraints
    is_match: bool = Field(
        default=False,
        description="RF-30. Si lo es, la resuelve el motor de reglas antes de narrarse",
    )

    @model_validator(mode="after")
    def _pov_is_in_cast(self) -> Self:
        if self.identity.pov not in self.content.cast:
            raise ValueError(
                f"el POV {self.identity.pov!r} no esta en el elenco activo. "
                "Quien cuenta la escena tiene que estar en ella"
            )
        return self

    def semantic_query(self) -> str:
        """El texto con el que se busca en la prosa congelada.

        **La especificacion ya es la consulta** (RF-72): el artefacto que
        describe lo que se va a escribir es la mejor descripcion de lo que
        conviene recuperar, y ya existe. Redactar otra seria escribir dos veces
        lo mismo y arriesgarse a que se separen.
        """
        return " ".join(
            [
                self.function.function.value,
                self.function.objective,
                self.function.obstacle,
                self.function.value_change,
                *self.content.beats,
            ]
        )
