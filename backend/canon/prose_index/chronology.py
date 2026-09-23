"""La cronologia de la novela: una fila por escena congelada, en orden de mundo.

RF-242, RD-40, D-89. MUN-05. Es la vista SQL `chronology` sobre `prose_scene` y
`prose_scene_character`, creada en la migracion 5 (`canon/db/migrations.py`).
Proyeccion del indice de prosa: no guarda verdad propia, y por eso es una vista
y no una tabla, que no puede desincronizarse de lo que proyecta.

**Forma de la vista**, que lee el generador de Lean (RF-243)::

    chronology(
        scene_id      TEXT     -- prose_scene.id
        chapter       INTEGER  -- capitulo de la escena
        scene_number  INTEGER  -- numero de escena dentro del capitulo
        world_time    TEXT     -- instante de mundo, ISO 8601 (MUN-05)
        world_seq     INTEGER  -- desempate dentro del instante (D-07)
        place_entity  TEXT     -- entity.id del lugar; NULL si la escena no lo fija
        pov_entity    TEXT     -- entity.id del punto de vista
        present       TEXT     -- JSON: lista de entity.id presentes, POV incluido,
                               --       sin repetir y en orden de id
        summary       TEXT     -- resumen vigente de la escena
    )

Orden: `world_time, world_seq, chapter, scene_number`. Quien necesite el orden
garantizado lo pide con `ORDER BY`, como `read`: el de una vista lo respeta
SQLite, pero el estandar no lo promete.
"""

from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel, ConfigDict

from commons.types.primitives import WorldTime

#: Las columnas de la vista, en su orden.
COLUMNS = (
    "scene_id",
    "chapter",
    "scene_number",
    "world_time",
    "world_seq",
    "place_entity",
    "pov_entity",
    "present",
    "summary",
)

#: El cuerpo de la vista. La migracion 5 lo congela en `CREATE VIEW`; `read` lo
#: usa tal cual sobre un fichero que aun no se ha migrado, porque leer no migra.
#: No se edita: una vista distinta es una migracion nueva con su propio cuerpo,
#: o los ficheros ya migrados y los nuevos dirian cosas distintas.
SELECT = """
SELECT
    s.id            AS scene_id,
    s.chapter       AS chapter,
    s.scene_number  AS scene_number,
    s.world_time    AS world_time,
    s.world_seq     AS world_seq,
    s.place_entity  AS place_entity,
    s.pov_entity    AS pov_entity,
    (
        SELECT json_group_array(p.entity_id) FROM (
            SELECT s.pov_entity AS entity_id
            UNION
            SELECT c.entity_id FROM prose_scene_character c WHERE c.scene_id = s.id
            ORDER BY 1
        ) p
    )               AS present,
    s.summary       AS summary
FROM prose_scene s
ORDER BY s.world_time, s.world_seq, s.chapter, s.scene_number
"""


class ChronologyRow(BaseModel):
    """Una escena congelada vista como suceso: cuando, donde y con quien."""

    model_config = ConfigDict(frozen=True)

    scene_id: str
    chapter: int
    scene_number: int
    world_time: WorldTime
    place_entity: str | None
    pov_entity: str
    present: tuple[str, ...]
    summary: str


def _has_view(con: sqlite3.Connection) -> bool:
    return (
        con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'view' AND name = 'chronology'"
        ).fetchone()
        is not None
    )


_FROM_VIEW = (
    "SELECT scene_id, chapter, scene_number, world_time, world_seq, place_entity, "
    "pov_entity, present, summary FROM chronology "
    "ORDER BY world_time, world_seq, chapter, scene_number"
)


def read(con: sqlite3.Connection) -> list[ChronologyRow]:
    """La cronologia entera, en orden de mundo.

    Sin la vista, el mismo `SELECT` sobre las tablas: trae las columnas de
    `COLUMNS` en su orden y ya ordenado.
    """
    filas = con.execute(_FROM_VIEW if _has_view(con) else SELECT).fetchall()
    return [
        ChronologyRow(
            scene_id=r[0],
            chapter=r[1],
            scene_number=r[2],
            world_time=WorldTime(stamp=r[3], seq=r[4]),
            place_entity=r[5],
            pov_entity=r[6],
            present=tuple(json.loads(r[7])),
            summary=r[8],
        )
        for r in filas
    ]
