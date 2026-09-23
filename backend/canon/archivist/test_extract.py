"""`delta.extract` y la proscripcion. RF-55, RF-56, RF-108, RD-19. VER-05 y VER-06."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from canon.archivist import proscription
from canon.archivist.extract import EmptyDeltaError, parse, to_events
from canon.brief import Brief, BriefEntity, create_novel
from canon.db import connection
from canon.events import log
from canon.events.types import AttributeSet
from commons.types.primitives import Provenance, WorldTime

START = WorldTime(stamp="2026-08-01")


def _brief() -> Brief:
    return Brief(
        title="p",
        start=START,
        entities=(BriefEntity(id="marcos", kind="person", name="Marcos"),),
        style_guide="Tercera persona.",
        target_words=3_000,
    )


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    return path


def _raw(*eventos: dict[str, object]) -> str:
    return json.dumps({"events": list(eventos)})


def _lesion(stamp: str = "2026-08-10", seq: int = 0) -> dict[str, object]:
    return {
        "world_time": {"stamp": stamp, "seq": seq},
        "payload": {
            "type": "attribute.set",
            "entity_id": "marcos",
            "name": "estado",
            "value": "lesionado",
        },
        "quote": "sintio el tiron en el muslo y supo que no iba a levantarse",
    }


def test_una_salida_valida_se_convierte_en_eventos_con_procedencia_prosa(novela: Path) -> None:
    proposal = parse(_raw(_lesion()))
    with connection.reader(novela) as con:
        eventos = to_events(proposal, con, chapter=1)

    assert len(eventos) == 1
    assert eventos[0].provenance is Provenance.PROSE
    assert eventos[0].chapter_origin == 1
    assert eventos[0].entities == frozenset({"marcos"})
    assert isinstance(eventos[0].payload, AttributeSet)


def test_un_tipo_desconocido_no_encaja() -> None:
    """RI-18: la salida que no valida cuenta como llamada fallida."""
    with pytest.raises(ValidationError):
        parse(
            _raw(
                {
                    "world_time": {"stamp": "2026-08-10"},
                    "payload": {"type": "gol.marcado", "quien": "marcos"},
                    "quote": "marco un gol de cabeza en el ultimo minuto del partido",
                }
            )
        )


def test_un_delta_vacio_es_un_fallo(novela: Path) -> None:
    """Trampa 12: cada escena declara un cambio de valor, algo tuvo que pasar."""
    with connection.reader(novela) as con, pytest.raises(EmptyDeltaError):
        to_events(parse('{"events": []}'), con, chapter=1)


def test_una_cita_vacia_no_es_evidencia() -> None:
    with pytest.raises(ValidationError):
        parse(_raw({**_lesion(), "quote": ""}))


@settings(max_examples=40, deadline=None)
@given(
    ya_registrados=st.integers(min_value=0, max_value=5),
    propuestos=st.integers(min_value=1, max_value=5),
)
def test_los_desempates_caen_siempre_detras_de_lo_registrado(
    ya_registrados: int, propuestos: int
) -> None:
    """RD-19. El Archivero ordena; el codigo garantiza que no pisa nada."""
    # Un directorio propio por caso generado: la fixture de pytest no se
    # reinicia entre entradas de hypothesis.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "n.sqlite"
        _check_seq_offsets(path, ya_registrados, propuestos)


def _check_seq_offsets(path: Path, ya_registrados: int, propuestos: int) -> None:
    create_novel(path, _brief())

    # Eventos ya congelados en el mismo instante que va a usar el delta, uno a
    # uno: cada uno cae detras del anterior, que es lo que se comprueba.
    with connection.canon_writer(path) as con:
        for _ in range(ya_registrados):
            log.append(con, to_events(parse(_raw(_lesion())), con, chapter=1))

    with connection.reader(path) as con:
        proposal = parse(_raw(*[_lesion(seq=i) for i in range(propuestos)]))
        nuevos = to_events(proposal, con, chapter=2)
        maximo_previo = log.next_seq(con, "2026-08-10") - 1

    seqs = [e.world_time.seq for e in nuevos]
    assert min(seqs) > maximo_previo
    assert len(set(seqs)) == len(seqs), "sin colisiones entre los propuestos"
    assert seqs == sorted(seqs), "conserva el orden de causalidad del Archivero"


# -------------------------------------------------------------- proscripcion


def test_un_ngrama_repetido_dos_veces_en_el_capitulo_se_proscribe() -> None:
    texto = "El estadio olia a hierba mojada. Volvio a salir y el estadio olia a hierba mojada otra vez."
    repetidos = proscription.repeated_ngrams([texto])
    assert ("estadio olia a hierba", "ngram") in repetidos


def test_una_vez_aqui_y_una_en_prosa_congelada_tambien() -> None:
    congelado = "El estadio olia a hierba mojada aquella tarde."
    nuevo = "Al volver, el estadio olia a hierba mojada."
    assert ("estadio olia a hierba", "ngram") in proscription.repeated_ngrams(
        [nuevo], frozen_texts=[congelado]
    )


def test_las_palabras_funcionales_no_se_proscriben() -> None:
    texto = "Lo que se dijo de la que se fue. Lo que se dijo de la que se quedo."
    assert all(
        not proscription._is_only_function_words(t)
        for t, _ in proscription.repeated_ngrams([texto])
    )
    assert ("de la que se", "ngram") not in proscription.repeated_ngrams([texto])


@settings(max_examples=30, deadline=None)
@given(st.lists(st.text(alphabet="abcdefg ", min_size=0, max_size=60), max_size=4))
def test_la_deteccion_es_determinista(textos: list[str]) -> None:
    assert proscription.repeated_ngrams(textos) == proscription.repeated_ngrams(textos)
