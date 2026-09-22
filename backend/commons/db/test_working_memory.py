"""La separacion de escrituras, comprobada.

RD-09, RD-18, D-30. Metodo VER-05. Si estas pruebas pasan, "el canon solo lo
escribe la congelacion" es un invariante; si no, es una promesa.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from commons.db.working_memory import (
    ForbiddenTableError,
    WorkingMemoryConnection,
    working_memory_writer,
)


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "novela.sqlite"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE wm_run_state (chapter INTEGER, scene INTEGER);
        CREATE TABLE wm_draft (id INTEGER PRIMARY KEY, text TEXT);
        CREATE TABLE event (id INTEGER PRIMARY KEY, kind TEXT);
        CREATE TABLE entity (id INTEGER PRIMARY KEY, name TEXT);
        """
    )
    con.commit()
    con.close()
    return path


def test_escribe_en_memoria_de_trabajo(novela: Path) -> None:
    with working_memory_writer(novela) as wm:
        wm.execute("INSERT INTO wm_run_state (chapter, scene) VALUES (?, ?)", (3, 2))

    con = sqlite3.connect(novela)
    assert con.execute("SELECT chapter, scene FROM wm_run_state").fetchone() == (3, 2)
    con.close()


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO event (kind) VALUES ('x')",
        "insert into entity (name) values ('x')",
        "UPDATE event SET kind = 'y'",
        "DELETE FROM entity",
        "INSERT OR REPLACE INTO event (id, kind) VALUES (1, 'x')",
    ],
)
def test_no_escribe_canon(novela: Path, sql: str) -> None:
    """Cualquier forma de tocar una tabla sin prefijo wm_ se rechaza.

    Las variantes estan aqui porque la deteccion es sintactica: si solo
    cubriera `INSERT INTO`, un `INSERT OR REPLACE` se colaria.
    """
    with pytest.raises(ForbiddenTableError, match="memoria de trabajo"), working_memory_writer(
        novela
    ) as wm:
        wm.execute(sql)


def test_el_rechazo_revierte_lo_anterior(novela: Path) -> None:
    """Un intento de escribir canon deja la transaccion entera sin efecto.

    Si no revirtiera, media escritura de memoria de trabajo sobreviviria a un
    fallo que indica que el codigo esta haciendo algo que no debe.
    """
    with pytest.raises(ForbiddenTableError), working_memory_writer(novela) as wm:
        wm.execute("INSERT INTO wm_draft (text) VALUES ('borrador')")
        wm.execute("INSERT INTO event (kind) VALUES ('deberia abortar')")

    con = sqlite3.connect(novela)
    assert con.execute("SELECT count(*) FROM wm_draft").fetchone()[0] == 0
    con.close()


def test_no_hereda_de_connection(novela: Path) -> None:
    """La conexion envuelve, no hereda.

    Heredar dejaria el `execute` original accesible por cualquier atajo y la
    restriccion seria decorativa.
    """
    with working_memory_writer(novela) as wm:
        assert isinstance(wm, WorkingMemoryConnection)
        assert not isinstance(wm, sqlite3.Connection)
