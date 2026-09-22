"""Fabrica de escritura de memoria de trabajo.

D-30, RD-09, RD-18. `architecture.md` 3.2.

Existe porque las cinco tablas de memoria de trabajo las escribe **quien
produce ese estado** --`orchestration/` el punto de reanudacion y la cola,
`generation/` los borradores, `verification/` los defectos-- y ninguno de ellos
puede importar la fabrica de escritura de canon, que es exclusiva de `canon/`.

La salida no fue relajar la regla de `canon/`, porque es la que protege lo
unico que hay que proteger. Fue separar dos escrituras que solo comparten
fichero por comodidad. Y lo que hace **comprobable** la separacion es el
prefijo: esta conexion no puede nombrar una tabla que no empiece por `wm_`.
Sin eso, "el canon solo lo escribe la congelacion" seria una promesa y no un
invariante.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

#: Tablas de memoria de trabajo (RD-07). `wm_verdict` se crea aunque la v1 no
#: tenga Jurado, para que el fichero sea completo.
WORKING_MEMORY_TABLES = frozenset(
    {"wm_run_state", "wm_draft", "wm_defect", "wm_verdict", "wm_admission"}
)

#: Identificadores que aparecen tras INSERT INTO / UPDATE / DELETE FROM.
_TARGET = re.compile(
    r"\b(?:insert\s+(?:or\s+\w+\s+)?into|update|delete\s+from)\s+[\"'`\[]?(\w+)",
    re.IGNORECASE,
)


class ForbiddenTableError(RuntimeError):
    """Se intento escribir fuera de `wm_*` con la conexion de memoria de trabajo.

    No es una comprobacion defensiva de mas: es el invariante de D-30 hecho
    codigo. Si esto salta, alguien esta a punto de escribir canon sin congelar.
    """


def _targets(sql: str) -> Sequence[str]:
    return [m.group(1).lower() for m in _TARGET.finditer(sql)]


class WorkingMemoryConnection:
    """Conexion de escritura acotada a las tablas de memoria de trabajo.

    No hereda de `sqlite3.Connection` a proposito: heredar dejaria `execute`
    original accesible por cualquier atajo y la restriccion seria decorativa.
    """

    def __init__(self, raw: sqlite3.Connection) -> None:
        self._raw = raw

    def execute(self, sql: str, parameters: Sequence[object] = ()) -> sqlite3.Cursor:
        """Ejecuta una sentencia, previa comprobacion del destino.

        Los valores van siempre como parametros y nunca concatenados (RD-11).
        """
        for table in _targets(sql):
            if table not in WORKING_MEMORY_TABLES:
                raise ForbiddenTableError(
                    f"la conexion de memoria de trabajo no escribe en {table!r}; "
                    "solo el prefijo wm_. Escribir canon es exclusivo de la congelacion"
                )
        return self._raw.execute(sql, parameters)

    def executemany(
        self, sql: str, seq_of_parameters: Sequence[Sequence[object]]
    ) -> sqlite3.Cursor:
        for table in _targets(sql):
            if table not in WORKING_MEMORY_TABLES:
                raise ForbiddenTableError(
                    f"la conexion de memoria de trabajo no escribe en {table!r}"
                )
        return self._raw.executemany(sql, seq_of_parameters)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()


@contextmanager
def working_memory_writer(path: Path) -> Iterator[WorkingMemoryConnection]:
    """Abre una conexion de escritura de memoria de trabajo sobre la novela."""
    raw = sqlite3.connect(path, isolation_level="DEFERRED")
    raw.execute("PRAGMA foreign_keys = ON")
    try:
        yield WorkingMemoryConnection(raw)
        raw.commit()
    except BaseException:
        raw.rollback()
        raise
    finally:
        raw.close()
