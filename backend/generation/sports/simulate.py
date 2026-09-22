"""`match.simulate`. Motor de reglas que resuelve un encuentro.

RF-42, RF-43. **El encuentro se resuelve primero con reglas y despues se narra.**
El modelo no inventa el marcador, lo dramatiza.

Esto es lo que mas devuelve de todo el subdominio deportivo: elimina de raiz
toda la familia de defectos de verosimilitud --marcadores que no cuadran con la
clasificacion, goleadores que no jugaron, estadisticas que no suman-- porque
deja de haber un sitio donde puedan aparecer. Un verificador que los busque
despues siempre llega tarde y siempre se le escapa alguno.

**Determinista dada una semilla** (RF-42). Sin eso, reanudar una tirada
interrumpida daria un partido distinto y el capitulo ya escrito hablaria de otro
encuentro.
"""

from __future__ import annotations

import random
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commons.types.primitives import WorldTime


class Availability(StrEnum):
    """DEP-13, DEP-14. Por que alguien no puede jugar."""

    AVAILABLE = "disponible"
    INJURED = "lesionado"
    SUSPENDED = "sancionado"
    UNREGISTERED = "no-inscrito"


class Player(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    availability: Availability = Availability.AVAILABLE
    #: 0 a 100. Sale del canon, no se inventa aqui.
    skill: int = Field(default=50, ge=0, le=100)


class Squad(BaseModel):
    model_config = ConfigDict(frozen=True)

    team_id: str = Field(min_length=1)
    players: tuple[Player, ...]

    def available(self) -> tuple[Player, ...]:
        return tuple(p for p in self.players if p.availability is Availability.AVAILABLE)


class MilestoneKind(StrEnum):
    GOAL = "gol"
    INJURY = "lesion"
    CARD = "tarjeta"
    SUBSTITUTION = "cambio"


class Milestone(BaseModel):
    """Un hito del encuentro, con su minuto.

    La cronologia es lo que `match.narrate` dramatiza y lo que `check.ledger`
    contrasta contra lo narrado. Por eso lleva minuto: sin el, no se puede
    comprobar que la prosa cuente los hechos en el orden en que pasaron.
    """

    model_config = ConfigDict(frozen=True)

    minute: int = Field(ge=0, le=120)
    kind: MilestoneKind
    team_id: str
    player_id: str
    detail: str = ""


class MatchResult(BaseModel):
    """DEP-07. El resultado, ya cerrado."""

    model_config = ConfigDict(frozen=True)

    home_team: str
    away_team: str
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)
    at: WorldTime
    milestones: tuple[Milestone, ...]
    injuries: tuple[str, ...] = Field(
        default_factory=tuple, description="Entidades que salen lesionadas"
    )

    @model_validator(mode="after")
    def _goals_match_milestones(self) -> Self:
        """El marcador y los hitos cuentan lo mismo.

        Que puedan discrepar es el defecto que todo esto existe para evitar, asi
        que no se deja para un verificador: se impone al construir el resultado.
        """
        goles = [m for m in self.milestones if m.kind is MilestoneKind.GOAL]
        local = sum(1 for m in goles if m.team_id == self.home_team)
        visitante = sum(1 for m in goles if m.team_id == self.away_team)
        if (local, visitante) != (self.home_goals, self.away_goals):
            raise ValueError(
                f"el marcador dice {self.home_goals}-{self.away_goals} y los hitos "
                f"cuentan {local}-{visitante}"
            )
        return self


class UnavailablePlayerError(RuntimeError):
    """Se intento alinear a alguien que no podia jugar (DEP-I2)."""


def simulate(
    home: Squad,
    away: Squad,
    *,
    at: WorldTime,
    seed: int,
    injury_chance: float = 0.08,
) -> MatchResult:
    """Resuelve el encuentro completo. Determinista dada `seed`.

    Solo alinea a quien esta disponible **en esa fecha** (RF-43, DEP-I2): que
    nadie juegue estando lesionado no se comprueba despues, se hace imposible
    antes.
    """
    for squad in (home, away):
        if not squad.available():
            raise UnavailablePlayerError(
                f"el equipo {squad.team_id!r} no tiene ningun jugador disponible"
            )

    rng = random.Random(seed)  # nosec B311
    hitos: list[Milestone] = []
    lesionados: list[str] = []
    marcador = {home.team_id: 0, away.team_id: 0}

    for squad, rival in ((home, away), (away, home)):
        ocasiones = _chances(squad, rival, rng)
        for minuto in sorted(rng.sample(range(1, 91), k=min(ocasiones, 90))):
            autor = _pick(squad, rng)
            hitos.append(
                Milestone(
                    minute=minuto,
                    kind=MilestoneKind.GOAL,
                    team_id=squad.team_id,
                    player_id=autor.entity_id,
                )
            )
            marcador[squad.team_id] += 1

    for squad in (home, away):
        if rng.random() < injury_chance:
            victima = _pick(squad, rng)
            minuto = rng.randint(1, 90)
            hitos.append(
                Milestone(
                    minute=minuto,
                    kind=MilestoneKind.INJURY,
                    team_id=squad.team_id,
                    player_id=victima.entity_id,
                    detail="se retira",
                )
            )
            lesionados.append(victima.entity_id)

    # Orden por minuto y, a igualdad, por equipo y jugador: la cronologia tiene
    # que ser total o dos ejecuciones con la misma semilla podrian narrarse en
    # orden distinto.
    hitos.sort(key=lambda m: (m.minute, m.team_id, m.player_id, m.kind.value))

    return MatchResult(
        home_team=home.team_id,
        away_team=away.team_id,
        home_goals=marcador[home.team_id],
        away_goals=marcador[away.team_id],
        at=at,
        milestones=tuple(hitos),
        injuries=tuple(sorted(lesionados)),
    )


def _chances(squad: Squad, rival: Squad, rng: random.Random) -> int:
    """Cuantos goles marca un equipo.

    La diferencia de nivel medio inclina la moneda sin decidirla: un equipo
    mejor gana mas veces, no siempre. Que pueda perder es lo que hace que el
    arco competitivo tenga algo que contar.
    """
    mio = sum(p.skill for p in squad.available()) / len(squad.available())
    suyo = sum(p.skill for p in rival.available()) / len(rival.available())
    ventaja = (mio - suyo) / 100
    esperados = max(0.2, 1.3 + ventaja * 1.5)
    return min(6, sum(1 for _ in range(6) if rng.random() < esperados / 6))


def _pick(squad: Squad, rng: random.Random) -> Player:
    """Elige un jugador, ponderando por nivel."""
    disponibles = squad.available()
    pesos = [max(1, p.skill) for p in disponibles]
    return rng.choices(disponibles, weights=pesos, k=1)[0]
