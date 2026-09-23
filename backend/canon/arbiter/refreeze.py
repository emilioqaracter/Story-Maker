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

**Toda recongelacion conserva lo que ven las versiones anteriores** (RD-34,
PRO-08). Antes de reemplazar una escena, su texto vigente se guarda en
`scene_text_history` para la ultima version que ya no es la vigente, si esa
version no tiene ya uno guardado. La enmienda lo guarda ella misma, para la
version que deja de ser vigente, y aqui no se anade nada; el retcon del Arbitro
no crea version, y sin esto reescribiria la version 1 despues de publicada la 2:
el contraejemplo B2 de `orchestration/model/README.md` §7.1.
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
from canon.prose_index import usage
from canon.prose_index.chunk import Chunk, chunk_scene
from canon.prose_index.reindex import scene_text_from_chunks
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
    antes = usage.vigente(con)
    _keep_history(con, ids)
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
    # RF-241. Recongelar reescribe las filas de las escenas recongeladas; el
    # valor que el evento deja de hacer vigente pierde las suyas.
    usage.refresh(con, scenes=ids, before=antes)


def _keep_history(con: sqlite3.Connection, scene_ids: Sequence[str]) -> None:
    """RD-34. El texto que las versiones no vigentes siguen viendo, antes de tocarlo.

    Con la version `v` vigente, una version anterior lee de la escena la fila de
    historia de menor `until_version >= version` o, sin ninguna, el texto
    vigente (`manuscript.text_at`). Si ninguna fila llega a `v - 1`, la version
    `v - 1` y las que la siguen sin fila propia estan leyendo el texto vigente, y
    reemplazarlo las cambiaria: se guarda hasta `v - 1`. Con la version 1 vigente
    no hay version anterior que proteger, y una escena de un capitulo congelado
    despues de crearse la `v` no esta en ninguna anterior (`manuscript.chapters_in`).
    """
    row = con.execute(
        "SELECT version, max_chapter FROM manuscript_version ORDER BY version DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return
    vigente, ultimo = int(row["version"]), int(row["max_chapter"])
    capitulo_de = {
        r["id"]: int(r["chapter"]) for r in con.execute("SELECT id, chapter FROM prose_scene")
    }
    for sid in scene_ids:
        if capitulo_de.get(sid, ultimo + 1) > ultimo:
            continue
        cubierta = con.execute(
            "SELECT 1 FROM scene_text_history WHERE scene_id = ? AND until_version >= ?",
            (sid, vigente - 1),
        ).fetchone()
        if cubierta is not None:
            continue
        trozos = [
            r["text"]
            for r in con.execute(
                "SELECT text FROM prose_chunk WHERE scene_id = ? ORDER BY ordinal", (sid,)
            )
        ]
        con.execute(
            "INSERT INTO scene_text_history (scene_id, until_version, text) VALUES (?, ?, ?)",
            (sid, vigente - 1, scene_text_from_chunks(trozos)),
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
