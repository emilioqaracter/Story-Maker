"""Versiones del manuscrito, fichas y renombrado. `specs/srs-backend-v3.md` §4.2. VER-05, VER-06."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from canon import entities, manuscript
from canon.arbiter import refreeze
from canon.arbiter.retcon import RetconPlan
from canon.brief import Brief, BriefEntity, create_novel
from canon.db import connection
from canon.events import log
from canon.events.types import EntityRenamed, Event
from canon.freeze.freeze import SceneToFreeze, commit_chapter, prepare
from canon.prose_index.reindex import scene_texts
from commons.provider.port import Embedding
from commons.types.primitives import Provenance, WorldTime

START = WorldTime(stamp="2026-08-01")


class _Embedder:
    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        return [Embedding(values=(0.1, 0.2), model_id="doble", dimension=2) for _ in texts]


def _brief() -> Brief:
    return Brief(
        title="El verano de Rex",
        start=START,
        entities=(
            BriefEntity(id="lucia", kind="person", name="Lucía", attributes=(("edad", "10"),)),
            BriefEntity(id="rex", kind="object", name="Rex", attributes=(("color", "negro"),)),
            BriefEntity(id="parque", kind="place", name="el parque"),
        ),
        style_guide="Tercera persona, pasado.",
        target_words=2000,
        dedication="Para Lucía",
    )


def _escena(cap: int, n: int, texto: str, present: tuple[str, ...]) -> SceneToFreeze:
    return SceneToFreeze(
        id=f"c{cap}e{n}",
        chapter=cap,
        scene_number=n,
        pov_entity="lucia",
        place_entity="parque",
        world_time=WorldTime(stamp=f"2026-08-{cap}{n}"),
        function="establecer",
        text=texto,
        summary=f"resumen {cap}.{n}",
        present=present,
    )


def _congelar(path: Path, cap: int, escenas: Sequence[SceneToFreeze]) -> None:
    prep = prepare(escenas, chapter=cap, chapter_summary=f"cap {cap}", embed=_Embedder())
    with connection.canon_writer(path) as con:
        commit_chapter(con, prep)


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    _congelar(
        path,
        1,
        [
            _escena(1, 1, "Lucía llegó al parque con Rex.", ("lucia", "rex")),
            _escena(1, 2, "Lucía miró las nubes sola.", ("lucia",)),
        ],
    )
    _congelar(path, 2, [_escena(2, 1, "Rex ladró al ver la pelota.", ("lucia", "rex"))])
    return path


def _rename(path: Path, request_text: str, old: str, new: str) -> int:
    """Lo que hara el Orquestador, con un Reparador de reemplazo literal."""
    with connection.canon_writer(path) as con:
        rid = manuscript.insert_request(
            con,
            text=request_text,
            anchor={"entity_id": "rex", "attribute": "nombre"},
            interpretation=manuscript.Interpretation(
                entity_id="rex", attribute="nombre", previous_value=old, new_value=new
            ),
            reason="",
        )
    with connection.reader(path) as con:
        textos = scene_texts(con)
        creado = con.execute("SELECT created_at FROM entity WHERE id = 'rex'").fetchone()[0]
    afectadas = [sid for sid, t in sorted(textos.items()) if old in t]
    nuevas = [
        refreeze.RefrozenScene(scene_id=s, text=textos[s].replace(old, new), summary=f"r {s}")
        for s in afectadas
    ]
    plan = RetconPlan(
        fact_key="rex.nombre",
        entity_id="rex",
        attribute="nombre",
        previous_value=old,
        new_value=new,
        frozen_since=creado,
        scenes=tuple(afectadas),
        paid=False,
    )
    with connection.canon_writer(path) as con:
        evento = Event(
            world_time=WorldTime(stamp=creado, seq=log.next_seq(con, creado)),
            payload=EntityRenamed(entity_id="rex", name=new),
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
            old_texts={s: textos[s] for s in afectadas},
            chapter_summaries={1: "cap 1 bis", 2: "cap 2 bis"},
        )


def _texto(path: Path, cap: int, version: int) -> list[str]:
    with connection.reader(path) as con:
        return [s.text for s in manuscript.chapter_at(con, cap, version) or []]


def test_sin_enmiendas_la_unica_version_es_la_tirada(novela: Path) -> None:
    with connection.reader(novela) as con:
        vs = manuscript.versions(con)
        m = manuscript.manifest(
            con, 1, title="El verano de Rex", dedication="Para Lucía", recipient_name="Lucía"
        )
    assert [(v.number, v.current, v.cause) for v in vs] == [(1, True, None)]
    assert m is not None and [c.number for c in m.chapters] == [1, 2]
    assert not any(c.changed for c in m.chapters) and m.chapters[0].title is None


def test_una_enmienda_crea_la_version_2_y_conserva_la_1(novela: Path) -> None:
    """RF-203, RF-204, RF-206. La 1 se lee igual; la 2 marca capitulos y escenas."""
    antes = [_texto(novela, 1, 1), _texto(novela, 2, 1)]
    assert _rename(novela, "el perro se llama Nala", "Rex", "Nala") == 2

    assert [_texto(novela, 1, 1), _texto(novela, 2, 1)] == antes
    assert _texto(novela, 1, 2) == ["Lucía llegó al parque con Nala.", "Lucía miró las nubes sola."]
    with connection.reader(novela) as con:
        v2 = manuscript.chapter_at(con, 1, 2) or []
        v1 = manuscript.chapter_at(con, 1, 1) or []
        vs = manuscript.versions(con)
        solicitud = manuscript.request(con, 1)
    assert [s.changed for s in v2] == [True, False]
    assert not any(s.changed for s in v1)
    assert [(v.number, v.current, v.changed_chapters) for v in vs] == [
        (1, False, ()),
        (2, True, (1, 2)),
    ]
    assert solicitud is not None and solicitud.status == "applied" and solicitud.version == 2


def test_el_renombrado_cambia_el_nombre_y_no_deja_alias(novela: Path) -> None:
    """RF-210, D-76."""
    _rename(novela, "el perro se llama Nala", "Rex", "Nala")
    with connection.reader(novela) as con:
        ficha = entities.entity_file(con, "rex")
        alias = con.execute("SELECT alias FROM entity_alias WHERE entity_id = 'rex'").fetchall()
    assert ficha is not None and ficha.entity.name == "Nala"
    assert alias == []


@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE scene_text_history SET text = 'otro'",
        "DELETE FROM scene_text_history",
        "UPDATE manuscript_version SET cause = 0",
    ],
)
def test_la_historia_no_se_reescribe(novela: Path, sentencia: str) -> None:
    """RD-34. Append-only: una version publicada no cambia, ni se borra su historia."""
    antes = _texto(novela, 1, 1)
    _rename(novela, "el perro se llama Nala", "Rex", "Nala")
    with connection.canon_writer(novela) as con, pytest.raises(sqlite3.DatabaseError):
        con.execute(sentencia)
    assert _texto(novela, 1, 1) == antes
    assert [v.number for v in manuscript_versions(novela)] == [1, 2]


@settings(
    max_examples=12, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(st.lists(st.sampled_from(["Nala", "Toby", "Luna", "Kira"]), min_size=1, max_size=3))
def test_la_version_1_sobrevive_a_cualquier_secuencia_de_enmiendas(
    tmp_path_factory: pytest.TempPathFactory, nombres: list[str]
) -> None:
    """§7.3: tras cualquier secuencia, cada escena de la version 1 es la de antes."""
    path = tmp_path_factory.mktemp("v") / "n.sqlite"
    create_novel(path, _brief())
    _congelar(path, 1, [_escena(1, 1, "Lucía llegó al parque con Rex.", ("lucia", "rex"))])
    antes = _texto(path, 1, 1)
    actual = "Rex"
    for i, nombre in enumerate(nombres, start=2):
        if nombre == actual:
            continue
        v = _rename(path, f"se llama {nombre}", actual, nombre)
        assert v == len(manuscript_versions(path))
        assert _texto(path, 1, v) == [f"Lucía llegó al parque con {nombre}."]
        actual = nombre
        assert i >= 2
    assert _texto(path, 1, 1) == antes


def manuscript_versions(path: Path) -> list[manuscript.VersionInfo]:
    with connection.reader(path) as con:
        return manuscript.versions(con)


def test_entidades_con_sus_capitulos_y_ficha_con_procedencia(novela: Path) -> None:
    """RF-207, RF-208."""
    with connection.reader(novela) as con:
        todas = {e.entity_id: e for e in entities.list_entities(con)}
        lugares = entities.list_entities(con, "place")
        ficha = entities.entity_file(con, "lucia")
    assert todas["rex"].chapters == (1, 2)
    assert todas["lucia"].chapters == (1, 2)
    assert [e.entity_id for e in lugares] == ["parque"]
    assert ficha is not None
    assert [(f.attribute, f.value, f.provenance) for f in ficha.facts] == [("edad", "10", "brief")]
    assert {(a.scene_id, a.roles) for a in ficha.appearances} >= {("c1e1", ("pov", "cast"))}
    assert entities.entity_file(con_path(novela), "no-existe") is None


def con_path(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def test_las_prohibidas_del_brief_entran_como_proscritas(tmp_path: Path) -> None:
    """RF-202, RD-37, D-91: las del brief son nivel `cliente` y tipo `term`."""
    path = tmp_path / "p.sqlite"
    brief = _brief().model_copy(update={"forbidden_words": ("Sangre", " ")})
    create_novel(path, brief)
    with connection.reader(path) as con:
        filas = con.execute("SELECT term, kind, level FROM proscribed").fetchall()
    assert [(r["term"], r["kind"], r["level"]) for r in filas] == [("sangre", "term", "cliente")]


def test_sin_solicitudes_la_version_vigente_es_la_1(novela: Path) -> None:
    """Sin ninguna solicitud aplicada, la vigente es la 1."""
    with connection.reader(novela) as con:
        assert manuscript.requests(con) == []
        assert manuscript.current_version(con) == 1


# ------------------------------------------------------ capas de la lectura


def _filas_de_indice(path: Path, scene_id: str) -> list[tuple[object, ...]]:
    with connection.reader(path) as con:
        return [
            tuple(r)
            for r in con.execute(
                "SELECT rowid, id, scene_id, ordinal, text, vector, vector_model, vector_dim "
                "FROM prose_chunk WHERE scene_id = ? ORDER BY ordinal",
                (scene_id,),
            )
        ]


def test_la_enmienda_no_toca_el_indice_de_las_escenas_que_no_nombran_el_hecho(
    novela: Path,
) -> None:
    """RF-203, RF-224 (ENT-15). c1e2 no nombra a Rex: sus fragmentos y vectores quedan igual."""
    intacta = _filas_de_indice(novela, "c1e2")
    tocada = _filas_de_indice(novela, "c1e1")
    assert intacta and tocada

    _rename(novela, "el perro se llama Nala", "Rex", "Nala")

    assert _filas_de_indice(novela, "c1e2") == intacta
    despues = _filas_de_indice(novela, "c1e1")
    assert despues != tocada and all("Nala" in str(f[4]) for f in despues)


def test_una_recongelacion_que_falla_a_medias_no_deja_version_ni_historia(
    novela: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RNF-50 (ENT-18). La caida llega despues de recongelar y antes de confirmar."""
    real = refreeze.commit

    def cae(*args: object, **kw: object) -> None:
        real(*args, **kw)  # type: ignore[arg-type]
        raise RuntimeError("caida a mitad de la transaccion")

    monkeypatch.setattr(refreeze, "commit", cae)
    antes = [_texto(novela, 1, 1), _texto(novela, 2, 1)]
    with pytest.raises(RuntimeError, match="caida"):
        _rename(novela, "el perro se llama Nala", "Rex", "Nala")

    with connection.reader(novela) as con:
        assert manuscript.current_version(con) == 1
        assert con.execute("SELECT count(*) FROM scene_text_history").fetchone()[0] == 0
        nombre = con.execute("SELECT name FROM entity WHERE id = 'rex'").fetchone()[0]
        textos = scene_texts(con)
    assert [_texto(novela, 1, 1), _texto(novela, 2, 1)] == antes
    assert nombre == "Rex" and not any("Nala" in t for t in textos.values())


