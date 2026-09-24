"""Un caso que Lean detecta y los verificadores deterministas no. RF-272. VER-04, VER-10.

`evals/formal/CASOS.md`. Mutacion declarada como tal sobre la fixture limpia de
`verification/formal/fixtures`, que se construye con la API del canon: Tomas se
marcha el 2026-08-13 (`excluded`), y una escena nueva del capitulo 3, el
2026-08-30, lo trae de vuelta con una prosa que no nombra ninguna fecha.

- `check.formal` refuta `i4_absent_after_exclusion` antes de congelar, con la
  escena por entrar como fila de origen.
- `check.timeline` solo lee fechas explicitas: no hay ninguna, no marca nada.
- `check.availability` solo corre en la escena de encuentro y solo conoce
  lesionados y sancionados: con la lista que el motor le daria aqui, no marca.

    python -m pytest evals/formal/test_case.py -q

Sin `lake` las dos pruebas de Lean se saltan; el paso de Lean de `gate.py`
falla sin el.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from canon.freeze.freeze import SceneToFreeze
from commons.types.primitives import WorldTime
from verification.checks import deterministic as checks
from verification.formal import check, fixtures
from verification.formal.generate import THEOREMS, Pending

#: La prosa de la escena mutada. Sin fechas y sin marcador: nada que leer para
#: un verificador de texto.
TEXT = "Tomás volvió al parque aquella tarde y se sentó en el banco, junto a Lucía."

MUTATION = SceneToFreeze(
    id="c3e1",
    chapter=3,
    scene_number=1,
    pov_entity="lucia",
    place_entity="parque",
    world_time=WorldTime(stamp="2026-08-30"),
    function="cerrar",
    text=TEXT,
    summary="Tomás vuelve al parque",
    present=("tomas",),
)

real_lake = pytest.mark.skipif(check.find_lake() is None, reason="sin lake")


@pytest.fixture(scope="module")
def clean(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_clean(tmp_path_factory.mktemp("caso") / "clean.sqlite")


@real_lake
def test_sin_la_mutacion_lean_demuestra_la_cronologia(clean: Path) -> None:
    assert check.run_lean(clean).passed


@real_lake
def test_lean_caza_la_vuelta_del_excluido(clean: Path) -> None:
    result = check.run_lean(clean, Pending(scenes=(MUTATION,)))
    assert result.passed is False
    assert result.failed_theorems == (THEOREMS["I4"],)
    [violation] = result.violations
    assert violation.sources[0].pending is True
    assert violation.sources[0].key == ("c3e1", "tomas")
    assert 'attribute["tomas", "excluded", "2026-08-13"]' in result.rule


def test_los_verificadores_de_texto_no_ven_nada() -> None:
    # Las fechas del calendario de la obra: las de la fixture y la de la escena.
    fechas = ["2026-08-11", "2026-08-12", "2026-08-13", "2026-08-21", "2026-08-30"]
    assert checks.check_timeline(TEXT, allowed_dates=fechas) == []
    # `excluded` no es lesion ni sancion: el motor no lo pasa como indisponible.
    assert checks.check_availability(TEXT, unavailable=[]) == []
