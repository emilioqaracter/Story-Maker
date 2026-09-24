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


# ------------------------------------------- D-130: entidad desconocida


def _ev(stamp: str, payload: object, *, seq: int = 0) -> Event:
    return Event(
        world_time=WorldTime(stamp=stamp, seq=seq),
        payload=payload,  # type: ignore[arg-type]
        provenance=Provenance.PROSE,
        chapter_origin=2,
        entities=frozenset({"marcos"}),
    )


def test_un_atributo_sobre_una_entidad_desconocida_se_descarta_y_el_resto_sigue(
    novela: Path,
) -> None:
    """D-130. La tirada eval-02 se estrello al congelar por esto: la clave ajena
    de `attribute` a `entity`. Se descarta con su motivo; el capitulo no vuelve
    al Reparador, porque la prosa no contradice nada: el que falla es el delta."""
    texto = "La cometa roja quedo rota en la arena y Marcos siguio sano toda la tarde."
    fantasma = _ev("2026-08-20", AttributeSet(entity_id="cometa", name="estado", value="rota"))
    bueno = _set("2026-08-20", "recuperado", seq=1, chapter=2)
    with connection.reader(novela) as con:
        resultado = validate_delta(
            con,
            [fantasma, bueno],
            quotes={0: "La cometa roja quedo rota en la arena"},
            chapter_text=texto,
        )

    assert resultado.clean, "un descarte no es una contradiccion"
    assert resultado.accepted == (bueno,)
    (descarte,) = resultado.dropped
    assert descarte.event == fantasma
    assert descarte.entity == "cometa"
    assert descarte.defect.kind == "unknown-entity"
    assert descarte.defect.severity is Severity.S2
    assert descarte.defect.evidence.quote == "La cometa roja quedo rota en la arena"
    assert descarte.defect.evidence.offset == 0
    assert "cometa" in descarte.defect.rule


def test_una_entidad_creada_antes_en_el_mismo_delta_vale(novela: Path) -> None:
    from canon.events.types import EntityCreated

    crea = _ev("2026-08-20", EntityCreated(entity_id="cometa", kind="object", name="la cometa"))
    usa = _ev("2026-08-20", AttributeSet(entity_id="cometa", name="estado", value="rota"), seq=1)
    with connection.reader(novela) as con:
        resultado = validate_delta(con, [usa, crea])  # el orden de la lista no importa
    assert resultado.dropped == ()
    assert set(resultado.accepted) == {crea, usa}


def test_una_entidad_creada_despues_de_usarla_se_descarta(novela: Path) -> None:
    """La proyeccion aplica por `(world_time, seq)` y la clave ajena es inmediata:
    usar antes de crear revienta igual que no crear."""
    from canon.events.types import EntityCreated

    usa = _ev("2026-08-20", AttributeSet(entity_id="cometa", name="estado", value="rota"))
    crea = _ev("2026-08-21", EntityCreated(entity_id="cometa", kind="object", name="la cometa"))
    with connection.reader(novela) as con:
        resultado = validate_delta(con, [usa, crea])
    assert resultado.accepted == (crea,)
    assert [d.event for d in resultado.dropped] == [usa]
    assert "antes de crearse" in resultado.dropped[0].defect.rule


@pytest.mark.parametrize(
    "payload",
    [
        "alias",
        "relacion-origen",
        "relacion-destino",
        "conocimiento",
        "competencia",
        "renombre",
    ],
)
def test_todo_evento_con_entidad_desconocida_se_descarta(novela: Path, payload: str) -> None:
    """Todos los tipos que referencian `entity`: clave ajena o `UPDATE` sin efecto."""
    from canon.events.types import (
        AliasAdded,
        CompetenceSet,
        EntityRenamed,
        KnowledgeGained,
        RelationSet,
    )

    cuerpos = {
        "alias": AliasAdded(entity_id="nadie", alias="el Nadie"),
        "relacion-origen": RelationSet(source_id="nadie", target_id="marcos", kind="amistad"),
        "relacion-destino": RelationSet(source_id="marcos", target_id="nadie", kind="amistad"),
        "conocimiento": KnowledgeGained(entity_id="nadie", fact_key="marcos.estado"),
        "competencia": CompetenceSet(entity_id="nadie", name="regate", level="alto"),
        "renombre": EntityRenamed(entity_id="nadie", name="Nadie"),
    }
    with connection.reader(novela) as con:
        resultado = validate_delta(con, [_ev("2026-08-20", cuerpos[payload])])
    assert resultado.accepted == ()
    assert [d.entity for d in resultado.dropped] == ["nadie"]
