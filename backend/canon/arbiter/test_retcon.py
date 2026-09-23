"""El retcon: regla dura, evento y recongelacion atomica. RF-151 a RF-155. VER-05, VER-06."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from canon.arbiter import refreeze, retcon
from canon.arbiter.entries import validate_delta
from canon.brief import Brief, BriefEntity, create_novel
from canon.db import connection
from canon.events.types import AttributeSet, Event
from canon.freeze.freeze import SceneToFreeze, commit_chapter, prepare
from canon.skills import read
from commons.provider.port import Embedding
from commons.types.primitives import Provenance, WorldTime


class _Embedder:
    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        return [Embedding(values=(0.1, 0.2), model_id="doble", dimension=2) for _ in texts]


def _lesion(chapter: int, stamp: str, value: str) -> Event:
    return Event(
        world_time=WorldTime(stamp=stamp),
        payload=AttributeSet(entity_id="marcos", name="estado", value=value),
        provenance=Provenance.PROSE,
        chapter_origin=chapter,
        entities=frozenset({"marcos"}),
    )


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    """Capitulo 1 congelado: Marcos esta lesionado desde el dia 10, y lo dicen dos escenas."""
    path = tmp_path / "n.sqlite"
    create_novel(
        path,
        Brief(
            title="p",
            start=WorldTime(stamp="2026-08-01"),
            entities=(
                BriefEntity(
                    id="marcos", kind="person", name="Marcos", attributes=(("estado", "sano"),)
                ),
            ),
            style_guide="x",
            target_words=1000,
        ),
    )
    escenas = [
        SceneToFreeze(
            id=f"c1e{n}",
            chapter=1,
            scene_number=n,
            pov_entity="marcos",
            world_time=WorldTime(stamp=f"2026-08-1{n}"),
            function="establecer",
            text=f"Marcos seguia lesionado aquella tarde {n}.",
            summary=f"resumen {n}",
            present=("marcos",),
        )
        for n in (1, 2)
    ]
    prep = prepare(
        escenas,
        chapter=1,
        chapter_summary="c1",
        embed=_Embedder(),
        delta=[_lesion(1, "2026-08-10", "lesionado")],
    )
    with connection.canon_writer(path) as con:
        commit_chapter(con, prep)
    return path


def _rechazo(path: Path) -> object:
    with connection.reader(path) as con:
        return validate_delta(con, [_lesion(2, "2026-08-05", "sano")]).rejections[0]


def test_el_plan_cuenta_los_pasajes_que_sostienen_el_hecho(novela: Path) -> None:
    with connection.reader(novela) as con:
        p = retcon.plan(con, _rechazo(novela), payoff_scenes=())  # type: ignore[arg-type]
    assert p is not None
    assert p.scenes == ("c1e1", "c1e2")
    assert p.previous_value == "lesionado" and p.new_value == "sano"
    assert p.admissible


def test_la_regla_dura_rechaza_lo_cobrado_y_lo_que_toca_de_mas(novela: Path) -> None:
    """RF-152."""
    with connection.reader(novela) as con:
        cobrado = retcon.plan(con, _rechazo(novela), payoff_scenes={"c1e2"})  # type: ignore[arg-type]
    assert cobrado is not None and not cobrado.admissible and "payoff" in cobrado.reason()
    largo = cobrado.model_copy(update={"paid": False, "scenes": ("a", "b", "c", "d")})
    assert not largo.admissible
    assert largo.model_copy(update={"scenes": ("a", "b", "c")}).admissible


def test_la_recongelacion_reemplaza_indice_termina_la_vigencia_y_registra(novela: Path) -> None:
    """RF-153, RF-154, RD-24, RD-25."""
    with connection.reader(novela) as con:
        p = retcon.plan(con, _rechazo(novela), payoff_scenes=())  # type: ignore[arg-type]
        assert p is not None
        ev = retcon.event_for(con, p, chapter=2)
    nuevas = [
        refreeze.RefrozenScene(
            scene_id=s, text=f"Marcos estaba sano aquella tarde en {s}.", summary=f"nuevo {s}"
        )
        for s in p.scenes
    ]
    prep = refreeze.prepare(nuevas, embed=_Embedder())
    with connection.canon_writer(novela) as con:
        refreeze.commit(
            con,
            prep,
            retcon=p,
            event=ev,
            chapter_summaries={1: "c1 nuevo"},
            rule="retcon-admisible",
            chapter_origin=2,
        )

    with connection.reader(novela) as con:
        textos = [r["text"] for r in con.execute("SELECT text FROM prose_chunk ORDER BY scene_id")]
        estado = dict(read.query(con, ["marcos"], at=WorldTime(stamp="2026-08-20"))[0].attributes)
        registro = refreeze.read_retcons(con)
        fts = con.execute(
            "SELECT count(*) AS n FROM prose_chunk_fts WHERE prose_chunk_fts MATCH 'lesionado'"
        ).fetchone()["n"]
    assert all("sano" in t for t in textos)
    assert estado["estado"] == "sano", "el hecho anterior dejo de regir"
    assert registro[0]["refrozen_scenes"] == ["c1e1", "c1e2"]
    assert fts == 0, "la entrada lexica tambien se reemplazo"
    with connection.reader(novela) as con:
        versiones = con.execute(
            "SELECT count(*) AS n FROM summary_version WHERE level = 'chapter' AND ref_id = '1'"
        ).fetchone()["n"]
    assert versiones >= 1, "el resumen regenerado queda versionado (RD-23)"


def _recongela_sano(path: Path) -> None:
    with connection.reader(path) as con:
        p = retcon.plan(con, _rechazo(path), payoff_scenes=())  # type: ignore[arg-type]
        assert p is not None
        ev = retcon.event_for(con, p, chapter=2)
    nuevas = [
        refreeze.RefrozenScene(scene_id=s, text=f"Marcos estaba sano en {s}.", summary="s")
        for s in p.scenes
    ]
    with connection.canon_writer(path) as con:
        refreeze.commit(
            con,
            refreeze.prepare(nuevas, embed=_Embedder()),
            retcon=p,
            event=ev,
            chapter_summaries={},
            rule="retcon-admisible",
            chapter_origin=2,
        )


def _historia(path: Path) -> list[tuple[str, int, str]]:
    with connection.reader(path) as con:
        return [
            (r["scene_id"], r["until_version"], r["text"])
            for r in con.execute("SELECT * FROM scene_text_history ORDER BY scene_id")
        ]


def test_con_la_version_1_vigente_recongelar_no_guarda_historia(novela: Path) -> None:
    """RD-34: no hay version anterior que proteger."""
    _recongela_sano(novela)
    assert _historia(novela) == []


def test_recongelar_con_la_version_2_guarda_lo_que_ve_la_1(novela: Path) -> None:
    """B2, RD-34, PRO-08. La version 2 existe y no toco estas escenas: el retcon
    guarda su texto hasta la 1 antes de reemplazarlo, una sola vez."""
    with connection.canon_writer(novela) as con:
        con.execute(
            "INSERT INTO manuscript_version (version, cause, changed_chapters, max_chapter, "
            "created_at) VALUES (2, NULL, '[]', 1, datetime('now'))"
        )
    _recongela_sano(novela)
    assert _historia(novela) == [
        ("c1e1", 1, "Marcos seguia lesionado aquella tarde 1."),
        ("c1e2", 1, "Marcos seguia lesionado aquella tarde 2."),
    ]


def test_una_recongelacion_que_falla_no_toca_nada(novela: Path) -> None:
    """RNF-30. Todo junto o nada."""
    with connection.reader(novela) as con:
        p = retcon.plan(con, _rechazo(novela), payoff_scenes=())  # type: ignore[arg-type]
        assert p is not None
        ev = retcon.event_for(con, p, chapter=2)
    prep = refreeze.prepare(
        [refreeze.RefrozenScene(scene_id="c1e1", text="Marcos sano.", summary="s")],
        embed=_Embedder(),
    )
    with pytest.raises(RuntimeError), connection.canon_writer(novela) as con:
        refreeze.commit(
            con, prep, retcon=p, event=ev, chapter_summaries={}, rule="r", chapter_origin=2
        )
        raise RuntimeError("caida a mitad")
    with connection.reader(novela) as con:
        assert con.execute("SELECT count(*) AS n FROM retcon").fetchone()["n"] == 0
        assert (
            "lesionado"
            in con.execute("SELECT text FROM prose_chunk WHERE scene_id='c1e1'").fetchone()["text"]
        )


def test_solo_se_reinterpreta_el_hecho_en_disputa_y_con_su_valor(novela: Path) -> None:
    """RF-155. El plan sale del rechazo: hecho y valor los trae el delta, no el modelo."""
    with connection.reader(novela) as con:
        p = retcon.plan(con, _rechazo(novela), payoff_scenes=())  # type: ignore[arg-type]
    assert p is not None
    assert (p.entity_id, p.attribute, p.new_value) == ("marcos", "estado", "sano")
    assert set(retcon.RetconProposal.model_fields) == {"propose", "rationale"}, (
        "el modelo solo propone"
    )
