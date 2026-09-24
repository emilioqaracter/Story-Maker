"""La plantilla de lectura humana y su esquema. RF-270, RD-48, D-95. VER-10 con VER-05.

La puerta de T51 para la plantilla: desde una novela de prueba congelada
(`evals/fixtures/novela-prueba.json`) se regenera identica a la versionada, con
las dimensiones y los niveles de las rubricas que guarda la novela; y el
fichero relleno de prueba valida contra el esquema, citas incluidas, mientras
que la plantilla vacia y cada forma de rellenarla mal no.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from canon.brief import Brief, create_novel
from canon.db import connection
from canon.freeze.freeze import SceneToFreeze, commit_chapter, prepare
from commons.provider.port import Embedding
from commons.types.primitives import WorldTime
from commons.types.rubrics import DEFAULT_RUBRICS, RubricSet
from commons.types.rubrics import dumps as dump_rubrics
from evals import human_template
from evals.human_template import HumanReading, load, problems, template

FIXTURES = Path(__file__).parent / "fixtures"
NOVEL = FIXTURES / "novela-prueba.json"
READING = FIXTURES / "human" / "novela-prueba.json"
EXPECTED = FIXTURES / "expected" / "plantilla-novela-prueba.json"


class _Embedder:
    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        return [Embedding(values=(0.1, 0.2), model_id="doble", dimension=2) for _ in texts]


def build_novel(path: Path) -> Path:
    """La novela de prueba, congelada capitulo a capitulo como en una tirada."""
    datos = json.loads(NOVEL.read_text(encoding="utf-8"))
    brief = Brief.model_validate(datos["brief"])
    create_novel(path, brief)
    for cap in datos["chapters"]:
        escenas = [
            SceneToFreeze(
                id=e["id"],
                chapter=cap["chapter"],
                scene_number=n,
                pov_entity="ines",
                place_entity="embarcadero",
                world_time=WorldTime(stamp=f"2026-08-{cap['chapter']:02d}", seq=n),
                function="establecer",
                text=e["text"],
                summary=f"resumen de {e['id']}",
                present=("ines", "tito"),
            )
            for n, e in enumerate(cap["scenes"], start=1)
        ]
        prep = prepare(
            escenas, chapter=cap["chapter"], chapter_summary="resumen", embed=_Embedder()
        )
        with connection.canon_writer(path) as con:
            commit_chapter(con, prep)
    return path


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    return build_novel(tmp_path / "novela-prueba.sqlite")


def _filled() -> dict[str, Any]:
    cuerpo: dict[str, Any] = json.loads(READING.read_text(encoding="utf-8"))
    return cuerpo


def _reading(cuerpo: dict[str, Any]) -> HumanReading:
    return HumanReading.model_validate(cuerpo)


# ------------------------------------------------------------ plantilla


def test_la_plantilla_se_regenera_identica(novela: Path) -> None:
    primera = template(novela, "novela-prueba")
    assert primera == template(novela, "novela-prueba")
    assert primera == EXPECTED.read_text(encoding="utf-8")


def test_el_comando_escribe_la_plantilla_y_check_la_reconoce(novela: Path, tmp_path: Path) -> None:
    out = tmp_path / "human" / "novela-prueba.json"
    args = ["template", "--novel", str(novela), "--id", "novela-prueba", "--out", str(out)]
    assert human_template.main(args) == 0
    assert out.read_text(encoding="utf-8") == EXPECTED.read_text(encoding="utf-8")
    assert human_template.main([*args, "--check"]) == 0
    out.write_text("{}", encoding="utf-8")
    assert human_template.main([*args, "--check"]) == 1


def test_una_entrada_por_capitulo_y_por_dimension_de_las_rubricas(novela: Path) -> None:
    cuerpo = json.loads(template(novela, "novela-prueba"))
    dims = [r.dimension.value for r in DEFAULT_RUBRICS.rubrics]
    assert [c["chapter"] for c in cuerpo["chapters"]] == [1, 2]
    assert [c["scenes"] for c in cuerpo["chapters"]] == [["c1e1", "c1e2"], ["c2e1", "c2e2"]]
    for c in cuerpo["chapters"]:
        assert [s["dimension"] for s in c["scores"]] == dims
        assert all(s["level"] is None for s in c["scores"])
    assert RubricSet.model_validate(cuerpo["rubrics"]) == DEFAULT_RUBRICS, "con sus cinco niveles"


def test_la_plantilla_sale_de_las_rubricas_de_la_novela_no_de_una_lista(novela: Path) -> None:
    """RNF-37: la version vigente es la del fichero. Con otra, otra plantilla."""
    dos = RubricSet(version=2, rubrics=DEFAULT_RUBRICS.rubrics[:2])
    con = sqlite3.connect(novela)
    try:
        evento = con.execute(
            "SELECT source_event FROM document_version WHERE doc_kind = 'rubrics'"
        ).fetchone()[0]
        con.execute(
            "INSERT INTO document_version (doc_kind, version, body, source_event) "
            "VALUES ('rubrics', 2, ?, ?)",
            (dump_rubrics(dos), evento),
        )
        con.commit()
    finally:
        con.close()
    cuerpo = json.loads(template(novela, "novela-prueba"))
    assert cuerpo["rubrics"]["version"] == 2
    assert [s["dimension"] for s in cuerpo["chapters"][0]["scores"]] == ["voice", "style_guide"]


def test_una_novela_sin_capitulos_congelados_no_tiene_plantilla(tmp_path: Path) -> None:
    datos = json.loads(NOVEL.read_text(encoding="utf-8"))
    path = tmp_path / "vacia.sqlite"
    create_novel(path, Brief.model_validate(datos["brief"]))
    with pytest.raises(ValueError, match="no tiene capitulos congelados"):
        template(path, "vacia")


# ------------------------------------------------------------ esquema


def test_la_plantilla_vacia_no_valida(novela: Path) -> None:
    with pytest.raises(ValidationError):
        HumanReading.model_validate_json(template(novela, "novela-prueba"))


def test_la_lectura_rellena_valida_con_sus_citas(novela: Path) -> None:
    assert problems(load(READING), novela) == []


def test_el_comando_valida_la_lectura(novela: Path, tmp_path: Path) -> None:
    assert human_template.main(["validate", "--reading", str(READING), "--novel", str(novela)]) == 0
    roto = tmp_path / "roto.json"
    roto.write_text(template(novela, "novela-prueba"), encoding="utf-8")
    assert human_template.main(["validate", "--reading", str(roto)]) == 1


def test_el_revisor_va_por_su_papel() -> None:
    cuerpo = _filled()
    cuerpo["reviewer"] = "Nombre Apellido"
    with pytest.raises(ValidationError, match="reviewer"):
        _reading(cuerpo)


def test_un_campo_de_mas_no_valida() -> None:
    cuerpo = _filled()
    cuerpo["nota"] = "algo"
    with pytest.raises(ValidationError):
        _reading(cuerpo)


def test_sin_justificacion_no_valida() -> None:
    cuerpo = _filled()
    cuerpo["chapters"][0]["scores"][0]["justification"] = ""
    with pytest.raises(ValidationError, match="justification"):
        _reading(cuerpo)


def test_un_nivel_fuera_de_la_escala_no_valida() -> None:
    cuerpo = _filled()
    cuerpo["chapters"][0]["scores"][0]["level"] = 6
    with pytest.raises(ValidationError, match="level"):
        _reading(cuerpo)


def test_falta_una_dimension_o_se_repite() -> None:
    cuerpo = _filled()
    scores = cuerpo["chapters"][0]["scores"]
    scores[1] = dict(scores[0])
    assert problems(_reading(cuerpo)) == [
        "capitulo 1: falta style_guide",
        "capitulo 1: voice repetida",
    ]


def test_una_escena_de_otro_capitulo_no_cuenta() -> None:
    cuerpo = _filled()
    cuerpo["chapters"][0]["scores"][0]["scene"] = "c2e1"
    assert problems(_reading(cuerpo)) == ["capitulo 1: voice cita la escena c2e1, que no es suya"]


def test_una_cita_que_no_ancla_no_cuenta(novela: Path) -> None:
    cuerpo = _filled()
    cuerpo["chapters"][0]["scores"][0]["quote"] = "una frase que no esta en la escena de nadie"
    assert problems(_reading(cuerpo), novela) == [
        "capitulo 1: la cita de voice no ancla literal y unica en c1e2"
    ]


def test_un_capitulo_sin_leer_o_con_otras_rubricas(novela: Path) -> None:
    cuerpo = _filled()
    cuerpo["chapters"] = cuerpo["chapters"][:1]
    cuerpo["rubrics"]["version"] = 7
    assert problems(_reading(cuerpo), novela) == [
        "las rubricas del fichero (version 7) no son las vigentes de la novela (version 2)",
        "capitulo 2: congelado y sin leer",
    ]
