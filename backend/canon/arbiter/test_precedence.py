"""La politica de precedencia.

RF-59, RF-61, RF-62. Metodos VER-04 y VER-06. Las dos propiedades que abren la
puerta de este tramo: la politica es TOTAL y sin ciclos, y fusionar dos deltas
es asociativo.

Que sea total no es elegancia: es lo que hace que el sistema pueda terminar
solo. Una regla que a veces empata es una regla que a veces necesita a alguien.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from canon.arbiter.precedence import Claim, Rule, arbitrate, merge_deltas
from commons.types.primitives import Provenance


def _claim(**kw: object) -> Claim:
    base: dict[str, object] = {
        "fact_key": "marcos.estado", "value": "sano",
        "provenance": Provenance.PROSE, "frozen": False,
    }
    base.update(kw)
    return Claim(**base)  # type: ignore[arg-type]


_claims = st.builds(
    Claim,
    fact_key=st.just("marcos.estado"),
    value=st.sampled_from(["sano", "lesionado", "dudoso"]),
    provenance=st.sampled_from(list(Provenance)),
    frozen=st.booleans(),
    hard_invariant=st.booleans(),
    payoff_paid=st.booleans(),
)


# --------------------------------------------------- las cuatro reglas

def test_el_canon_congelado_gana_al_delta_nuevo() -> None:
    v = arbitrate(_claim(frozen=True), _claim(value="lesionado"))
    assert not v.challenger_won
    assert v.rule is Rule.FROZEN_OVER_NEW


def test_el_brief_gana_al_canon_derivado() -> None:
    v = arbitrate(
        _claim(provenance=Provenance.DERIVED),
        _claim(provenance=Provenance.BRIEF, value="lesionado"),
    )
    assert v.challenger_won
    assert v.rule is Rule.BRIEF_OVER_DERIVED


def test_el_invariante_duro_gana_a_la_preferencia() -> None:
    v = arbitrate(_claim(), _claim(hard_invariant=True, value="lesionado"))
    assert v.challenger_won
    assert v.rule is Rule.HARD_OVER_AESTHETIC


def test_un_hecho_con_payoff_cobrado_gana() -> None:
    v = arbitrate(_claim(payoff_paid=True), _claim(value="lesionado"))
    assert not v.challenger_won
    assert v.rule is Rule.PAID_OVER_UNPAID


def test_el_orden_de_las_reglas_manda() -> None:
    """Congelado pesa mas que procedencia: un delta del brief no tumba canon
    congelado, aunque el brief gane al canon derivado."""
    v = arbitrate(
        _claim(frozen=True, provenance=Provenance.DERIVED),
        _claim(provenance=Provenance.BRIEF, value="lesionado"),
    )
    assert not v.challenger_won
    assert v.rule is Rule.FROZEN_OVER_NEW


# ------------------------------------------------- totalidad y sin ciclos

@settings(max_examples=100, deadline=None)
@given(a=_claims, b=_claims)
def test_todo_conflicto_tiene_exactamente_un_ganador(a: Claim, b: Claim) -> None:
    """RF-61. Sin esto, un conflicto podria quedar sin resolver y el ciclo se
    detendria esperando a alguien que no existe."""
    v = arbitrate(a, b)
    assert v.winner in (a, b)


@settings(max_examples=100, deadline=None)
@given(a=_claims, b=_claims)
def test_el_veredicto_no_depende_del_orden(a: Claim, b: Claim) -> None:
    """La afirmacion mas fuerte gana en los dos ordenes.

    Es la forma comprobable de "sin ciclos": si invertir los argumentos cambiara
    al ganador, el resultado dependeria de cual llego antes, que es justo lo que
    una politica total tiene que quitar.

    Se compara por fuerza y no por identidad porque dos afirmaciones pueden ser
    indistinguibles para las cuatro reglas; entonces gana la establecida, que en
    cada orden es una distinta, y las dos son respuestas correctas.
    """
    from canon.arbiter.precedence import _score

    assert _score(arbitrate(a, b).winner) == _score(arbitrate(b, a).winner)


@settings(max_examples=100, deadline=None)
@given(a=_claims, b=_claims)
def test_la_mas_fuerte_gana_siempre(a: Claim, b: Claim) -> None:
    """Y cuando una es estrictamente mas fuerte, gana ella en los dos ordenes."""
    from canon.arbiter.precedence import _score

    if _score(a) > _score(b):
        assert arbitrate(a, b).winner is a
        assert arbitrate(b, a).winner is a


@settings(max_examples=100, deadline=None)
@given(a=_claims, b=_claims)
def test_en_empate_gana_lo_establecido(a: Claim, b: Claim) -> None:
    """No es un desempate arbitrario: lo establecido es lo que el resto de la
    obra ya da por cierto, y cambiarlo obliga a revisar lo que se apoyo en
    ello."""
    from canon.arbiter.precedence import _score

    if _score(a) == _score(b):
        assert arbitrate(a, b).winner is a


def test_dos_hechos_distintos_no_son_un_conflicto() -> None:
    with pytest.raises(ValueError, match="hechos distintos"):
        arbitrate(_claim(), _claim(fact_key="elena.estado"))


# ---------------------------------------------------------- asociatividad

@settings(max_examples=60, deadline=None)
@given(
    a=st.lists(_claims, max_size=3),
    b=st.lists(_claims, max_size=3),
    c=st.lists(_claims, max_size=3),
)
def test_fusionar_deltas_es_asociativo(
    a: list[Claim], b: list[Claim], c: list[Claim]
) -> None:
    """RF-62. El orden en que llegan los deltas de dos capitulos no puede
    cambiar el canon resultante."""
    izq = merge_deltas(merge_deltas(tuple(a), tuple(b)), tuple(c))
    der = merge_deltas(tuple(a), merge_deltas(tuple(b), tuple(c)))
    assert {(x.fact_key, x.value) for x in izq} == {(x.fact_key, x.value) for x in der}


def test_el_arbitraje_registra_la_regla_no_solo_el_ganador() -> None:
    """Sin la regla, revisar una tirada de treinta capitulos es adivinar por que
    el sistema decidio lo que decidio."""
    v = arbitrate(_claim(frozen=True), _claim(value="lesionado"),
                  affected_passages=("cap-3-esc-2",))
    assert v.rule is Rule.FROZEN_OVER_NEW
    assert v.affected_passages == ("cap-3-esc-2",)
