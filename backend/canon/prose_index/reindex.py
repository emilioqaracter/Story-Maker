"""Reindexar la prosa congelada con otros parametros de corte.

RF-124, RD-27. Cambiar el tamano de fragmento es reindexar la novela entera,
igual que cambiar el modelo de los vectores (RD-13): fragmentos de dos cortes
distintos no se comparan. Se hace sobre una **copia** del fichero cuando es una
medida (`evals/`), y sobre el fichero cuando es una decision tomada.

El texto de cada escena se reconstruye desde sus fragmentos: el corte solapa un
parrafo entre fragmentos consecutivos, asi que basta con no repetir el parrafo
que abre cada uno a partir del segundo.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from canon.db import connection
from canon.prose_index.chunk import chunk_scene, paragraphs
from commons.types.vectors import pack_vector


def scene_text_from_chunks(chunk_texts: Sequence[str]) -> str:
    """Deshace el solape: el primer parrafo de cada fragmento, salvo el primero,
    repite el ultimo del anterior."""
    out: list[str] = []
    for i, texto in enumerate(chunk_texts):
        parrafos = paragraphs(texto)
        if i > 0 and out and parrafos and parrafos[0] == out[-1]:
            parrafos = parrafos[1:]
        out.extend(parrafos)
    return "\n\n".join(out)


def scene_texts(con: sqlite3.Connection) -> dict[str, str]:
    rows = con.execute(
        "SELECT scene_id, text FROM prose_chunk ORDER BY scene_id, ordinal"
    ).fetchall()
    por_escena: dict[str, list[str]] = {}
    for r in rows:
        por_escena.setdefault(r["scene_id"], []).append(r["text"])
    return {sid: scene_text_from_chunks(ts) for sid, ts in por_escena.items()}


def write_params(
    con: sqlite3.Connection, *, chunk_tokens: int, fusion_k: int, quotas: Sequence[str]
) -> None:
    """RD-27. Con que parametros esta cortada e indexada esta novela."""
    con.execute(
        "INSERT INTO retrieval_params (id, chunk_tokens, fusion_k, quotas, updated_at) "
        "VALUES (1, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(id) DO UPDATE SET chunk_tokens=excluded.chunk_tokens, "
        "  fusion_k=excluded.fusion_k, quotas=excluded.quotas, updated_at=excluded.updated_at",
        (chunk_tokens, fusion_k, json.dumps(list(quotas))),
    )


def read_params(con: sqlite3.Connection) -> tuple[int, int, list[str]] | None:
    row = con.execute(
        "SELECT chunk_tokens, fusion_k, quotas FROM retrieval_params WHERE id = 1"
    ).fetchone()
    if row is None:
        return None
    return int(row["chunk_tokens"]), int(row["fusion_k"]), list(json.loads(row["quotas"]))


def reindex(
    path: Path,
    *,
    chunk_tokens: int,
    embed: object,
    fusion_k: int,
    quotas: Sequence[str] = (),
) -> int:
    """Recorta y revectoriza toda la prosa congelada. Devuelve cuantos fragmentos.

    Lo caro --los vectores-- fuera de la transaccion; borrar e insertar, dentro
    y todo junto o nada (RF-68 por analogia).
    """
    with connection.reader(path) as con:
        textos = scene_texts(con)

    nuevos = []
    for sid, texto in textos.items():
        nuevos.extend(chunk_scene(sid, texto, max_tokens=chunk_tokens))
    vectores = embed.embed([c.text for c in nuevos], is_query=False) if nuevos else []  # type: ignore[attr-defined]

    with connection.canon_writer(path) as con:
        con.execute("DELETE FROM prose_chunk_fts")
        con.execute("DELETE FROM prose_chunk")
        for chunk, vec in zip(nuevos, vectores, strict=True):
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
        write_params(con, chunk_tokens=chunk_tokens, fusion_k=fusion_k, quotas=quotas)
    return len(nuevos)