def test_una_entidad_que_no_sale_en_ninguna_escena_no_tiene_capitulos_ni_enlaces(
    tmp_path: Path,
) -> None:
    """RF-207, RF-208 (ENT-11). Sin POV, lugar ni elenco no hay aparicion que enlazar."""
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    _congelar(path, 1, [_escena(1, 1, "Lucía miró las nubes sola.", ("lucia",))])
    with connection.reader(path) as con:
        rex = {e.entity_id: e for e in entities.list_entities(con)}["rex"]
        ficha = entities.entity_file(con, "rex")
    assert rex.chapters == ()
    assert ficha is not None and ficha.appearances == ()


@settings(
    max_examples=15, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    capitulos=st.lists(st.lists(st.booleans(), min_size=1, max_size=3), min_size=1, max_size=3),
    renombrar=st.booleans(),
)
def test_toda_aparicion_de_la_ficha_apunta_a_una_escena_de_ese_capitulo(
    tmp_path_factory: pytest.TempPathFactory, capitulos: list[list[bool]], renombrar: bool
) -> None:
    """RF-206 a RF-208 (ENT-11). Cada enlace de la ficha llega a una escena de la vigente.

    `capitulos[c][e]` dice si Rex esta en el elenco de la escena e del capitulo c.
    """
    path = tmp_path_factory.mktemp("f") / "n.sqlite"
    create_novel(path, _brief())
    esperadas: set[tuple[int, str]] = set()
    for c, escenas in enumerate(capitulos, start=1):
        lote = []
        for e, con_rex in enumerate(escenas, start=1):
            texto = "Lucía llegó al parque con Rex." if con_rex else "Lucía miró las nubes sola."
            lote.append(_escena(c, e, texto, ("lucia", "rex") if con_rex else ("lucia",)))
            if con_rex:
                esperadas.add((c, f"c{c}e{e}"))
        _congelar(path, c, lote)
    if renombrar and esperadas:
        _rename(path, "el perro se llama Nala", "Rex", "Nala")

    with connection.reader(path) as con:
        vigente = manuscript.current_version(con)
        for resumen in entities.list_entities(con):
            ficha = entities.entity_file(con, resumen.entity_id)
            assert ficha is not None
            assert resumen.chapters == tuple(sorted({a.chapter for a in ficha.appearances}))
            for a in ficha.appearances:
                escenas_cap = manuscript.chapter_at(con, a.chapter, vigente) or []
                assert a.scene_id in {s.scene_id for s in escenas_cap}, (a, vigente)
        rex = entities.entity_file(con, "rex")
    assert rex is not None
    assert {(a.chapter, a.scene_id) for a in rex.appearances} == esperadas


