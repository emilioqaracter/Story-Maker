"""Almacen de entrevistas. RD-32, D-74.

Una entrevista no es una novela: no tiene fichero propio hasta RI-01. Todas
viven en `_interviews.sqlite`, en el directorio de tiradas. El guion bajo no
es casual: ningun identificador de novela puede empezar por el
(`commons/settings.py`), asi que el almacen nunca choca con una novela.

`interview` guarda el estado vigente; `interview_turn` guarda cada turno tal
como llego, y solo admite inserciones: es lo que permite saber de donde salio
cada campo del brief.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from brief.interview import InterviewState, TurnIn

FILENAME = "_interviews.sqlite"
ID_PATTERN = r"^[a-f0-9]{12}$"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interview (
    id          TEXT PRIMARY KEY,
    state       TEXT NOT NULL CHECK (json_valid(state)),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interview_turn (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id TEXT NOT NULL REFERENCES interview(id),
    input        TEXT NOT NULL CHECK (json_valid(input)),
    at           TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS interview_turn_no_update BEFORE UPDATE ON interview_turn
BEGIN SELECT RAISE(ABORT, 'los turnos de una entrevista son append-only'); END;
CREATE TRIGGER IF NOT EXISTS interview_turn_no_delete BEFORE DELETE ON interview_turn
BEGIN SELECT RAISE(ABORT, 'los turnos de una entrevista son append-only'); END;
"""


@contextmanager
def _open(runs_dir: Path) -> Iterator[sqlite3.Connection]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(runs_dir / FILENAME)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(_SCHEMA)
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def new_id() -> str:
    return secrets.token_hex(6)


def create(runs_dir: Path, state: InterviewState) -> None:
    with _open(runs_dir) as con:
        con.execute(
            "INSERT INTO interview (id, state, created_at, updated_at) VALUES (?, ?, datetime('now'), datetime('now'))",
            (state.interview_id, state.model_dump_json()),
        )


def load(runs_dir: Path, interview_id: str) -> InterviewState | None:
    if not (runs_dir / FILENAME).exists():
        return None
    with _open(runs_dir) as con:
        row = con.execute("SELECT state FROM interview WHERE id = ?", (interview_id,)).fetchone()
    return None if row is None else InterviewState.model_validate_json(row["state"])


def save_turn(runs_dir: Path, incoming: TurnIn, state: InterviewState) -> None:
    """El turno tal como llego y el estado que produjo, juntos o nada."""
    with _open(runs_dir) as con:
        con.execute(
            "INSERT INTO interview_turn (interview_id, input, at) VALUES (?, ?, datetime('now'))",
            (state.interview_id, json.dumps(incoming.model_dump(mode="json"), ensure_ascii=False)),
        )
        con.execute(
            "UPDATE interview SET state = ?, updated_at = datetime('now') WHERE id = ?",
            (state.model_dump_json(), state.interview_id),
        )
