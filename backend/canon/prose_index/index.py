"""Escritura del indice de prosa, dos niveles.

RF-12, RD-06, RD-15, RD-16. Una fila por escena congelada con su resumen y el
vector de ese resumen, y filas de fragmento dentro de cada escena.

**Solo entra prosa congelada** (RF-71). Ni siquiera marcada como provisional: si
entrara, la recuperacion de la escena siguiente podria traer texto que aun puede
desaparecer, que es el camino directo al envenenamiento de contexto.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from commons.types.vectors import pack_vector

if TYPE_CHECKING:
    from canon.freeze.freeze import PreparedChapter


def write_index(con: sqlite3.Connection, prepared: PreparedChapter) -> None:
    """Inserta escenas y fragmentos con sus vectores. Dentro de la transaccion."""
    vec_por_escena = {
        s.id: v for s, v in zip(prepared.scenes, prepared.scene_vectors, strict=False)
    }

    for scene in prepared.scenes:
        vec = vec_por_escena.get(scene.id)
        con.execute(
            "INSERT OR REPLACE INTO prose_scene "
            "(id, chapter, scene_number, pov_entity, place_entity, world_time, "
            " world_seq, function, summary, vector, vector_model, vector_dim) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                scene.id,
                scene.chapter,
                scene.scene_number,
                scene.pov_entity,
                scene.place_entity,
                scene.world_time.stamp,
                scene.world_time.seq,
                scene.function,
                scene.summary,
                pack_vector(vec.values) if vec else None,
                vec.model_id if vec else None,
                vec.dimension if vec else None,
            ),
        )
        con.executemany(
            "INSERT OR IGNORE INTO prose_scene_character (scene_id, entity_id) VALUES (?,?)",
            [(scene.id, e) for e in scene.present],
        )

    vec_por_frag = {c.id: v for c, v in zip(prepared.chunks, prepared.chunk_vectors, strict=False)}
    for chunk in prepared.chunks:
        vec = vec_por_frag.get(chunk.id)
        con.execute(
            "INSERT OR REPLACE INTO prose_chunk "
            "(id, scene_id, ordinal, text, vector, vector_model, vector_dim) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                chunk.id,
                chunk.scene_id,
                chunk.ordinal,
                chunk.text,
                pack_vector(vec.values) if vec else None,
                vec.model_id if vec else None,
                vec.dimension if vec else None,
            ),
        )
        # La tabla lexica es externa: se alimenta desde la de fragmentos para no
        # duplicar el texto en el fichero.
        con.execute(
            "INSERT INTO prose_chunk_fts (rowid, text) "
            "SELECT rowid, text FROM prose_chunk WHERE id = ?",
            (chunk.id,),
        )
