"""Comparar tiradas por version de prompt. RF-266, VER-16.

Que version de prompt uso cada tirada, cuales cambiaron entre las dos, y los
resultados de cada agente por version. Todo sale de los registros `call`.
"""

from __future__ import annotations

from pydantic import JsonValue

from commons.tracing.trace import TraceRecord
from evals import compare


def _call(seq: int, agent: str, version: str, **extra: JsonValue) -> TraceRecord:
    campos: dict[str, JsonValue] = {
        "agent": agent,
        "prompt_version": version,
        "output_tokens": 100,
        "duration_ms": 2_000,
        "cost_usd": 0.01,
        "ok": True,
    }
    campos.update(extra)
    return TraceRecord(seq=seq, at="2026-09-23T10:00:00+00:00", kind="call", fields=campos)


def _metrics(**prompt_versions: tuple[str, ...]) -> compare.RunMetrics:
    return compare.RunMetrics(
        words=1_000,
        chapters=1,
        closed=True,
        defects_per_1000=0.0,
        s1_per_1000=0.0,
        repair_rate=0.0,
        quarantines=0,
        discarded_citations=0,
        packet_tokens_mean=0.0,
        calls=1,
        estimate_short=0,
        prompt_versions=prompt_versions,
    )


def test_los_resultados_se_agrupan_por_agente_y_version() -> None:
    registros = [
        _call(0, "escritor", "aaa"),
        _call(1, "escritor", "aaa", ok=False, output_tokens=300, cost_usd=None),
        _call(2, "escritor", "bbb"),
        _call(3, "juez", "ccc", duration_ms=1_000),
        TraceRecord(seq=4, at="2026-09-23T10:00:00+00:00", kind="retry", fields={}),
    ]
    por = compare.by_prompt(registros)
    assert set(por) == {"escritor", "juez"}
    assert set(por["escritor"]) == {"aaa", "bbb"}
    aaa = por["escritor"]["aaa"]
    assert (aaa.calls, aaa.failed) == (2, 1)
    assert aaa.output_tokens_mean == 200.0
    assert aaa.cost_usd == 0.01
    assert por["juez"]["ccc"].duration_ms_mean == 1_000.0


def test_la_comparacion_dice_que_prompts_cambiaron() -> None:
    """RF-266: una mejora o un empeoramiento se atribuye al prompt que cambio."""
    ref = _metrics(escritor=("aaa",), juez=("ccc",))
    cand = _metrics(escritor=("bbb",), juez=("ccc",), lector=("ddd",))
    c = compare.compare(ref, cand)
    assert c.changed_prompts == ("escritor", "lector")
    assert compare.compare(ref, ref).changed_prompts == ()
    # Cambiar un prompt no decide la promocion: la deciden las medidas.
    assert c.promotable
