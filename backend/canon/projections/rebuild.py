"""Proyeccion del canon estructurado desde el registro de eventos.

RF-03 a RF-06. El canon estructurado **no es un almacen**, es una vista
calculada: se puede tirar entera y regenerarla, y el resultado tiene que ser
identico a haberla mantenido incremental (RF-05).

Dos propiedades sostienen todo lo demas y son las que abren la puerta de T1:

- **Independencia del orden de insercion** (RF-04). Se consigue proyectando en
  orden `(world_time, world_seq, id)` y no en orden de llegada.
- **Vigencia coherente** (RF-06). Un atributo nuevo cierra al anterior en el
  instante en que empieza, en vez de dejar dos vigentes a la vez.

La segunda es la que mas facil es hacer mal: guardar el atributo nuevo sin
cerrar el viejo deja dos valores vigentes en `t`, que es exactamente el
conflicto de contexto CTX-15 fabricado en origen.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from canon.events import log
from canon.events.types import (
    AliasAdded,
    AttributeSet,
    CompetenceSet,
    DocumentVersion,
    EntityCreated,
    KnowledgeGained,
    RelationSet,
    StoredEvent,
)
from commons.types.primitives import WorldTime

#: Tablas que son proyeccion pura. Se vacian antes de reconstruir; nada que no
#: derive de un evento puede vivir aqui, o RF-05 dejaria de cumplirse.
PROJECTED_TABLES = (
    "document_version",
    "competence",
    "knowledge",
    "relation",
    "attribute",
    "entity_alias",
    "entity",
)


def rebuild(con: sqlite3.Connection, *, until: WorldTime | None = None) -> None:
    """Reconstruye las proyecciones desde cero.

    `until` acota a los eventos anteriores o iguales a ese instante, que es como
    se responde "que era cierto entonces" sin filtrar despues de proyectar.
    """
    for table in PROJECTED_TABLES:
        con.execute(f"DELETE FROM {table}")

    events = log.read_all(con) if until is None else log.read_until(con, until)
    apply_all(con, events)


def apply_all(con: sqlite3.Connection, events: Sequence[StoredEvent]) -> None:
    """Aplica un lote de eventos, ordenandolo antes.

    **Precondicion, y es la que sostiene RF-05**: un lote no puede contener
    eventos anteriores a lo ya proyectado. El motivo esta en `_close_open`, que
    cierra vigencias mirando solo hacia atras: si llegara un evento con instante
    anterior al ultimo aplicado, no cerraria al que ya esta abierto y quedarian
    dos vigentes, con lo que mantener incremental dejaria de dar lo mismo que
    reconstruir.

    En el sistema eso no ocurre porque el unico que aplica eventos es la
    congelacion, y congela capitulos en orden. Cuando deje de ser cierto --el
    retcon, que la v1 no tiene-- la salida no es parchear aqui: es reconstruir
    desde cero, que para eso `rebuild` existe.

    Se ordena el lote aunque `log` ya devuelva ordenado, porque quien llame con
    una lista propia no tiene por que haberla ordenado.
    """
    for stored in sorted(events, key=lambda s: s.sort_key):
        _apply(con, stored)


def _apply(con: sqlite3.Connection, stored: StoredEvent) -> None:
    payload = stored.event.payload
    at = stored.event.world_time

    match payload:
        case EntityCreated():
            con.execute(
                "INSERT OR IGNORE INTO entity (id, kind, name, created_at) VALUES (?, ?, ?, ?)",
                (payload.entity_id, payload.kind, payload.name, at.stamp),
            )

        case AliasAdded():
            con.execute(
                "INSERT OR REPLACE INTO entity_alias "
                "(entity_id, alias, valid_from, valid_to) VALUES (?, ?, ?, ?)",
                (
                    payload.entity_id,
                    payload.alias,
                    at.stamp,
                    payload.valid_to.stamp if payload.valid_to else None,
                ),
            )

        case AttributeSet():
            _close_open(
                con,
                table="attribute",
                where="entity_id = ? AND name = ?",
                params=(payload.entity_id, payload.name),
                at=at,
            )
            con.execute(
                "INSERT OR REPLACE INTO attribute "
                "(entity_id, name, value, valid_from, valid_to, source_event) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    payload.entity_id,
                    payload.name,
                    payload.value,
                    at.stamp,
                    payload.valid_to.stamp if payload.valid_to else None,
                    stored.id,
                ),
            )

        case RelationSet():
            _close_open(
                con,
                table="relation",
                where="source_id = ? AND target_id = ? AND kind = ?",
                params=(payload.source_id, payload.target_id, payload.kind),
                at=at,
            )
            con.execute(
                "INSERT OR REPLACE INTO relation "
                "(source_id, target_id, kind, valid_from, valid_to, source_event) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    payload.source_id,
                    payload.target_id,
                    payload.kind,
                    at.stamp,
                    payload.valid_to.stamp if payload.valid_to else None,
                    stored.id,
                ),
            )

        case KnowledgeGained():
            # PER-10: se conoce desde la primera vez. Un segundo evento sobre el
            # mismo hecho no adelanta ni retrasa cuando se supo.
            con.execute(
                "INSERT OR IGNORE INTO knowledge "
                "(entity_id, fact_key, known_from, source_event) VALUES (?, ?, ?, ?)",
                (payload.entity_id, payload.fact_key, at.stamp, stored.id),
            )

        case CompetenceSet():
            _close_open(
                con,
                table="competence",
                where="entity_id = ? AND name = ?",
                params=(payload.entity_id, payload.name),
                at=at,
            )
            con.execute(
                "INSERT OR REPLACE INTO competence "
                "(entity_id, name, level, valid_from, valid_to, source_event) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    payload.entity_id,
                    payload.name,
                    payload.level,
                    at.stamp,
                    payload.valid_to.stamp if payload.valid_to else None,
                    stored.id,
                ),
            )

        case DocumentVersion():
            row = con.execute(
                "SELECT coalesce(max(version), 0) AS v FROM document_version WHERE doc_kind = ?",
                (payload.doc_kind,),
            ).fetchone()
            con.execute(
                "INSERT INTO document_version (doc_kind, version, body, source_event) "
                "VALUES (?, ?, ?, ?)",
                (payload.doc_kind, row["v"] + 1, payload.body, stored.id),
            )


def _close_open(
    con: sqlite3.Connection,
    *,
    table: str,
    where: str,
    params: tuple[object, ...],
    at: WorldTime,
) -> None:
    """Cierra la vigencia abierta anterior en el instante en que empieza la nueva.

    Sin esto quedarian dos filas vigentes a la vez para el mismo atributo, que
    es un conflicto de contexto (CTX-15) fabricado en origen: el paquete
    llevaria las dos versiones y el Arbitro tendria que resolver algo que nunca
    debio existir.
    """
    # El orden importa: el primer marcador es el `SET`, no el primer `WHERE`.
    con.execute(
        f"UPDATE {table} SET valid_to = ? "
        f"WHERE {where} AND valid_to IS NULL AND valid_from < ?",
        (at.stamp, *params, at.stamp),
    )
