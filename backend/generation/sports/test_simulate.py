"""El motor de reglas del encuentro.

RF-42, RF-43, DEP-I1, DEP-I2. Metodos VER-05 y VER-06. Las dos propiedades que
importan: es determinista dada una semilla, y no alinea a quien no puede jugar.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from commons.types.primitives import WorldTime
from generation.sports.simulate import (
    Availability,
    MilestoneKind,
    Player,
    Squad,
    UnavailablePlayerError,
    simulate,
)

AT = WorldTime(stamp="2026-03-15")


def _squad(tid: str, n: int = 11, skill: int = 50, **kw: object) -> Squad:
    return Squad(
        team_id=tid,
        players=tuple(
            Player(entity_id=f"{tid}-{i}", name=f"{tid} {i}", skill=skill, **kw)  # type: ignore[arg-type]
            for i in range(n)
        ),
    )


def test_el_mismo_seed_da_el_mismo_partido() -> None:
    """Sin esto, reanudar una tirada daria un partido distinto y el capitulo ya
    escrito hablaria de otro encuentro."""
    a = simulate(_squad("local"), _squad("visitante"), at=AT, seed=7)
    b = simulate(_squad("local"), _squad("visitante"), at=AT, seed=7)
    assert a == b


def test_seeds_distintas_dan_partidos_distintos() -> None:
    resultados = {
        (r.home_goals, r.away_goals, tuple(m.minute for m in r.milestones))
        for r in (simulate(_squad("local"), _squad("visitante"), at=AT, seed=s) for s in range(12))
    }
    assert len(resultados) > 1


@settings(max_examples=30, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000))
def test_el_marcador_siempre_cuadra_con_los_hitos(seed: int) -> None:
    """DEP-I1. Que puedan discrepar es el defecto que todo esto existe para
    evitar, asi que se impone al construir el resultado y no se deja para un
    verificador posterior."""
    r = simulate(_squad("local"), _squad("visitante"), at=AT, seed=seed)
    goles = [m for m in r.milestones if m.kind is MilestoneKind.GOAL]
    assert sum(1 for m in goles if m.team_id == "local") == r.home_goals
    assert sum(1 for m in goles if m.team_id == "visitante") == r.away_goals


@settings(max_examples=30, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000))
def test_nadie_indisponible_aparece_en_el_encuentro(seed: int) -> None:
    """DEP-I2. No se comprueba despues: se hace imposible antes."""
    lesionados = Squad(
        team_id="local",
        players=(
            Player(entity_id="sano", name="Sano", skill=60),
            Player(entity_id="roto", name="Roto", availability=Availability.INJURED),
            Player(entity_id="sancionado", name="Sancionado", availability=Availability.SUSPENDED),
        ),
    )
    r = simulate(lesionados, _squad("visitante"), at=AT, seed=seed)
    actores = {m.player_id for m in r.milestones if m.team_id == "local"}
    assert actores <= {"sano"}


@settings(max_examples=20, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000))
def test_la_cronologia_va_en_orden(seed: int) -> None:
    """Sin orden total, dos ejecuciones con la misma semilla podrian narrarse
    en secuencia distinta."""
    r = simulate(_squad("local"), _squad("visitante"), at=AT, seed=seed)
    minutos = [m.minute for m in r.milestones]
    assert minutos == sorted(minutos)


def test_un_equipo_sin_nadie_disponible_no_juega() -> None:
    vacio = Squad(
        team_id="local",
        players=(Player(entity_id="roto", name="Roto", availability=Availability.INJURED),),
    )
    with pytest.raises(UnavailablePlayerError, match="ningun jugador disponible"):
        simulate(vacio, _squad("visitante"), at=AT, seed=1)


def test_el_mejor_gana_mas_veces_pero_no_siempre() -> None:
    """Que pueda perder es lo que hace que el arco competitivo tenga algo que
    contar: un desenlace seguro no es un arco."""
    fuerte, debil = _squad("fuerte", skill=90), _squad("debil", skill=30)
    victorias = sum(
        1
        for s in range(60)
        if simulate(fuerte, debil, at=AT, seed=s).home_goals
        > simulate(fuerte, debil, at=AT, seed=s).away_goals
    )
    assert 25 < victorias < 60
