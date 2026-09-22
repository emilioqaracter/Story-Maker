"""Punto de reanudacion.

RF-20, PRO-14, PRO-I2, RNF-08, RNF-09. `architecture.md` §7.4.

Se escribe **al cerrar cada escena**, no cada llamada. Por escena y no por
llamada porque la escena **ya es** la unidad de reintento: reanudar por ahi
reaprovecha una frontera que el diseno tiene, en vez de inventar otra. Persistir
cada llamada obligaria a serializar su paquete de contexto y multiplicaria la
escritura sin comprar nada.

Al arrancar con un capitulo sin congelar se reanuda desde la ultima escena
cerrada y **se descarta todo borrador posterior**: puede estar a medias y no ha
pasado ninguna puerta. Conservarlo seria dejar entrar al ciclo texto que nadie
aprobo, por la puerta de atras de una interrupcion.

Usa la conexion de **memoria de trabajo** (D-30), no la de canon: el punto de
reanudacion es estado efimero, y confundirlo con canon es lo que la separacion
de fabricas existe para impedir.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from commons.db.working_memory import working_memory_writer


class ResumePoint(BaseModel):
    """Desde donde sigue una tirada interrumpida."""

    model_config = ConfigDict(frozen=True)

    chapter: int = Field(ge=1)
    last_closed_scene: int | None = Field(
        default=None, description="`None` si el capitulo no ha cerrado ninguna aun"
    )
    step: str = Field(default="scene_loop")

    def next_scene(self) -> int:
        return 1 if self.last_closed_scene is None else self.last_closed_scene + 1


def save(path: Path, point: ResumePoint) -> None:
    """Escribe el punto de reanudacion y descarta lo posterior.

    Las dos cosas van juntas y en la misma transaccion a proposito: guardar el
    punto sin limpiar dejaria borradores de escenas que el punto dice que no
    existen, y al reanudar habria material sin dueno con aspecto de valido.
    """
    with working_memory_writer(path) as wm:
        wm.execute(
            "INSERT INTO wm_run_state (id, chapter, last_closed_scene, step, updated_at) "
            "VALUES (1, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(id) DO UPDATE SET chapter=excluded.chapter, "
            "  last_closed_scene=excluded.last_closed_scene, step=excluded.step, "
            "  updated_at=excluded.updated_at",
            (point.chapter, point.last_closed_scene, point.step),
        )
        wm.execute(
            "DELETE FROM wm_draft WHERE chapter = ? AND scene_number > ?",
            (point.chapter, point.last_closed_scene or 0),
        )


def load(path: Path) -> ResumePoint | None:
    """Lee el punto de reanudacion. `None` si la tirada no ha empezado."""
    import sqlite3

    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT chapter, last_closed_scene, step FROM wm_run_state WHERE id = 1"
        ).fetchone()
    finally:
        con.close()

    if row is None:
        return None
    return ResumePoint(
        chapter=row["chapter"],
        last_closed_scene=row["last_closed_scene"],
        step=row["step"],
    )


def clear(path: Path) -> None:
    """Borra el punto. Se llama al terminar la obra, no al congelar un capitulo.

    Al congelar se purga la memoria de trabajo del capitulo, pero el punto de
    reanudacion tiene que sobrevivir: si se borrara, una caida justo despues de
    congelar dejaria la tirada sin saber por donde iba.
    """
    with working_memory_writer(path) as wm:
        wm.execute("DELETE FROM wm_run_state WHERE id = 1")
