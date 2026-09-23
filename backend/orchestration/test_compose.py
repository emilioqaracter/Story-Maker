"""La puerta de T40: una tirada con dobles y el espejo de Langfuse con un cliente doble.

`specs/srs-backend-v4.md` RF-233 a RF-235, RI-60, RNF-53. Metodo VER-05, con el
proveedor guionizado de `test_engine.py` (RNF-17) y sin red: el cliente de
Langfuse es un doble que guarda lo que recibe.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import datetime
from pathlib import Path

import pytest

from canon.brief import Brief, create_novel
from commons.provider.port import Completion
from commons.tokens.counter import TokenCounter
from commons.tokens.factors import ModelFactors
from commons.tracing.langfuse_export import (
    LangfuseObject,
    LangfuseObservation,
    LangfuseTrace,
    install_live_export,
    to_langfuse,
    uninstall_live_export,
)
from commons.tracing.trace import Trace
from orchestration.admission import Admission
from orchestration.compose import run_novel
from orchestration.engine import Composer
from orchestration.test_engine import ScriptedPort, _brief, _Embedder

FAKE_ENV = {
    "LANGFUSE_PUBLIC_KEY": "TU_CLAVE_PUBLICA_AQUI",
    "LANGFUSE_SECRET_KEY": "TU_CLAVE_SECRETA_AQUI",  # nosec B105: de mentira
    "LANGFUSE_BASE_URL": "http://localhost:9",
}

#: Dos capitulos: `chapters_for` divide la extension por el capitulo tipico.
_TARGET = 5_500


class _CostPort(ScriptedPort):
    """El proveedor guionizado, declarando coste y modelo como el CLI."""

    def _completion(self, text: str, prefix: str, packet: str, instruction: str) -> Completion:
        return (
            super()
            ._completion(text, prefix, packet, instruction)
            .model_copy(update={"cost_usd": 0.001, "model": "claude-haiku-4-5"})
        )


class FakeClient:
    def __init__(self) -> None:
        self.sent: list[LangfuseObject] = []

    def send(self, objects: Sequence[LangfuseObject]) -> None:
        self.sent.extend(objects)


class BrokenClient:
    def send(self, objects: Sequence[LangfuseObject]) -> None:
        raise ConnectionError("Langfuse no responde")


def _brief_largo() -> Brief:
    return _brief().model_copy(update={"target_words": _TARGET})


def _compose(path: Path, trace: Trace, *, model: str, invocation: str) -> tuple[Composer, Brief]:
    """`compose_engine` con dobles: sin CLI, sin embeddings reales y calibracion fija."""
    factores = ModelFactors()
    factores.set(model, 1.35)
    trace.emit("calibration", model=model, factor=1.35, ratio=1.0, invocation=invocation)
    composer = Composer(
        port=_CostPort(),
        path=path,
        brief=_brief_largo(),
        embedder=_Embedder(),
        counter=TokenCounter(factores),
        model_id=model,
        trace=trace,
        admission=Admission(trace=trace),
    )
    return composer, _brief_largo()


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    uninstall_live_export()
    yield
    uninstall_live_export()


def _tirada(tmp_path: Path) -> tuple[Trace, object]:
    path = tmp_path / "mi-novela.sqlite"
    create_novel(path, _brief())
    traza = Trace(tmp_path / "mi-novela.trace.jsonl")
    informe = run_novel(path, "mi-novela", traza, compose=_compose)
    return traza, informe


def test_una_tirada_con_dobles_llega_al_espejo_con_sesion_coste_y_latencia(tmp_path: Path) -> None:
    """La puerta de T40 (RF-233 a RF-235)."""
    cliente = FakeClient()
    live = install_live_export(FAKE_ENV, client_factory=lambda: cliente)
    assert live is not None
    traza, _informe = _tirada(tmp_path)
    assert live.drain(10)

    trazas = [o for o in cliente.sent if isinstance(o, LangfuseTrace)]
    generaciones = [
        o for o in cliente.sent if isinstance(o, LangfuseObservation) and o.type == "generation"
    ]
    # Una traza por generacion: la tirada es una, con la novela como sesion.
    assert {t.name for t in trazas} == {"run"}
    assert len({t.id for t in trazas}) == 1
    assert {t.session_id for t in trazas} == {"mi-novela"}
    # Una generation por llamada, con tokens, coste, modelo y latencia.
    llamadas = traza.records("call")
    assert llamadas and len(generaciones) == len(llamadas)
    for g in generaciones:
        assert g.model == "claude-haiku-4-5"
        assert g.cost_details == {"total": 0.001}
        assert g.usage_details is not None and set(g.usage_details) == {
            "input",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "output",
        }
        assert g.end_time is not None
        assert datetime.fromisoformat(g.start_time) <= datetime.fromisoformat(g.end_time)
        assert isinstance(g.metadata.get("duration_ms"), int)
    # `work.cost` cierra la tirada con los totales de la novela.
    (coste,) = traza.records("work.cost")
    assert coste.fields["calls"] == len(llamadas)
    assert coste.fields["cost_usd"] == pytest.approx(0.001 * len(llamadas))
    assert coste.fields["calls_without_cost"] == 0
    final = [t for t in trazas if t.output and "cost_usd" in t.output][-1]
    assert final.output is not None and final.output["calls"] == len(llamadas)
    # D-85: lo que envio el conductor en vivo es lo que daria el lote.
    assert cliente.sent == to_langfuse(
        traza.records(), source="mi-novela.trace.jsonl", session_id="mi-novela"
    )
    assert not traza.records("export.failed")


def test_si_el_cliente_lanza_la_tirada_cierra_igual(tmp_path: Path) -> None:
    """RNF-53: el espejo no para, no espera y no decide."""
    live = install_live_export(FAKE_ENV, client_factory=BrokenClient)
    assert live is not None
    traza, informe = _tirada(tmp_path / "rota")
    assert live.drain(10)

    uninstall_live_export()
    _traza_sin, informe_sin = _tirada(tmp_path / "sin")

    assert informe.closed == informe_sin.closed  # type: ignore[attr-defined]
    assert informe.reason == informe_sin.reason  # type: ignore[attr-defined]
    assert traza.records("work.cost")
    assert traza.records("export.failed")
    assert traza.failures >= 1


def test_sin_claves_la_tirada_lo_dice_una_vez_y_sigue(tmp_path: Path) -> None:
    """RI-60: `export.disabled` una sola vez, con nombres y sin valores."""
    traza, _informe = _tirada(tmp_path)
    (aviso,) = traza.records("export.disabled")
    assert aviso.fields["missing"] == [
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_BASE_URL",
    ]
    assert traza.records("work.cost")
