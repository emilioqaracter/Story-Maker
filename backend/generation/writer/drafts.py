"""Borradores de escena en memoria de trabajo.

RD-07, RD-18, RF-20, PRO-13. `generation/` es quien produce el estado
"borrador", asi que es quien lo escribe, con la fabrica de memoria de trabajo
de `commons/db` y nunca con la de canon.

Sirve para dos cosas y ninguna es "guardar por si acaso": la reanudacion lee
de aqui las escenas ya cerradas del capitulo en curso (RF-20), y el paquete del
Escritor lee de aqui la prosa literal de la escena anterior cuando esta todavia
no esta congelada (§4.3, bloque 6). Al congelar, la purga lo vacia (PRO-I1).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from commons.db.working_memory import working_memory_writer


class Draft(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapter: int
    scene_number: int
    attempt: int
    text: str


def save_draft(path: Path, *, chapter: int, scene_number: int, attempt: int, text: str) -> None:
    """Guarda el borrador de una escena que paso su puerta. Sustituye al anterior."""
    with working_memory_writer(path) as wm:
        wm.execute(
            "DELETE FROM wm_draft WHERE chapter = ? AND scene_number = ?", (chapter, scene_number)
        )
        wm.execute(
            "INSERT INTO wm_draft (chapter, scene_number, attempt, text, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (chapter, scene_number, attempt, text),
        )


def load_drafts(path: Path, *, chapter: int) -> list[Draft]:
    """Las escenas cerradas del capitulo, en orden. Vacio si no hay ninguna."""
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT chapter, scene_number, attempt, text FROM wm_draft "
            " WHERE chapter = ? ORDER BY scene_number",
            (chapter,),
        ).fetchall()
    finally:
        con.close()
    return [Draft(**dict(r)) for r in rows]
