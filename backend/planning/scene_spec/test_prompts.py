"""El Planificador: de la salida a especificaciones. RF-28 a RF-30. VER-05, VER-08."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from commons.types.primitives import WorldTime
from commons.types.scene import SceneFunction
from planning.outline.types import SceneEntry
from planning.scene_spec.prompts import parse


def _entry(is_match: bool = False) -> SceneEntry:
    return SceneEntry(
        id="c1e1",
        chapter=1,
        ordinal=1,
        act=1,
        function=SceneFunction.ESTABLISH,
        pov="marcos",
        value_change="de la duda a la decision",
        world_time=WorldTime(stamp="2026-08-10"),
        target_words=900,
        is_match=is_match,
    )


def _body(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "place": "vestuario",
        "cast": ["marcos", "tecnico"],
        "beats": ["entra", "descubre la lista", "sale"],
        "objective": "saber si juega",
        "obstacle": "nadie habla",
        "ends_with": "sale sin saberlo",
        "setups_to_plant": ["la-lista"],
        "setups_to_pay": [],
    }
    base.update(kw)
    return base


def test_lo_que_la_escaleta_fijo_no_se_decide_otra_vez() -> None:
    spec = parse(json.dumps({"scenes": {"c1e1": _body()}}), [_entry()])[0]
    assert spec.identity.pov == "marcos"
    assert spec.identity.chapter == 1
    assert spec.function.value_change == "de la duda a la decision"
    assert spec.output.target_words == 900
    assert spec.content.setups_to_plant == ("la-lista",)


def test_una_escena_de_encuentro_se_marca() -> None:
    """RF-30."""
    spec = parse(json.dumps({"scenes": {"c1e1": _body()}}), [_entry(is_match=True)])[0]
    assert spec.is_match


def test_un_pov_fuera_del_elenco_no_encaja() -> None:
    """RF-29, EST-I1: se rechaza en el parseo."""
    with pytest.raises(ValidationError):
        parse(json.dumps({"scenes": {"c1e1": _body(cast=["tecnico"])}}), [_entry()])


def test_una_escena_sin_especificar_es_un_error() -> None:
    with pytest.raises(ValueError, match="no especifico"):
        parse(json.dumps({"scenes": {}}), [_entry()])


def test_sin_pasos_no_hay_especificacion() -> None:
    with pytest.raises(ValidationError):
        parse(json.dumps({"scenes": {"c1e1": _body(beats=[])}}), [_entry()])
