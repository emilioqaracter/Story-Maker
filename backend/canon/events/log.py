"""Registro de eventos: escritura y lectura.

Append-only (RF-01). La inmutabilidad la imponen los triggers del esquema, no
este modulo: una regla que vive solo en el codigo de acceso se salta la primera
vez que alguien abre el fichero con otra herramienta.

Lo que este modulo garantiza es lo otro: que nada incompleto llegue a la base
(RF-02) y que la lectura salga siempre en el orden de proyeccion (RD-03).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence

from pydantic import TypeAdapter

from canon.events.types import Event, Payload, StoredEvent
from commons.types.primitives import Provenance, WorldTime

_PAYLOAD_ADAPTER: TypeAdapter[Payload] = TypeAdapter(Payload)

_INSERT_EVENT = """
    INSERT INTO event (world_time, world_seq, type, payload, provenance,
                       chapter_origin, recorded_at)
    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
"""

_INSERT_LINK = "INSERT INTO event_entity (event_id, entity_id) VALUES (?, ?)"

_COLUMNS = "id, world_time, world_seq, type, payload, provenance, chapter_origin"

# RD-03: el orden de insercion NO participa. Ordenar aqui, y no en quien lee, es
# lo que hace que la proyeccion sea independiente del orden de llegada sin que
# cada consumidor tenga que acordarse.
_ORDER = "ORDER BY world_time, world_seq, id"

_SELECT_ALL = f"SELECT {_COLUMNS} FROM event {_ORDER}"
_SELECT_UNTIL = (
    f"SELECT {_COLUMNS} FROM event WHERE (world_time, world_seq) <= (?, ?) {_ORDER}"
)


def append(con: sqlite3.Connection, events: Iterable[Event]) -> list[int]:
    """Anade eventos al registro y devuelve sus identificadores.

    No hace commit: quien llama decide la frontera de la transaccion, y en la
    congelacion esa frontera abarca mucho mas que esto (RF-57).
    """
    ids: list[int] = []
    for ev in events:
        cur = con.execute(
            _INSERT_EVENT,
            (
                ev.world_time.stamp,
                ev.world_time.seq,
                str(ev.payload.type),
                ev.payload.model_dump_json(exclude={"type"}),
                str(ev.provenance),
                ev.chapter_origin,
            ),
        )
        event_id = cur.lastrowid
        if event_id is None:  # pragma: no cover - sqlite siempre lo da en INSERT
            raise RuntimeError("sqlite no devolvio identificador de evento")
        con.executemany(_INSERT_LINK, [(event_id, e) for e in sorted(ev.entities)])
        ids.append(event_id)
    return ids


def read_all(con: sqlite3.Connection) -> Sequence[StoredEvent]:
    """Todos los eventos, en orden de proyeccion."""
    return _read(con, _SELECT_ALL, ())


def read_until(con: sqlite3.Connection, t: WorldTime) -> Sequence[StoredEvent]:
    """Solo los eventos con instante menor o igual que `t` (RF-03).

    Es lo que permite responder "que era cierto en la jornada 14" sin
    ambiguedad: no se filtra despues de proyectar, se proyecta menos.
    """
    return _read(con, _SELECT_UNTIL, (t.stamp, t.seq))


def _read(
    con: sqlite3.Connection, sql: str, params: tuple[object, ...]
) -> Sequence[StoredEvent]:
    rows = con.execute(sql, params).fetchall()
    if not rows:
        return []
    links = _entities_for(con, [r["id"] for r in rows])
    return [_to_stored(r, links.get(r["id"], frozenset())) for r in rows]


def _entities_for(
    con: sqlite3.Connection, event_ids: Sequence[int]
) -> Mapping[int, frozenset[str]]:
    """Carga las entidades de todos los eventos de una vez.

    En bloque y no por evento: una consulta por fila multiplicaria por cinco el
    coste de proyectar una novela entera, que es lo que hace RF-05 --regenerar
    el canon desde cero-- practicable en vez de teorico.
    """
    placeholders = ",".join("?" * len(event_ids))
    rows = con.execute(
        f"SELECT event_id, entity_id FROM event_entity WHERE event_id IN ({placeholders})",
        list(event_ids),
    ).fetchall()

    grouped: dict[int, set[str]] = {}
    for row in rows:
        grouped.setdefault(row["event_id"], set()).add(row["entity_id"])
    return {k: frozenset(v) for k, v in grouped.items()}


def _to_stored(row: sqlite3.Row, entities: frozenset[str]) -> StoredEvent:
    data = json.loads(row["payload"])
    data["type"] = row["type"]
    return StoredEvent(
        id=row["id"],
        event=Event(
            world_time=WorldTime(stamp=row["world_time"], seq=row["world_seq"]),
            payload=_PAYLOAD_ADAPTER.validate_python(data),
            provenance=Provenance(row["provenance"]),
            chapter_origin=row["chapter_origin"],
            entities=entities,
        ),
    )
