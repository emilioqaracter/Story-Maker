"""Metricas de salud y veredicto del Supervisor. RF-144 a RF-149. VER-05, VER-06."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from canon.freeze.rows import MetricRow
from commons.tracing.trace import TraceRecord
from supervision import metrics
from supervision.prompts import HealthVerdict, clamp


def _r(seq: int, kind: str, **fields: object) -> TraceRecord:
    return TraceRecord(seq=seq, at="t", kind=kind, fields=fields)  # type: ignore[arg-type]


def _hist(signal: str, values: list[float]) -> list[MetricRow]:
    return [
        MetricRow(chapter=i + 1, signal=signal, value=v, threshold="", state="ok")
        for i, v in enumerate(values)
    ]


def test_solo_cuenta_lo_posterior_a_la_ultima_congelacion() -> None:
    regs = [_r(0, "scene.attempt"), _r(1, "chapter.frozen"), _r(2, "repair")]
    assert [r.seq for r in metrics.since_last_freeze(regs)] == [2]


def test_las_trece_senales_salen_siempre() -> None:
    """RF-144."""
    filas = metrics.compute(
        1, [], [], open_setups=0, act_quarantines=0, deviations=[], after_first_act=False
    )
    assert [f.signal for f in filas] == list(metrics.SIGNALS)
    assert all(f.state in {"ok", "unknown"} for f in filas)


def test_la_tasa_de_reparacion_por_encima_del_30_es_alarma() -> None:
    """RF-145, literal de §11."""
    regs = [
        _r(0, "scene.attempt", passed=True, words=500, defects=[]),
        _r(1, "scene.attempt", passed=True, words=500, defects=[]),
        _r(2, "repair", accepted=True),
    ]
    filas = {
        f.signal: f
        for f in metrics.compute(
            3, regs, [], open_setups=0, act_quarantines=0, deviations=[], after_first_act=False
        )
    }
    assert filas["repair_rate"].value == 0.5
    assert filas["repair_rate"].state == "alarm"


def test_la_deuda_al_alza_tres_capitulos_es_alarma_y_dos_no() -> None:
    """RF-145: tendencia creciente es tres capitulos consecutivos al alza."""
    dos = metrics.compute(
        2,
        [],
        _hist("narrative_debt", [1]),
        open_setups=2,
        act_quarantines=0,
        deviations=[],
        after_first_act=False,
    )
    tres = metrics.compute(
        3,
        [],
        _hist("narrative_debt", [1, 2]),
        open_setups=3,
        act_quarantines=0,
        deviations=[],
        after_first_act=False,
    )
    assert {f.signal: f.state for f in dos}["narrative_debt"] == "ok"
    assert {f.signal: f.state for f in tres}["narrative_debt"] == "alarm"


def test_real_por_encima_de_estimado_y_degradacion_son_alarma_a_la_primera() -> None:
    regs = [
        _r(0, "call", estimate_short=True),
        _r(1, "packet", degraded=True, blocks=[], quotas=[], empty_quotas=[]),
    ]
    filas = {
        f.signal: f.state
        for f in metrics.compute(
            1, regs, [], open_setups=0, act_quarantines=0, deviations=[], after_first_act=False
        )
    }
    assert filas["estimate_short"] == "alarm"
    assert filas["degraded_retrievals"] == "alarm"


@settings(max_examples=50, deadline=None)
@given(st.lists(st.floats(min_value=0, max_value=10, allow_nan=False), min_size=0, max_size=6))
def test_las_metricas_son_deterministas(serie: list[float]) -> None:
    """RF-144: recomputables."""
    hist = _hist("s1_per_1000", serie)
    a = metrics.compute(
        9, [], hist, open_setups=1, act_quarantines=0, deviations=[], after_first_act=True
    )
    b = metrics.compute(
        9, [], hist, open_setups=1, act_quarantines=0, deviations=[], after_first_act=True
    )
    assert a == b


def test_el_tramo_nunca_empieza_en_un_capitulo_congelado() -> None:
    """RF-147."""
    v = HealthVerdict(healthy=False, signal="narrative_debt", act=2, from_chapter=2)
    acotado = clamp(v, last_frozen=4, total_chapters=8)
    assert acotado is not None and acotado.from_chapter == 5
    assert clamp(v, last_frozen=8, total_chapters=8) is None
    assert clamp(HealthVerdict(healthy=True), last_frozen=1, total_chapters=8) is None
