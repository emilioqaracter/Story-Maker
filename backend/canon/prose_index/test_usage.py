"""Hecho x escena, el registro `fact_usage`. RF-241, RD-39, D-89. VER-05, VER-06.

La igualdad con `orchestration/amend.py:affected_scenes` se prueba en
`orchestration/test_fact_usage.py`: `canon/` no importa de `orchestration/`.
"""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Sequence
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from canon import manuscript
from canon.arbiter import refreeze
from canon.arbiter.retcon import RetconPlan
from canon.brief import create_novel
from canon.db import connection
from canon.events import log
from canon.events.types import AttributeSet, Event
from canon.freeze.freeze import SceneToFreeze, commit_chapter, prepare
from canon.prose_index import usage
from canon.prose_index.reindex import scene_texts
from canon.test_manuscript import _brief, _congelar, _Embedder, _escena
from commons.types.primitives import Provenance, WorldTime


def _filas(path: Path) -> list[tuple[str, str, int]]:
    with connection.reader(path) as con:
        return [
            (r["fact_key"], r["scene_id"], r["chapter"])
            for r in con.execute(
                "SELECT fact_key, scene_id, chapter FROM fact_usage ORDER BY chapter, scene_id, fact_key"
            )
        ]


def _fuente(path: Path, entidad: str, atributo: str) -> int:
    with connection.reader(path) as con:
        return int(
            con.execute(
                "SELECT source_event FROM attribute WHERE entity_id = ? AND name = ? AND valid_to IS NULL",
                (entidad, atributo),
            ).fetchone()[0]
        )


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    """El color de Rex sale en el capitulo 1 y no en el 2."""
    path = tmp_path / "usos.sqlite"
    create_novel(path, _brief())
    _congelar(
        path,
        1,
        [
            _escena(1, 1, "Rex, negro como el carbón, corrió.", ("lucia", "rex")),
            _escena(1, 2, "Lucía miró el cielo negro sin luna.", ("lucia",)),
        ],
    )
    _congelar(path, 2, [_escena(2, 1, "Rex ladró al ver la pelota.", ("lucia", "rex"))])
    return path


def test_congelar_dos_capitulos_registra_el_hecho_solo_donde_se_usa(novela: Path) -> None:
    """RF-241. «negro» sin Rex presente no es un uso del color de Rex."""
    assert _filas(novela) == [("rex.color", "c1e1", 1)]
    with connection.reader(novela) as con:
        assert usage.scenes_using(con, "rex", "color") == ["c1e1"]
        assert usage.chapters_using(con, "rex", "color") == [1]
        fuente = con.execute("SELECT source_event FROM fact_usage").fetchone()[0]
    assert fuente == _fuente(novela, "rex", "color")


def test_la_edad_de_lucia_no_se_usa_si_su_valor_no_esta_en_el_texto(novela: Path) -> None:
    with connection.reader(novela) as con:
        assert usage.scenes_using(con, "lucia", "edad") == []


def test_por_palabra_completa_y_sin_mayusculas(tmp_path: Path) -> None:
    """La regla de `affected_scenes`: palabra completa, sin distinguir mayusculas."""
    path = tmp_path / "palabra.sqlite"
    create_novel(path, _brief())
    _congelar(
        path,
        1,
        [
            _escena(1, 1, "NEGRO era Rex.", ("rex",)),
            _escena(1, 2, "Rex y los negros nubarrones.", ("rex",)),
            _escena(1, 3, "Rex ennegrecido.", ("rex",)),
        ],
    )
    with connection.reader(path) as con:
        assert usage.scenes_using(con, "rex", "color") == ["c1e1"]


