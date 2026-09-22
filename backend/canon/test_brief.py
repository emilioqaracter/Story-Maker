"""Carga del brief.

RF-11, D-09. Lo que se comprueba es que el brief no es un caso especial: entra
como eventos y desde la primera fila el canon ya es proyeccion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from canon.brief import Brief, BriefEntity, BriefRelation, create_novel, to_events
from canon.db import connection
from canon.skills import read
from commons.types.primitives import Provenance, WorldTime

START = WorldTime(stamp="2026-01-01")


def _brief() -> Brief:
    return Brief(
        title="La temporada larga",
        start=START,
        entities=(
            BriefEntity(
                id="marcos",
                kind="person",
                name="Marcos Vela",
                aliases=("el Chino",),
                attributes=(("estado", "sano"), ("dorsal", "9")),
                competences=(("remate", "alto"),),
            ),
            BriefEntity(id="elena", kind="person", name="Elena Ruiz"),
            BriefEntity(id="estadio", kind="place", name="El Molinon"),
        ),
        relations=(BriefRelation(source="marcos", target="elena", kind="pareja"),),
        style_guide="Tercera persona, pasado, POV unico por escena.",
        rulebook="Once contra once. Tres cambios.",
        target_words=200_000,
    )


def test_el_brief_entra_como_eventos_no_como_documento() -> None:
    eventos = to_events(_brief())
    assert all(e.provenance is Provenance.BRIEF for e in eventos)
    assert all(e.chapter_origin is None for e in eventos)


def test_cada_evento_del_brief_lleva_seq_distinto() -> None:
    """Si dos coincidieran en instante y seq, el orden de carga decidiria el
    resultado: es la ambiguedad que deja fijada la prueba de las proyecciones."""
    seqs = [e.world_time.seq for e in to_events(_brief())]
    assert len(seqs) == len(set(seqs))


def test_las_entidades_van_antes_que_lo_que_las_referencia() -> None:
    """Una relacion sobre algo que aun no existe rompe la clave ajena."""
    eventos = to_events(_brief())
    creaciones = [i for i, e in enumerate(eventos) if e.payload.type == "entity.created"]
    otros = [i for i, e in enumerate(eventos) if e.payload.type != "entity.created"]
    assert max(creaciones) < min(otros)


def test_crear_la_novela_deja_el_canon_consultable(tmp_path: Path) -> None:
    path = tmp_path / "n.sqlite"
    n = create_novel(path, _brief())
    assert n > 0

    with connection.reader(path) as con:
        [marcos] = read.query(con, ["marcos"], at=START, full=True)
        assert marcos.name == "Marcos Vela"
        assert "el Chino" in marcos.aliases
        assert dict(marcos.attributes)["estado"] == "sano"
        assert dict(marcos.competences)["remate"] == "alto"
        assert read.related(con, ["marcos"], at=START) == {"marcos", "elena"}

        guia = con.execute(
            "SELECT body FROM document_version WHERE doc_kind='style_guide'"
        ).fetchone()
        assert "POV unico" in guia["body"]


def test_una_relacion_a_una_entidad_inexistente_se_rechaza() -> None:
    with pytest.raises(ValueError, match="no declara"):
        Brief(
            title="x",
            start=START,
            entities=(BriefEntity(id="a", kind="person", name="A"),),
            relations=(BriefRelation(source="a", target="fantasma", kind="rival"),),
            style_guide="g",
            target_words=1000,
        )


def test_identificadores_repetidos_se_rechazan() -> None:
    with pytest.raises(ValueError, match="repetidos"):
        Brief(
            title="x",
            start=START,
            entities=(
                BriefEntity(id="a", kind="person", name="A"),
                BriefEntity(id="a", kind="person", name="Otro A"),
            ),
            style_guide="g",
            target_words=1000,
        )


def test_el_rango_de_longitud_sale_del_brief() -> None:
    """La condicion de cierre de obra lo consulta: una novela fuera de rango no
    esta terminada por muchos arcos que haya resuelto."""
    assert _brief().word_range() == (180_000, 220_000)
