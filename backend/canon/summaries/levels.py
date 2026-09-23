"""Cuando se regenera cada nivel de resumen, y como se escribe.

RF-116, RF-117, RF-120, RD-23, CTX-06. `architecture.md` §4.5:

- **Escena y capitulo**: al congelar el capitulo.
- **Arco**: al congelar el capitulo que lo cierra. Que arcos cierra un capitulo
  lo sabe `planning/outline/arcs.py`, porque es una lectura de la escaleta.
- **Obra**: cada 5 capitulos congelados.

Todo se genera fuera de la transaccion y se escribe dentro (RF-68, RF-120). La
version vigente vive en `summary`; todas las versiones, en `summary_version`,
porque ninguna se sobrescribe (RF-10 por analogia).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

#: `architecture.md` §4.5: el resumen de obra se regenera cada 5 capitulos.
WORK_SUMMARY_EVERY = 5


class SummaryToWrite(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: str = Field(pattern="^(scene|chapter|arc|work)$")
    ref_id: str = Field(min_length=1)
    body: str = Field(min_length=1)
    covers_to: int | None = None


def work_due(chapter: int) -> bool:
    """RF-117. Cada 5 capitulos congelados."""
    return chapter % WORK_SUMMARY_EVERY == 0


def chapter_summaries(con: sqlite3.Connection, chapters: Sequence[int]) -> list[str]:
    if not chapters:
        return []
    marks = ",".join("?" * len(chapters))
    rows = con.execute(
        f"SELECT body FROM summary WHERE level = 'chapter' AND ref_id IN ({marks}) "  # nosec B608
        "ORDER BY CAST(ref_id AS INTEGER)",
        [str(c) for c in chapters],
    ).fetchall()
    return [r["body"] for r in rows]


def arc_summaries(con: sqlite3.Connection) -> list[str]:
    rows = con.execute("SELECT body FROM summary WHERE level = 'arc' ORDER BY ref_id").fetchall()
    return [r["body"] for r in rows]


def write(con: sqlite3.Connection, summaries: Sequence[SummaryToWrite]) -> None:
    """Escribe la vigente y guarda la version. Dentro de la transaccion."""
    for s in summaries:
        con.execute(
            "INSERT OR REPLACE INTO summary (level, ref_id, parent_ref, body, updated_at) "
            "VALUES (?, ?, NULL, ?, datetime('now'))",
            (s.level, s.ref_id, s.body),
        )
        row = con.execute(
            "SELECT coalesce(max(version), 0) AS v FROM summary_version WHERE level = ? AND ref_id = ?",
            (s.level, s.ref_id),
        ).fetchone()
        con.execute(
            "INSERT INTO summary_version (level, ref_id, version, covers_to, body, created_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            (s.level, s.ref_id, int(row["v"]) + 1, s.covers_to, s.body),
        )
