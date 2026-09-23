"""Tipos de evento y el evento mismo.

MET-05, MET-09. Un evento es el unico modo de que algo entre en el canon: todo
lo demas --entidades, atributos, relaciones, conocimiento-- es proyeccion
reconstruible de estas filas (RF-05).

Los tipos son un conjunto cerrado porque la proyeccion es un despacho sobre
ellos: un tipo desconocido no es un evento raro, es un hecho que nadie sabe
aplicar y que quedaria como ruido en el registro.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commons.types.primitives import Provenance, WorldTime


class EventType(StrEnum):
    ENTITY_CREATED = "entity.created"
    ALIAS_ADDED = "alias.added"
    ATTRIBUTE_SET = "attribute.set"
    RELATION_SET = "relation.set"
    KNOWLEDGE_GAINED = "knowledge.gained"
    COMPETENCE_SET = "competence.set"
    DOCUMENT_VERSION = "document.version"
    ENTITY_RENAMED = "entity.renamed"


# ------------------------------------------------------------------- payloads


class EntityCreated(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal[EventType.ENTITY_CREATED] = EventType.ENTITY_CREATED
    entity_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)


class AliasAdded(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal[EventType.ALIAS_ADDED] = EventType.ALIAS_ADDED
    entity_id: str = Field(min_length=1)
    alias: str = Field(min_length=1)
    valid_to: WorldTime | None = None


class AttributeSet(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal[EventType.ATTRIBUTE_SET] = EventType.ATTRIBUTE_SET
    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    value: str
    valid_to: WorldTime | None = None


class RelationSet(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal[EventType.RELATION_SET] = EventType.RELATION_SET
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    valid_to: WorldTime | None = None


class KnowledgeGained(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal[EventType.KNOWLEDGE_GAINED] = EventType.KNOWLEDGE_GAINED
    entity_id: str = Field(min_length=1)
    fact_key: str = Field(min_length=1)


class CompetenceSet(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal[EventType.COMPETENCE_SET] = EventType.COMPETENCE_SET
    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    level: str = Field(min_length=1)
    valid_to: WorldTime | None = None


class DocumentVersion(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal[EventType.DOCUMENT_VERSION] = EventType.DOCUMENT_VERSION
    doc_kind: str = Field(min_length=1)
    body: str = Field(min_length=1)


class EntityRenamed(BaseModel):
    """RF-210, D-76. El nombre canonico cambia en todo el canon, desde siempre.

    Solo lo produce una enmienda al brief: quien encarga no dice «desde el
    capitulo 7 se llama Nala», dice que se llama Nala. El nombre anterior no
    queda como alias, o `check.lexicon` lo seguiria aceptando.
    """

    model_config = ConfigDict(frozen=True)
    type: Literal[EventType.ENTITY_RENAMED] = EventType.ENTITY_RENAMED
    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


Payload = (
    EntityCreated
    | AliasAdded
    | AttributeSet
    | RelationSet
    | KnowledgeGained
    | CompetenceSet
    | DocumentVersion
    | EntityRenamed
)


# --------------------------------------------------------------------- evento


class Event(BaseModel):
    """Un hecho canonico fechado.

    RD-01: sin instante, tipo, entidad afectada, procedencia y capitulo de
    origen no llega a tocar la base. Uno incompleto se rechaza antes (RF-02).
    """

    model_config = ConfigDict(frozen=True)

    world_time: WorldTime
    payload: Payload = Field(discriminator="type")
    provenance: Provenance
    chapter_origin: int | None = Field(default=None, ge=1)
    entities: frozenset[str] = Field(
        description="Entidades que el evento modifica. Al menos una (RD-02)"
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.entities:
            raise ValueError("un evento sin entidad afectada no se puede proyectar sobre nada")
        brief = self.provenance is Provenance.BRIEF
        if brief != (self.chapter_origin is None):
            raise ValueError("solo el brief va sin capitulo de origen, y el brief nunca lo lleva")
        return self


class StoredEvent(BaseModel):
    """Un evento ya en el registro, con su identificador.

    El `id` es el ultimo desempate del orden de proyeccion (RD-03), detras de
    `world_time` y `world_seq`. Es lo que hace que el orden sea total y que dos
    eventos en el mismo instante no dependan de como se lean.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    event: Event

    @property
    def sort_key(self) -> tuple[str, int, int]:
        return (self.event.world_time.stamp, self.event.world_time.seq, self.id)
