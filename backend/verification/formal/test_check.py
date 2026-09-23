"""`run_lean`: fallo cerrado, teorema que falla y filas de origen. RF-245, RF-246, RNF-55. VER-05, VER-04."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from canon.events.types import AttributeSet, Event
from canon.freeze.freeze import SceneToFreeze
from commons.types.primitives import Evidence, Provenance, Severity, WorldTime
from verification.formal import check, fixtures
from verification.formal.check import LeanResult, Origin, Violation, parse_build, parse_report
from verification.formal.generate import THEOREMS, Pending, src

LAKE = check.find_lake()
real_lake = pytest.mark.skipif(
    LAKE is None,
    reason="sin lake: la compilacion real la exige, fallando, `python -m verification.formal.fixtures`",
)


@pytest.fixture(scope="module")
def clean(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_clean(tmp_path_factory.mktemp("lean") / "clean.sqlite")


@pytest.fixture(scope="module")
def seeded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_seeded(tmp_path_factory.mktemp("lean") / "seeded.sqlite")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Un proyecto vacio: con un `lake` doble no hace falta el de verdad."""
    (tmp_path / "proj").mkdir()
    return tmp_path / "proj"


# ------------------------------------------------------------------ fallo cerrado


def test_sin_lake_run_lean_devuelve_fallo_y_no_lanza(
    clean: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check, "find_lake", lambda: None)
    result = check.run_lean(clean, project=project)
    assert result.passed is False
    assert "lake" in result.reason
    assert result.rule.startswith("check.formal: ")


def test_un_lake_que_no_se_puede_ejecutar_es_fallo(clean: Path, project: Path) -> None:
    result = check.run_lean(clean, project=project, lake=[str(project / "no-existe.exe")])
    assert result.passed is False
    assert "no se pudo ejecutar" in result.reason


def test_agotar_el_tope_es_fallo(clean: Path, project: Path) -> None:
    dormido = [sys.executable, "-c", "import time; time.sleep(30)"]
    result = check.run_lean(clean, project=project, lake=dormido, timeout_s=0.5)
    assert result.passed is False
    assert "tope" in result.reason


def test_el_tope_por_defecto_es_el_del_proveedor() -> None:
    assert check.LAKE_TIMEOUT_S == 600


def test_una_novela_que_no_se_puede_leer_es_fallo(tmp_path: Path, project: Path) -> None:
    roto = tmp_path / "roto.sqlite"
    roto.write_bytes(b"no soy sqlite")
    result = check.run_lean(roto, project=project, lake=[sys.executable, "-c", "pass"])
    assert result.passed is False
    assert "no se pudo exportar" in result.reason


def test_lo_pendiente_que_no_se_puede_proyectar_es_fallo(clean: Path, project: Path) -> None:
    def evento(value: str) -> Event:
        return Event(
            world_time=WorldTime(stamp="2026-08-29"),
            payload=AttributeSet(entity_id="tomas", name="color", value=value),
            provenance=Provenance.PROSE,
            chapter_origin=3,
            entities=frozenset({"tomas"}),
        )

    # Dos eventos en el mismo instante y desempate: la proyeccion los rechaza.
    pending = Pending(events=(evento("a"), evento("b")))
    result = check.run_lean(clean, pending, project=project, lake=[sys.executable, "-c", "pass"])
    assert result.passed is False
    assert "no se pudo exportar" in result.reason


# ------------------------------------------------------------ con un lake doble

_FAKE = textwrap.dedent(
    '''
    import pathlib, sys
    args = sys.argv[1:]
    if args[0] == "build":
        module = args[1]
        rel = module.replace(".", "/") + ".lean"
        lines = pathlib.Path(rel).read_text(encoding="utf-8").splitlines()
        where = next(i for i, l in enumerate(lines, 1) if l.startswith("theorem MARK "))
        print(f"error: {rel}:{where + OFFSET}:10: Tactic `decide` proved that the proposition")
        print("  X.check chronicle = true")
        print("is false")
        sys.exit(1)
    print("I4\\t" + SRC_A + "\\t" + SRC_B)
    print("I1\\tno debe salir: su teorema no fallo")
    '''
)


def _fake(project: Path, *, theorem: str, offset: int = 0) -> list[str]:
    body = (
        _FAKE.replace("MARK", theorem)
        .replace("OFFSET", str(offset))
        .replace("SRC_A", repr(src("chronology", "c2e1", "tomas")))
        .replace("SRC_B", repr(src("attribute", "tomas", "excluded", "2026-08-13")))
    )
    script = project / "fake_lake.py"
    script.write_text(body, encoding="utf-8")
    return [sys.executable, str(script)]