def test_un_valor_cambiado_por_el_delta_se_busca_en_todas_las_escenas(tmp_path: Path) -> None:
    """El valor vigente cambia al congelar el 2: el registro deja el viejo y busca el nuevo en el 1."""
    path = tmp_path / "delta.sqlite"
    create_novel(path, _brief())
    _congelar(
        path,
        1,
        [
            _escena(1, 1, "Rex, negro, corrió.", ("rex",)),
            _escena(1, 2, "Rex tenía una mancha gris.", ("rex",)),
        ],
    )
    with connection.canon_writer(path) as con:
        instante = "2026-08-21"
        delta = Event(
            world_time=WorldTime(stamp=instante, seq=log.next_seq(con, instante)),
            payload=AttributeSet(entity_id="rex", name="color", value="gris"),
            provenance=Provenance.PROSE,
            chapter_origin=2,
            entities=frozenset({"rex"}),
        )
        commit_chapter(
            con,
            prepare(
                [_escena(2, 1, "Rex, ya gris, durmió.", ("rex",))],
                chapter=2,
                chapter_summary="cap 2",
                embed=_Embedder(),
                delta=[delta],
            ),
        )
    assert _filas(path) == [("rex.color", "c1e2", 1), ("rex.color", "c2e1", 2)]
    with connection.reader(path) as con:
        assert usage.scenes_using(con, "rex", "color") == ["c1e2", "c2e1"]
        fuentes = {r[0] for r in con.execute("SELECT source_event FROM fact_usage")}
    assert fuentes == {_fuente(path, "rex", "color")}


def _enmendar_color(path: Path, nuevo: str) -> int:
    """Una enmienda de atributo con un Reparador de reemplazo literal."""
    with connection.reader(path) as con:
        textos = scene_texts(con)
        viejo, desde = con.execute(
            "SELECT value, valid_from FROM attribute WHERE entity_id='rex' AND name='color' AND valid_to IS NULL"
        ).fetchone()
        escenas = usage.scenes_using(con, "rex", "color") or []
    with connection.canon_writer(path) as con:
        rid = manuscript.insert_request(
            con,
            text=f"Rex es {nuevo}",
            anchor={"entity_id": "rex", "attribute": "color"},
            interpretation=manuscript.Interpretation(
                entity_id="rex", attribute="color", previous_value=viejo, new_value=nuevo
            ),
            reason="",
        )
    plan = RetconPlan(
        fact_key="rex.color",
        entity_id="rex",
        attribute="color",
        previous_value=viejo,
        new_value=nuevo,
        frozen_since=desde,
        scenes=tuple(escenas),
        paid=False,
    )
    nuevas = [
        refreeze.RefrozenScene(scene_id=s, text=textos[s].replace(viejo, nuevo), summary=f"r {s}")
        for s in escenas
    ]
    with connection.canon_writer(path) as con:
        evento = Event(
            world_time=WorldTime(stamp=desde, seq=log.next_seq(con, desde)),
            payload=AttributeSet(entity_id="rex", name="color", value=nuevo),
            provenance=Provenance.BRIEF,
            chapter_origin=None,
            entities=frozenset({"rex"}),
        )
        return manuscript.commit_amendment(
            con,
            request_id=rid,
            plan=plan,
            event=evento,
            prepared=refreeze.prepare(nuevas, embed=_Embedder()),
            old_texts={s: textos[s] for s in escenas},
            chapter_summaries={1: "cap 1 bis"},
        )


def test_tras_enmendar_las_filas_apuntan_a_las_escenas_recongeladas_con_el_hecho_nuevo(
    novela: Path,
) -> None:
    """RF-241: recongelar reescribe las filas; no queda ninguna del valor anterior."""
    anterior = _fuente(novela, "rex", "color")
    assert _enmendar_color(novela, "blanco") == 2
    assert _filas(novela) == [("rex.color", "c1e1", 1)]
    with connection.reader(novela) as con:
        fuentes = {r[0] for r in con.execute("SELECT source_event FROM fact_usage")}
    assert fuentes == {_fuente(novela, "rex", "color")}
    assert anterior not in fuentes


def test_una_enmienda_que_no_toca_escenas_tambien_refresca_el_registro(tmp_path: Path) -> None:
    """Sin escenas que reescribir, el valor nuevo puede estar ya en la prosa."""
    path = tmp_path / "sin-escenas.sqlite"
    create_novel(path, _brief())
    _congelar(path, 1, [_escena(1, 1, "Rex, blanco como la nieve, corrió.", ("rex",))])
    with connection.reader(path) as con:
        assert usage.scenes_using(con, "rex", "color") == []
    _enmendar_color(path, "blanco")
    with connection.reader(path) as con:
        assert usage.scenes_using(con, "rex", "color") == ["c1e1"]


