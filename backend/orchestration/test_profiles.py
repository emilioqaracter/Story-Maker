"""El perfil de extension `breve` de punta a punta, sin modelo (D-132).

`specs/srs-backend-v4.md` RF-274, RD-50. Metodo VER-05: el brief lo acepta con
su rango de obra, `compose` planifica diez capitulos, lo periodico cae en el
5 y el 10, y los limites de escena del esquema no se mueven.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from canon.brief import Brief
from commons.types.length import BREVE, SCENE_WORDS_BOUNDS, LengthProfileName, of
from orchestration.compose import chapters_for
from orchestration.test_engine import _brief


def _breve(target: int) -> Brief:
    return Brief.model_validate(
        {
            **_brief().model_dump(),
            "length_profile": "breve",
            "target_words": target,
            "word_tolerance": 0.1,
        }
    )


def test_breve_son_diez_capitulos_de_una_escena_de_mil_a_mil_quinientas() -> None:
    assert of("breve") is BREVE
    assert BREVE.name is LengthProfileName.BREVE
    assert BREVE.chapters == 10 and BREVE.scenes_per_chapter == 1
    assert BREVE.chapter_words == BREVE.scene_words == (1_000, 1_500)
    assert BREVE.work_words == (10_000, 15_000)
    assert (BREVE.jury_threshold, BREVE.quote_min_words, BREVE.golden_cases) == (2, 8, 1)


def test_el_brief_breve_acepta_su_rango_y_compose_planifica_diez() -> None:
    brief = _breve(12_500)
    assert brief.word_range() == (11_250, 13_750)
    assert chapters_for(brief) == 10


@pytest.mark.parametrize("target", [9_999, 15_001])
def test_el_brief_breve_rechaza_una_extension_fuera_de_su_rango(target: int) -> None:
    with pytest.raises(ValidationError, match="breve"):
        _breve(target)


def test_en_breve_lo_periodico_corre_en_el_cinco_y_el_diez() -> None:
    due = [c for c in range(1, 11) if BREVE.periodic_due(c, last_chapter=10, every=5)]
    assert due == [5, 10]


def test_breve_no_mueve_los_limites_de_escena_del_esquema() -> None:
    assert SCENE_WORDS_BOUNDS == (400, 1_500)


def test_corta_son_cinco_capitulos_de_una_escena_y_permisiva() -> None:
    """D-139. `breve` con cinco capitulos."""
    from commons.types.length import CORTA

    assert of("corta") is CORTA
    assert CORTA.chapters == 5 and CORTA.scenes_per_chapter == 1
    assert CORTA.chapter_words == CORTA.scene_words == BREVE.chapter_words
    assert CORTA.work_words == (5_000, 7_500)
    assert CORTA.lenient and CORTA.jury_threshold == 2 and CORTA.golden_cases == 1


def test_el_brief_corta_planifica_cinco_y_lo_periodico_cae_al_cierre() -> None:
    from commons.types.length import CORTA

    brief = Brief.model_validate(
        {**_brief().model_dump(), "length_profile": "corta", "target_words": 6_250}
    )
    assert chapters_for(brief) == 5
    assert [c for c in range(1, 6) if CORTA.periodic_due(c, last_chapter=5, every=5)] == [5]
