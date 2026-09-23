"""`retcon.propose` y la regla dura. CAN-10.

RF-151 a RF-155, D-43. `architecture.md` §8 y §10. Cuando un delta choca con un
hecho congelado, antes de rechazarlo el Arbitro puede proponer una
reinterpretacion del canon. Proponer es del modelo; **admitir es del codigo**:

> Solo procede si el hecho afectado no ha sido cobrado en ningun payoff y el
> numero de pasajes que habria que tocar es igual o menor que 3.

Si no procede, gana el congelado (regla 1 de PRO-10) y el capitulo nuevo vuelve
al Reparador, como en la version 1.

Alcance: conflictos de **atributo**, que son los que un capitulo puede
contradecir de una escena a otra --estado fisico, dorsal, cargo--. Una
identidad o un alias en conflicto no se reinterpreta: gana el congelado.

**Contramedida contra el envenenamiento** (RF-155, `verification.md` §5.9): el
retcon solo toca el hecho que un delta puso en conflicto, con el valor que el
delta trae. Ninguna herramienta escribe, y la cadena "proponer y reparar" no
puede llegar a un hecho que nadie disputo.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Collection

from pydantic import BaseModel, ConfigDict, Field

from canon.arbiter.entries import Rejection
from canon.events import log
from canon.events.types import AttributeSet, Event
from commons.types.primitives import Provenance, WorldTime

#: `architecture.md` §8: pasajes maximos que un retcon puede tocar.
RETCON_MAX_PASSAGES = 3

SYSTEM = """Eres el Arbitro de una novela. Eres un componente de un sistema
automatico: devuelves JSON y nada mas.

Un capitulo nuevo afirma un hecho que contradice lo que el canon congelado ya
tenia por cierto. Lo normal es que gane el canon y el capitulo se corrija. Solo
en un caso propones lo contrario, un retcon: cuando el hecho nuevo es mejor
para la obra que el antiguo Y reinterpretar el pasado no traiciona nada que el
lector ya haya cobrado.

REGLAS QUE NO SE NEGOCIAN

1. Por defecto, NO propones retcon. El canon congelado es la verdad.
2. Propones retcon solo si el hecho antiguo es un detalle que pocos pasajes
   sostienen y el nuevo abre algo que la obra necesita.
3. No decides si el retcon se aplica: lo decide una regla. Tu solo propones."""


class RetconProposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    propose: bool
    rationale: str = ""


class RetconPlan(BaseModel):
    """Lo que un retcon tocaria, calculado por codigo sobre el canon."""

    model_config = ConfigDict(frozen=True)

    fact_key: str
    entity_id: str
    attribute: str
    previous_value: str
    new_value: str
    frozen_since: str = Field(description="Desde cuando rige el hecho congelado")
    scenes: tuple[str, ...] = Field(description="Escenas congeladas que lo sostienen")
    paid: bool = Field(description="Si alguna es la de cobro de una promesa")

    @property
    def admissible(self) -> bool:
        """RF-152. La regla dura, entera."""
        return not self.paid and len(self.scenes) <= RETCON_MAX_PASSAGES

    def reason(self) -> str:
        if self.paid:
            return "el hecho ya lo cobro un payoff"
        if len(self.scenes) > RETCON_MAX_PASSAGES:
            return f"tocaria {len(self.scenes)} pasajes y el maximo es {RETCON_MAX_PASSAGES}"
        return "admisible"


def schema() -> str:
    return "Objeto con propose (true|false) y rationale.\nEjemplo:\n" + json.dumps(
        {"propose": False, "rationale": "el canon congelado es mas coherente"}
    )


def instruction(rejection: Rejection, passages: Collection[str]) -> str:
    a = rejection.arbitration
    return f"""CONFLICTO

Hecho congelado: {a.incumbent.fact_key} = {a.incumbent.value!r} (procedencia {a.incumbent.provenance.value})
Hecho nuevo:     {a.challenger.fact_key} = {a.challenger.value!r}, del capitulo {a.challenger.chapter_origin}
Pasaje del capitulo nuevo: «{rejection.defect.evidence.quote}»

Pasajes congelados que sostienen el hecho antiguo: {", ".join(sorted(passages)) or "(ninguno)"}

¿Propones retcon? Devuelve SOLO el JSON."""


def parse(raw: str) -> RetconProposal:
    return RetconProposal.model_validate_json(raw)


def plan(
    con: sqlite3.Connection, rejection: Rejection, *, payoff_scenes: Collection[str]
) -> RetconPlan | None:
    """Que tocaria el retcon. `None` si el conflicto no es de atributo."""
    payload = rejection.event.payload
    if not isinstance(payload, AttributeSet):
        return None
    anterior = rejection.arbitration.incumbent.value
    row = con.execute(
        "SELECT valid_from FROM attribute WHERE entity_id = ? AND name = ? AND value = ? "
        "ORDER BY valid_from DESC LIMIT 1",
        (payload.entity_id, payload.name, anterior),
    ).fetchone()
    if row is None:
        return None
    escenas = tuple(
        r["id"]
        for r in con.execute(
            "SELECT DISTINCT s.id AS id FROM prose_scene s "
            "JOIN prose_scene_character c ON c.scene_id = s.id "
            "JOIN prose_chunk k ON k.scene_id = s.id "
            "WHERE c.entity_id = ? AND s.world_time >= ? AND instr(lower(k.text), lower(?)) > 0 "
            "ORDER BY s.chapter, s.scene_number",
            (payload.entity_id, row["valid_from"], anterior),
        )
    )
    return RetconPlan(
        fact_key=rejection.arbitration.incumbent.fact_key,
        entity_id=payload.entity_id,
        attribute=payload.name,
        previous_value=anterior,
        new_value=payload.value,
        frozen_since=row["valid_from"],
        scenes=escenas,
        paid=any(s in set(payoff_scenes) for s in escenas),
    )


def event_for(con: sqlite3.Connection, retcon: RetconPlan, *, chapter: int) -> Event:
    """El evento que termina la vigencia del hecho anterior.

    En el mismo instante que el congelado y detras de el: el registro sigue
    siendo append-only y la proyeccion deja vigente el nuevo desde ahi.
    """
    return Event(
        world_time=WorldTime(stamp=retcon.frozen_since, seq=log.next_seq(con, retcon.frozen_since)),
        payload=AttributeSet(
            entity_id=retcon.entity_id, name=retcon.attribute, value=retcon.new_value
        ),
        provenance=Provenance.ARBITRATION,
        chapter_origin=chapter,
        entities=frozenset({retcon.entity_id}),
    )
