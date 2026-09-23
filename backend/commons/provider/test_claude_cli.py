"""El protocolo de herramientas sobre el CLI (D-46) y el andamiaje (D-35). VER-05."""

from __future__ import annotations

from commons.provider.claude_cli import HARNESS_TOKENS, _sum_usage, _tool_protocol, _tool_request
from commons.provider.port import Usage


def test_una_peticion_de_herramienta_se_reconoce_y_se_tipa() -> None:
    llamada = _tool_request(
        '{"tool": "canon.lookup", "arguments": {"kind": "entity", "entity_ids": ["marcos"]}}'
    )
    assert llamada is not None
    assert llamada.name == "canon.lookup"
    assert '"kind": "entity"' in llamada.arguments


def test_la_respuesta_final_no_es_una_peticion() -> None:
    assert _tool_request('{"events": []}') is None
    assert _tool_request("Marcos entró el último.") is None
    assert _tool_request('```json\n{"tool": "context.budget"}\n```') is not None


def test_el_protocolo_lista_solo_las_herramientas_cerradas() -> None:
    texto = _tool_protocol(("canon.lookup",))
    assert "- canon.lookup" in texto
    assert "- context.budget" not in texto
    assert _tool_protocol(()) == ""


def test_el_uso_se_suma_turno_a_turno() -> None:
    a = Usage(input_tokens=100, cache_read_tokens=50, output_tokens=10)
    b = Usage(input_tokens=200, cache_creation_tokens=5, output_tokens=20)
    total = _sum_usage(a, b)
    assert total.total_input == 355
    assert total.output_tokens == 30


def test_el_andamiaje_es_el_medido() -> None:
    """D-35: 38.600, y no cuenta contra el techo del proyecto."""
    assert HARNESS_TOKENS == 38_600
