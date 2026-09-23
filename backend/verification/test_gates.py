"""Las puertas de la version 1. RF-22, D-06. VER-05."""

from __future__ import annotations

from commons.types.primitives import Defect, Evidence, Severity
from verification.gates import CHAPTER_MAX_S2, chapter_gate, scene_gate


def _d(sev: Severity) -> Defect:
    return Defect(kind="x", severity=sev, evidence=Evidence(quote="q", offset=0), rule="r")


def test_una_escena_pasa_sin_s1_aunque_tenga_s2() -> None:
    assert scene_gate([_d(Severity.S2), _d(Severity.S3)]).passed
    assert not scene_gate([_d(Severity.S1)]).passed


def test_un_capitulo_tolera_hasta_dos_s2_y_ningun_s1() -> None:
    assert chapter_gate([_d(Severity.S2)] * CHAPTER_MAX_S2).passed
    assert not chapter_gate([_d(Severity.S2)] * (CHAPTER_MAX_S2 + 1)).passed
    assert not chapter_gate([_d(Severity.S1)]).passed


def test_la_razon_dice_que_fallo() -> None:
    r = chapter_gate([_d(Severity.S1), _d(Severity.S2)] + [_d(Severity.S2)] * 2)
    assert "1 S1" in r.reason()
    assert "S2" in r.reason()
    assert chapter_gate([]).reason() == "pasa"
