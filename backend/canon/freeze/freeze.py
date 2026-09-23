"""La congelacion. El punto donde el texto se convierte en verdad.

RF-57, RF-58, RF-68, RF-108, PRO-I1. `architecture.md` §3.3 y §10.

Es **la unica operacion que escribe canon**, y esta partida en dos mitades a
proposito:

**Fuera de la transaccion**, con el capitulo ya aprobado: cortar los fragmentos,
generar los resumenes y calcular los vectores. Es la parte cara --cientos de
vectores por capitulo-- y una transaccion abierta mientras se calculan bloquea
el fichero sin motivo.

**Dentro y todo junto o nada**: aplicar los eventos, recalcular proyecciones,
insertar el indice, escribir resumenes, insertar en la proscripcion y purgar la
memoria de trabajo.

Escribirlo al reves es el error que parece inocuo y no lo es: deja el fichero
bloqueado durante segundos y, si el proceso cae a mitad, el estado a medias.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from canon.events import log
from canon.events.types import Event
from canon.freeze import rows
from canon.projections import rebuild
from canon.prose_index.chunk import Chunk, chunk_scene
from canon.summaries import levels
from commons.provider.port import Embedding
from commons.types.primitives import WorldTime


class SceneToFreeze(BaseModel):
    """Una escena aprobada, lista para congelarse."""

    model_config = ConfigDict(frozen=True)

    id: str
    chapter: int
    scene_number: int = Field(ge=1)
    pov_entity: str
    place_entity: str | None = None
    world_time: WorldTime
    function: str
    text: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    present: tuple[str, ...] = Field(default_factory=tuple)


class PreparedChapter(BaseModel):
    """Lo calculado fuera de la transaccion, listo para escribirse."""

    model_config = ConfigDict(frozen=True)

    chapter: int
    scenes: tuple[SceneToFreeze, ...]
    chunks: tuple[Chunk, ...]
    chunk_vectors: tuple[Embedding, ...]
    scene_vectors: tuple[Embedding, ...]
    chapter_summary: str
    new_proscribed: tuple[tuple[str, str], ...] = Field(
        default_factory=tuple, description="Pares (termino, tipo) que este capitulo hace repetidos"
    )
    delta: tuple[Event, ...] = Field(default_factory=tuple)
    #: RF-116, RF-117. Resumenes de arco y de obra que este capitulo dispara,
    #: ya generados fuera de la transaccion.
    higher_summaries: tuple[levels.SummaryToWrite, ...] = Field(default_factory=tuple)
    #: RD-20, RD-21, RD-22. Preparadas por quien produce el estado; escritas aqui.
    verdicts: tuple[rows.SceneVerdictRow, ...] = Field(default_factory=tuple)
    fingerprint: rows.FingerprintRow | None = None
    metrics: tuple[rows.MetricRow, ...] = Field(default_factory=tuple)


def prepare(
    scenes: Sequence[SceneToFreeze],
    *,
    chapter: int,
    chapter_summary: str,
    embed: object,
    delta: Sequence[Event] = (),
    new_proscribed: Sequence[tuple[str, str]] = (),
    higher_summaries: Sequence[levels.SummaryToWrite] = (),
    verdicts: Sequence[rows.SceneVerdictRow] = (),
    fingerprint: rows.FingerprintRow | None = None,
    metrics: Sequence[rows.MetricRow] = (),
) -> PreparedChapter:
    """Primera mitad: todo lo caro, **fuera** de la transaccion.

    `embed` es cualquier cosa con `.embed(textos, is_query=...)`. Se inyecta en
    vez de importarse para que esta mitad se pueda comprobar sin cargar 2,24 GB
    de pesos.
    """
    chunks: list[Chunk] = []
    for scene in scenes:
        chunks.extend(chunk_scene(scene.id, scene.text))

    # Se indexa con el prefijo de pasaje, no el de consulta: el modelo los
    # distingue y mezclarlos recupera peor sin dar error.
    chunk_vecs = embed.embed([c.text for c in chunks], is_query=False) if chunks else []  # type: ignore[attr-defined]
    scene_vecs = embed.embed([s.summary for s in scenes], is_query=False) if scenes else []  # type: ignore[attr-defined]

    return PreparedChapter(
        chapter=chapter,
        scenes=tuple(scenes),
        chunks=tuple(chunks),
        chunk_vectors=tuple(chunk_vecs),
        scene_vectors=tuple(scene_vecs),
        chapter_summary=chapter_summary,
        new_proscribed=tuple(new_proscribed),
        delta=tuple(delta),
        higher_summaries=tuple(higher_summaries),
        verdicts=tuple(verdicts),
        fingerprint=fingerprint,
        metrics=tuple(metrics),
    )


def commit_chapter(con: sqlite3.Connection, prepared: PreparedChapter) -> None:
    """Segunda mitad: todo junto o nada.

    No abre ni cierra transaccion: quien llama lo hace con `canon_writer`, que
    revierte entero si algo lanza. Asi la frontera de la transaccion es visible
    en el sitio donde se decide, no escondida aqui.
    """
    from canon.prose_index.index import write_index

    if prepared.delta:
        log.append(con, prepared.delta)
        rebuild.apply_all(con, [s for s in log.read_all(con) if s.event in prepared.delta])

    write_index(con, prepared)
    _write_summaries(con, prepared)
    _write_proscribed(con, prepared)
    rows.write_verdicts(con, prepared.verdicts)
    rows.write_fingerprint(con, prepared.fingerprint)
    rows.write_metrics(con, prepared.metrics)
    purge_working_memory(con, prepared.chapter)


def _write_summaries(con: sqlite3.Connection, prepared: PreparedChapter) -> None:
    """Los cuatro niveles de CTX-06, cada uno con su version (RD-23)."""
    for scene in prepared.scenes:
        con.execute(
            "INSERT OR REPLACE INTO summary (level, ref_id, parent_ref, body, updated_at) "
            "VALUES ('scene', ?, ?, ?, datetime('now'))",
            (scene.id, str(prepared.chapter), scene.summary),
        )
    levels.write(
        con,
        [
            levels.SummaryToWrite(
                level="chapter",
                ref_id=str(prepared.chapter),
                body=prepared.chapter_summary,
                covers_to=prepared.chapter,
            ),
            *prepared.higher_summaries,
        ],
    )


def _write_proscribed(con: sqlite3.Connection, prepared: PreparedChapter) -> None:
    """RF-108. La lista de proscripcion la inserta **la congelacion**.

    No `check.repetition`, aunque sea quien detecta: el verificador opera sobre
    borradores, y un borrador puede acabar en cuarentena. Proscribir desde ahi
    condicionaria toda la obra por un texto que nunca existio. La lista es una
    proyeccion de la prosa congelada, igual que el indice.
    """
    con.executemany(
        "INSERT OR IGNORE INTO proscribed (term, kind, added_chapter, added_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        [(t, k, prepared.chapter) for t, k in prepared.new_proscribed],
    )


def purge_working_memory(con: sqlite3.Connection, chapter: int) -> None:
    """PRO-I1. Tras congelar no queda ninguna fila de memoria de trabajo.

    Se purga desde `canon/` y con la conexion de canon porque forma parte de la
    misma transaccion: purgar fuera dejaria una ventana en la que el capitulo
    esta congelado y sus borradores siguen vivos, y un borrador vivo de algo ya
    congelado es justo el material que no puede volver a un paquete.
    """
    for tabla in ("wm_draft", "wm_defect", "wm_verdict"):
        con.execute(f"DELETE FROM {tabla} WHERE chapter = ?", (chapter,))  # nosec B608
