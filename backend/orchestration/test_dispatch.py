"""La frontera de confianza.

RF-21, RI-18, RI-25, RNF-10. Aqui el texto de un modelo se convierte en objeto
tipado, y todo lo que pase sin validar contamina el canon sin que nadie lo vea.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Sequence
from pathlib import Path

import pytest
from pydantic import BaseModel

from commons.provider.claude_cli import _server_schemas, _tool_protocol
from commons.provider.port import Completion, ToolCall, ToolResult, Usage
from commons.tracing.trace import Trace
from commons.types.primitives import WorldTime
from orchestration.dispatch import (
    MAX_OUTPUT_TOKENS,
    OutputValidationError,
    dispatch,
)
from orchestration.tools.server import LOOKUP_INPUT_SCHEMA, CallBudget, ToolServer


class Esperado(BaseModel):
    texto: str
    palabras: int


class _Puerto:
    """Doble del proveedor que recuerda con que se le llamo."""

    def __init__(self, respuesta: str = '{"texto":"x","palabras":3}') -> None:
        self.respuesta = respuesta
        self.max_visto: int | None = None
        self.modo: str = ""

    def _completion(self) -> Completion:
        return Completion(
            text=self.respuesta,
            usage=Usage(
                input_tokens=100,
                cache_read_tokens=4_000,
                cache_creation_tokens=50,
                output_tokens=200,
            ),
            stop_reason="end_turn",
        )

    def complete_once(self, *, max_output_tokens: int, **kw: object) -> Completion:
        self.max_visto = max_output_tokens
        self.modo = "once"
        return self._completion()

    def complete_with_tools(self, *, max_output_tokens: int, **kw: object) -> Completion:
        self.max_visto = max_output_tokens
        self.modo = "tools"
        return self._completion()

    def embed(self, texts: Sequence[str], *, is_query: bool) -> Sequence[object]:
        return []

    def count_tokens(self, text: str, model_id: str) -> int:
        return len(text)


class _Servidor:
    def serve(self, call: ToolCall) -> ToolResult:
        raise AssertionError("no deberia llamarse en estas pruebas")


def _dispatch(puerto: _Puerto, **kw: object):  # type: ignore[no-untyped-def]
    args: dict[str, object] = {
        "agent": "escritor",
        "cacheable_prefix": "ancla",
        "packet": "p",
        "instruction": "escribe",
        "output_schema": "{}",
        "max_output_tokens": 3_000,
    }
    args.update(kw)
    return dispatch(puerto, **args)  # type: ignore[arg-type]


def test_una_salida_valida_pasa() -> None:
    r = _dispatch(_Puerto(), parse=Esperado)
    assert r.agent == "escritor"


def test_una_salida_que_no_encaja_cuenta_como_fallida() -> None:
    """No se intenta arreglar el texto: un modelo que devuelve algo que no
    encaja ha entendido mal el encargo, y remendarlo esconde el problema."""
    with pytest.raises(OutputValidationError, match="no encaja"):
        _dispatch(_Puerto('{"otra":"cosa"}'), parse=Esperado)


def test_el_tope_de_salida_lo_aplica_el_codigo() -> None:
    """RI-25. Un tope que el modelo decide si invoca no es un tope."""
    p = _Puerto()
    _dispatch(p, max_output_tokens=200_000, parse=Esperado)
    assert p.max_visto == MAX_OUTPUT_TOKENS


def test_el_tope_del_agente_manda_si_es_menor() -> None:
    """El de 50.000 es red de seguridad, no sustituye al limite narrativo del
    agente: una escena son 3.000, no 50.000."""
    p = _Puerto()
    _dispatch(p, max_output_tokens=3_000, parse=Esperado)
    assert p.max_visto == 3_000


def test_sin_herramientas_va_por_la_llamada_suelta() -> None:
    p = _Puerto()
    _dispatch(p, parse=Esperado)
    assert p.modo == "once"


def test_con_herramientas_va_por_el_bucle() -> None:
    p = _Puerto()
    _dispatch(p, tools=["canon.lookup"], server=_Servidor(), parse=Esperado)
    assert p.modo == "tools"


def test_declarar_herramientas_sin_quien_las_sirva_es_un_error() -> None:
    with pytest.raises(ValueError, match="quien las sirve"):
        _dispatch(_Puerto(), tools=["canon.lookup"], parse=Esperado)


def test_la_entrada_real_suma_los_tres_campos() -> None:
    """Leer solo el primero da la cola no cacheada y no el tamano del prompt:
    lo servido desde cache ocupa ventana igual."""
    r = _dispatch(_Puerto(), parse=Esperado)
    assert r.real_input_tokens == 100 + 4_000 + 50


# ------------------------------------------------ RF-235 · coste y latencia


class _PuertoLento(_Puerto):
    """Tarda y declara coste y modelo, como el CLI."""

    def _completion(self) -> Completion:
        time.sleep(0.03)
        return (
            super()
            ._completion()
            .model_copy(update={"cost_usd": 0.0042, "model": "claude-haiku-4-5"})
        )


def test_la_llamada_se_traza_con_coste_modelo_uso_y_latencia(tmp_path: Path) -> None:
    """RF-235, RD-44: `cost_usd` del transporte y `duration_ms` medido aqui."""
    traza = Trace(tmp_path / "n.trace.jsonl")
    r = _dispatch(_PuertoLento(), parse=Esperado, trace=traza, estimated_input=5_000)
    (call,) = traza.records("call")
    f = call.fields
    assert f["cost_usd"] == 0.0042
    assert f["model"] == "claude-haiku-4-5"
    assert isinstance(f["duration_ms"], int) and f["duration_ms"] >= 25
    assert r.duration_ms == f["duration_ms"]
    assert (f["input_tokens"], f["cache_creation_tokens"], f["cache_read_tokens"]) == (
        100,
        50,
        4_000,
    )
    assert f["real_input"] == 4_150 and f["output_tokens"] == 200


def test_sin_coste_declarado_la_llamada_lo_traza_nulo(tmp_path: Path) -> None:
    traza = Trace(tmp_path / "n.trace.jsonl")
    _dispatch(_Puerto(), parse=Esperado, trace=traza)
    (call,) = traza.records("call")
    assert call.fields["cost_usd"] is None
    assert call.fields["model"] is None


def test_la_latencia_incluye_el_bucle_de_herramientas(tmp_path: Path) -> None:
    traza = Trace(tmp_path / "n.trace.jsonl")
    _dispatch(
        _PuertoLento(), tools=["canon.lookup"], server=_Servidor(), parse=Esperado, trace=traza
    )
    (call,) = traza.records("call")
    assert call.fields["duration_ms"] >= 25  # type: ignore[operator]


# ------------------------------------------------ RF-230 · protocolo de herramientas


def test_el_protocolo_del_cli_ensena_el_esquema_que_exporta_el_servidor() -> None:
    """RF-230: `json.dumps(LOOKUP_INPUT_SCHEMA)` tal cual, y solo de lo que el agente tiene."""
    con = sqlite3.connect(":memory:")
    servidor = ToolServer(
        con,
        CallBudget(ceiling=1_000, quota=100),
        allowed=["canon.lookup"],
        at=WorldTime(stamp="2026-08-01"),
        estimate=len,
        model_id="haiku",
    )
    texto = _tool_protocol(["canon.lookup"], _server_schemas(servidor))
    assert json.dumps(LOOKUP_INPUT_SCHEMA, ensure_ascii=False, sort_keys=True) in texto
    assert "context.budget" not in texto
    assert servidor.input_schemas() == {"canon.lookup": LOOKUP_INPUT_SCHEMA}