def test_la_insercion_incremental_es_la_reconstruccion_desde_cero(novela: Path) -> None:
    _enmendar_color(novela, "blanco")
    antes = _filas(novela)
    with connection.canon_writer(novela) as con:
        con.execute("DELETE FROM fact_usage")
        usage.rebuild(con)
    assert _filas(novela) == antes


def test_un_fichero_sin_el_registro_no_da_respuesta_en_lectura(tmp_path: Path) -> None:
    """Leer no migra (RI-35): sin la tabla, `None` y no una lista vacia que mienta."""
    path = tmp_path / "viejo.sqlite"
    create_novel(path, _brief())
    con = sqlite3.connect(path)
    con.execute("DROP TABLE fact_usage")
    con.commit()
    con.close()
    with connection.reader(path) as lector:
        assert usage.scenes_using(lector, "rex", "color") is None


# ------------------------------------------------------------------ propiedad

_PALABRAS = ("Rex", "negro", "Negro", "negros", "blanco", "gris", "diez", "10", "corrió", "el")
_ELENCOS = st.sets(st.sampled_from(("lucia", "rex")), max_size=2)
_ESCENA = st.tuples(st.lists(st.sampled_from(_PALABRAS), min_size=1, max_size=8), _ELENCOS)
_CAPITULO = st.lists(_ESCENA, min_size=1, max_size=3)
_PASO: st.SearchStrategy[tuple[str, list[tuple[list[str], set[str]]], str | None]] = st.one_of(
    st.tuples(st.just("capitulo"), _CAPITULO, st.none()),
    st.tuples(st.just("delta"), _CAPITULO, st.sampled_from(("negro", "gris", "blanco"))),
    st.tuples(st.just("enmienda"), st.just([]), st.sampled_from(("negro", "gris", "blanco"))),
)


def _escenas(cap: int, datos: Sequence[tuple[list[str], set[str]]]) -> list[SceneToFreeze]:
    return [
        _escena(cap, n, " ".join(palabras) + ".", tuple(sorted(elenco)))
        for n, (palabras, elenco) in enumerate(datos, start=1)
    ]


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(pasos=st.lists(_PASO, min_size=1, max_size=5))
def test_propiedad_el_registro_incremental_es_la_reconstruccion(
    pasos: list[tuple[str, list[tuple[list[str], set[str]]], str | None]],
) -> None:
    """RF-241, VER-06: para cualquier secuencia de congelaciones, deltas y enmiendas,
    el registro que se mantiene paso a paso es el que se reconstruye desde cero."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "p.sqlite"
        create_novel(path, _brief())
        cap = 0
        for kind, datos, valor in pasos:
            if kind == "enmienda" and valor is not None:
                if cap:
                    _enmendar_color(path, valor)
                continue
            cap += 1
            delta: list[Event] = []
            if kind == "delta" and valor is not None:
                with connection.reader(path) as con:
                    instante = f"2026-08-{cap}0"
                    delta = [
                        Event(
                            world_time=WorldTime(stamp=instante, seq=log.next_seq(con, instante)),
                            payload=AttributeSet(entity_id="rex", name="color", value=valor),
                            provenance=Provenance.PROSE,
                            chapter_origin=cap,
                            entities=frozenset({"rex"}),
                        )
                    ]
            with connection.canon_writer(path) as con:
                commit_chapter(
                    con,
                    prepare(
                        _escenas(cap, datos),
                        chapter=cap,
                        chapter_summary=f"cap {cap}",
                        embed=_Embedder(),
                        delta=delta,
                    ),
                )
        incremental = _filas(path)
        with connection.canon_writer(path) as con:
            con.execute("DELETE FROM fact_usage")
            usage.rebuild(con)
        assert _filas(path) == incremental
