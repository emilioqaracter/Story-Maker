"""La lectura humana frente al Jurado. RF-271, D-95, D-39. VER-10.

La puerta de T51 para la comparacion: desde la lectura de prueba
(`evals/fixtures/human/novela-prueba.json`) y el extracto de su traza se
regenera identica a la versionada, con las cifras calculadas a mano abajo. El
extracto tiene, en el capitulo 1, un veredicto suspendido antes del aprobado:
si la comparacion leyera el que no es, la voz y el ritmo saldrian distintos.

| Dimension | Humano c1, c2 | Jurado aprobado c1, c2 | Diferencias |
|---|---|---|---|
| voice | 3, 4 | 3, 4 | 0, 0 |
| style_guide | 4, 4 | 4, 4 | 0, 0 |
| pacing | 1, 3 | 3, 4 | -2, -1 |
| subtext | 4, 3 | 4, 5 | 0, -2 |
| theme | 3, 5 | 4, sin nivel | -1 |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evals import human_vs_jury
from evals.brief_table import load_records
from evals.human_template import load
from evals.human_vs_jury import MANUAL, approved_levels, compare, render
from evals.test_human_template import build_novel

FIXTURES = Path(__file__).parent / "fixtures"
READING = FIXTURES / "human" / "novela-prueba.json"
TRACE = FIXTURES / "human" / "novela-prueba.trace.json"
EXPECTED = FIXTURES / "expected" / "human-vs-jury.md"


@pytest.fixture(scope="module")
def output() -> str:
    lectura = load(READING)
    return render(lectura, compare(lectura, load_records(TRACE)))


def _args(out: Path, *extra: str) -> list[str]:
    return ["--human", str(READING), "--trace", str(TRACE), "--out", str(out), *extra]


# ------------------------------------------------------------ determinismo


def test_se_regenera_identica_desde_los_ficheros_de_prueba(output: str) -> None:
    assert output == EXPECTED.read_text(encoding="utf-8")


def test_el_comando_da_el_mismo_fichero_dos_veces(tmp_path: Path) -> None:
    outs = [tmp_path / "a.md", tmp_path / "b.md"]
    for out in outs:
        assert human_vs_jury.main(_args(out)) == 0
    assert outs[0].read_bytes() == outs[1].read_bytes()
    assert human_vs_jury.main(_args(outs[0], "--check")) == 0


def test_la_traza_jsonl_y_su_extracto_dan_lo_mismo(tmp_path: Path, output: str) -> None:
    jsonl = tmp_path / "novela-prueba.trace.jsonl"
    jsonl.write_text(
        "".join(r.model_dump_json() + "\n" for r in load_records(TRACE)), encoding="utf-8"
    )
    lectura = load(READING)
    assert render(lectura, compare(lectura, load_records(jsonl))) == output


# ------------------------------------------------------------ contenido


def test_usa_el_ultimo_veredicto_aprobado_de_cada_capitulo() -> None:
    niveles = approved_levels(load_records(TRACE))
    assert niveles[1]["voice"] == 3 and niveles[1]["pacing"] == 3, "no el suspendido, de 2"
    assert "theme" not in niveles[2]


def test_medias_y_diferencia_media_absoluta_por_dimension(output: str) -> None:
    assert "| `voice` | 2 | 3.50 | 3.50 | 0.00 | ninguno |" in output
    assert "| `pacing` | 2 | 2.00 | 3.50 | 1.50 | 1 |" in output
    assert "| `subtext` | 2 | 3.50 | 4.50 | 1.00 | 2 |" in output
    assert "| `theme` | 1 | 3.00 | 4.00 | 1.00 | ninguno |" in output


def test_el_detalle_lleva_la_diferencia_firmada(output: str) -> None:
    assert "| 1 | `pacing` | 1 | 3 | -2 |" in output
    assert "| 2 | `subtext` | 3 | 5 | -2 |" in output
    assert "| 1 | `voice` | 3 | 3 | +0 |" in output


def test_una_dimension_sin_nivel_del_jurado_consta_fuera(output: str) -> None:
    assert "- Capitulo 2, `theme`: el veredicto aprobado no tiene nivel de esa dimension." in output


def test_un_capitulo_sin_veredicto_aprobado_consta_fuera() -> None:
    lectura = load(READING)
    registros = [
        r for r in load_records(TRACE) if not (r.kind == "jury" and r.fields.get("chapter") == 2)
    ]
    comparacion = compare(lectura, registros)
    assert comparacion.without_verdict == (2,)
    assert {p.chapter for p in comparacion.pairs} == {1}


def test_sin_umbral_una_discrepancia_grande_no_suspende_nada(tmp_path: Path) -> None:
    """D-95: la herramienta informa. Discrepar no es un error de la herramienta."""
    out = tmp_path / "h.md"
    assert human_vs_jury.main(_args(out)) == 0
    texto = out.read_text(encoding="utf-8")
    assert "Sin umbral de acuerdo" in texto
    assert not any(
        p in texto.lower() for p in ("suspend", "falla", "insuficiente", "acuerdo suficiente")
    )


# ------------------------------------------------------------ lectura a mano y validacion


def test_regenerar_conserva_la_lectura_a_mano(tmp_path: Path) -> None:
    out = tmp_path / "human-vs-jury.md"
    assert human_vs_jury.main(_args(out)) == 0
    a_mano = f"{MANUAL}\n\nEl ritmo es donde mas discrepa: hipotesis con su cita.\n"
    out.write_text(out.read_text(encoding="utf-8") + "\n" + a_mano, encoding="utf-8")
    assert human_vs_jury.main(_args(out)) == 0
    texto = out.read_text(encoding="utf-8")
    assert texto.count(MANUAL) == 1 and texto.endswith("hipotesis con su cita.\n")
    assert human_vs_jury.main(_args(out, "--check")) == 0


def test_una_lectura_invalida_no_se_compara(tmp_path: Path) -> None:
    roto = tmp_path / "roto.json"
    novela = build_novel(tmp_path / "n.sqlite")
    out = tmp_path / "h.md"
    base = ["--trace", str(TRACE), "--out", str(out), "--novel", str(novela)]
    assert human_vs_jury.main(["--human", str(READING), *base]) == 0, "la de prueba valida"
    malo = READING.read_text(encoding="utf-8").replace("La barca de su abuelo", "La lancha", 1)
    roto.write_text(malo, encoding="utf-8")
    assert human_vs_jury.main(["--human", str(roto), *base]) == 1, "cita que no ancla"


def test_la_plantilla_sin_rellenar_no_se_compara(tmp_path: Path) -> None:
    plantilla = FIXTURES / "expected" / "plantilla-novela-prueba.json"
    out = tmp_path / "h.md"
    assert (
        human_vs_jury.main(["--human", str(plantilla), "--trace", str(TRACE), "--out", str(out)])
        == 1
    )
    assert not out.exists()
