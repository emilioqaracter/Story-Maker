"""Las dos puertas del Arbitro.

RF-59, RF-60, RF-63, PRO-10. `architecture.md` §6.2 y §10. La politica vive en
`precedence.py`; aqui esta **quien la invoca y con que**:

- **Puerta 1, el Orquestador.** Al validar el delta del Archivero contra el
  canon antes de congelar. Un hecho del delta que contradice un hecho congelado
  se arbitra; en la version 1 el congelado gana siempre (D-05), el evento se
  rechaza y el capitulo recibe un defecto S1 con la cita del pasaje (RF-60).
- **Puerta 2, el Documentalista.** Cuando `context.audit` encuentra dos versiones
  del mismo hecho en un paquete. Se resuelve por precedencia antes de generar:
  arbitrar antes es mas barato que reparar despues.

Que cuenta como contradiccion es una regla de codigo, no de criterio: un hecho
nuevo contradice al canon cuando afirma algo sobre un instante que el canon ya
tiene cubierto con otro valor. Que Marcos se lesione el dia 20 estando sano el
10 no es una contradiccion, es la novela; que se lesione el dia 5 cuando el
canon dice que estaba sano el 10, si.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from canon.arbiter.precedence import Arbitration, Claim, arbitrate
from canon.events.types import (
    AliasAdded,
    AttributeSet,
    CompetenceSet,
    EntityCreated,
    Event,
)
from commons.types.primitives import Defect, Evidence, Provenance, Severity


class Rejection(BaseModel):
    """Un evento del delta que el canon congelado no admite."""

    model_config = ConfigDict(frozen=True)

    event: Event
    arbitration: Arbitration
    defect: Defect


class DeltaValidation(BaseModel):
    """Resultado de la puerta 1."""

    model_config = ConfigDict(frozen=True)

    accepted: tuple[Event, ...]
    rejections: tuple[Rejection, ...] = Field(default_factory=tuple)

    @property
    def clean(self) -> bool:
        return not self.rejections


def _frozen_claim(
    con: sqlite3.Connection, *, fact_key: str, value: str, source_event: int | None
) -> Claim:
    provenance = Provenance.PROSE
    chapter: int | None = None
    if source_event is not None:
        row = con.execute(
            "SELECT provenance, chapter_origin FROM event WHERE id = ?", (source_event,)
        ).fetchone()
        if row is not None:
            provenance = Provenance(row["provenance"])
            chapter = row["chapter_origin"]
    return Claim(
        fact_key=fact_key,
        value=value,
        provenance=provenance,
        frozen=True,
        chapter_origin=chapter,
    )


def _conflict_of(con: sqlite3.Connection, ev: Event) -> tuple[str, Claim] | None:
    """La afirmacion congelada que este evento contradice, si la hay."""
    stamp = ev.world_time.stamp
    payload = ev.payload

    match payload:
        case AttributeSet():
            row = con.execute(
                "SELECT value, source_event FROM attribute "
                "WHERE entity_id = ? AND name = ? AND valid_from >= ? AND value <> ? "
                "ORDER BY valid_from DESC LIMIT 1",
                (payload.entity_id, payload.name, stamp, payload.value),
            ).fetchone()
            if row is None:
                return None
            key = f"{payload.entity_id}.{payload.name}"
            return key, _frozen_claim(
                con, fact_key=key, value=row["value"], source_event=row["source_event"]
            )
        case CompetenceSet():
            row = con.execute(
                "SELECT level, source_event FROM competence "
                "WHERE entity_id = ? AND name = ? AND valid_from >= ? AND level <> ? "
                "ORDER BY valid_from DESC LIMIT 1",
                (payload.entity_id, payload.name, stamp, payload.level),
            ).fetchone()
            if row is None:
                return None
            key = f"{payload.entity_id}.competence.{payload.name}"
            return key, _frozen_claim(
                con, fact_key=key, value=row["level"], source_event=row["source_event"]
            )
        case EntityCreated():
            row = con.execute(
                "SELECT kind, name FROM entity WHERE id = ?", (payload.entity_id,)
            ).fetchone()
            if row is None or (row["kind"], row["name"]) == (payload.kind, payload.name):
                return None
            key = f"{payload.entity_id}.identity"
            return key, _frozen_claim(
                con, fact_key=key, value=f"{row['kind']}:{row['name']}", source_event=None
            )
        case AliasAdded():
            row = con.execute(
                "SELECT entity_id FROM entity_alias WHERE alias = ? AND entity_id <> ? "
                "AND (valid_to IS NULL OR valid_to > ?) LIMIT 1",
                (payload.alias, payload.entity_id, stamp),
            ).fetchone()
            if row is None:
                return None
            key = f"alias.{payload.alias}"
            return key, _frozen_claim(con, fact_key=key, value=row["entity_id"], source_event=None)
        case _:
            return None


def _new_value(ev: Event) -> str:
    payload = ev.payload
    match payload:
        case AttributeSet():
            return payload.value
        case CompetenceSet():
            return payload.level
        case EntityCreated():
            return f"{payload.kind}:{payload.name}"
        case AliasAdded():
            return payload.entity_id
        case _:
            return str(payload.type)


def validate_delta(
    con: sqlite3.Connection,
    delta: Sequence[Event],
    *,
    quotes: Mapping[int, str] | None = None,
    chapter_text: str = "",
) -> DeltaValidation:
    """Puerta 1. Contrasta cada evento con el canon y arbitra las contradicciones.

    `quotes` da, por posicion del evento en `delta`, el pasaje que lo sostiene;
    es lo que convierte un rechazo en un defecto **con cita**, que es la unica
    forma de defecto que el Reparador acepta (RI-19).
    """
    quotes = quotes or {}
    accepted: list[Event] = []
    rejections: list[Rejection] = []

    for i, ev in enumerate(delta):
        conflicto = _conflict_of(con, ev)
        if conflicto is None:
            accepted.append(ev)
            continue

        key, incumbent = conflicto
        challenger = Claim(
            fact_key=key,
            value=_new_value(ev),
            provenance=ev.provenance,
            frozen=False,
            chapter_origin=ev.chapter_origin,
        )
        veredicto = arbitrate(incumbent, challenger)
        if veredicto.challenger_won:
            # En la version 1 no ocurre: el congelado gana por la regla 1 y el
            # retador nunca esta congelado. Se deja el camino porque la
            # politica es total y el retcon de la version 2 entra por aqui.
            accepted.append(ev)
            continue

        quote = quotes.get(i, "")
        offset = chapter_text.find(quote) if quote else -1
        evidencia = Evidence(quote=quote or f"{key}={challenger.value}", offset=max(offset, 0))
        rejections.append(
            Rejection(
                event=ev,
                arbitration=veredicto,
                defect=Defect(
                    kind="arbitration",
                    severity=Severity.S1,
                    evidence=evidencia,
                    rule=(
                        f"el capitulo afirma {key}={challenger.value!r} en "
                        f"{ev.world_time.stamp}, pero el canon congelado dice "
                        f"{incumbent.value!r} ({veredicto.rule.value})"
                    ),
                ),
            )
        )

    return DeltaValidation(accepted=tuple(accepted), rejections=tuple(rejections))


def resolve_claims(
    claims: Sequence[Claim],
) -> tuple[dict[str, Claim], tuple[Arbitration, ...]]:
    """Puerta 2. Resuelve por precedencia las afirmaciones repetidas de un paquete.

    Devuelve la vigente por clave y los arbitrajes que hicieron falta, para que
    el Documentalista incorpore la primera y trace los segundos (RF-36).
    """
    vigentes: dict[str, Claim] = {}
    arbitrajes: list[Arbitration] = []
    for claim in claims:
        actual = vigentes.get(claim.fact_key)
        if actual is None or actual == claim:
            vigentes[claim.fact_key] = claim
            continue
        veredicto = arbitrate(actual, claim)
        arbitrajes.append(veredicto)
        vigentes[claim.fact_key] = veredicto.winner
    return vigentes, tuple(arbitrajes)
