"""Hecho x escena: que escenas congeladas usan cada hecho vigente.

RF-241, RD-39, D-89. `architecture.md` §3.1 y §3.3.

**La regla** es la que `orchestration/amend.py:affected_scenes` aplica a un
atributo, para que el registro y el calculo al vuelo no puedan discrepar sin que
salte: una escena congelada usa el hecho `entidad.atributo` si la entidad es POV,
lugar o elenco de la escena y el valor vigente aparece en su texto como palabra
completa, sin distinguir mayusculas. El nombre de una entidad no es un atributo
de `attribute` y no entra: `affected_scenes` lo busca sin exigir presencia y con
formas que dependen del nombre nuevo (D-83), que el registro no puede conocer.

**Donde vive**: en el indice de prosa y no en el canon estructurado, porque es un
indice y no verdad (RD-39). El canon estructurado es proyeccion pura del
registro de eventos; esto es proyeccion del texto congelado sobre el canon.

**Esquema** (migracion 5, `canon/db/migrations.py`)::

    fact_usage(
        fact_key     TEXT    NOT NULL,  -- "<entity_id>.<atributo>"
        source_event INTEGER NOT NULL,  -- event.id que fijo el valor usado
        scene_id     TEXT    NOT NULL,  -- prose_scene.id
        chapter      INTEGER NOT NULL,  -- prose_scene.chapter
        PRIMARY KEY (fact_key, source_event, scene_id)
    )

Solo guarda filas de valores **vigentes** (`attribute.valid_to IS NULL`): cuando
un evento cambia el valor, las filas del anterior se van y el nuevo se busca en
todas las escenas. Se escribe dentro de la transaccion de congelacion y de
recongelacion, despues de las proyecciones y del indice, que es lo que lee.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable
from typing import NamedTuple

from canon.prose_index.reindex import scene_text_from_chunks


class Fact(NamedTuple):
    """Un valor vigente de `attribute`, identificado por el evento que lo fijo."""

    entity_id: str
    attribute: str
    value: str
    source_event: int

    @property
    def key(self) -> str:
        return fact_key(self.entity_id, self.attribute)


#: RF-261. Las claves de hecho x escena de los elementos del brief.
_ELEMENT_LIKE = "element.%"


def fact_key(entity_id: str, attribute: str) -> str:
    """La clave del hecho, la misma que usa el `RetconPlan` de una enmienda."""
    return f"{entity_id}.{attribute}"


def value_pattern(value: str) -> re.Pattern[str]:
    """El valor como palabra completa, sin distinguir mayusculas. Pura.

    Es `orchestration/amend.py:_names` para una sola forma. Si cambia uno, cambia
    el otro: `orchestration/test_fact_usage.py` lo comprueba con una propiedad.
    """
    return re.compile(rf"(?<!\w)(?:{re.escape(value)})(?!\w)", re.IGNORECASE)


def _has_table(con: sqlite3.Connection) -> bool:
    return (
        con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'fact_usage'"
        ).fetchone()
        is not None
    )


def vigente(con: sqlite3.Connection) -> frozenset[Fact]:
    """Los valores vigentes ahora. Se toma antes de escribir para saber que cambio."""
    return frozenset(
        Fact(r[0], r[1], r[2], int(r[3]))
        for r in con.execute(
            "SELECT entity_id, name, value, source_event FROM attribute WHERE valid_to IS NULL"
        )
    )


def _scenes(
    con: sqlite3.Connection, only: Iterable[str] | None
) -> list[tuple[str, int, set[str], str]]:
    """Escenas congeladas con capitulo, entidades presentes y texto."""
    ids = None if only is None else set(only)
    presentes: dict[str, set[str]] = {}
    capitulo: dict[str, int] = {}
    for r in con.execute("SELECT id, chapter, pov_entity, place_entity FROM prose_scene"):
        if ids is not None and r[0] not in ids:
            continue
        capitulo[r[0]] = int(r[1])
        presentes[r[0]] = {e for e in (r[2], r[3]) if e}
    for r in con.execute("SELECT scene_id, entity_id FROM prose_scene_character"):
        if r[0] in presentes:
            presentes[r[0]].add(r[1])
    trozos: dict[str, list[str]] = {}
    for r in con.execute("SELECT scene_id, text FROM prose_chunk ORDER BY scene_id, ordinal"):
        if r[0] in presentes:
            trozos.setdefault(r[0], []).append(r[1])
    # El texto se reconstruye desde los fragmentos igual que `reindex.scene_texts`,
    # que es lo que lee `affected_scenes`.
    return [
        (sid, capitulo[sid], presentes[sid], scene_text_from_chunks(trozos.get(sid, [])))
        for sid in sorted(presentes)
    ]


def _scan(con: sqlite3.Connection, facts: Iterable[Fact], scenes: Iterable[str] | None) -> None:
    por_entidad: dict[str, list[tuple[Fact, re.Pattern[str]]]] = {}
    for f in facts:
        por_entidad.setdefault(f.entity_id, []).append((f, value_pattern(f.value)))
    if not por_entidad:
        return
    filas = []
    for sid, cap, presentes, texto in _scenes(con, scenes):
        for entidad in presentes:
            for f, patron in por_entidad.get(entidad, ()):
                if patron.search(texto):
                    filas.append((f.key, f.source_event, sid, cap))
    con.executemany(
        "INSERT OR IGNORE INTO fact_usage (fact_key, source_event, scene_id, chapter) VALUES (?,?,?,?)",
        filas,
    )


def refresh(con: sqlite3.Connection, *, scenes: Iterable[str], before: frozenset[Fact]) -> None:
    """Pone el registro al dia tras congelar o recongelar. Dentro de la transaccion.

    `scenes` son las escenas cuyo texto acaba de escribirse: sus filas se
    reescriben enteras. `before` es `vigente(con)` tomado antes de aplicar los
    eventos: un valor que ya no rige pierde sus filas, y uno que rige desde ahora
    se busca en todas las escenas congeladas, porque el texto viejo tambien
    puede nombrarlo.
    """
    ahora = vigente(con)
    claves = {(f.key, f.source_event) for f in ahora}
    # RF-261. Las filas `element.<id>` no son valores de atributo: las escribe
    # la congelacion con su cita anclada (`canon/freeze/elements.py`) y solo
    # caen si la cita deja de estar en la escena.
    viejas = [
        (r[0], r[1])
        for r in con.execute(
            "SELECT DISTINCT fact_key, source_event FROM fact_usage WHERE fact_key NOT LIKE ?",
            (_ELEMENT_LIKE,),
        )
        if (r[0], r[1]) not in claves
    ]
    con.executemany("DELETE FROM fact_usage WHERE fact_key = ? AND source_event = ?", viejas)

    tocadas = sorted(set(scenes))
    if tocadas:
        marks = ",".join("?" * len(tocadas))
        con.execute(
            f"DELETE FROM fact_usage WHERE scene_id IN ({marks}) AND fact_key NOT LIKE ?",  # nosec B608
            (*tocadas, _ELEMENT_LIKE),
        )
        _scan(con, ahora, tocadas)
        # Import tardio: `canon/freeze` importa este modulo.
        from canon.freeze import elements

        elements.reanchor(con, tocadas)
    nuevos = ahora - before
    if nuevos:
        _scan(con, nuevos, None)


def rebuild(con: sqlite3.Connection) -> None:
    """El registro desde cero. Lo usa la migracion 5 para lo ya congelado.

    Los usos de elementos se conservan: no se derivan del texto, llevan cita.
    """
    con.execute("DELETE FROM fact_usage WHERE fact_key NOT LIKE ?", (_ELEMENT_LIKE,))
    _scan(con, vigente(con), None)


def scenes_using(con: sqlite3.Connection, entity_id: str, attribute: str) -> list[str] | None:
    """Escenas que usan el valor vigente del hecho, en orden de capitulo y escena.

    `None` si el fichero no tiene el registro: leer no migra (RI-35), y una lista
    vacia diria que el hecho no se usa en ningun sitio.
    """
    if not _has_table(con):
        return None
    return [
        r[0]
        for r in con.execute(
            "SELECT u.scene_id FROM fact_usage u "
            "JOIN attribute a ON a.source_event = u.source_event "
            " AND a.entity_id = ? AND a.name = ? AND a.valid_to IS NULL "
            "JOIN prose_scene s ON s.id = u.scene_id "
            "WHERE u.fact_key = ? ORDER BY s.chapter, s.scene_number",
            (entity_id, attribute, fact_key(entity_id, attribute)),
        )
    ]


def chapters_using(con: sqlite3.Connection, entity_id: str, attribute: str) -> list[int] | None:
    """Capitulos que usan el valor vigente del hecho: hecho x capitulo."""
    if not _has_table(con):
        return None
    return [
        int(r[0])
        for r in con.execute(
            "SELECT DISTINCT u.chapter FROM fact_usage u "
            "JOIN attribute a ON a.source_event = u.source_event "
            " AND a.entity_id = ? AND a.name = ? AND a.valid_to IS NULL "
            "WHERE u.fact_key = ? ORDER BY u.chapter",
            (entity_id, attribute, fact_key(entity_id, attribute)),
        )
    ]
