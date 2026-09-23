"""Version 5 del esquema: `fact_usage`, `chronology` y la historia que no se borra.

RD-39, RD-40, RD-34. VER-05.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from canon.brief import create_novel
from canon.db import connection
from canon.db.migrations import SCHEMA_VERSION, current_version
from canon.test_manuscript import _brief, _congelar, _escena


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    _congelar(path, 1, [_escena(1, 1, "Rex, negro, corrió.", ("lucia", "rex"))])
    with connection.canon_writer(path) as con:
        con.execute(
            "INSERT INTO manuscript_version (version, cause, changed_chapters, max_chapter, created_at) "
            "VALUES (2, NULL, '[1]', 1, 'x')"
        )
        con.execute(
            "INSERT INTO scene_text_history (scene_id, until_version, text) VALUES ('c1e1', 1, 'viejo')"
        )
    return path


@pytest.mark.parametrize(
    "sentencia",
    [
        "DELETE FROM manuscript_version",
        "UPDATE manuscript_version SET cause = 0",
        "DELETE FROM scene_text_history",
        "UPDATE scene_text_history SET text = 'otro'",
    ],
)
def test_la_historia_del_manuscrito_solo_admite_inserciones(novela: Path, sentencia: str) -> None:
    """RD-34: las dos tablas de historia ni se actualizan ni se borran."""
    with pytest.raises(sqlite3.DatabaseError), connection.canon_writer(novela) as con:
        con.execute(sentencia)
    with connection.reader(novela) as con:
        assert con.execute("SELECT count(*) FROM manuscript_version").fetchone()[0] == 1
        assert con.execute("SELECT text FROM scene_text_history").fetchone()[0] == "viejo"


def test_la_version_5_crea_la_tabla_la_vista_y_el_disparador(novela: Path) -> None:
    with connection.reader(novela) as con:
        assert current_version(con) == SCHEMA_VERSION >= 5
        tipos = {
            r["name"]: r["type"]
            for r in con.execute(
                "SELECT name, type FROM sqlite_master WHERE name IN "
                "('fact_usage', 'chronology', 'manuscript_version_no_delete')"
            )
        }
    assert tipos == {
        "fact_usage": "table",
        "chronology": "view",
        "manuscript_version_no_delete": "trigger",
    }


def test_un_fichero_de_la_version_3_sube_y_rellena_el_registro(tmp_path: Path) -> None:
    """RD-39: el esquema sube solo anadiendo, y lo ya congelado entra en el registro al migrar."""
    path = tmp_path / "v3.sqlite"
    create_novel(path, _brief())
    _congelar(path, 1, [_escena(1, 1, "Rex, negro, corrió.", ("lucia", "rex"))])
    con = sqlite3.connect(path)
    con.execute("DROP VIEW chronology")
    con.execute("DROP TRIGGER manuscript_version_no_delete")
    con.execute("DROP TABLE fact_usage")
    con.execute("DELETE FROM schema_version WHERE version > 3")
    con.commit()
    con.close()

    with connection.reader(path) as lector:
        assert current_version(lector) == 3
    with connection.canon_writer(path):
        pass
    with connection.reader(path) as lector:
        assert current_version(lector) == SCHEMA_VERSION
        filas = lector.execute("SELECT fact_key, scene_id, chapter FROM fact_usage").fetchall()
        crono = lector.execute("SELECT scene_id FROM chronology").fetchall()
    assert [tuple(f) for f in filas] == [("rex.color", "c1e1", 1)]
    assert [c[0] for c in crono] == ["c1e1"]
