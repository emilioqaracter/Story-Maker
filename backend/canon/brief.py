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

from canon import brief_rules
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
from commons.types import rubrics
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


class Recipient(BaseModel):
    """RF-200. Para quien es la novela: una entidad del brief, con lo que la entrevista recogio."""

    model_config = ConfigDict(frozen=True)

    entity_id: str = Field(min_length=1)
    age: int = Field(ge=0, le=120)
    traits: tuple[str, ...] = Field(default_factory=tuple)
    memories: tuple[str, ...] = Field(default_factory=tuple)
    role: str = Field(min_length=1, description="Papel en la historia")


class Brief(BaseModel):
    """El encargo de la obra.

    `start` es el instante en que arranca el mundo: todo lo que el brief
    establece es cierto desde ahi, y nada anterior existe.

    Lo que va despues de `word_tolerance` lo trae la entrevista (RF-200). Es
    opcional para que un brief escrito a mano, sin destinatario, siga valiendo.
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
    genre: str = ""
    tone: str = ""
    dedication: str = ""
    recipient: Recipient | None = None
    forbidden_words: tuple[str, ...] = Field(default_factory=tuple)
    forbidden_themes: tuple[str, ...] = Field(default_factory=tuple)

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
        if self.recipient is not None and self.recipient.entity_id not in known:
            raise ValueError(
                f"el destinatario {self.recipient.entity_id!r} no es una entidad del brief"
            )
        # RF-201, `srs-frontend-v1.md` RI-41: un brief contradictorio no se carga.
        encontradas = self.contradictions()
        if encontradas:
            raise ValueError("el brief se contradice: " + " ".join(c.message for c in encontradas))
        return self

    def contradictions(self) -> list[brief_rules.Contradiction]:
        return brief_rules.contradictions(
            age=self.recipient.age if self.recipient else None,
            genre=self.genre,
            tone=self.tone,
            title=self.title,
            dedication=self.dedication,
            names=[e.name for e in self.entities],
            forbidden_words=self.forbidden_words,
            forbidden_themes=self.forbidden_themes,
        )

    def recipient_name(self) -> str:
        if self.recipient is None:
            return ""
        return next((e.name for e in self.entities if e.id == self.recipient.entity_id), "")

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
    # El brief entero tambien, por la misma puerta: es lo que la ruta de
    # arranque (RI-02) necesita para componer el motor sin que nadie lo pase.
    add(DocumentVersion(doc_kind="brief", body=brief.model_dump_json()), anchor)
    # RNF-37. Las rubricas del Jurado son datos del fichero, no constantes del
    # juez: cambiar una es un despliegue (RF-157), y entra por la misma puerta.
    add(DocumentVersion(doc_kind="rubrics", body=rubrics.dumps(rubrics.DEFAULT_RUBRICS)), anchor)

    return events


def load_brief(path: Path) -> Brief:
    """El brief con el que se creo la novela, desde su version en el canon."""
    with connection.reader(path) as con:
        row = con.execute(
            "SELECT body FROM document_version WHERE doc_kind = 'brief' "
            "ORDER BY version DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise ValueError(f"la novela {path.name} no guarda su brief")
    return Brief.model_validate_json(row["body"])


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
        # RF-202. Lo que quien encarga prohibio entra como proscrito desde la
        # primera escena, y `check.repetition` lo detecta sin modelo (POE-12).
        for word in brief.forbidden_words:
            if word.strip():
                con.execute(
                    "INSERT OR IGNORE INTO proscribed (term, kind, added_chapter, added_at) "
                    "VALUES (?, 'brief', 0, datetime('now'))",
                    (word.strip().lower(),),
                )
    return len(events)
