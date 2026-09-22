"""El punto de reanudacion.

RF-20, PRO-I2, RNF-09. Lo que se comprueba: se escribe por escena, descarta lo
posterior, y una caida pierde como mucho una escena.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from canon.db import connection
from commons.db.working_memory import working_memory_writer
from orchestration.checkpoint import ResumePoint, clear, load, save


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    connection.create(path)
    return path


def _borrador(path: Path, chapter: int, scene: int) -> None:
    with working_memory_writer(path) as wm:
        wm.execute(
            "INSERT INTO wm_draft (chapter, scene_number, text, created_at) "
            "VALUES (?, ?, 'texto', datetime('now'))",
            (chapter, scene),
        )


def _borradores(path: Path) -> list[int]:
    con = sqlite3.connect(path)
    filas = [r[0] for r in con.execute("SELECT scene_number FROM wm_draft ORDER BY 1")]
    con.close()
    return filas


def test_sin_tirada_no_hay_punto(novela: Path) -> None:
    assert load(novela) is None


def test_se_guarda_y_se_recupera(novela: Path) -> None:
    save(novela, ResumePoint(chapter=3, last_closed_scene=2))
    punto = load(novela)
    assert punto is not None
    assert (punto.chapter, punto.last_closed_scene) == (3, 2)


def test_la_siguiente_escena_sale_del_punto(novela: Path) -> None:
    assert ResumePoint(chapter=1).next_scene() == 1
    assert ResumePoint(chapter=1, last_closed_scene=4).next_scene() == 5


def test_guardar_descarta_los_borradores_posteriores(novela: Path) -> None:
    """PRO-I2. Un borrador posterior puede estar a medias y no ha pasado ninguna
    puerta: conservarlo dejaria entrar texto que nadie aprobo por la puerta de
    atras de una interrupcion."""
    for escena in (1, 2, 3, 4):
        _borrador(novela, 3, escena)

    save(novela, ResumePoint(chapter=3, last_closed_scene=2))
    assert _borradores(novela) == [1, 2]


def test_una_caida_pierde_como_mucho_una_escena(novela: Path) -> None:
    """RNF-09. Se guarda al cerrar CADA escena, asi que lo perdido es siempre la
    que estaba en curso."""
    save(novela, ResumePoint(chapter=2, last_closed_scene=1))
    _borrador(novela, 2, 2)  # la que estaba escribiendose cuando cayo

    punto = load(novela)
    assert punto is not None
    assert punto.next_scene() == 2  # se reanuda justo en la que se perdio


def test_el_punto_sobrevive_a_la_congelacion(novela: Path) -> None:
    """Se borra al terminar la obra, no al congelar un capitulo: si se borrara,
    una caida justo despues de congelar dejaria la tirada sin saber por donde
    iba."""
    from canon.freeze.freeze import purge_working_memory

    save(novela, ResumePoint(chapter=2, last_closed_scene=3))
    with connection.canon_writer(novela) as con:
        purge_working_memory(con, chapter=2)

    assert load(novela) is not None


def test_al_terminar_la_obra_se_limpia(novela: Path) -> None:
    save(novela, ResumePoint(chapter=9, last_closed_scene=4))
    clear(novela)
    assert load(novela) is None
