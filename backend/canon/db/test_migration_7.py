"""Version 7 del esquema: la solicitud de cambio gana `kind` y `term`.

`specs/srs-backend-v4.md` RD-49, RF-256. VER-05. Solo anade: una solicitud
anterior sube como `fact` con `term` nulo, y leer un fichero sin migrar la ve
igual (RI-35).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from canon import manuscript
from canon.db import connection
from canon.db.migrations import SCHEMA_VERSION, current_version


def _columnas(path: Path) -> set[str]:
    con = sqlite3.connect(path)
    try:
        return {str(r[1]) for r in con.execute("PRAGMA table_info(change_request)")}
    finally:
        con.close()


def _como_version_6(path: Path) -> None:
    """Un fichero recien creado como lo dejaba la version 6, con una solicitud."""
    con = sqlite3.connect(path)
    con.execute("ALTER TABLE change_request DROP COLUMN term")
    con.execute("ALTER TABLE change_request DROP COLUMN kind")
    con.execute("DELETE FROM schema_version WHERE version >= 7")
    con.execute(
        "INSERT INTO change_request (text, anchor, status, entity_id, attribute, previous_value, "
        "new_value, created_at, updated_at) VALUES (?, ?, 'queued', 'rex', 'nombre', 'Rex', "
        "'Nala', 'x', 'x')",
        (
            "el perro se llama Nala",
            json.dumps({"kind": "fact", "entity_id": "rex", "attribute": "nombre"}),
        ),
    )
    con.commit()
    con.close()


def test_un_fichero_nuevo_nace_con_kind_y_term(tmp_path: Path) -> None:
    path = tmp_path / "n.sqlite"
    connection.create(path)
    assert {"kind", "term"} <= _columnas(path)
    with connection.reader(path) as con:
        assert current_version(con) == SCHEMA_VERSION >= 7


def test_leer_un_fichero_de_la_version_6_da_la_solicitud_como_hecho(tmp_path: Path) -> None:
    """RI-35: leer no migra, y la solicitud se lee como la migracion la dejaria."""
    path = tmp_path / "v6.sqlite"
    connection.create(path)
    _como_version_6(path)
    with connection.reader(path) as con:
        [s] = manuscript.requests(con)
    assert s.interpretation is not None
    assert (s.interpretation.kind, s.interpretation.term) == ("fact", None)
    assert {"kind", "term"}.isdisjoint(_columnas(path))


def test_un_fichero_de_la_version_6_sube_sin_perder_la_solicitud(tmp_path: Path) -> None:
    path = tmp_path / "v6.sqlite"
    connection.create(path)
    _como_version_6(path)

    with connection.canon_writer(path):
        pass

    assert {"kind", "term"} <= _columnas(path)
    with connection.reader(path) as con:
        assert current_version(con) == SCHEMA_VERSION
        fila = dict(con.execute("SELECT kind, term, new_value FROM change_request").fetchone())
    assert fila == {"kind": "fact", "term": None, "new_value": "Nala"}


def test_kind_solo_admite_fact_o_forbid(tmp_path: Path) -> None:
    path = tmp_path / "n.sqlite"
    connection.create(path)
    con = sqlite3.connect(path)
    try:
        con.execute(
            "INSERT INTO change_request (text, anchor, status, kind, created_at, updated_at) "
            "VALUES ('x', '{}', 'queued', 'otro', 'x', 'x')"
        )
        raise AssertionError("un kind desconocido no deberia entrar")
    except sqlite3.IntegrityError:
        pass
    finally:
        con.close()
