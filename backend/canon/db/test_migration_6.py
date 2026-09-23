"""Version 6 del esquema: el punto de reanudacion conserva reintentos y escaleta.

`architecture.md` §7.4, RD-10. Contraejemplos B4 y R1 de TLC
(`orchestration/model/README.md` §7.1). VER-05. Que el punto se lee y se
escribe con ellas lo prueba `orchestration/test_checkpoint.py`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from canon.db import connection
from canon.db.migrations import SCHEMA_VERSION, current_version

NUEVAS = ("chapter_attempts", "arc_replans", "outline")


def _columnas(path: Path) -> set[str]:
    con = sqlite3.connect(path)
    try:
        return {str(r[1]) for r in con.execute("PRAGMA table_info(wm_run_state)")}
    finally:
        con.close()


def como_version_5(path: Path) -> None:
    """Deja un fichero recien creado como lo dejaba la version 5, con un punto."""
    con = sqlite3.connect(path)
    for columna in NUEVAS:
        con.execute(f"ALTER TABLE wm_run_state DROP COLUMN {columna}")  # nosec B608
    con.execute("DELETE FROM schema_version WHERE version >= 6")
    con.execute(
        "INSERT INTO wm_run_state (id, chapter, last_closed_scene, step, updated_at) "
        "VALUES (1, 3, 1, 'scene_loop', 'x')"
    )
    con.commit()
    con.close()


def test_un_fichero_nuevo_nace_con_las_columnas(tmp_path: Path) -> None:
    path = tmp_path / "n.sqlite"
    connection.create(path)
    assert set(NUEVAS) <= _columnas(path)
    with connection.reader(path) as con:
        assert current_version(con) == SCHEMA_VERSION == 6


def test_un_fichero_de_la_version_5_sube_sin_perder_el_punto(tmp_path: Path) -> None:
    """RD-10: solo anade. El punto que ya tenia sigue ahi, con la cuenta a cero."""
    path = tmp_path / "v5.sqlite"
    connection.create(path)
    como_version_5(path)

    with connection.canon_writer(path):
        pass

    assert set(NUEVAS) <= _columnas(path)
    with connection.reader(path) as con:
        assert current_version(con) == 6
        fila = dict(con.execute("SELECT * FROM wm_run_state").fetchone())
    assert (fila["chapter"], fila["last_closed_scene"]) == (3, 1)
    assert (fila["chapter_attempts"], fila["arc_replans"], fila["outline"]) == (0, 0, None)


def test_migrar_dos_veces_es_lo_mismo_que_una(tmp_path: Path) -> None:
    path = tmp_path / "n.sqlite"
    connection.create(path)
    con = sqlite3.connect(path)
    con.execute("DELETE FROM schema_version WHERE version >= 6")
    con.commit()
    con.close()
    with connection.canon_writer(path):
        pass
    assert set(NUEVAS) <= _columnas(path)


def test_la_escaleta_guardada_tiene_que_ser_json(tmp_path: Path) -> None:
    path = tmp_path / "n.sqlite"
    connection.create(path)
    con = sqlite3.connect(path)
    try:
        con.execute(
            "INSERT INTO wm_run_state (id, chapter, step, outline, updated_at) "
            "VALUES (1, 1, 'scene_loop', '{roto', 'x')"
        )
        raise AssertionError("una escaleta que no es JSON no deberia entrar")
    except sqlite3.IntegrityError:
        pass
    finally:
        con.close()
