"""Carga del brief como eventos.

RF-11, D-09. El brief **no se guarda como documento**: se descompone en eventos
con procedencia `brief` y sin capitulo de origen. Desde la primera fila el canon
ya es una proyeccion, sin casos especiales.

Esta es la unica escritura de canon fuera de la congelacion, y vive aqui porque
`canon/` es el dueno de los almacenes y la unica carpeta desde la que se importa
la conexion de escritura.

El brief llega **ya estructurado**, con sus entidades identificadas: convertir
texto libre a estructura es trabajo de modelo y en la version 1 nadie lo ha
presupuestado.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from canon.db import connection
from canon.events import log
from canon.events.types import (
    AliasAdded,
    AttributeSet,
    CompetenceSet,
    DocumentVersion,
    EntityCreated,
    Event,
    RelationSet,
)
from canon.projections import rebuild
from commons.types.primitives import Provenance, WorldTime


class BriefEntity(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1, description="person | place | institution | object")
    name: str = Field(min_length=1)
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    attributes: tuple[tuple[str, str], ...] = Field(default_factory=tuple)
    competences: tuple[tuple[str, str], ...] = Field(default_factory=tuple)


class BriefRelation(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    kind: str = Field(min_length=1)


class Brief(BaseModel):
    """El encargo de la obra.

    `start` es el instante en que arranca el mundo: todo lo que el brief
    establece es cierto desde ahi, y nada anterior existe.
    """

    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    start: WorldTime
    entities: tuple[BriefEntity, ...]
    relations: tuple[BriefRelation, ...] = Field(default_factory=tuple)
    style_guide: str = Field(min_length=1, description="POE-06")
    rulebook: str = Field(default="", description="DEP-02, vacio si no es deportiva")
    target_words: int = Field(gt=0)
    word_tolerance: float = Field(default=0.1, gt=0, lt=1)

    @model_validator(mode="after")
    def _relations_point_somewhere(self) -> Self:
        known = {e.id for e in self.entities}
        for rel in self.relations:
            missing = {rel.source, rel.target} - known
            if missing:
                raise ValueError(
                    f"la relacion {rel.kind!r} apunta a entidades que el brief no "
                    f"declara: {sorted(missing)}"
                )
        if len(known) != len(self.entities):
            raise ValueError("hay identificadores de entidad repetidos en el brief")
        return self

    def word_range(self) -> tuple[int, int]:
        """Rango de longitud aceptable de la obra.

        Lo consulta la condicion de cierre: una novela dentro de rango es una de
        las cuatro cosas que tienen que cumplirse para dar la obra por terminada.
        """
        margin = int(self.target_words * self.word_tolerance)
        return (self.target_words - margin, self.target_words + margin)


def to_events(brief: Brief) -> list[Event]:
    """Descompone el brief en eventos.

    Todos con procedencia `brief` y sin capitulo de origen, que es la unica
    combinacion que el esquema acepta para esta procedencia.

    El `seq` crece a lo largo de la carga y no se reinicia por entidad: dos
    eventos del brief en el mismo instante y con el mismo `seq` sobre el mismo
    atributo harian que el orden de carga decidiera el resultado, que es la
    ambiguedad que la prueba deterministica de las proyecciones deja fijada.
    """
    events: list[Event] = []
    seq = 0

    def at() -> WorldTime:
        nonlocal seq
        t = WorldTime(stamp=brief.start.stamp, seq=seq)
        seq += 1
        return t

    def add(payload: object, entities: set[str]) -> None:
        events.append(
            Event(
                world_time=at(),
                payload=payload,  # type: ignore[arg-type]
                provenance=Provenance.BRIEF,
                chapter_origin=None,
                entities=frozenset(entities),
            )
        )

    # Las entidades primero y enteras: una relacion o un atributo sobre algo
    # que todavia no existe rompe la clave ajena al proyectar.
    for ent in brief.entities:
        add(EntityCreated(entity_id=ent.id, kind=ent.kind, name=ent.name), {ent.id})

    for ent in brief.entities:
        for alias in ent.aliases:
            add(AliasAdded(entity_id=ent.id, alias=alias), {ent.id})
        for name, value in ent.attributes:
            add(AttributeSet(entity_id=ent.id, name=name, value=value), {ent.id})
        for name, level in ent.competences:
            add(CompetenceSet(entity_id=ent.id, name=name, level=level), {ent.id})

    for rel in brief.relations:
        add(
            RelationSet(source_id=rel.source, target_id=rel.target, kind=rel.kind),
            {rel.source, rel.target},
        )

    # La guia de estilo y el reglamento entran por el registro y se proyectan a
    # versiones (D-08), en vez de vivir en una tabla aparte: asi el canon
    # estructurado sigue siendo proyeccion pura.
    anchor = {brief.entities[0].id}
    add(DocumentVersion(doc_kind="style_guide", body=brief.style_guide), anchor)
    if brief.rulebook:
        add(DocumentVersion(doc_kind="rulebook", body=brief.rulebook), anchor)

    return events


def create_novel(path: Path, brief: Brief) -> int:
    """Crea el fichero de la novela y carga el brief. Devuelve cuantos eventos.

    Todo dentro de una transaccion: un brief a medias dejaria una novela con
    entidades sin relaciones y nadie sabria que falta.
    """
    connection.create(path)
    events = to_events(brief)
    with connection.canon_writer(path) as con:
        log.append(con, events)
        rebuild.rebuild(con)
    return len(events)
