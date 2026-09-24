"""Cada coincidencia del guardarrail queda en el audit log y en Langfuse. RF-240, RF-265, RNF-54.

La traza local es el audit log (`architecture.md` §11): la coincidencia queda ahi
con su termino literal, su nivel, su decision y su instante. En Langfuse llega
como score `guardrail.forbidden` sobre el intento de escena que la tuvo, con el
nivel legible y el termino como sha256 recortado a 12 caracteres: puede ser el
nombre de una persona real que el cliente prohibio. Metodo VER-05, con un
cliente doble y sin red.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from commons.tracing import langfuse_export as lf
from commons.tracing.trace import Trace

FAKE_ENV = {
    "LANGFUSE_PUBLIC_KEY": "TU_CLAVE_PUBLICA_AQUI",
    "LANGFUSE_SECRET_KEY": "TU_CLAVE_SECRETA_AQUI",  # nosec B105: de mentira
    "LANGFUSE_BASE_URL": "http://localhost:9",
}


class FakeClient:
    def __init__(self) -> None:
        self.sent: list[lf.LangfuseObject] = []

    def send(self, objects: Sequence[lf.LangfuseObject]) -> None:
        self.sent.extend(objects)


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    lf.uninstall_live_export()
    yield
    lf.uninstall_live_export()


def _coincidencia(traza: Trace, term: str, level: str, attempt: int) -> None:
    """Como la escribe `loop._emit_matches` (RF-240)."""
    traza.emit(
        "guardrail.match",
        chapter=1,
        scene=2,
        attempt=attempt,
        term=term,
        level=level,
        quote=f"y entonces {term} salto",
        offset=12,
        decision="reintentar",
        stage="escena",
    )


def test_cada_coincidencia_queda_en_el_audit_log_y_en_langfuse(tmp_path: Path) -> None:
    cliente = FakeClient()
    live = lf.install_live_export(FAKE_ENV, client_factory=lambda: cliente)
    assert live is not None
    ruta = tmp_path / "n.trace.jsonl"
    traza = Trace(ruta)
    traza.emit("calibration", invocation="run")
    _coincidencia(traza, "Venancio", "cliente", 1)
    _coincidencia(traza, "Rosalia", "novela", 2)
    assert live.drain(5)

    # El audit log local: cada coincidencia, con termino, nivel, decision e instante.
    locales = traza.records("guardrail.match")
    assert [r.fields["term"] for r in locales] == ["Venancio", "Rosalia"]
    assert all(r.fields["decision"] == "reintentar" and r.at for r in locales)

    # Langfuse: un score por coincidencia, sobre la escena, con nivel y hash.
    scores = [
        o
        for o in cliente.sent
        if isinstance(o, lf.LangfuseScore) and o.name == "guardrail.forbidden"
    ]
    assert len(scores) == 2
    assert all(s.value == 0.0 and s.data_type == "BOOLEAN" for s in scores)
    escena = next(
        o
        for o in cliente.sent
        if isinstance(o, lf.LangfuseObservation)
        and o.name == "scene"
        and dict(o.metadata) == {"chapter": 1, "scene": 2}
    )
    assert {s.observation_id for s in scores} == {escena.id}
    assert [s.metadata["level"] for s in scores] == ["cliente", "novela"]
    assert [s.metadata["term_hash"] for s in scores] == [
        lf.term_hash("Venancio"),
        lf.term_hash("Rosalia"),
    ]
    assert scores[0].comment == f"nivel=cliente; termino=sha256:{lf.term_hash('Venancio')}"

    # RNF-54: el literal no sale de la maquina por ninguna via.
    volcado = json.dumps([o.model_dump() for o in cliente.sent], ensure_ascii=False)
    assert "Venancio" not in volcado and "Rosalia" not in volcado
    assert "Venancio" in ruta.read_text(encoding="utf-8")


def test_el_lote_da_las_mismas_coincidencias_que_el_vivo(tmp_path: Path) -> None:
    """D-85: reexportar la tirada da los mismos scores, con los mismos identificadores."""
    cliente = FakeClient()
    live = lf.install_live_export(FAKE_ENV, client_factory=lambda: cliente)
    assert live is not None
    traza = Trace(tmp_path / "n.trace.jsonl")
    traza.emit("calibration", invocation="run")
    _coincidencia(traza, "Venancio", "cliente", 1)
    assert live.drain(5)
    lote = lf.to_langfuse(traza.records(), source="n.trace.jsonl", session_id="n")
    assert [o for o in cliente.sent if isinstance(o, lf.LangfuseScore)] == [
        o for o in lote if isinstance(o, lf.LangfuseScore)
    ]
