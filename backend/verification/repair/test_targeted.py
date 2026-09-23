"""`revise.targeted`: agrupar y revalidar. RF-53, RF-54. VER-05."""

from __future__ import annotations

from commons.types.primitives import Defect, Evidence, Severity
from verification.repair.targeted import evaluate, group_by_zone


def _d(rule: str, offset: int = 0, sev: Severity = Severity.S1) -> Defect:
    return Defect(kind="k", severity=sev, evidence=Evidence(quote="q", offset=offset), rule=rule)


def test_los_defectos_cercanos_se_reparan_juntos() -> None:
    grupos = group_by_zone([_d("a", 0), _d("b", 100), _d("c", 2000)])
    assert [len(g) for g in grupos] == [2, 1]


def test_una_reparacion_que_cierra_sin_abrir_se_acepta() -> None:
    r = evaluate([_d("a"), _d("b")], [_d("b")])
    assert r.accepted
    assert r.closed == ("k|a",)
    assert r.persisting == ("k|b",)


def test_una_reparacion_que_abre_un_defecto_nuevo_se_revierte() -> None:
    """RF-54: la que rompe otra cosa no vale, aunque cierre la suya."""
    r = evaluate([_d("a")], [_d("nuevo")])
    assert not r.accepted
    assert r.regressions == ("k|nuevo",)
    assert "revertida" in r.reason()


def test_solo_los_s1_cuentan_como_regresion_si_se_pide() -> None:
    r = evaluate([_d("a")], [_d("estilo", sev=Severity.S3)], blocking_only=True)
    assert r.accepted
