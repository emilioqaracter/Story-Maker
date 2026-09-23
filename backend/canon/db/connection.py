"""Fabricas de conexion a la novela.

RD-09, D-30. Hay tres, y la separacion no es comodidad:

- **Lectura**: la importa cualquiera, por la excepcion de lectura de
  `architecture.md` 2.3. No puede escribir.
- **Escritura de canon**: vive aqui y **no sale de `canon/`**. En la practica la
  usa solo la congelacion.
- **Escritura de memoria de trabajo**: vive en `commons/db` y no puede tocar
  nada sin prefijo `wm_`.

La de escritura de canon esta aqui y no en `commons/` precisamente para que la
frontera sea de paquete y no de disciplina: si viviera en `commons/`, cualquiera
podria importarla y la regla dependeria de que nadie lo hiciera.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from canon.db.migrations import SCHEMA_VERSION, migrate

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class SchemaVersionError(RuntimeError):
    """El fichero tiene una version de esquema que este codigo no sabe abrir.

    RD-10: hacia delante se migra; una version desconocida falla. Abrir a
    ciegas un fichero mas nuevo es como se corrompe una novela entera.
    """


def _connect(path: Path, *, read_only: bool) -> sqlite3.Connection:
    if read_only:
        uri = f"file:{path.as_posix()}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
    else:
        con = sqlite3.connect(path, isolation_level="DEFERRED")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def create(path: Path) -> None:
    """Crea el fichero de una novela con el esquema al dia."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
        con.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (1, datetime('now'))"
        )
        con.row_factory = sqlite3.Row
        migrate(con)
        con.commit()
    finally:
        con.close()


def _check_version(con: sqlite3.Connection) -> None:
    row = con.execute("SELECT max(version) AS v FROM schema_version").fetchone()
    found = row["v"] if row is not None else None
    if found is None:
        raise SchemaVersionError("el fichero no declara version de esquema")
    if found > SCHEMA_VERSION:
        raise SchemaVersionError(
            f"el fichero es version {found} y este codigo entiende hasta {SCHEMA_VERSION}"
        )


@contextmanager
def reader(path: Path) -> Iterator[sqlite3.Connection]:
    """Conexion de solo lectura. La importa cualquier funcionalidad."""
    con = _connect(path, read_only=True)
    try:
        _check_version(con)
        yield con
    finally:
        con.close()


@contextmanager
def canon_writer(path: Path) -> Iterator[sqlite3.Connection]:
    """Conexion de escritura de canon. **No se importa fuera de `canon/`.**

    Todo o nada: si el bloque lanza, se revierte entero. La congelacion se
    apoya en esto para que un fallo a mitad no deje el canon descuadrado.
    """
    con = _connect(path, read_only=False)
    try:
        _check_version(con)
        # RD-10, RI-35: hacia delante, en escritura. Leer no migra.
        migrate(con)
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()
