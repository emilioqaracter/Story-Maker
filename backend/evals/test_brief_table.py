"""La tabla brief x verificador. RF-269, D-95. VER-10.

La puerta de T51 para la tabla: se regenera identica desde ficheros de prueba
versionados, `evals/fixtures/traces/`, y dice lo que tiene que decir de cada
brief: el temporal falla `check.timeline` y Lean, el no deportivo no tiene
encuentros que verificar. Los extractos de prueba son dobles con la forma de la
traza real; la ultima prueba la obtiene del bucle de verdad con motores dobles,
para que la forma no se desvie de la que escribe `orchestration/loop.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from commons.tracing.trace import Trace
from commons.types.primitives import Defect, Evidence, Severity
from commons.types.rubrics import Dimension
from commons.types.scene import SceneSpec
from evals import brief_table
from evals.brief_table import NOT_APPLICABLE, PASSED, extract, load_extracts, render
from orchestration.loop import run
from orchestration.test_loop import _brief, _engine, _specs

FIXTURES = Path(__file__).parent / "fixtures"
TRACES = FIXTURES / "traces"
EXPECTED = FIXTURES / "expected" / "briefs.md"


def _row(table: str, brief: str) -> dict[str, str]:
    """La fila de un brief, por columna."""
    lineas = table.splitlines()
    cabecera = next(ln for ln in lineas if ln.startswith("| Brief | `outline.check`"))
    nombres = [c.strip().strip("`") for c in cabecera.strip("|").split("|")]
    fila = next(ln for ln in lineas if ln.startswith(f"| {brief} | ") and "`" not in ln[:40])
    return dict(zip(nombres, (c.strip() for c in fila.strip("|").split("|")), strict=True))


@pytest.fixture(scope="module")
def table() -> str:
    return render(load_extracts(TRACES))


# ------------------------------------------------------------ determinismo


def test_se_regenera_identica_desde_los_extractos_versionados(table: str) -> None:
    assert table == EXPECTED.read_text(encoding="utf-8")


def test_el_comando_da_el_mismo_fichero_dos_veces(tmp_path: Path) -> None:
    salidas = []
    for n in (1, 2):
        out = tmp_path / f"briefs-{n}.md"
        assert brief_table.main(["table", "--extracts", str(TRACES), "--out", str(out)]) == 0
        salidas.append(out.read_bytes())
    assert salidas[0] == salidas[1]
    assert salidas[0].decode("utf-8") == EXPECTED.read_text(encoding="utf-8")


def test_check_detecta_una_tabla_editada_a_mano(tmp_path: Path) -> None:
    out = tmp_path / "briefs.md"
    args = ["table", "--extracts", str(TRACES), "--out", str(out), "--check"]
    assert brief_table.main(args) == 1, "sin fichero no hay nada que coincida"
    out.write_text(EXPECTED.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    assert brief_table.main(args) == 0
    editada = EXPECTED.read_text(encoding="utf-8").replace("falló (1)", PASSED, 1)
    out.write_text(editada, encoding="utf-8", newline="\n")
    assert brief_table.main(args) == 1


# ------------------------------------------------------------ contenido


def test_el_brief_temporal_falla_la_cronologia_y_lean(table: str) -> None:
    fila = _row(table, "03-temporal")
    assert fila["check.timeline"] == "falló (1)"
    assert fila["check.formal"] == "falló (1)"
    assert fila["continuity"] == "falló (1)"
    assert fila["work.close"] == "falló (1)"
    assert fila["check.forbidden"] == PASSED


def test_el_brief_semilla_pasa_todo_lo_que_le_aplica(table: str) -> None:
    fila = _row(table, "01-semilla")
    assert {v for k, v in fila.items() if k != "Brief"} <= {PASSED, NOT_APPLICABLE}
    assert fila["check.ledger"] == PASSED, "tiene encuentros: verify_match corrio"


def test_forbidden_cuenta_la_escena_y_la_red_antes_de_congelar(table: str) -> None:
    assert _row(table, "04-menor")["check.forbidden"] == "falló (2)"


def test_sin_encuentros_los_verificadores_de_partido_no_aplican(table: str) -> None:
    fila = _row(table, "05-no-deportivo")
    assert fila["check.ledger"] == fila["check.availability"] == NOT_APPLICABLE
    assert fila["check.formal"] == NOT_APPLICABLE
    assert fila["quiz"] == NOT_APPLICABLE, "un examen sin preguntas no se hizo"
    assert fila["check.format"] == PASSED


def test_sin_cierre_la_obra_cuenta_como_fallida(table: str) -> None:
    """`AGENTS.md` §5.3: una comprobacion que no corre cuenta como fallida."""
    assert _row(table, "05-no-deportivo")["work.close"] == "falló (1)"
    assert "| 05-no-deportivo | `5e6f7a8` | 2026-09-23 | sin work.close |" in table


def test_una_columna_por_dimension_de_las_rubricas(table: str) -> None:
    fila = _row(table, "01-semilla")
    assert [k for k in fila if k.startswith("jury.")] == [f"jury.{d.value}" for d in Dimension]


def test_un_kind_sin_columna_gana_la_suya(table: str) -> None:
    fila = _row(table, "05-no-deportivo")
    assert fila["check.novedad"] == "falló (1)"
    assert _row(table, "01-semilla")["check.novedad"] == PASSED


def test_cada_tirada_lleva_su_commit_y_sus_versiones_de_prompt(table: str) -> None:
    assert "| 03-temporal | `1a2b3c4` | 2026-09-21 | no cerró: deuda narrativa" in table
    assert "`jurado=99aa88bb77cc/dd11ee22ff33`" in table, "dos versiones en una tirada constan"


# ------------------------------------------------------------ extractos


def _traza(path: Path) -> Trace:
    traza = Trace(path)
    traza.emit("outline.check", defects=[], passed=True, outline="{...escaleta...}", messages=[])
    traza.emit("call", agent="escritor", prompt_version="abc123abc123", real_input=900, ok=True)
    traza.emit("packet", agent="escritor", tokens=900)
    traza.emit("work.close", closed=True, reason="", words=10)
    return traza


def test_el_extracto_guarda_lo_que_la_tabla_mide_y_nada_mas(tmp_path: Path) -> None:
    traza = _traza(tmp_path / "t.trace.jsonl")
    ex = extract("01-semilla", traza.path or Path(), "abcdef1")
    assert [r.kind for r in ex.records] == ["outline.check", "call", "work.close"]
    assert "outline" not in ex.records[0].fields, "la escaleta no es un resultado"
    assert set(ex.records[1].fields) == {"agent", "prompt_version", "ok"}
    assert ex.source == "t.trace.jsonl", "sin ruta: la maquina no entra en el fichero"


def test_extraer_dos_veces_da_el_mismo_fichero(tmp_path: Path) -> None:
    traza = _traza(tmp_path / "t.trace.jsonl")
    outs = [tmp_path / "a.json", tmp_path / "b.json"]
    for out in outs:
        args = ["extract", "--brief", "01-semilla", "--trace", str(traza.path)]
        assert brief_table.main([*args, "--commit", "abcdef1", "--out", str(out)]) == 0
    assert outs[0].read_bytes() == outs[1].read_bytes()
    assert brief_table.load_records(outs[0]) == list(
        extract("x", traza.path or Path(), "abcdef1").records
    )


def test_un_extracto_sin_commit_valido_o_sin_traza_no_se_escribe(tmp_path: Path) -> None:
    traza = _traza(tmp_path / "t.trace.jsonl")
    with pytest.raises(ValidationError):
        extract("01-semilla", traza.path or Path(), "no-es-un-commit")
    with pytest.raises(FileNotFoundError):
        extract("01-semilla", tmp_path / "no-existe.jsonl", "abcdef1")
    (tmp_path / "vacia.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="no tiene registros"):
        extract("01-semilla", tmp_path / "vacia.jsonl", "abcdef1")


# ------------------------------------------------------------ con el bucle real


def test_desde_la_traza_del_bucle_con_dobles(tmp_path: Path) -> None:
    """La traza que escribe `loop.py`, con un `check.timeline` en el primer
    intento de la primera escena, da esa celda y deja las demas en «pasó»."""
    from canon.brief import create_novel

    novela = tmp_path / "n.sqlite"
    create_novel(novela, _brief())
    vistos: set[str] = set()

    def verifica(spec: SceneSpec, texto: str) -> list[Defect]:
        sid = spec.identity.scene_id
        if sid == "c1e1" and sid not in vistos:
            vistos.add(sid)
            return [
                Defect(
                    kind="check.timeline",
                    severity=Severity.S1,
                    evidence=Evidence(quote=texto.split()[0], offset=0),
                    rule="fecha fuera del calendario",
                )
            ]
        return []

    traza = Trace(tmp_path / "loop.trace.jsonl")
    informe = run(
        novela,
        _brief(),
        _engine(verify_scene=verifica),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )
    assert informe.closed, informe.reason

    carpeta = tmp_path / "extractos"
    carpeta.mkdir()
    ex = extract("99-bucle", traza.path or Path(), "0123abc")
    (carpeta / "99-bucle.json").write_text(brief_table.dumps(ex), encoding="utf-8")
    fila = _row(render(load_extracts(carpeta)), "99-bucle")

    assert fila["check.timeline"] == "falló (1)"
    esperados: Sequence[str] = ("outline.check", "check.format", "continuity", "quiz", "work.close")
    assert all(fila[c] == PASSED for c in esperados), fila
    assert all(fila[f"jury.{d.value}"] == PASSED for d in Dimension)


def test_la_columna_del_jurado_usa_el_umbral_registrado_con_el_veredicto() -> None:
    """D-115. En `prueba` un 2 aprueba; una traza sin umbral lleva el de `novela`."""
    from pydantic import JsonValue

    from commons.tracing.trace import TraceRecord

    def jurado(nivel: int, **extra: int) -> TraceRecord:
        campos: dict[str, JsonValue] = {"levels": {"voice": nivel}, **extra}
        return TraceRecord(seq=0, at="2026-09-24T00:00:00Z", kind="jury", fields=campos)

    celda = brief_table._jury(Dimension.VOICE).cell
    assert celda([jurado(2, threshold=2)], []).render() == PASSED
    assert celda([jurado(2)], []).render() == "falló (1)"
    assert celda([jurado(1, threshold=2)], []).render() == "falló (1)"
