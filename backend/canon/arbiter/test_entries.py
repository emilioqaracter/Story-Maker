"""Las dos puertas del Arbitro. RF-59, RF-60, RF-63. VER-05."""

from __future__ import annotations

from pathlib import Path

import pytest

from canon.arbiter.entries import resolve_claims, validate_delta
from canon.arbiter.precedence import Claim, Rule
from canon.brief import Brief, BriefEntity, create_novel
from canon.db import connection
from canon.events import log
from canon.events.types import AttributeSet, Event
from canon.projections import rebuild
from commons.types.primitives import Provenance, Severity, WorldTime


def _brief() -> Brief:
    return Brief(
        title="p",
        start=WorldTime(stamp="2026-08-01"),
        entities=(
            BriefEntity(
                id="marcos", kind="person", name="Marcos", attributes=(("estado", "sano"),)
            ),
        ),
        style_guide="Tercera persona.",
        target_words=3_000,
    )


def _set(stamp: str, value: str, *, seq: int = 0, chapter: int = 1) -> Event:
    return Event(
        world_time=WorldTime(stamp=stamp, seq=seq),
        payload=AttributeSet(entity_id="marcos", name="estado", value=value),
        provenance=Provenance.PROSE,
        chapter_origin=chapter,
        entities=frozenset({"marcos"}),
    )


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    # El capitulo 1 congelo que el dia 10 Marcos esta lesionado.
    with connection.canon_writer(path) as con:
        log.append(con, [_set("2026-08-10", "lesionado")])
        rebuild.rebuild(con)
    return path


def test_la_evolucion_normal_no_es_contradiccion(novela: Path) -> None:
    """Sano el 1, lesionado el 10, recuperado el 20: eso es la novela."""
    with connection.reader(novela) as con:
        resultado = validate_delta(con, [_set("2026-08-20", "recuperado", chapter=2)])
    assert resultado.clean
    assert len(resultado.accepted) == 1


def test_reescribir_el_pasado_la_pierde_el_delta_y_deja_un_s1_con_cita(novela: Path) -> None:
    """RF-60. El canon congelado gana; el capitulo vuelve al Reparador."""
    texto = "Aquella manana del cinco Marcos se levanto lesionado y no dijo nada a nadie."
    with connection.reader(novela) as con:
        resultado = validate_delta(
            con,
            [_set("2026-08-05", "lesionado-grave", chapter=2)],
            quotes={0: "Marcos se levanto lesionado y no dijo nada a nadie"},
            chapter_text=texto,
        )

    assert not resultado.clean
    assert resultado.accepted == ()
    rechazo = resultado.rejections[0]
    assert rechazo.arbitration.rule is Rule.FROZEN_OVER_NEW
    assert rechazo.defect.severity is Severity.S1
    assert rechazo.defect.evidence.offset == texto.find("Marcos se levanto")
    assert "canon congelado" in rechazo.defect.rule


def test_el_mismo_valor_en_el_mismo_instante_no_contradice(novela: Path) -> None:
    with connection.reader(novela) as con:
        resultado = validate_delta(con, [_set("2026-08-10", "lesionado", seq=3, chapter=2)])
    assert resultado.clean


def test_la_puerta_del_documentalista_resuelve_por_precedencia() -> None:
    """RF-36, RF-63. Dos versiones de un hecho en el paquete: manda el brief."""
    derivado = Claim(
        fact_key="marcos.dorsal", value="7", provenance=Provenance.DERIVED, frozen=True
    )
    del_brief = Claim(fact_key="marcos.dorsal", value="9", provenance=Provenance.BRIEF, frozen=True)
    otro = Claim(fact_key="marcos.estado", value="sano", provenance=Provenance.BRIEF, frozen=True)

    vigentes, arbitrajes = resolve_claims([derivado, del_brief, otro])

    assert vigentes["marcos.dorsal"].value == "9"
    assert vigentes["marcos.estado"].value == "sano"
    assert len(arbitrajes) == 1
    assert arbitrajes[0].rule is Rule.BRIEF_OVER_DERIVED
