"""La escaleta y sus piezas.

EST-03 a EST-14, DEP-20. La escaleta es el plan de la obra entera: arcos, actos,
curva de tension, promesas y el reparto de escenas por capitulo.

Se congela cuando pasa su verificacion y ya no cambia salvo replanificacion. Por
eso todo lo de aqui es inmutable: una escaleta que se puede editar sobre la
marcha deja de ser un plan y pasa a ser un registro de lo que fue pasando.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commons.types.primitives import WorldTime
from commons.types.scene import SceneFunction

#: EST-07. Rango de longitud de un capitulo.
CHAPTER_WORDS = (1_500, 4_000)

#: EST-08. Rango de longitud de una escena.
SCENE_WORDS = (400, 1_500)


class ArcKind(StrEnum):
    """DEP-20. El doble arco del genero.

    El competitivo pregunta si ganan; el interno, si se convierte en quien debe
    ser. Resolverlos en el mismo momento es el fallo estructural clasico de la
    epica deportiva: la victoria explica el cambio interior y lo abarata.
    """

    COMPETITIVE = "competitivo"
    INTERNAL = "interno"
    SECONDARY = "secundario"


class Arc(BaseModel):
    """EST-03. Un arco, con sus tres momentos planificados."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    kind: ArcKind
    subject: str = Field(min_length=1, description="Entidad cuyo arco es")
    start_scene: str = Field(min_length=1)
    crisis_scene: str = Field(min_length=1)
    resolution_scene: str | None = Field(
        default=None,
        description="Escena donde se resuelve. `None` solo si queda abierto a proposito",
    )
    left_open: bool = Field(
        default=False, description="EST-I2: abierto hacia la siguiente obra, declarado"
    )

    @model_validator(mode="after")
    def _closed_or_declared_open(self) -> Self:
        if (self.resolution_scene is None) != self.left_open:
            raise ValueError(
                f"el arco {self.id!r} no se cierra ni se declara abierto. "
                "EST-I2 no admite el silencio: un arco sin resolucion y sin declarar "
                "es un cabo suelto que nadie va a echar de menos hasta el final"
            )
        return self


class Setup(BaseModel):
    """CAN-08. Una promesa plantada y donde se cobra."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    planted_scene: str = Field(min_length=1)
    payoff_scene: str = Field(min_length=1)
    description: str = Field(min_length=1)


class SceneEntry(BaseModel):
    """Una entrada de escena en la escaleta.

    Todavia no es una especificacion de escena: dice que lugar ocupa, no como se
    escribe. La especificacion la produce el Planificador capitulo a capitulo.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    chapter: int = Field(ge=1)
    ordinal: int = Field(ge=1, description="Posicion dentro del capitulo")
    act: int = Field(ge=1)
    function: SceneFunction
    pov: str = Field(min_length=1, description="EST-I1: exactamente uno")
    value_change: str = Field(
        min_length=1, description="EST-13. Una escena sin el es relleno"
    )
    world_time: WorldTime
    target_words: int = Field(ge=SCENE_WORDS[0], le=SCENE_WORDS[1])
    is_match: bool = Field(default=False, description="DEP-06")
    arcs: tuple[str, ...] = Field(default_factory=tuple)


class ActPlan(BaseModel):
    """Un acto con su curva de tension planificada."""

    model_config = ConfigDict(frozen=True)

    number: int = Field(ge=1)
    tension: tuple[int, ...] = Field(
        description="Tension planificada, un valor por capitulo del acto"
    )


class Outline(BaseModel):
    """EST-12. La escaleta de la obra."""

    model_config = ConfigDict(frozen=True)

    arcs: tuple[Arc, ...]
    acts: tuple[ActPlan, ...]
    scenes: tuple[SceneEntry, ...]
    setups: tuple[Setup, ...] = Field(default_factory=tuple)

    def scene_ids(self) -> frozenset[str]:
        return frozenset(s.id for s in self.scenes)

    def scene(self, scene_id: str) -> SceneEntry | None:
        return next((s for s in self.scenes if s.id == scene_id), None)

    def chapters(self) -> dict[int, list[SceneEntry]]:
        out: dict[int, list[SceneEntry]] = {}
        for s in self.scenes:
            out.setdefault(s.chapter, []).append(s)
        for scenes in out.values():
            scenes.sort(key=lambda s: s.ordinal)
        return out
