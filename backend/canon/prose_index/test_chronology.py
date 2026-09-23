"""La vista `chronology`. RF-242, RD-40, D-89. VER-05."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from canon.brief import create_novel
from canon.db import connection
from canon.freeze.freeze import SceneToFreeze
from canon.prose_index import chronology
from canon.test_manuscript import _brief, _congelar
from commons.types.primitives import WorldTime


def _escena(
    cap: int, n: int, instante: str, lugar: str | None, presentes: tuple[str, ...], seq: int = 0
) -> SceneToFreeze:
    return SceneToFreeze(
        id=f"c{cap}e{n}",
        chapter=cap,
        scene_number=n,
        pov_entity="lucia",
        place_entity=lugar,
        world_time=WorldTime(stamp=instante, seq=seq),
        function="establecer",
        text=f"Texto de la escena {cap}.{n}.",
        summary=f"resumen {cap}.{n}",
        present=presentes,
    )


def _novela(tmp_path: Path) -> Path:
    """El capitulo 1 es un recuerdo: ocurre despues que el 2 en el mundo, pero se congela antes."""
    path = tmp_path / "crono.sqlite"
    create_novel(path, _brief())
    _congelar(
        path,
        1,
        [
            _escena(1, 1, "2026-08-20T18:00", "parque", ("rex", "lucia")),
            _escena(1, 2, "2026-08-05", None, ()),
        ],
    )
    _congelar(
        path,
        2,
        [
            _escena(2, 1, "2026-08-02", "parque", ("rex",)),
            # Mismo instante que 1.2: a igualdad, capitulo y numero de escena.
            _escena(2, 2, "2026-08-05", "parque", ()),
        ],
    )
    return path


def test_la_cronologia_va_en_orden_de_mundo_aunque_se_congelara_en_otro(tmp_path: Path) -> None:
    """La puerta de T42: orden de mundo, no de congelacion."""
    path = _novela(tmp_path)
    with connection.reader(path) as con:
        filas = chronology.read(con)
        crudas = [r["scene_id"] for r in con.execute("SELECT scene_id FROM chronology")]
    assert [f.scene_id for f in filas] == ["c2e1", "c1e2", "c2e2", "c1e1"]
    assert crudas == ["c2e1", "c1e2", "c2e2", "c1e1"]


def test_cada_fila_trae_instante_lugar_presentes_y_resumen(tmp_path: Path) -> None:
    path = _novela(tmp_path)
    with connection.reader(path) as con:
        por_id = {f.scene_id: f for f in chronology.read(con)}
        cruda = con.execute("SELECT * FROM chronology WHERE scene_id = 'c1e1'").fetchone()
    f = por_id["c1e1"]
    assert (f.chapter, f.scene_number) == (1, 1)
    assert f.world_time == WorldTime(stamp="2026-08-20T18:00")
    assert (f.place_entity, f.pov_entity) == ("parque", "lucia")
    # El POV es un presente mas; la lista va ordenada y sin repetir.
    assert f.present == ("lucia", "rex")
    assert f.summary == "resumen 1.1"
    assert por_id["c1e2"].place_entity is None
    assert por_id["c1e2"].present == ("lucia",)
    assert json.loads(cruda["present"]) == ["lucia", "rex"]
    assert list(cruda.keys()) == list(chronology.COLUMNS)


def test_el_desempate_del_instante_cuenta_antes_que_el_capitulo(tmp_path: Path) -> None:
    path = tmp_path / "seq.sqlite"
    create_novel(path, _brief())
    _congelar(path, 1, [_escena(1, 1, "2026-08-03", "parque", (), seq=2)])
    _congelar(path, 2, [_escena(2, 1, "2026-08-03", "parque", (), seq=1)])
    with connection.reader(path) as con:
        assert [f.scene_id for f in chronology.read(con)] == ["c2e1", "c1e1"]


def test_es_una_vista_y_no_guarda_verdad_propia(tmp_path: Path) -> None:
    """RF-242: proyeccion del indice de prosa. Lo que cambia en `prose_scene` se ve sin mas."""
    path = _novela(tmp_path)
    with connection.reader(path) as con:
        tipo = con.execute("SELECT type FROM sqlite_master WHERE name = 'chronology'").fetchone()
    assert tipo[0] == "view"
    with connection.canon_writer(path) as con:
        con.execute("UPDATE prose_scene SET summary = 'otro' WHERE id = 'c2e1'")
    with connection.reader(path) as con:
        assert chronology.read(con)[0].summary == "otro"


def test_un_fichero_sin_la_vista_se_lee_igual(tmp_path: Path) -> None:
    """Leer no migra (RI-35): sin la vista, la misma consulta sobre las tablas."""
    path = _novela(tmp_path)
    with connection.reader(path) as con:
        esperado = chronology.read(con)
    con = sqlite3.connect(path)
    con.execute("DROP VIEW chronology")
    con.commit()
    con.close()
    with connection.reader(path) as con:
        assert chronology.read(con) == esperado


def test_sin_escenas_congeladas_la_cronologia_esta_vacia(tmp_path: Path) -> None:
    path = tmp_path / "vacia.sqlite"
    create_novel(path, _brief())
    with connection.reader(path) as con:
        assert chronology.read(con) == []
