"""El Jurado cabe en su presupuesto: 13.200 por instancia, 39.600 las tres.

RNF-57, D-94. VER-12, VER-06. `architecture.md` §4.2 y §4.9. Vive en
`orchestration/` porque cruza dos funcionalidades: la instruccion del Jurado
(`verification/`) y el presupuesto de la receta (`context/`).
"""

from __future__ import annotations

from collections.abc import Sequence

from hypothesis import given, settings
from hypothesis import strategies as st

from commons.types.rubrics import DEFAULT_RUBRICS
from context.packing.recipes import BUDGETS
from verification.jury import prompts
from verification.jury.prompts import COMMISSION_TOKENS
from verification.jury.test_rubrics_v2 import ESCENA, _relleno, _spec, tokens


def test_un_capitulo_en_el_techo_cabe_entero_en_13200() -> None:
    """RNF-57, D-94. Capitulo de 8.000, fichas de 800 y encargo de 500: la
    instancia entera, con su formato de salida, no pasa de su presupuesto, y las
    tres suman 39.600."""
    assert BUDGETS["juez"].input_tokens == 13_200
    assert 3 * BUDGETS["juez"].input_tokens == 39_600
    capitulo = _relleno(8_000, ESCENA)
    fichas = _relleno(800, "- Marcos (marcos, person): estado=sano, dorsal=9")
    encargo = prompts.commission_text(
        recipient="Ines",
        traits=(),
        memories=(_relleno(430, "el verano en que aprendio a flotar en el rio"),),
        tone="contenido",
    )
    assert tokens(encargo) <= COMMISSION_TOKENS
    instruccion = prompts.instruction(
        [_spec()],
        [capitulo],
        rubrics=DEFAULT_RUBRICS,
        voice_cards=fichas,
        seed=2,
        commission=encargo,
    )
    assert tokens(prompts.SYSTEM, instruccion, prompts.schema()) <= BUDGETS["juez"].input_tokens


@settings(max_examples=15, deadline=None)
@given(
    st.integers(min_value=0, max_value=8_000),
    st.integers(min_value=0, max_value=800),
    st.lists(st.sampled_from(["paciente", "el rio", "la cometa roja"]), max_size=6),
    st.integers(min_value=0, max_value=10_000),
)
def test_propiedad_dentro_de_los_cupos_la_instancia_cabe(
    cap: int, fichas: int, memorias: Sequence[str], semilla: int
) -> None:
    """VER-06. Sea cual sea la semilla y el tamano de cada bloque dentro de su cupo."""
    capitulo = _relleno(cap, ESCENA) if cap >= 60 else ""
    tarjetas = _relleno(fichas, "- Marcos (marcos, person): estado=sano") if fichas >= 20 else ""
    encargo = prompts.commission_text(
        recipient="Ines", traits=("paciente",), memories=tuple(memorias), tone="contenido"
    )
    instruccion = prompts.instruction(
        [_spec()],
        [capitulo],
        rubrics=DEFAULT_RUBRICS,
        voice_cards=tarjetas,
        seed=semilla,
        commission=encargo,
    )
    assert tokens(prompts.SYSTEM, instruccion, prompts.schema()) <= BUDGETS["juez"].input_tokens
