"""De identificadores de fragmento a candidatos con lo que hace falta para decidir su cupo.

RF-79, RF-80. La fusion devuelve identificadores ordenados; los cupos necesitan
saber de cada fragmento donde ocurre, quien lo cuenta, si tiene dialogo, que
promesas planta y a quien nombra. Todo eso es canon y prosa congelada, asi que
se lee del fichero con la conexion de lectura, en bloque, y sin llamar a nada.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence

from context.retrieval.quotas import Candidate

#: Marcas de dialogo en espanol: raya, guion largo al inicio de linea, comillas
#: angulares. Basta con que aparezca una para que el fragmento cuente como voz.
_DIALOGUE_MARKS = ("—", "«", "»", "\n-", "\n–")  # noqa: RUF001


def has_dialogue(text: str) -> bool:
    return any(m in text for m in _DIALOGUE_MARKS) or text.lstrip().startswith("-")


def load(
    con: sqlite3.Connection,
    chunk_ids: Sequence[str],
    *,
    estimate: Callable[[str], int],
    setups_by_scene: Mapping[str, Sequence[str]] | None = None,
) -> list[Candidate]:
    """Construye los candidatos en el orden en que llegan los identificadores.

    `setups_by_scene` dice que promesas planta cada escena; viene de la escaleta,
    que es quien lo sabe. `estimate` es el contador de `commons/`: el coste de
    cada fragmento entra ya con factor, porque es lo que el presupuesto compara.
    """
    if not chunk_ids:
        return []
    setups_by_scene = setups_by_scene or {}

    marks = ",".join("?" * len(chunk_ids))
    rows = con.execute(
        f"""
        SELECT c.id AS id, c.text AS text, s.id AS scene_id, s.chapter AS chapter,
               s.place_entity AS place, s.pov_entity AS pov, s.function AS function,
               s.summary AS summary
          FROM prose_chunk c JOIN prose_scene s ON s.id = c.scene_id
         WHERE c.id IN ({marks})
        """,  # nosec B608
        list(chunk_ids),
    ).fetchall()
    por_id = {r["id"]: r for r in rows}

    escenas = {r["scene_id"] for r in rows}
    presentes: dict[str, set[str]] = {}
    if escenas:
        marks = ",".join("?" * len(escenas))
        for r in con.execute(
            f"SELECT scene_id, entity_id FROM prose_scene_character WHERE scene_id IN ({marks})",  # nosec B608
            sorted(escenas),
        ):
            presentes.setdefault(r["scene_id"], set()).add(r["entity_id"])

    out: list[Candidate] = []
    for cid in chunk_ids:
        r = por_id.get(cid)
        if r is None:
            continue
        out.append(
            Candidate(
                chunk_id=cid,
                scene_id=r["scene_id"],
                chapter=r["chapter"],
                text=r["text"],
                tokens=max(1, estimate(r["text"])),
                place=r["place"],
                pov=r["pov"],
                function=r["function"],
                has_dialogue=has_dialogue(r["text"]),
                plants_setup=tuple(setups_by_scene.get(r["scene_id"], ())),
                entities=frozenset(presentes.get(r["scene_id"], set())),
                summary=r["summary"] or "",
            )
        )
    return out
