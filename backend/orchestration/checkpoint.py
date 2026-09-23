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

Ademas del capitulo y la escena, el punto guarda dos cosas que una caida no
puede perder:

- **La cuenta de reintentos consumidos** del capitulo en curso
  (`architecture.md` §7.4). Sin ella cada caida regalaria una escalera entera:
  el contraejemplo B4 de `orchestration/model/README.md` §7.1.
- **La escaleta vigente**, con las replanificaciones de acto, de Supervisor y
  de cuarentena ya hechas. Sin ella reanudar volveria a pedirla desde el brief
  y los capitulos que faltan se escribirian contra otra (R1). No es canon
  (RI-17): es estado de la tirada, y se va con el punto.
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
    #: `architecture.md` §7.4. Los peldanos de capitulo y de tramo que el
    #: capitulo en curso ya gasto. El de escena no: se reinicia en cada escena.
    chapter_attempts: int = Field(default=0, ge=0)
    arc_replans: int = Field(default=0, ge=0)

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
            "INSERT INTO wm_run_state (id, chapter, last_closed_scene, step, "
            "  chapter_attempts, arc_replans, updated_at) "
            "VALUES (1, ?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(id) DO UPDATE SET chapter=excluded.chapter, "
            "  last_closed_scene=excluded.last_closed_scene, step=excluded.step, "
            "  chapter_attempts=excluded.chapter_attempts, arc_replans=excluded.arc_replans, "
            "  updated_at=excluded.updated_at",
            (
                point.chapter,
                point.last_closed_scene,
                point.step,
                point.chapter_attempts,
                point.arc_replans,
            ),
        )
        wm.execute(
            "DELETE FROM wm_draft WHERE chapter = ? AND scene_number > ?",
            (point.chapter, point.last_closed_scene or 0),
        )


def save_budget(path: Path, *, chapter: int, chapter_attempts: int, arc_replans: int) -> None:
    """Guarda los reintentos consumidos en cuanto cambian, sin mover el punto.

    Un peldano de capitulo o de tramo se gasta a mitad de escena --al
    reespecificarla-- o entre dos pases del capitulo. Esperar a que la escena
    cierre para guardarlo dejaria una ventana en la que una caida lo devuelve.
    No toca la escena cerrada ni los borradores: solo la cuenta.
    """
    with working_memory_writer(path) as wm:
        wm.execute(
            "INSERT INTO wm_run_state (id, chapter, last_closed_scene, step, "
            "  chapter_attempts, arc_replans, updated_at) "
            "VALUES (1, ?, NULL, 'scene_loop', ?, ?, datetime('now')) "
            "ON CONFLICT(id) DO UPDATE SET chapter_attempts=excluded.chapter_attempts, "
            "  arc_replans=excluded.arc_replans, updated_at=excluded.updated_at",
            (chapter, chapter_attempts, arc_replans),
        )


def save_outline(path: Path, outline_json: str) -> None:
    """Guarda la escaleta vigente. Sin punto todavia, la tirada esta en el capitulo 1."""
    with working_memory_writer(path) as wm:
        wm.execute(
            "INSERT INTO wm_run_state (id, chapter, last_closed_scene, step, outline, updated_at) "
            "VALUES (1, 1, NULL, 'scene_loop', ?, datetime('now')) "
            "ON CONFLICT(id) DO UPDATE SET outline=excluded.outline, "
            "  updated_at=excluded.updated_at",
            (outline_json,),
        )


def _row(path: Path) -> dict[str, object] | None:
    import sqlite3

    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT * FROM wm_run_state WHERE id = 1").fetchone()
    finally:
        con.close()
    # `SELECT *` y no una lista de columnas: un fichero anterior a la version 6
    # del esquema se sigue pudiendo leer (leer no migra, RD-10).
    return None if row is None else dict(row)


def load(path: Path) -> ResumePoint | None:
    """Lee el punto de reanudacion. `None` si la tirada no ha empezado."""
    row = _row(path)
    if row is None:
        return None
    return ResumePoint(
        chapter=row["chapter"],  # type: ignore[arg-type]
        last_closed_scene=row["last_closed_scene"],  # type: ignore[arg-type]
        step=row["step"],  # type: ignore[arg-type]
        chapter_attempts=row.get("chapter_attempts") or 0,  # type: ignore[arg-type]
        arc_replans=row.get("arc_replans") or 0,  # type: ignore[arg-type]
    )


def load_outline(path: Path) -> str | None:
    """La escaleta vigente, en JSON. `None` si la tirada aun no la tiene."""
    row = _row(path)
    outline = None if row is None else row.get("outline")
    return None if outline is None else str(outline)


def clear(path: Path) -> None:
    """Borra el punto. Se llama al terminar la obra, no al congelar un capitulo.

    Al congelar se purga la memoria de trabajo del capitulo, pero el punto de
    reanudacion tiene que sobrevivir: si se borrara, una caida justo despues de
    congelar dejaria la tirada sin saber por donde iba.
    """
    with working_memory_writer(path) as wm:
        wm.execute("DELETE FROM wm_run_state WHERE id = 1")
