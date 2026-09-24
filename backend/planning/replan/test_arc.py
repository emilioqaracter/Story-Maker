"""`replan.arc`. RF-19, RF-106. VER-05."""

from __future__ import annotations

import json

import pytest

from commons.types.primitives import WorldTime
from commons.types.scene import SceneFunction
from planning.outline.check import check
from planning.outline.types import ActPlan, Arc, ArcKind, Outline, SceneEntry, Setup
from planning.replan.arc import apply, parse


def _e(cap: int, pos: int, act: int, func: SceneFunction, dia: int) -> SceneEntry:
    return SceneEntry(
        id=f"c{cap}e{pos}",
        chapter=cap,
        ordinal=pos,
        act=act,
        function=func,
        pov="marcos",
        value_change="cambio",
        world_time=WorldTime(stamp=f"2026-08-{dia:02d}"),
        target_words=900,
    )


def _outline() -> Outline:
    return Outline(
        arcs=(
            Arc(
                id="comp",
                kind=ArcKind.COMPETITIVE,
                subject="marcos",
                start_scene="c1e1",
                crisis_scene="c1e2",
                resolution_scene="c2e1",
            ),
            Arc(
                id="int",
                kind=ArcKind.INTERNAL,
                subject="marcos",
                start_scene="c1e1",
                crisis_scene="c1e2",
                resolution_scene="c2e2",
            ),
        ),
        acts=(ActPlan(number=1, tension=(3,)), ActPlan(number=2, tension=(8,))),
        scenes=(
            _e(1, 1, 1, SceneFunction.ESTABLISH, 10),
            _e(1, 2, 1, SceneFunction.COMPLICATE, 11),
            _e(2, 1, 2, SceneFunction.CULMINATE, 20),
            _e(2, 2, 2, SceneFunction.ASSIMILATE, 21),
        ),
        setups=(Setup(id="la-lista", planted_scene="c1e1", payoff_scene="c2e1", description="d"),),
    )


def _tract() -> str:
    return json.dumps(
        {
            "scenes": [
                {
                    "id": "c2e1",
                    "chapter": 2,
                    "ordinal": 1,
                    "act": 2,
                    "function": "culminar",
                    "pov": "marcos",
                    "value_change": "de perder a ganar",
                    "world_time": {"stamp": "2026-08-20", "seq": 0},
                    "target_words": 900,
                },
                {
                    "id": "c2e2",
                    "chapter": 2,
                    "ordinal": 2,
                    "act": 2,
                    "function": "asimilar",
                    "pov": "marcos",
                    "value_change": "de ganar a entender",
                    "world_time": {"stamp": "2026-08-21", "seq": 0},
                    "target_words": 900,
                },
            ],
            "payoffs": {"la-lista": "c2e2"},
            "resolutions": {"comp": "c2e1", "int": "c2e2"},
            "tension": [9],
        }
    )


def test_el_tramo_nuevo_reemplaza_solo_el_acto_pedido() -> None:
    nueva = apply(_outline(), parse(_tract()), act=2, from_chapter=2)
    ids = [s.id for s in nueva.scenes]
    assert ids == ["c1e1", "c1e2", "c2e1", "c2e2"]
    assert nueva.scene("c2e1") is not None
    assert nueva.scene("c2e1").value_change == "de perder a ganar"  # type: ignore[union-attr]
    assert nueva.scene("c1e1") == _outline().scene("c1e1"), "lo anterior no se toca"


def test_las_promesas_se_recolocan_y_la_escaleta_sigue_pasando() -> None:
    nueva = apply(_outline(), parse(_tract()), act=2, from_chapter=2)
    assert nueva.setups[0].payoff_scene == "c2e2"
    assert nueva.acts[1].tension == (9,)
    assert check(nueva, word_range=(3_000, 4_000)) == []


def test_tocar_un_capitulo_congelado_se_rechaza() -> None:
    """Lo congelado no se toca: el remedio mira hacia delante."""
    tramo = parse(_tract())
    with pytest.raises(ValueError, match="fuera del tramo"):
        apply(_outline(), tramo, act=2, from_chapter=3)


def test_con_perfil_prueba_la_instruccion_fija_la_forma_y_el_presupuesto() -> None:
    """D-129. La tirada real eval-01 aborto porque la replanificacion del acto 2
    devolvia capitulos y una obra fuera del perfil `prueba`: la instruccion no le
    decia al Arquitecto la forma obligatoria. Ahora la dice, con el presupuesto."""
    from commons.types.length import PRUEBA
    from planning.replan.arc import instruction

    outline = _outline()
    texto = instruction(
        outline, act=2, from_chapter=2, unpaid_setups=[], reasons=["x"], profile=PRUEBA
    )
    low, high = PRUEBA.scene_words
    assert "FORMA OBLIGATORIA" in texto
    assert f"entre {low} y {high}" in texto
    assert f"{PRUEBA.scenes_per_chapter} escena" in texto
    assert "palabras en total" in texto


def test_con_perfil_novela_la_instruccion_no_cambia() -> None:
    from commons.types.length import NOVELA
    from planning.replan.arc import instruction

    outline = _outline()
    base = instruction(outline, act=2, from_chapter=2, unpaid_setups=[], reasons=["x"])
    con = instruction(
        outline, act=2, from_chapter=2, unpaid_setups=[], reasons=["x"], profile=NOVELA
    )
    assert base == con
    assert "FORMA OBLIGATORIA" not in con
