"""Las dos piernas que se fusionan: lexica y semantica.

RF-75, RF-76, RF-78. De las cuatro consultas que hace el Documentalista, solo
estas dos producen **fragmentos** y solo estas dos se fusionan. Las otras dos
--la estructurada al canon y la del grafo-- producen **hechos** y van directas a
sus bloques del paquete.

Fusionar fichas de canon con fragmentos de prosa seria comparar cosas que no se
comparan, y ademas pondria en riesgo la separacion entre lo que es verdad y lo
que solo se escribio una vez.

Las dos piernas **filtran por metadatos antes de puntuar**. Eso es lo que hace
barata la consulta: en vez de puntuar los 1.200 fragmentos de la obra, se
descartan por capitulo, lugar o instante y se puntua el resto, que es un punado.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from commons.types.vectors import cosine, unpack_vector
from context.query.build import RetrievalRequest

#: Cuantos fragmentos devuelve cada pierna antes de fusionar. Mas que los cupos
#: a proposito: la fusion necesita margen para que aparecer en las dos listas
#: signifique algo, y con listas de cinco casi todo coincide.
LEG_SIZE = 30


def _filter_clause(req: RetrievalRequest) -> tuple[str, list[object]]:
    """Filtro por metadatos, comun a las dos piernas."""
    where: list[str] = ["1=1"]
    params: list[object] = []

    if req.before is not None:
        where.append("(s.world_time, s.world_seq) < (?, ?)")
        params += [req.before.stamp, req.before.seq]

    if req.excluded_scenes:
        marks = ",".join("?" * len(req.excluded_scenes))
        where.append(f"s.id NOT IN ({marks})")
        params += sorted(req.excluded_scenes)

    return " AND ".join(where), params


def lexical(con: sqlite3.Connection, req: RetrievalRequest, *, limit: int = LEG_SIZE) -> list[str]:
    """Pierna lexica: FTS5 con BM25.

    Es la unica que acierta con nombres propios, y por eso sus terminos salen de
    la tabla de alias y no de un modelo: la tabla dice exactamente como se ha
    llamado a esa persona en la obra.
    """
    if not req.lexical_terms:
        return []

    # FTS5 con OR entre terminos entrecomillados: los nombres compuestos tienen
    # que buscarse enteros, o "Marcos Vela" encontraria cualquier Marcos.
    match = " OR ".join(f'"{t}"' for t in req.lexical_terms if t.strip())
    if not match:
        return []

    clause, params = _filter_clause(req)
    rows = con.execute(
        f"""
        SELECT c.id AS id
          FROM prose_chunk_fts f
          JOIN prose_chunk c ON c.rowid = f.rowid
          JOIN prose_scene s ON s.id = c.scene_id
         WHERE prose_chunk_fts MATCH ? AND {clause}
         ORDER BY bm25(prose_chunk_fts)
         LIMIT ?
        """,  # nosec B608
        [match, *params, limit],
    ).fetchall()
    return [r["id"] for r in rows]


def semantic(
    con: sqlite3.Connection,
    req: RetrievalRequest,
    query_vector: Sequence[float] | None,
    *,
    limit: int = LEG_SIZE,
) -> list[str]:
    """Pierna semantica: coseno sobre los vectores de fragmento.

    Es la unica que encuentra una escena espejo que no comparte ni una palabra
    con la consulta.

    Devuelve vacio si no hay vector de consulta o si los fragmentos no tienen
    vector comparable. **No aplica el fallo cerrado**: la recuperacion no es una
    comprobacion, asi que se degrada a una sola pierna y se marca (RF-78).
    """
    if query_vector is None:
        return []

    clause, params = _filter_clause(req)
    rows = con.execute(
        f"""
        SELECT c.id AS id, c.vector AS vector, c.vector_dim AS dim
          FROM prose_chunk c JOIN prose_scene s ON s.id = c.scene_id
         WHERE c.vector IS NOT NULL AND {clause}
        """,  # nosec B608
        params,
    ).fetchall()

    dim = len(query_vector)
    puntuados: list[tuple[float, str]] = []
    for row in rows:
        # Vectores de otra dimension no se comparan: mezclarlos daria numeros
        # sin significado, y es un error facil de cometer con un modelo local
        # porque cambiarlo es sustituir un fichero.
        if row["dim"] != dim:
            continue
        puntuados.append((cosine(query_vector, unpack_vector(row["vector"])), row["id"]))

    puntuados.sort(key=lambda pair: (-pair[0], pair[1]))
    return [chunk_id for _score, chunk_id in puntuados[:limit]]
