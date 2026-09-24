"""Los elementos del brief en el canon: los declarados y sus usos anclados.

RF-260, RF-261, RD-47, D-95. `architecture.md` §3.1 y §9.3.

Un elemento --rasgo o recuerdo del destinatario-- entra en el canon con la carga
del brief (`element.declared`, proyectado a `brief_element`). Que **aparece** no
lo decide una busqueda de subcadenas --un recuerdo casi nunca se narra literal--
sino una cita del Archivero que el codigo ancla en la escena con
`check.evidence` antes de congelar. Anclada, se escribe aqui dentro de la
transaccion de congelacion: en `element_use`, con la cita, y en hecho x escena
como `element.<id>` (RF-241). Sin anclar no llega: la descarta quien ancla.

El registro de setups da por cobrado un elemento solo si tiene un uso aqui
(`planning/ledger/setups.py`), y la puerta de cierre de obra lo exige.

Leer no migra (RI-35): un fichero anterior sin las tablas no tiene elementos
declarados, y las lecturas devuelven vacio en vez de fallar.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, ConfigDict, Field

from canon.brief import ELEMENT_PREFIX, BriefElement
from canon.prose_index.reindex import scene_text_from_chunks


class ElementUse(BaseModel):
    """Un uso anclado: el elemento, la escena y la cita literal que lo prueba."""

    model_config = ConfigDict(frozen=True)

    element_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    offset: int = Field(ge=0)


def _has(con: sqlite3.Connection, table: str) -> bool:
    return (
        con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        is not None
    )


def declared(con: sqlite3.Connection) -> list[BriefElement]:
    """Los elementos que declaro el brief, en orden de identificador."""
    if not _has(con, "brief_element"):
        return []
    return [
        BriefElement(id=r[0], kind=r[1], text=r[2], mandatory=bool(r[3]))
        for r in con.execute(
            "SELECT id, kind, text, mandatory FROM brief_element ORDER BY kind DESC, "
            "CAST(substr(id, instr(id, '-') + 1) AS INTEGER)"
        )
    ]


def used(con: sqlite3.Connection) -> frozenset[str]:
    """Los elementos con al menos un uso anclado en una escena congelada."""
    if not _has(con, "element_use"):
        return frozenset()
    return frozenset(str(r[0]) for r in con.execute("SELECT DISTINCT element_id FROM element_use"))


def unused_mandatory(con: sqlite3.Connection) -> list[BriefElement]:
    """RF-261. Los obligatorios sin uso anclado: lo que impide cerrar la obra."""
    usados = used(con)
    return [e for e in declared(con) if e.mandatory and e.id not in usados]


def record(con: sqlite3.Connection, uses: Sequence[ElementUse], *, chapter: int) -> None:
    """Escribe los usos anclados del capitulo. Dentro de la transaccion de congelacion.

    Un elemento que el brief no declara no se escribe: el anclaje ya lo descarto,
    y si llegara aqui seria un uso de algo que nadie pidio.
    """
    if not uses:
        return
    conocidos = {e.id: e for e in declared(con)}
    fuentes = {
        str(r[0]): int(r[1]) for r in con.execute("SELECT id, source_event FROM brief_element")
    }
    for u in uses:
        if u.element_id not in conocidos:
            continue
        con.execute(
            "INSERT OR REPLACE INTO element_use (element_id, scene_id, chapter, quote, offset) "
            "VALUES (?, ?, ?, ?, ?)",
            (u.element_id, u.scene_id, chapter, u.quote, u.offset),
        )
        con.execute(
            "INSERT OR IGNORE INTO fact_usage (fact_key, source_event, scene_id, chapter) "
            "VALUES (?, ?, ?, ?)",
            (f"{ELEMENT_PREFIX}{u.element_id}", fuentes[u.element_id], u.scene_id, chapter),
        )


def reanchor(con: sqlite3.Connection, scenes: Iterable[str]) -> None:
    """Tras recongelar, un uso sigue solo si su cita sigue literal en la escena.

    Una escena reescrita --un retcon, una enmienda-- puede haber perdido el
    recuerdo que la hacia cobrarlo. Se comprueba con la misma regla que ancla:
    la cita aparece en el texto. Si no, el uso se va de las dos tablas y el
    elemento vuelve a ser deuda.
    """
    ids = sorted(set(scenes))
    if not ids or not _has(con, "element_use"):
        return
    marks = ",".join("?" * len(ids))
    trozos: dict[str, list[str]] = {}
    for r in con.execute(
        f"SELECT scene_id, text FROM prose_chunk WHERE scene_id IN ({marks}) "  # nosec B608
        "ORDER BY scene_id, ordinal",
        ids,
    ):
        trozos.setdefault(str(r[0]), []).append(str(r[1]))
    textos = {sid: scene_text_from_chunks(t) for sid, t in trozos.items()}
    caidos = [
        (str(r[0]), str(r[1]))
        for r in con.execute(
            f"SELECT element_id, scene_id, quote FROM element_use WHERE scene_id IN ({marks})",  # nosec B608
            ids,
        )
        if _normal(str(r[2])) not in _normal(textos.get(str(r[1]), ""))
    ]
    for elemento, escena in caidos:
        con.execute(
            "DELETE FROM element_use WHERE element_id = ? AND scene_id = ?", (elemento, escena)
        )
        con.execute(
            "DELETE FROM fact_usage WHERE fact_key = ? AND scene_id = ?",
            (f"{ELEMENT_PREFIX}{elemento}", escena),
        )


def _normal(text: str) -> str:
    """Espacios colapsados: la misma cita en un texto troceado y reunido."""
    return " ".join(text.split())
