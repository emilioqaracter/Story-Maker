"""Los elementos del brief en SQLite: declarados, proyectados y usados.

RF-260, RF-261, RD-47, D-95. VER-01, VER-05. `specs/srs-backend-v4.md` T47.

La cobertura de los rasgos y recuerdos del destinatario se comprueba contra la
base, no contra la prosa: aqui se fija que el brief los deja como hechos
consultables con procedencia `brief`, que la proyeccion se puede reconstruir, y
que un uso anclado se registra en `element_use` y en hecho x escena y cae si la
escena recongelada pierde la cita.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from canon.archivist.extract import parse
from canon.brief import Brief, BriefEntity, Recipient, create_novel, elements
from canon.db import connection
from canon.db.migrations import SCHEMA_VERSION, current_version
from canon.events.types import ElementDeclared, Event
from canon.freeze import elements as freeze_elements
from canon.freeze.elements import ElementUse
from canon.freeze.freeze import SceneToFreeze, commit_chapter, prepare
from canon.projections import rebuild
from canon.prose_index import usage
from commons.provider.port import Embedding
from commons.types.primitives import Provenance, WorldTime

START = WorldTime(stamp="2026-03-01")
RECUERDO = "el verano en que su padre le enseno a flotar en el rio"
COMETA = "la tarde de la cometa roja enganchada en el pino"
TEXTO = (
    "Ines bajo al embarcadero cuando todavia no habia nadie. "
    "Se acordo del verano del rio, cuando su padre le sostenia la nuca y le decia que flotara. "
    "Ato la barca con el nudo de siempre y no miro atras."
)
CITA = "Se acordo del verano del rio, cuando su padre le sostenia la nuca"


def _brief() -> Brief:
    return Brief(
        title="El embarcadero",
        start=START,
        entities=(
            BriefEntity(id="ines", kind="person", name="Ines"),
            BriefEntity(id="embarcadero", kind="place", name="el embarcadero"),
        ),
        style_guide="Tercera persona, pasado.",
        target_words=3_000,
        recipient=Recipient(
            entity_id="ines",
            age=12,
            traits=("paciente",),
            memories=(RECUERDO, COMETA),
            optional=(COMETA,),
            role="protagonista",
        ),
    )


class _Embedder:
    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        return [Embedding(values=(0.1, 0.2), model_id="doble", dimension=2) for _ in texts]


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief(), global_terms=())
    return path


def _freeze(path: Path, text: str = TEXTO, uses: Sequence[ElementUse] = ()) -> None:
    escena = SceneToFreeze(
        id="c1e1",
        chapter=1,
        scene_number=1,
        pov_entity="ines",
        world_time=WorldTime(stamp="2026-03-02"),
        function="establecer",
        text=text,
        summary="Ines en el embarcadero",
    )
    prep = prepare(
        [escena], chapter=1, chapter_summary="resumen", embed=_Embedder(), element_uses=uses
    )
    with connection.canon_writer(path) as con:
        commit_chapter(con, prep)


def _uso(quote: str = CITA) -> ElementUse:
    return ElementUse(element_id="memory-1", scene_id="c1e1", quote=quote, offset=TEXTO.find(quote))


# ------------------------------------------------------------- declarados


def test_cada_rasgo_y_recuerdo_entra_como_hecho_con_procedencia_brief(novela: Path) -> None:
    """RF-260, RD-47. Obligatorios salvo los que la entrevista marca opcionales."""
    with connection.reader(novela) as con:
        filas = [
            (r["id"], r["kind"], r["text"], bool(r["mandatory"]), r["provenance"], r["type"])
            for r in con.execute(
                "SELECT b.id, b.kind, b.text, b.mandatory, e.provenance, e.type "
                "FROM brief_element b JOIN event e ON e.id = b.source_event ORDER BY b.id"
            )
        ]
    assert filas == [
        ("memory-1", "memory", RECUERDO, True, "brief", "element.declared"),
        ("memory-2", "memory", COMETA, False, "brief", "element.declared"),
        ("trait-1", "trait", "paciente", True, "brief", "element.declared"),
    ]


def test_la_proyeccion_de_los_elementos_se_reconstruye_igual(novela: Path) -> None:
    """RF-05. `brief_element` es proyeccion pura del registro."""
    with connection.reader(novela) as con:
        antes = [tuple(r) for r in con.execute("SELECT * FROM brief_element ORDER BY id")]
    with connection.canon_writer(novela) as con:
        rebuild.rebuild(con)
    with connection.reader(novela) as con:
        despues = [tuple(r) for r in con.execute("SELECT * FROM brief_element ORDER BY id")]
    assert antes == despues and len(antes) == 3


def test_los_identificadores_son_tipo_y_posicion() -> None:
    assert [(e.id, e.setup_id, e.mandatory) for e in elements(_brief())] == [
        ("trait-1", "element.trait-1", True),
        ("memory-1", "element.memory-1", True),
        ("memory-2", "element.memory-2", False),
    ]
    sin = _brief().model_copy(update={"recipient": None})
    assert elements(sin) == []


def test_la_prosa_no_puede_declarar_un_elemento() -> None:
    """RD-47. `element.declared` es del brief: ni un evento de prosa ni el delta."""
    carga = ElementDeclared(
        element_id="memory-9", element_kind="memory", text="x", mandatory=True, entity_id="ines"
    )
    with pytest.raises(ValidationError, match="solo lo produce la carga del brief"):
        Event(
            world_time=START,
            payload=carga,
            provenance=Provenance.PROSE,
            chapter_origin=1,
            entities=frozenset({"ines"}),
        )
    delta = {
        "events": [
            {
                "world_time": {"stamp": "2026-03-02", "seq": 0},
                "payload": carga.model_dump(mode="json"),
                "quote": CITA,
            }
        ]
    }
    with pytest.raises(ValidationError, match="va en elements"):
        parse(json.dumps(delta))


def test_el_tipo_y_el_identificador_casan() -> None:
    with pytest.raises(ValidationError):
        ElementDeclared(
            element_id="trait-1", element_kind="memory", text="x", mandatory=True, entity_id="i"
        )


def test_un_fichero_nuevo_es_de_la_version_8(novela: Path) -> None:
    with connection.reader(novela) as con:
        assert current_version(con) == SCHEMA_VERSION == 8


def test_un_fichero_anterior_sin_las_tablas_no_tiene_elementos(tmp_path: Path) -> None:
    """RI-35: leer no migra. Sin tablas, ni declarados ni usados; no falla."""
    con = sqlite3.connect(":memory:")
    assert freeze_elements.declared(con) == []
    assert freeze_elements.used(con) == frozenset()
    assert freeze_elements.unused_mandatory(con) == []


# ------------------------------------------------------------------ usos


def test_un_uso_anclado_se_registra_en_element_use_y_en_hecho_por_escena(novela: Path) -> None:
    """RF-261. Anclado, entra en hecho x escena como `element.<id>`."""
    _freeze(novela, uses=[_uso()])
    with connection.reader(novela) as con:
        uso = con.execute("SELECT * FROM element_use").fetchone()
        hecho = con.execute(
            "SELECT u.fact_key, u.scene_id, e.type FROM fact_usage u "
            "JOIN event e ON e.id = u.source_event WHERE u.fact_key LIKE 'element.%'"
        ).fetchall()
        assert freeze_elements.used(con) == {"memory-1"}
        faltan = [e.id for e in freeze_elements.unused_mandatory(con)]
    assert (uso["element_id"], uso["scene_id"], uso["quote"]) == ("memory-1", "c1e1", CITA)
    assert [tuple(r) for r in hecho] == [("element.memory-1", "c1e1", "element.declared")]
    # El opcional no se exige; el rasgo obligatorio sin uso, si.
    assert faltan == ["trait-1"]


def test_sin_uso_los_dos_obligatorios_faltan(novela: Path) -> None:
    _freeze(novela)
    with connection.reader(novela) as con:
        assert [e.id for e in freeze_elements.unused_mandatory(con)] == ["trait-1", "memory-1"]


def test_un_uso_de_un_elemento_no_declarado_no_se_escribe(novela: Path) -> None:
    _freeze(novela, uses=[_uso().model_copy(update={"element_id": "memory-7"})])
    with connection.reader(novela) as con:
        assert freeze_elements.used(con) == frozenset()


def test_el_uso_sobrevive_a_la_siguiente_congelacion(novela: Path) -> None:
    """Las filas `element.*` no son valores de atributo: la purga no las toca."""
    _freeze(novela, uses=[_uso()])
    with connection.canon_writer(novela) as con:
        usage.refresh(con, scenes=(), before=frozenset())
        usage.rebuild(con)
    with connection.reader(novela) as con:
        assert freeze_elements.used(con) == {"memory-1"}
        n = con.execute("SELECT count(*) FROM fact_usage WHERE fact_key LIKE 'element.%'")
        assert n.fetchone()[0] == 1


def test_recongelar_sin_la_cita_devuelve_el_elemento_a_la_deuda(novela: Path) -> None:
    """Una escena reescrita que pierde el recuerdo deja de cobrarlo."""
    _freeze(novela, uses=[_uso()])
    with connection.canon_writer(novela) as con:
        con.execute(
            "UPDATE prose_chunk SET text = ? WHERE scene_id = 'c1e1'",
            ("Ines bajo al embarcadero y ato la barca sin acordarse de nada en particular.",),
        )
        usage.refresh(con, scenes=["c1e1"], before=usage.vigente(con))
    with connection.reader(novela) as con:
        assert freeze_elements.used(con) == frozenset()
        n = con.execute("SELECT count(*) FROM fact_usage WHERE fact_key LIKE 'element.%'")
        assert n.fetchone()[0] == 0


def test_recongelar_con_la_cita_la_conserva(novela: Path) -> None:
    _freeze(novela, uses=[_uso()])
    with connection.canon_writer(novela) as con:
        usage.refresh(con, scenes=["c1e1"], before=usage.vigente(con))
    with connection.reader(novela) as con:
        assert freeze_elements.used(con) == {"memory-1"}
