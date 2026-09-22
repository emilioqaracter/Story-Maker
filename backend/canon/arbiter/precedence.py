"""El Arbitro y la politica de precedencia.

RF-59 a RF-63, PRO-10. **Desde aqui el sistema es autonomo**: antes de esta
pieza, cualquier contradiccion lo detiene porque no hay a quien preguntar.

La politica es un **orden total sin ciclos**: todo conflicto tiene exactamente
un ganador. Que sea total no es elegancia, es lo que hace que el sistema pueda
terminar solo: una regla que a veces empata es una regla que a veces necesita a
alguien.

Las cuatro reglas, en orden de fuerza:

1. Canon congelado sobre delta nuevo.
2. Brief sobre canon derivado.
3. Invariante duro sobre preferencia estetica.
4. Hecho con payoff cobrado sobre hecho sin cobrar.

Todo arbitraje deja registro con **la regla aplicada**, no solo con el ganador:
sin eso, revisar una tirada de treinta capitulos es adivinar por que el sistema
decidio lo que decidio.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic import BaseModel, ConfigDict, Field

from commons.types.primitives import Provenance


class Rule(StrEnum):
    """La regla que resolvio el conflicto."""

    FROZEN_OVER_NEW = "canon-congelado-sobre-delta-nuevo"
    BRIEF_OVER_DERIVED = "brief-sobre-canon-derivado"
    HARD_OVER_AESTHETIC = "invariante-sobre-preferencia"
    PAID_OVER_UNPAID = "payoff-cobrado-sobre-sin-cobrar"


class Claim(BaseModel):
    """Una de las dos afirmaciones en conflicto."""

    model_config = ConfigDict(frozen=True)

    fact_key: str = Field(min_length=1)
    value: str
    provenance: Provenance
    frozen: bool = Field(description="Si ya esta en canon congelado")
    hard_invariant: bool = Field(default=False)
    payoff_paid: bool = Field(
        default=False, description="Si algun payoff ya se apoyo en este hecho"
    )
    chapter_origin: int | None = None


class _Strength(IntEnum):
    """Fuerza de una afirmacion. Mayor gana.

    Se calcula como un numero y no con una cadena de `if`, porque asi la
    totalidad del orden es evidente: dos afirmaciones siempre tienen fuerzas
    comparables, y solo hay empate si son identicas en las cuatro dimensiones.
    """

    BASE = 0


class Arbitration(BaseModel):
    """El veredicto, con su registro.

    Contrato de spec §3.5: las dos afirmaciones, la regla aplicada, la ganadora
    y los pasajes afectados.
    """

    model_config = ConfigDict(frozen=True)

    incumbent: Claim
    challenger: Claim
    winner: Claim
    rule: Rule
    affected_passages: tuple[str, ...] = Field(default_factory=tuple)

    @property
    def challenger_won(self) -> bool:
        return self.winner is self.challenger


def _score(claim: Claim) -> tuple[int, int, int, int]:
    """Fuerza de una afirmacion, en orden lexicografico de las cuatro reglas.

    El orden de la tupla **es** el orden de las reglas: congelado pesa mas que
    procedencia, procedencia mas que invariante, invariante mas que payoff. Con
    eso la comparacion es una sola linea y la totalidad es evidente.
    """
    return (
        1 if claim.frozen else 0,
        1 if claim.provenance is Provenance.BRIEF else 0,
        1 if claim.hard_invariant else 0,
        1 if claim.payoff_paid else 0,
    )


def _rule_for(winner: Claim, loser: Claim) -> Rule:
    """Que regla explica la victoria. La primera que los separa."""
    if winner.frozen != loser.frozen:
        return Rule.FROZEN_OVER_NEW
    if (winner.provenance is Provenance.BRIEF) != (loser.provenance is Provenance.BRIEF):
        return Rule.BRIEF_OVER_DERIVED
    if winner.hard_invariant != loser.hard_invariant:
        return Rule.HARD_OVER_AESTHETIC
    return Rule.PAID_OVER_UNPAID


def arbitrate(
    incumbent: Claim, challenger: Claim, *, affected_passages: tuple[str, ...] = ()
) -> Arbitration:
    """Resuelve un conflicto. Siempre hay exactamente un ganador.

    Cuando las dos afirmaciones son indistinguibles por las cuatro reglas, gana
    **la que ya estaba**. No es un desempate arbitrario: en un sistema donde el
    canon congelado manda, lo establecido es lo que el resto de la obra ya da
    por cierto, y cambiarlo sin motivo obliga a revisar todo lo que se apoyo en
    ello.
    """
    if incumbent.fact_key != challenger.fact_key:
        raise ValueError(
            f"no hay conflicto entre {incumbent.fact_key!r} y {challenger.fact_key!r}: "
            "son hechos distintos"
        )

    gana_retador = _score(challenger) > _score(incumbent)
    winner = challenger if gana_retador else incumbent
    loser = incumbent if gana_retador else challenger

    return Arbitration(
        incumbent=incumbent,
        challenger=challenger,
        winner=winner,
        rule=_rule_for(winner, loser),
        affected_passages=affected_passages,
    )


def merge_deltas(a: tuple[Claim, ...], b: tuple[Claim, ...]) -> tuple[Claim, ...]:
    """RF-62. Fusionar dos deltas es **asociativo**.

    Que lo sea importa porque el orden en que llegan los deltas de dos capitulos
    no puede cambiar el canon resultante. Se consigue resolviendo cada hecho por
    fuerza y no por orden de llegada.
    """
    por_clave: dict[str, Claim] = {}
    for claim in (*a, *b):
        actual = por_clave.get(claim.fact_key)
        if actual is None:
            por_clave[claim.fact_key] = claim
        else:
            por_clave[claim.fact_key] = arbitrate(actual, claim).winner
    return tuple(por_clave[k] for k in sorted(por_clave))
