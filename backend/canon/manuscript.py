"""Versiones del manuscrito y solicitudes de cambio.

RF-203 a RF-206, RD-33, RD-34. `specs/srs-backend-v3.md` §4.2. La version 1 es
la tirada y no tiene fila; cada enmienda aplicada anade la siguiente. Recongelar
reemplaza el indice de prosa, asi que **antes** se guarda el texto que cada
escena reescrita tenia, con la ultima version en que regia: la version anterior
se lee siempre igual (D-52 del frontend).

Las lecturas no migran el esquema: un fichero de la version 2 del esquema no
tiene estas tablas hasta su siguiente escritura, y para leer se tratan como
vacias.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from canon.arbiter import refreeze
from canon.arbiter.retcon import RetconPlan
from canon.events import log
from canon.events.types import Event
from canon.projections import rebuild
from canon.prose_index import usage

FIRST_VERSION = 1

#: RF-226. Los cuatro estados de una solicitud; solo el backend los cambia.
STATUSES = ("queued", "applying", "applied", "rejected")


def _has(con: sqlite3.Connection, table: str) -> bool:
    return (
        con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        is not None
    )


def _words(text: str) -> int:
    return len(text.split())


# ------------------------------------------------------------------ versiones


class VersionInfo(BaseModel):
    """RI-42. Una version del manuscrito (PRO-08)."""

    model_config = ConfigDict(frozen=True)

    number: int = Field(ge=1)
    created_at: str | None = Field(description="Nulo en la 1: nace con la tirada")
    cause: int | None = Field(description="Solicitud que la produjo; nula en la 1")
    changed_chapters: tuple[int, ...] = Field(
        description="Capitulos cambiados respecto a la anterior"
    )
    current: bool


def versions(con: sqlite3.Connection) -> list[VersionInfo]:
    rows = (
        con.execute("SELECT * FROM manuscript_version ORDER BY version").fetchall()
        if _has(con, "manuscript_version")
        else []
    )
    last = rows[-1]["version"] if rows else FIRST_VERSION
    out = [
        VersionInfo(
            number=FIRST_VERSION,
            created_at=None,
            cause=None,
            changed_chapters=(),
            current=last == 1,
        )
    ]
    for r in rows:
        out.append(
            VersionInfo(
                number=r["version"],
                created_at=r["created_at"],
                cause=r["cause"],
                changed_chapters=tuple(json.loads(r["changed_chapters"])),
                current=r["version"] == last,
            )
        )
    return out


def current_version(con: sqlite3.Connection) -> int:
    return versions(con)[-1].number


def _frozen_chapters(con: sqlite3.Connection) -> list[int]:
    return [
        r["chapter"]
        for r in con.execute("SELECT DISTINCT chapter FROM prose_scene ORDER BY chapter")
    ]


def chapters_in(con: sqlite3.Connection, version: int) -> list[int]:
    """RF-204. Los capitulos de una version: los congelados hasta que se creo la siguiente."""
    todos = _frozen_chapters(con)
    if not _has(con, "manuscript_version"):
        return todos
    siguiente = con.execute(
        "SELECT max_chapter FROM manuscript_version WHERE version = ?", (version + 1,)
    ).fetchone()
    return todos if siguiente is None else [c for c in todos if c <= siguiente["max_chapter"]]


def _current_texts(con: sqlite3.Connection, scene_ids: Sequence[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for sid in scene_ids:
        partes = con.execute(
            "SELECT text FROM prose_chunk WHERE scene_id = ? ORDER BY ordinal", (sid,)
        ).fetchall()
        out[sid] = "\n\n".join(p["text"] for p in partes)
    return out


def text_at(con: sqlite3.Connection, scene_id: str, version: int, current: str) -> str:
    """RF-204. El texto guardado con la menor version >= `version`, o el vigente."""
    if not _has(con, "scene_text_history"):
        return current
    row = con.execute(
        "SELECT text FROM scene_text_history WHERE scene_id = ? AND until_version >= ? "
        "ORDER BY until_version LIMIT 1",
        (scene_id, version),
    ).fetchone()
    return current if row is None else str(row["text"])


def _changed_in(con: sqlite3.Connection, scene_id: str, version: int) -> bool:
    """Una escena cambio en `version` si su texto anterior se guardo hasta `version - 1`."""
    if version <= FIRST_VERSION or not _has(con, "scene_text_history"):
        return False
    return (
        con.execute(
            "SELECT 1 FROM scene_text_history WHERE scene_id = ? AND until_version = ?",
            (scene_id, version - 1),
        ).fetchone()
        is not None
    )


class SceneAt(BaseModel):
    """RI-44. Una escena tal como estaba en una version."""

    model_config = ConfigDict(frozen=True)

    scene_id: str
    scene_number: int
    pov: str
    text: str
    changed: bool = Field(description="Reescrita en esta version respecto a la anterior")


def chapter_at(con: sqlite3.Connection, chapter: int, version: int) -> list[SceneAt] | None:
    """RF-206. `None` si el capitulo no esta en esa version."""
    if chapter not in chapters_in(con, version):
        return None
    rows = con.execute(
        "SELECT id, scene_number, pov_entity FROM prose_scene WHERE chapter = ? ORDER BY scene_number",
        (chapter,),
    ).fetchall()
    actuales = _current_texts(con, [r["id"] for r in rows])
    return [
        SceneAt(
            scene_id=r["id"],
            scene_number=r["scene_number"],
            pov=r["pov_entity"],
            text=text_at(con, r["id"], version, actuales[r["id"]]),
            changed=_changed_in(con, r["id"], version),
        )
        for r in rows
    ]


class ChapterEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: int
    title: str | None = Field(description="Nulo mientras la escaleta no tenga almacen (D-79)")
    words: int
    changed: bool


class Manifest(BaseModel):
    """RI-43. Portada e indice de una version."""

    model_config = ConfigDict(frozen=True)

    version: int
    current: bool
    title: str
    dedication: str
    recipient_name: str
    chapters: tuple[ChapterEntry, ...]


def manifest(
    con: sqlite3.Connection, version: int, *, title: str, dedication: str, recipient_name: str
) -> Manifest | None:
    """RF-205. `None` si la version no existe."""
    todas = {v.number: v for v in versions(con)}
    if version not in todas:
        return None
    cambiados = set(todas[version].changed_chapters)
    entradas = []
    for c in chapters_in(con, version):
        escenas = chapter_at(con, c, version) or []
        entradas.append(
            ChapterEntry(
                number=c,
                title=None,
                words=sum(_words(s.text) for s in escenas),
                changed=c in cambiados,
            )
        )
    return Manifest(
        version=version,
        current=todas[version].current,
        title=title,
        dedication=dedication,
        recipient_name=recipient_name,
        chapters=tuple(entradas),
    )


# --------------------------------------------------------- solicitudes de cambio


class Interpretation(BaseModel):
    """Lo que el sistema entendio: exactamente una entidad y un atributo (RI-52)."""

    model_config = ConfigDict(frozen=True)

    entity_id: str
    attribute: str
    previous_value: str
    new_value: str


class ChangeRequest(BaseModel):
    """RI-49. Una solicitud y lo que el sistema hizo con ella."""

    model_config = ConfigDict(frozen=True)

    request_id: int
    text: str
    anchor: dict[str, str | int]
    status: str
    interpretation: Interpretation | None
    reason: str
    version: int | None
    changed_chapters: tuple[int, ...]
    created_at: str
    updated_at: str


def _request(r: sqlite3.Row) -> ChangeRequest:
    interp = (
        Interpretation(
            entity_id=r["entity_id"],
            attribute=r["attribute"],
            previous_value=r["previous_value"] or "",
            new_value=r["new_value"] or "",
        )
        if r["entity_id"] is not None
        else None
    )
    return ChangeRequest(
        request_id=r["id"],
        text=r["text"],
        anchor=json.loads(r["anchor"]),
        status=r["status"],
        interpretation=interp,
        reason=r["reason"],
        version=r["version"],
        changed_chapters=tuple(json.loads(r["changed_chapters"])),
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def requests(con: sqlite3.Connection) -> list[ChangeRequest]:
    if not _has(con, "change_request"):
        return []
    return [_request(r) for r in con.execute("SELECT * FROM change_request ORDER BY id")]


def request(con: sqlite3.Connection, request_id: int) -> ChangeRequest | None:
    if not _has(con, "change_request"):
        return None
    row = con.execute("SELECT * FROM change_request WHERE id = ?", (request_id,)).fetchone()
    return None if row is None else _request(row)


def insert_request(
    con: sqlite3.Connection,
    *,
    text: str,
    anchor: Mapping[str, str | int],
    interpretation: Interpretation | None,
    reason: str,
) -> int:
    """RF-222. `queued` si hay interpretacion; `rejected` con motivo si no."""
    status = "queued" if interpretation is not None else "rejected"
    cur = con.execute(
        "INSERT INTO change_request (text, anchor, status, entity_id, attribute, previous_value, "
        "new_value, reason, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?, datetime('now'), datetime('now'))",
        (
            text,
            json.dumps(dict(anchor), ensure_ascii=False),
            status,
            interpretation.entity_id if interpretation else None,
            interpretation.attribute if interpretation else None,
            interpretation.previous_value if interpretation else None,
            interpretation.new_value if interpretation else None,
            reason,
        ),
    )
    return int(cur.lastrowid or 0)


def set_status(con: sqlite3.Connection, request_id: int, status: str, *, reason: str = "") -> None:
    if status not in STATUSES:
        raise ValueError(f"estado desconocido: {status}")
    con.execute(
        "UPDATE change_request SET status = ?, reason = ?, updated_at = datetime('now') WHERE id = ?",
        (status, reason, request_id),
    )


def next_queued(con: sqlite3.Connection) -> ChangeRequest | None:
    """La mas antigua pendiente. Una que quedo en `applying` por una caida vuelve a la cola (RF-226)."""
    con.execute("UPDATE change_request SET status = 'queued' WHERE status = 'applying'")
    row = con.execute(
        "SELECT * FROM change_request WHERE status = 'queued' ORDER BY id LIMIT 1"
    ).fetchone()
    return None if row is None else _request(row)


def commit_amendment(
    con: sqlite3.Connection,
    *,
    request_id: int,
    plan: RetconPlan,
    event: Event,
    prepared: refreeze.PreparedRefreeze,
    old_texts: Mapping[str, str],
    chapter_summaries: Mapping[int, str],
) -> int:
    """RF-203, RF-224, RNF-50. Todo junto o nada; quien llama abre `canon_writer`.

    Guarda el texto anterior de cada escena reescrita, recongela con el evento de
    procedencia `brief`, crea la version y marca la solicitud aplicada. Devuelve
    la version nueva.
    """
    nueva = current_version(con) + 1
    for sid, texto in old_texts.items():
        con.execute(
            "INSERT INTO scene_text_history (scene_id, until_version, text) VALUES (?, ?, ?)",
            (sid, nueva - 1, texto),
        )
    capitulos_de = {
        r["id"]: r["chapter"] for r in con.execute("SELECT id, chapter FROM prose_scene")
    }
    congelados = _frozen_chapters(con)
    ultimo = congelados[-1] if congelados else 0
    if prepared.scenes:
        refreeze.commit(
            con,
            prepared,
            retcon=plan,
            event=event,
            chapter_summaries=chapter_summaries,
            rule="enmienda al brief: el brief gana sobre el canon derivado (PRO-10)",
            chapter_origin=max(1, ultimo),
        )
    else:
        # Nada que reescribir: el hecho no se nombra en ninguna escena congelada.
        antes = usage.vigente(con)
        log.append(con, [event])
        rebuild.rebuild(con)
        # RF-241. El valor nuevo puede estar ya en la prosa.
        usage.refresh(con, scenes=(), before=antes)
    cambiados = sorted(
        {capitulos_de[s.scene_id] for s in prepared.scenes if s.scene_id in capitulos_de}
    )
    con.execute(
        "INSERT INTO manuscript_version (version, cause, changed_chapters, max_chapter, created_at) "
        "VALUES (?, ?, ?, ?, datetime('now'))",
        (nueva, request_id, json.dumps(cambiados), ultimo),
    )
    con.execute(
        "UPDATE change_request SET status = 'applied', reason = '', version = ?, changed_chapters = ?, "
        "updated_at = datetime('now') WHERE id = ?",
        (nueva, json.dumps(cambiados), request_id),
    )
    return nueva
