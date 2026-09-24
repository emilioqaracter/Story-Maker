"""`delta.extract`: de la salida del Archivero a eventos que el registro acepta.

RF-55, RF-56, RD-19. Tres cosas ocurren aqui y son las que separan una
propuesta de un hecho:

1. **La salida se valida contra el esquema.** Un tipo de evento desconocido o un
   campo que falta no es un evento raro: es una salida que no encaja y cuenta
   como llamada fallida (RI-18).
2. **El desempate de instante lo fija el codigo, no el modelo.** El Archivero
   dice en que orden ocurren los hechos de un mismo instante; este modulo los
   coloca **detras** de lo ya registrado en ese instante, para que no colisionen
   con el canon congelado. La causalidad la decide el agente; que no pise nada,
   el codigo.
3. **Un delta vacio es un fallo, no un exito.** Cada escena declara un cambio de
   valor; un capitulo que no cambia nada en el mundo es un capitulo que el
   Archivero no ha leido (trampa 12 del plan).

Ademas de los eventos, el delta lleva los **elementos del brief** que aparecen
en el capitulo, cada uno con su cita literal (RF-261, D-95). No son eventos --el
canon ya los tiene desde el brief--: son usos, y el codigo los ancla con
`check.evidence` en la escena antes de congelarlos. Lo hace el Orquestador,
porque `canon/` no importa de `verification/`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from canon.events import log
from canon.events.types import ElementDeclared, Event, Payload
from commons.types.primitives import Provenance, WorldTime


class EmptyDeltaError(RuntimeError):
    """El Archivero no extrajo ningun hecho de un capitulo aprobado.

    Consume un reintento, como cualquier salida que no encaja: congelar con
    delta vacio dejaria el canon en el brief mientras la prosa avanza, que es
    justo lo que la tirada real destapo.
    """


class ProposedEvent(BaseModel):
    """Un hecho propuesto, con la cita que lo sostiene."""

    model_config = ConfigDict(frozen=True)

    world_time: WorldTime
    payload: Payload = Field(discriminator="type")
    entities: tuple[str, ...] = Field(default_factory=tuple)
    quote: str = Field(min_length=1, description="Pasaje literal del capitulo")

    @model_validator(mode="after")
    def _derive_entities(self) -> Self:
        if isinstance(self.payload, ElementDeclared):
            # RD-47: un elemento lo declara el brief. El Archivero lo cita en
            # `elements`; declararlo seria reescribir lo que se pidio.
            raise ValueError("element.declared no es un hecho de la prosa: va en elements")
        if self.entities:
            return self
        derivadas = _entities_of(self.payload)
        if not derivadas:
            raise ValueError("un evento sin entidad afectada no se puede proyectar")
        object.__setattr__(self, "entities", derivadas)
        return self


class ElementMention(BaseModel):
    """RF-261. Un elemento del brief que el capitulo usa, con la cita que lo muestra."""

    model_config = ConfigDict(frozen=True)

    element_id: str = Field(min_length=1)
    scene: str = Field(default="", description="La escena que nombra: pista, no prueba")
    quote: str = Field(min_length=1, description="Pasaje literal del capitulo")


class DeltaProposal(BaseModel):
    """CAN-11 antes de validarse: lo que el Archivero propone."""

    model_config = ConfigDict(frozen=True)

    events: tuple[ProposedEvent, ...] = Field(default_factory=tuple)
    elements: tuple[ElementMention, ...] = Field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return not self.events


def _entities_of(payload: Payload) -> tuple[str, ...]:
    """Las entidades que un payload modifica, por su forma."""
    source = getattr(payload, "source_id", None)
    target = getattr(payload, "target_id", None)
    if source is not None and target is not None:
        return (source, target)
    entity = getattr(payload, "entity_id", None)
    return (entity,) if entity else ()


def parse(raw: str, *, tolerant: bool = False) -> DeltaProposal:
    """Valida la salida cruda del modelo. Lanza `ValidationError` si no encaja.

    D-141. `tolerant` descarta los hechos y menciones mal formados en vez de
    rechazar el delta entero.
    """
    if tolerant:
        t = TolerantDeltaProposal.model_validate_json(raw)
        return DeltaProposal(events=t.events, elements=t.elements)
    return DeltaProposal.model_validate_json(raw)


class TolerantDeltaProposal(DeltaProposal):
    """D-141. El delta en modo permisivo: un hecho que no encaja con su esquema
    se descarta y el resto vale. Un solo hecho mal formado no tira lo demas."""

    @model_validator(mode="before")
    @classmethod
    def _drop_malformed(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        limpio = dict(data)
        modelos: tuple[tuple[str, type[BaseModel]], ...] = (
            ("events", ProposedEvent),
            ("elements", ElementMention),
        )
        for clave, modelo in modelos:
            items = limpio.get(clave)
            if not isinstance(items, list):
                continue
            validos = []
            for item in items:
                try:
                    modelo.model_validate(item)
                except ValidationError:
                    continue
                validos.append(item)
            limpio[clave] = validos
        return limpio


def to_events(
    proposal: DeltaProposal, con: sqlite3.Connection, *, chapter: int
) -> tuple[Event, ...]:
    """Convierte la propuesta en eventos con procedencia `prose` y sin colisiones.

    Por cada instante, los eventos propuestos se ordenan por el `seq` que dio el
    Archivero --su orden de causalidad-- y se renumeran a partir del primer
    hueco libre del registro (RD-19). Asi el agente decide el orden y el codigo
    garantiza que no pisa nada congelado.
    """
    if proposal.is_empty:
        raise EmptyDeltaError(
            "el Archivero no extrajo ningun hecho: un capitulo aprobado siempre "
            "cambia algo, porque cada escena declara un cambio de valor"
        )

    por_instante: dict[str, list[ProposedEvent]] = {}
    for ev in proposal.events:
        por_instante.setdefault(ev.world_time.stamp, []).append(ev)

    out: list[Event] = []
    for stamp in sorted(por_instante):
        base = log.next_seq(con, stamp)
        ordenados = sorted(por_instante[stamp], key=lambda e: e.world_time.seq)
        for offset, ev in enumerate(ordenados):
            out.append(
                Event(
                    world_time=WorldTime(stamp=stamp, seq=base + offset),
                    payload=ev.payload,
                    provenance=Provenance.PROSE,
                    chapter_origin=chapter,
                    entities=frozenset(ev.entities),
                )
            )
    return tuple(out)


def quotes_by_event(proposal: DeltaProposal, events: Sequence[Event]) -> dict[int, str]:
    """Indice de posicion del evento -> cita, en el mismo orden que `to_events`.

    Existe para que el Arbitro pueda citar el pasaje al rechazar un hecho: un
    defecto sin cita se descarta, y el Reparador necesita saber donde mirar.
    """
    por_payload = {(e.world_time.stamp, id(e.payload)): e.quote for e in proposal.events}
    out: dict[int, str] = {}
    for i, ev in enumerate(events):
        for (stamp, _pid), quote in por_payload.items():
            if stamp == ev.world_time.stamp and _same_payload(ev, proposal, quote):
                out[i] = quote
                break
    return out


def _same_payload(ev: Event, proposal: DeltaProposal, quote: str) -> bool:
    return any(p.quote == quote and p.payload == ev.payload for p in proposal.events)
