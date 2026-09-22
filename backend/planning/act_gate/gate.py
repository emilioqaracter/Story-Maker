"""Puerta de cierre de acto.

RF-105, RF-106. Es la unica de las cinco puertas que no se evalua por capitulo,
y por eso se le escapa a quien lee el flujo de pasada: corre **al congelar el
ultimo capitulo de un acto**.

**Por que existe aunque el cierre de obra ya compruebe deuda cero.** Porque
comprobarlo solo al final es comprobarlo cuando ya no se puede arreglar barato:
una deuda que se desmadra en el acto II y se detecta en el cierre obliga a
replanificar la obra entera. Esta puerta la detecta un acto antes, cuando queda
sitio por delante para cobrarla.

**Lo que no comprueba todavia**: que la curva de tension realizada se parezca a
la planificada. Medirla exige juicio, y el juicio llega con el Jurado. Queda en
riesgo aceptado, declarado y no omitido.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from planning.ledger.setups import SetupState, status
from planning.outline.types import Outline


class ActGateResult(BaseModel):
    """Veredicto de la puerta de un acto."""

    model_config = ConfigDict(frozen=True)

    act: int
    passed: bool
    unpaid: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Setups cuyo payoff estaba planificado en este acto y no se cobro",
    )

    def reason(self) -> str:
        if self.passed:
            return f"el acto {self.act} cierra sin deuda pendiente de este acto"
        return (
            f"el acto {self.act} deja sin cobrar {len(self.unpaid)} promesa(s) que "
            f"la escaleta situaba dentro de el: {', '.join(self.unpaid)}"
        )


def last_chapter_of(outline: Outline, act: int) -> int | None:
    """Ultimo capitulo del acto, o `None` si el acto no tiene escenas."""
    chapters = [s.chapter for s in outline.scenes if s.act == act]
    return max(chapters) if chapters else None


def closes_an_act(outline: Outline, chapter: int) -> int | None:
    """Que acto cierra este capitulo, si cierra alguno.

    Un capitulo puede tener escenas de dos actos --la escaleta no lo prohibe--
    asi que se comprueba acto por acto en vez de mirar el acto "del capitulo",
    que no siempre es uno solo.
    """
    for act in sorted({s.act for s in outline.scenes}):
        if last_chapter_of(outline, act) == chapter:
            return act
    return None


def check_act(
    outline: Outline, act: int, frozen_scenes: frozenset[str]
) -> ActGateResult:
    """Todo setup con payoff planificado dentro del acto aparece cobrado.

    **El umbral no es un numero nuevo**: lo fija la propia escaleta, que ya
    declara donde se cobra cada promesa. Eso importa porque inventar aqui un
    "maximo de deuda tolerable" habria sido meter una constante sin dueño en la
    puerta mas estructural del sistema.
    """
    escenas_del_acto = {s.id for s in outline.scenes if s.act == act}

    sin_cobrar = tuple(
        st.id
        for st in status(outline, frozen_scenes)
        if st.payoff_scene in escenas_del_acto and st.state is not SetupState.PAID
    )
    return ActGateResult(act=act, passed=not sin_cobrar, unpaid=sin_cobrar)


def replan_target(outline: Outline, act: int) -> int | None:
    """Que acto hay que replanificar cuando la puerta falla.

    **El siguiente, nunca el que se acaba de cerrar.** El canon congelado gana,
    asi que el remedio solo puede mirar hacia delante: se replanifica el tramo
    siguiente para dar payoff a lo que quedo sin cobrar.

    Devuelve `None` si no hay acto siguiente, que es el caso en que la deuda ya
    no se puede saldar y tiene que verla la condicion de cierre de obra.
    """
    actos = sorted({s.act for s in outline.scenes})
    posteriores = [a for a in actos if a > act]
    return posteriores[0] if posteriores else None