def test_un_teorema_refutado_devuelve_su_nombre_y_sus_filas(clean: Path, project: Path) -> None:
    lake = _fake(project, theorem=THEOREMS["I4"])
    result = check.run_lean(clean, project=project, lake=lake)
    assert result.passed is False
    assert result.failed_theorems == (THEOREMS["I4"],)
    assert [v.invariant for v in result.violations] == ["I4"]
    assert result.scenes() == ("c2e1",)
    assert result.entities() == ("tomas",)
    assert THEOREMS["I4"] in result.rule
    assert 'chronology["c2e1", "tomas"]' in result.rule
    # No queda nada generado en el proyecto.
    assert sorted(p.name for p in project.rglob("*.lean")) == []


def test_un_error_fuera_de_los_teoremas_es_que_no_compila(clean: Path, project: Path) -> None:
    # La linea de encima del teorema es su comentario, no el teorema.
    lake = _fake(project, theorem=THEOREMS["I4"], offset=-1)
    result = check.run_lean(clean, project=project, lake=lake)
    assert result.passed is False
    assert result.reason == "la cronologia no compila"
    assert result.violations == ()


# ------------------------------------------------------------------- analisis


def test_solo_cuenta_la_refutacion_en_la_linea_del_teorema_de_su_fichero() -> None:
    lines = {40: THEOREMS["I1"], 43: THEOREMS["I2"]}
    out = "\n".join(
        [
            "error: Generated/C1.lean:40:9: Tactic `decide` proved that the proposition",
            "error: Generated/C1.lean:43:9: maximum recursion depth has been reached",
            "error: StoryMaker/Invariants.lean:40:1: unknown identifier",
            "error: build failed",
        ]
    )
    failed, other = parse_build(out, lines, "Generated/C1.lean")
    assert failed == (THEOREMS["I1"],)
    assert len(other) == 2


def test_el_informe_se_lee_por_invariante_con_sus_origenes() -> None:
    a = src("attribute", "rex", "collar", "2026-08-12T10:00")
    b = "pending." + src("chronology", "c3e1", "a|b\tc")
    out = f"I3\t{a}\r\nruido\nI2\t{b}\t{a}\n"
    found = parse_report(out.replace("a|b\tc", "a|b\\tc"))
    assert [v.invariant for v in found] == ["I3", "I2"]
    assert found[0].sources == (Origin(table="attribute", key=("rex", "collar", "2026-08-12T10:00")),)
    assert found[1].sources[0].pending is True
    assert found[1].sources[0].key == ("c3e1", "a|b\tc")
    assert str(found[1].sources[0]) == b


def test_un_resultado_fallido_es_un_s1_check_formal() -> None:
    result = LeanResult(
        passed=False,
        reason="falla i1",
        failed_theorems=(THEOREMS["I1"],),
        violations=(
            Violation(
                invariant="I1",
                theorem=THEOREMS["I1"],
                sources=(Origin(table="chronology", key=("c1e1", "ana")),),
            ),
        ),
    )
    defect = result.to_defect(Evidence(quote="Ana llegó al parque.", offset=0))
    assert defect.kind == "check.formal"
    assert defect.severity is Severity.S1
    assert THEOREMS["I1"] in defect.rule and '"c1e1", "ana"' in defect.rule


def test_un_resultado_que_pasa_no_es_un_defecto() -> None:
    with pytest.raises(ValueError):
        LeanResult(passed=True, reason="").to_defect(Evidence(quote="x", offset=0))


# ------------------------------------------------------------ con Lean de verdad


@real_lake
def test_la_fixture_limpia_se_demuestra(clean: Path) -> None:
    result = check.run_lean(clean)
    assert result.passed, result.output
    assert result.reason == ""


@real_lake
def test_la_sembrada_falla_en_sus_cuatro_teoremas_y_con_sus_filas(seeded: Path) -> None:
    result = check.run_lean(seeded)
    assert result.passed is False
    assert set(result.failed_theorems) == set(fixtures.SEEDED)
    for theorem, expected in fixtures.SEEDED.items():
        found = {tuple(str(s) for s in v.sources) for v in result.violations if v.theorem == theorem}
        assert found == set(expected), theorem
    assert not list((check.PROJECT / "Generated").glob("*.lean"))


@real_lake
def test_lo_que_va_a_entrar_se_demuestra_antes_de_congelar(clean: Path) -> None:
    """Lo que hara T46: Tomas se marcho el 13 y la escena por congelar lo trae el 30."""
    escena = SceneToFreeze(
        id="c3e1",
        chapter=3,
        scene_number=1,
        pov_entity="lucia",
        place_entity="parque",
        world_time=WorldTime(stamp="2026-08-30"),
        function="cerrar",
        text="Tomás volvió al parque.",
        summary="vuelta",
        present=("tomas",),
    )
    result = check.run_lean(clean, Pending(scenes=(escena,)))
    assert result.failed_theorems == (THEOREMS["I4"],)
    # La escena implicada es la que va a entrar: ahi busca la cita T46.
    assert result.scenes() == ("c3e1",)
    [violation] = result.violations
    assert violation.sources[0].pending is True
    assert violation.sources[0].key == ("c3e1", "tomas")
