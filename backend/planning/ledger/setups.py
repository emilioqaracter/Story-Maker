"""`setup.ledger`. Registro de promesas y deuda narrativa.

RF-31, CAN-08. Vive en `planning/` y no en `supervision/` (D-31): `planning/`
planta los setups al escribir la escaleta y los cobra al especificar escenas, y
el Supervisor --que no existe en la version 1-- solo los leera cuando llegue.

La deuda narrativa es la metrica de salud estructural mas util del sistema: es
lo que mide la puerta de cierre de acto y una de las cuatro condiciones de
cierre de obra. Si esto esta mal, la novela puede terminar debiendo cosas sin
que nada lo señale.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from planning.outline.types import Outline


class SetupState(StrEnum):
    """Estado de una promesa.

    `PLANTED` cuando la escena que la planta esta congelada; `PAID` cuando lo
    esta la que la cobra. **Planificar no es plantar**: mientras las dos escenas
    sigan sin escribirse, la promesa esta prevista y no abierta, porque una
    promesa que el lector no ha leido todavia no debe nada.
    """

    PLANNED = "planificado"
    PLANTED = "plantado"
    PAID = "cobrado"


class SetupStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    state: SetupState
    planted_scene: str
    payoff_scene: str
    description: str
    planted_chapter: int | None = None
    payoff_chapter: int | None = None


class Debt(BaseModel):
    """CAN-08. La deuda narrativa vigente."""

    model_config = ConfigDict(frozen=True)

    open_setups: tuple[SetupStatus, ...] = Field(
        description="Plantados y sin cobrar. Esto es lo que se debe"
    )
    planned: tuple[SetupStatus, ...] = Field(
        description="Ni plantados aun. No son deuda todavia, pero son compromiso"
    )
    paid: tuple[SetupStatus, ...] = Field(default_factory=tuple)

    @property
    def is_clear(self) -> bool:
        """Deuda cero. Es una de las cuatro condiciones de cierre de obra.

        Cuenta los planificados tambien: una promesa que la escaleta prometia y
        nadie llego a plantar es una promesa incumplida igual, solo que el
        lector ni siquiera supo que existia.
        """
        return not self.open_setups and not self.planned


def status(outline: Outline, frozen_scenes: frozenset[str]) -> list[SetupStatus]:
    """Estado de cada setup dado lo que hay congelado.

    `frozen_scenes` son las escenas ya congeladas. Se pasa como argumento en vez
    de consultarlo aqui para que esta funcion sea pura: es lo que permite
    comprobarla generando casos, y lo que impide que `planning/` abra la base.
    """
    out: list[SetupStatus] = []
    for setup in outline.setups:
        planted = setup.planted_scene in frozen_scenes
        paid = setup.payoff_scene in frozen_scenes
        state = SetupState.PAID if paid else (SetupState.PLANTED if planted else SetupState.PLANNED)
        plant = outline.scene(setup.planted_scene)
        pay = outline.scene(setup.payoff_scene)
        out.append(
            SetupStatus(
                id=setup.id,
                state=state,
                planted_scene=setup.planted_scene,
                payoff_scene=setup.payoff_scene,
                description=setup.description,
                planted_chapter=plant.chapter if plant else None,
                payoff_chapter=pay.chapter if pay else None,
            )
        )
    return out


def debt(outline: Outline, frozen_scenes: frozenset[str]) -> Debt:
    """La deuda narrativa vigente."""
    todos = status(outline, frozen_scenes)
    return Debt(
        open_setups=tuple(s for s in todos if s.state is SetupState.PLANTED),
        planned=tuple(s for s in todos if s.state is SetupState.PLANNED),
        paid=tuple(s for s in todos if s.state is SetupState.PAID),
    )
