"""La especificacion de escena.

RF-28 a RF-30, EST-I1. Lo que se comprueba es que las invariantes se imponen al
CONSTRUIR: una escena sin POV en el elenco o sin cambio de valor no es una
especificacion mala, es un objeto que no deberia existir.
"""

from __future__ import annotations

import pytest

from commons.types.primitives import WorldTime
from commons.types.scene import SceneFunction
from planning.outline.types import SceneEntry
from planning.scene_spec.spec import from_entry


def _entry(**kw: object) -> SceneEntry:
    base: dict[str, object] = {
        "id": "s1",
        "chapter": 2,
        "ordinal": 1,
        "act": 1,
        "function": SceneFunction.REVEAL,
        "pov": "marcos",
        "value_change": "de la confianza a la sospecha",
        "world_time": WorldTime(stamp="2026-02-01", seq=0),
        "target_words": 900,
    }
    base.update(kw)
    return SceneEntry(**base)  # type: ignore[arg-type]


def _spec(**kw: object):  # type: ignore[no-untyped-def]
    args: dict[str, object] = {
        "place": "vestuario",
        "cast": ("marcos", "elena"),
        "beats": ("entra", "descubre", "calla"),
        "objective": "saber si le han vendido",
        "obstacle": "nadie se lo dira",
        "ends_with": "sale sabiendo menos de lo que creia",
    }
    args.update(kw)
    return from_entry(_entry(), **args)  # type: ignore[arg-type]


def test_lo_que_viene_de_la_escaleta_no_se_decide_otra_vez() -> None:
    """Si el Planificador pudiera cambiarlo, la escaleta congelada dejaria de
    gobernar y volveria a ser una sugerencia."""
    s = _spec()
    assert s.identity.chapter == 2
    assert s.identity.pov == "marcos"
    assert s.function.function is SceneFunction.REVEAL
    assert s.output.target_words == 900


def test_el_pov_tiene_que_estar_en_el_elenco() -> None:
    with pytest.raises(ValueError, match="no esta en el elenco"):
        _spec(cast=("elena", "tecnico"))


def test_un_encuentro_se_marca_como_tal() -> None:
    """RF-30. Lo marcado decide si el motor de reglas lo resuelve antes de que
    se narre."""
    spec = from_entry(
        _entry(is_match=True),
        place="estadio",
        cast=("marcos",),
        beats=("saca",),
        objective="ganar",
        obstacle="el rival",
        ends_with="pierden",
    )
    assert spec.is_match


def test_la_especificacion_ya_es_la_consulta() -> None:
    """RF-72. El artefacto que describe lo que se va a escribir es la mejor
    descripcion de lo que conviene recuperar, y ya existe."""
    q = _spec().semantic_query()
    assert "saber si le han vendido" in q
    assert "descubre" in q
    assert "sospecha" in q


def test_una_escena_sin_beats_no_se_puede_construir() -> None:
    with pytest.raises(ValueError):
        _spec(beats=())


def test_una_escena_sin_elenco_no_se_puede_construir() -> None:
    with pytest.raises(ValueError):
        _spec(cast=())
