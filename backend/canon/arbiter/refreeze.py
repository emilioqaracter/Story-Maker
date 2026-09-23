"""Recongelacion atomica de escenas tras un retcon.

RF-153, RD-24, RD-25, RNF-30. Igual que la congelacion, en dos mitades:

**Fuera de la transaccion**: cortar las escenas reescritas y calcular sus
vectores. **Dentro, todo junto o nada**: reemplazar sus filas de indice y su
entrada lexica, su resumen y el de su capitulo, anadir el evento que termina la
vigencia del hecho anterior, reconstruir las proyecciones y registrar el
retcon. Una caida a mitad deja la escena anterior intacta y el retcon sin
aplicar.

Se reconstruye entero en vez de aplicar el evento suelto porque el retcon
escribe en un instante ya proyectado, y la aplicacion incremental solo vale
hacia delante (`projections.rebuild.apply_all`).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from canon.arbiter.retcon import RetconPlan
from canon.events import log
from canon.events.types import Event
from canon.projections import rebuild
from canon.prose_index.chunk import Chunk, chunk_scene
from canon.summaries import levels
from commons.provider.port import Embedding
from commons.types.vectors import pack_vector


class RefrozenScene(BaseModel):
    model_config = ConfigDict(frozen=True)

    scene_id: str
    text: str
    summary: str


class PreparedRefreeze(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenes: tuple[RefrozenScene, ...]
    chunks: tuple[Chunk, ...]
    vectors: tuple[Embedding, ...]
    summary_vectors: tuple[Embedding, ...]


def prepare(scenes: Sequence[RefrozenScene], *, embed: object) -> PreparedRefreeze:
    """Lo caro, fuera de la transaccion."""
    chunks = [c for s in scenes for c in chunk_scene(s.scene_id, s.text)]
    vecs = embed.embed([c.text for c in chunks], is_query=False) if chunks else []  # type: ignore[attr-defined]
    svecs = embed.embed([s.summary for s in scenes], is_query=False) if scenes else []  # type: ignore[attr-defined]
    return PreparedRefreeze(
        scenes=tuple(scenes),
        chunks=tuple(chunks),
        vectors=tuple(vecs),
        summary_vectors=tuple(svecs),
    )


def commit(
    con: sqlite3.Connection,
    prepared: PreparedRefreeze,
    *,
    retcon: RetconPlan,
    event: Event,
    chapter_summaries: Mapping[int, str],
    rule: str,
    chapter_origin: int,
) -> None:
    """Todo junto o nada. Quien llama abre la transaccion con `canon_writer`."""
    ids = [s.scene_id for s in prepared.scenes]
    marks = ",".join("?" * len(ids))
    con.execute(
        f"DELETE FROM prose_chunk_fts WHERE rowid IN (SELECT rowid FROM prose_chunk WHERE scene_id IN ({marks}))",  # nosec B608
        ids,
    )
    con.execute(f"DELETE FROM prose_chunk WHERE scene_id IN ({marks})", ids)  # nosec B608

    for chunk, vec in zip(prepared.chunks, prepared.vectors, strict=True):
        con.execute(
            "INSERT INTO prose_chunk (id, scene_id, ordinal, text, vector, vector_model, vector_dim) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                chunk.id,
                chunk.scene_id,
                chunk.ordinal,
                chunk.text,
                pack_vector(vec.values),
                vec.model_id,
                vec.dimension,
            ),
        )
        con.execute(
            "INSERT INTO prose_chunk_fts (rowid, text) SELECT rowid, text FROM prose_chunk WHERE id = ?",
            (chunk.id,),
        )
    for escena, vec in zip(prepared.scenes, prepared.summary_vectors, strict=True):
        con.execute(
            "UPDATE prose_scene SET summary = ?, vector = ?, vector_model = ?, vector_dim = ? WHERE id = ?",
            (escena.summary, pack_vector(vec.values), vec.model_id, vec.dimension, escena.scene_id),
        )
        con.execute(
            "INSERT OR REPLACE INTO summary (level, ref_id, parent_ref, body, updated_at) "
            "SELECT 'scene', id, CAST(chapter AS TEXT), ?, datetime('now') FROM prose_scene WHERE id = ?",
            (escena.summary, escena.scene_id),
        )
    # El resumen de capitulo se regenera y se versiona como cualquier otro
    # (RD-23): la version anterior queda, que es lo que hace el retcon auditable.
    levels.write(
        con,
        [
            levels.SummaryToWrite(level="chapter", ref_id=str(c), body=cuerpo, covers_to=c)
            for c, cuerpo in chapter_summaries.items()
        ],
    )
    # Los veredictos del Jurado citaban el texto viejo, con sus posiciones: una
    # cita que ya no esta no es evidencia (AGENTS.md §5.3.5). Se retiran; la
    # muestra modelica deja de elegir esas escenas hasta que se vuelvan a juzgar.
    con.execute(f"DELETE FROM scene_verdict WHERE scene_id IN ({marks})", ids)  # nosec B608

    [event_id] = log.append(con, [event])
    rebuild.rebuild(con)
    con.execute(
        "INSERT INTO retcon (fact_key, previous_value, new_value, event_ids, refrozen_scenes, rule, "
        "chapter_origin, created_at) VALUES (?,?,?,?,?,?,?, datetime('now'))",
        (
            retcon.fact_key,
            retcon.previous_value,
            retcon.new_value,
            json.dumps([event_id]),
            json.dumps(ids),
            rule,
            chapter_origin,
        ),
    )


def read_retcons(con: sqlite3.Connection) -> list[dict[str, object]]:
    rows = con.execute("SELECT * FROM retcon ORDER BY id").fetchall()
    return [
        {
            "fact_key": r["fact_key"],
            "previous_value": r["previous_value"],
            "new_value": r["new_value"],
            "event_ids": json.loads(r["event_ids"]),
            "refrozen_scenes": json.loads(r["refrozen_scenes"]),
            "rule": r["rule"],
            "chapter_origin": r["chapter_origin"],
        }
        for r in rows
    ]
