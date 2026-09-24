"""La tabla de validadores de `architecture.md` §9.1 frente al codigo (RF-268, T50).

Cada prueba trabaja sobre copias en un directorio temporal: el `architecture.md`
y los modulos del backend reales no se tocan nunca. La puerta de T50 es que
borrar una fila `check.*` de la tabla, o anadir un `kind` sin fila, haga fallar
la comprobacion.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import coherence
from coherence import Report, check_validators

ARCH = coherence.DOCS / "architecture.md"


@pytest.fixture
def copia(tmp_path: Path) -> tuple[Path, Path]:
    """Una copia del `architecture.md` y de los `.py` del backend que la comprobacion lee."""
    arch = tmp_path / "architecture.md"
    shutil.copyfile(ARCH, arch)
    backend = tmp_path / "backend"
    for pkg in ("verification", "evals"):
        shutil.copytree(
            coherence.BACKEND / pkg,
            backend / pkg,
            ignore=shutil.ignore_patterns("__pycache__", "*.lean", "results", "fixtures"),
        )
    return arch, backend


def _errores(arch: Path, backend: Path) -> list[str]:
    report = Report()
    check_validators(report, arch.read_text(encoding="utf-8"), backend)
    return report.errors


def _reescribe(path: Path, viejo: str, nuevo: str) -> None:
    texto = path.read_text(encoding="utf-8")
    assert viejo in texto, f"la copia no contiene {viejo!r}"
    path.write_text(texto.replace(viejo, nuevo, 1), encoding="utf-8")


def _fila(arch: Path, validador: str) -> str:
    for line in coherence.section(arch.read_text(encoding="utf-8"), "9.1").splitlines():
        if line.startswith("|") and f"| {validador} |" in line:
            return line
    raise AssertionError(f"no hay fila {validador} en la copia")


def test_el_repositorio_real_pasa() -> None:
    report = Report()
    check_validators(report, ARCH.read_text(encoding="utf-8"), coherence.BACKEND)
    assert report.errors == []


def test_la_copia_intacta_pasa(copia: tuple[Path, Path]) -> None:
    assert _errores(*copia) == []


def test_los_kind_del_codigo_salen_de_sus_asignaciones() -> None:
    kinds = coherence.code_check_kinds(coherence.BACKEND)
    assert {
        "check.timeline",
        "check.format",
        "check.lexicon",
        "check.knowledge",
        "check.repetition",
        "check.forbidden",
        "check.ledger",
        "check.availability",
        "check.formal",
    } <= set(kinds)
    assert all(k.startswith("check.") for k in kinds)


@pytest.mark.parametrize("validador", ["`check.lexicon`", "`check.formal`", "`check.evidence`"])
def test_borrar_una_fila_falla(copia: tuple[Path, Path], validador: str) -> None:
    arch, backend = copia
    _reescribe(arch, _fila(arch, validador) + "\n", "")
    errores = _errores(arch, backend)
    assert errores, f"borrar la fila {validador} no hizo fallar la comprobacion"


def test_un_kind_sin_fila_falla(copia: tuple[Path, Path]) -> None:
    arch, backend = copia
    nuevo = backend / "verification" / "checks" / "nuevo.py"
    nuevo.write_text('KIND = "check.pacing"\n', encoding="utf-8")
    errores = _errores(arch, backend)
    assert any("check.pacing" in e and "§9.1" in e for e in errores), errores


def test_un_modulo_validador_sin_fila_falla(copia: tuple[Path, Path]) -> None:
    arch, backend = copia
    nuevo = backend / "verification" / "checks" / "pacing.py"
    nuevo.write_text('"""`check.pacing`. El ritmo de la escena."""\n', encoding="utf-8")
    errores = _errores(arch, backend)
    assert any("check.pacing" in e and "§9.1" in e for e in errores), errores


def test_un_modulo_que_no_se_declara_no_pide_fila(copia: tuple[Path, Path]) -> None:
    arch, backend = copia
    nuevo = backend / "verification" / "checks" / "helpers.py"
    nuevo.write_text('"""Utilidades comunes de los verificadores."""\n', encoding="utf-8")
    assert _errores(arch, backend) == []


def test_un_kind_en_una_llamada_sin_fila_falla(copia: tuple[Path, Path]) -> None:
    arch, backend = copia
    _reescribe(
        backend / "verification" / "checks" / "deterministic.py",
        'kind="check.knowledge"',
        'kind="check.omniscience"',
    )
    errores = _errores(arch, backend)
    assert any("check.omniscience" in e for e in errores), errores


def test_una_fila_sin_codigo_falla(copia: tuple[Path, Path]) -> None:
    arch, backend = copia
    fila = _fila(arch, "`check.lexicon`")
    _reescribe(arch, fila, fila + "\n" + fila.replace("check.lexicon", "check.meter"))
    errores = _errores(arch, backend)
    assert any("check.meter" in e for e in errores), errores


def test_una_fila_sin_punto_de_ejecucion_falla(copia: tuple[Path, Path]) -> None:
    arch, backend = copia
    fila = _fila(arch, "`check.knowledge`")
    celdas = fila.split("|")
    celdas[4] = " "
    _reescribe(arch, fila, "|".join(celdas))
    errores = _errores(arch, backend)
    assert any("check.knowledge" in e and "punto de ejecucion" in e for e in errores), errores


def test_el_modulo_basta_para_una_fila(copia: tuple[Path, Path]) -> None:
    """`check.evidence` no es `kind` de ningun defecto: existe como modulo."""
    arch, backend = copia
    (backend / "verification" / "checks" / "evidence.py").unlink()
    errores = _errores(arch, backend)
    assert any("check.evidence" in e for e in errores), errores


def test_la_tabla_por_brief_con_un_verificador_de_mas_falla(copia: tuple[Path, Path]) -> None:
    arch, backend = copia
    _reescribe(
        backend / "evals" / "brief_table.py",
        'MATCH_CHECKS = ("check.ledger", "check.availability")',
        'MATCH_CHECKS = ("check.ledger", "check.availability", "check.formal")',
    )
    errores = _errores(arch, backend)
    assert any("brief_table" in e and "check.formal" in e for e in errores), errores


def test_la_tabla_por_brief_con_un_verificador_de_menos_falla(copia: tuple[Path, Path]) -> None:
    arch, backend = copia
    _reescribe(backend / "evals" / "brief_table.py", '    "check.lexicon",\n', "")
    errores = _errores(arch, backend)
    assert any("brief_table" in e and "check.lexicon" in e for e in errores), errores


def test_sin_tabla_falla(copia: tuple[Path, Path]) -> None:
    arch, backend = copia
    texto = arch.read_text(encoding="utf-8")
    arch.write_text(texto.replace("| Punto de ejecución |", "| Cuando |"), encoding="utf-8")
    assert _errores(arch, backend)
