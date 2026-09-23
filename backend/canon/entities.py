"""Entidades y su ficha, para quien lee la novela.

RF-207, RF-208. `specs/srs-backend-v3.md` §4.2. Proyeccion del canon vigente
(D-58 del frontend): lo que tiene vigencia abierta. Nunca el registro de eventos
en crudo (`architecture.md` §2.2): la procedencia de un hecho sale del evento
que lo establecio, pero lo que se sirve es la ficha.
"""

from __future__ import annotations

import sqlite3

from pydantic import BaseModel, ConfigDict, Field

from canon.skills.read import EntityCard, query
from commons.types.primitives import WorldTime

#: RI-45. Los tipos por los que se puede filtrar: PER-01, MUN-01, MUN-03, MUN-02.
KINDS = ("person", "place", "institution", "object")


class EntitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_id: str
    kind: str
    name: str
    aliases: tuple[str, ...]
    chapters: tuple[int, ...] = Field(description="Capitulos congelados donde aparece")


class Fact(BaseModel):
    model_config = ConfigDict(frozen=True)

    attribute: str
    value: str
    provenance: str = Field(description="MET-09: brief, prose, derived o arbitration")
    valid_from: str


class EntityRelation(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    other_id: str
    other_name: str
    direction: str = Field(description="out si la entidad es el origen, in si es el destino")
    valid_from: str
    valid_to: str | None = None


class Appearance(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapter: int
    scene_id: str
    scene_number: int
    roles: tuple[str, ...] = Field(description="pov, place, cast")


class EntityFile(BaseModel):
    """RI-46. La ficha de una entidad."""

    model_config = ConfigDict(frozen=True)

    entity: EntitySummary
    card: EntityCard = Field(description="Ficha compacta, CTX-05")
    facts: tuple[Fact, ...]
    relations: tuple[EntityRelation, ...]
    appearances: tuple[Appearance, ...]


def _appearances(con: sqlite3.Connection, entity_id: str) -> list[Appearance]:
    rows = con.execute(
        "SELECT s.id, s.chapter, s.scene_number, s.pov_entity, s.place_entity, "
        "       EXISTS (SELECT 1 FROM prose_scene_character c WHERE c.scene_id = s.id AND c.entity_id = :e) AS cast_ "
        "  FROM prose_scene s "
        " WHERE s.pov_entity = :e OR s.place_entity = :e "
        "    OR EXISTS (SELECT 1 FROM prose_scene_character c WHERE c.scene_id = s.id AND c.entity_id = :e) "
        " ORDER BY s.chapter, s.scene_number",
        {"e": entity_id},
    ).fetchall()
    out = []
    for r in rows:
        roles = [
            name
            for name, on in (
                ("pov", r["pov_entity"] == entity_id),
                ("place", r["place_entity"] == entity_id),
                ("cast", bool(r["cast_"])),
            )
            if on
        ]
        out.append(
            Appearance(
                chapter=r["chapter"],
                scene_id=r["id"],
                scene_number=r["scene_number"],
                roles=tuple(roles),
            )
        )
    return out


def _summary(con: sqlite3.Connection, row: sqlite3.Row) -> EntitySummary:
    aliases = tuple(
        r["alias"]
        for r in con.execute(
            "SELECT alias FROM entity_alias WHERE entity_id = ? AND valid_to IS NULL ORDER BY alias",
            (row["id"],),
        )
    )
    chapters = tuple(sorted({a.chapter for a in _appearances(con, row["id"])}))
    return EntitySummary(
        entity_id=row["id"], kind=row["kind"], name=row["name"], aliases=aliases, chapters=chapters
    )


def list_entities(con: sqlite3.Connection, kind: str | None = None) -> list[EntitySummary]:
    """RF-207."""
    rows = (
        con.execute(
            "SELECT id, kind, name FROM entity WHERE kind = ? ORDER BY name", (kind,)
        ).fetchall()
        if kind
        else con.execute("SELECT id, kind, name FROM entity ORDER BY name").fetchall()
    )
    return [_summary(con, r) for r in rows]


def _latest_instant(con: sqlite3.Connection) -> WorldTime:
    row = con.execute("SELECT max(world_time) AS t FROM event").fetchone()
    return WorldTime(stamp=row["t"] or "0001-01-01")


def entity_file(con: sqlite3.Connection, entity_id: str) -> EntityFile | None:
    """RF-208. `None` si la entidad no existe."""
    row = con.execute("SELECT id, kind, name FROM entity WHERE id = ?", (entity_id,)).fetchone()
    if row is None:
        return None
    facts = tuple(
        Fact(
            attribute=r["name"],
            value=r["value"],
            provenance=r["provenance"],
            valid_from=r["valid_from"],
        )
        for r in con.execute(
            "SELECT a.name, a.value, a.valid_from, e.provenance FROM attribute a "
            "JOIN event e ON e.id = a.source_event WHERE a.entity_id = ? AND a.valid_to IS NULL ORDER BY a.name",
            (entity_id,),
        )
    )
    relations = tuple(
        EntityRelation(
            kind=r["kind"],
            other_id=r["other"],
            other_name=r["other_name"],
            direction=r["direction"],
            valid_from=r["valid_from"],
            valid_to=r["valid_to"],
        )
        for r in con.execute(
            "SELECT r.kind, r.target_id AS other, t.name AS other_name, 'out' AS direction, r.valid_from, r.valid_to "
            "  FROM relation r JOIN entity t ON t.id = r.target_id WHERE r.source_id = :e AND r.valid_to IS NULL "
            "UNION ALL "
            "SELECT r.kind, r.source_id, s.name, 'in', r.valid_from, r.valid_to "
            "  FROM relation r JOIN entity s ON s.id = r.source_id WHERE r.target_id = :e AND r.valid_to IS NULL "
            "ORDER BY 1, 3",
            {"e": entity_id},
        )
    )
    [card] = query(con, [entity_id], at=_latest_instant(con))
    return EntityFile(
        entity=_summary(con, row),
        card=card,
        facts=facts,
        relations=relations,
        appearances=tuple(_appearances(con, entity_id)),
    )
