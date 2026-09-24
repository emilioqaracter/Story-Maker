"""La congelacion es todo o nada. RF-57, D-130. VER-05.

La puerta 1 descarta el hecho sobre una entidad desconocida antes de congelar
(`canon/arbiter/entries.py`). Esto es la red de debajo: si aun asi llegara a
`commit_chapter` un delta que rompe una clave ajena, la transaccion se revierte
entera y el fichero queda como estaba.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pytest

from canon.arbiter.entries import validate_delta
from canon.brief import Brief, BriefEntity, create_novel
from canon.db import connection
from canon.events.types import AttributeSet, Event
from canon.freeze.freeze import SceneToFreeze, commit_chapter, prepare
from commons.provider.port import Embedding
from commons.types.primitives import Provenance, WorldTime


class _Embed:
    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        return [Embedding(values=(0.1,), model_id="d", dimension=1) for _ in texts]


def _novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    create_novel(
        path,
        Brief(
            title="p",
            start=WorldTime(stamp="2026-01-01"),
            entities=(BriefEntity(id="marcos", kind="person", name="Marcos"),),
            style_guide="x",
            target_words=1000,
        ),
    )
    return path


def _escena() -> SceneToFreeze:
    return SceneToFreeze(
        id="c1e1",
        chapter=1,
        scene_number=1,
        pov_entity="marcos",
        world_time=WorldTime(stamp="2026-01-02"),
        function="establecer",
        text="Marcos entro en el vestuario y la cometa quedo rota.",
        summary="s",
        present=("marcos",),
    )


def _set(entity: str, value: str, seq: int) -> Event:
    return Event(
        world_time=WorldTime(stamp="2026-01-02", seq=seq),
        payload=AttributeSet(entity_id=entity, name="estado", value=value),
        provenance=Provenance.PROSE,
        chapter_origin=1,
        entities=frozenset({entity}),
    )


def _foto(path: Path) -> dict[str, int]:
    tablas = ("event", "attribute", "prose_scene", "prose_chunk", "summary", "wm_draft")
    with connection.reader(path) as con:
        return {
            t: con.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"]  # nosec B608
            for t in tablas
        }


def test_una_clave_ajena_rota_revierte_la_congelacion_entera(tmp_path: Path) -> None:
    """Sin validar, el delta de eval-02 revienta en la proyeccion; no queda nada a medias."""
    path = _novela(tmp_path)
    antes = _foto(path)
    delta = [_set("marcos", "sano", 1), _set("cometa", "rota", 2)]
    preparado = prepare(
        [_escena()], chapter=1, chapter_summary="c", embed=_Embed(), delta=delta
    )

    with pytest.raises(sqlite3.IntegrityError), connection.canon_writer(path) as con:
        commit_chapter(con, preparado)

    assert _foto(path) == antes


def test_el_delta_validado_congela_sin_el_hecho_desconocido(tmp_path: Path) -> None:
    """D-130. La puerta 1 lo descarta y el resto se congela."""
    path = _novela(tmp_path)
    antes = _foto(path)
    with connection.reader(path) as con:
        validacion = validate_delta(con, [_set("marcos", "sano", 1), _set("cometa", "rota", 2)])
    assert [d.entity for d in validacion.dropped] == ["cometa"]

    preparado = prepare(
        [_escena()], chapter=1, chapter_summary="c", embed=_Embed(), delta=validacion.accepted
    )
    with connection.canon_writer(path) as con:
        commit_chapter(con, preparado)

    despues = _foto(path)
    assert despues["event"] == antes["event"] + 1
    assert despues["prose_scene"] == 1
    with connection.reader(path) as con:
        fila = con.execute(
            "SELECT value FROM attribute WHERE entity_id = 'marcos' AND name = 'estado'"
        ).fetchone()
    assert fila["value"] == "sano"