@settings(
    max_examples=12, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(st.lists(st.sampled_from(["Nala", "Toby", "Luna", "Kira"]), min_size=1, max_size=3))
def test_una_escena_sin_marca_se_lee_igual_que_en_la_version_anterior(
    tmp_path_factory: pytest.TempPathFactory, nombres: list[str]
) -> None:
    """RF-204, RF-206; RF-186 del frontend (ENT-17). La marca de cambio no miente en ningun sentido."""
    path = tmp_path_factory.mktemp("m") / "n.sqlite"
    create_novel(path, _brief())
    _congelar(
        path,
        1,
        [
            _escena(1, 1, "Lucía llegó al parque con Rex.", ("lucia", "rex")),
            _escena(1, 2, "Lucía miró las nubes sola.", ("lucia",)),
        ],
    )
    _congelar(path, 2, [_escena(2, 1, "Rex ladró al ver la pelota.", ("lucia", "rex"))])
    actual = "Rex"
    for nombre in nombres:
        if nombre != actual:
            _rename(path, f"se llama {nombre}", actual, nombre)
            actual = nombre

    with connection.reader(path) as con:
        for v in manuscript.versions(con)[1:]:
            for c in manuscript.chapters_in(con, v.number):
                ahora = manuscript.chapter_at(con, c, v.number) or []
                previa = manuscript.chapter_at(con, c, v.number - 1) or []
                antes = {s.scene_id: s.text for s in previa}
                for s in ahora:
                    if s.changed:
                        assert s.text != antes[s.scene_id], (v.number, s.scene_id)
                    else:
                        assert s.text == antes[s.scene_id], (v.number, s.scene_id)
                assert any(s.changed for s in ahora) == (c in v.changed_chapters), (v.number, c)
