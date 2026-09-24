"""El protocolo de herramientas sobre el CLI (D-46), el andamiaje (D-35) y el aislamiento (RI-62).

VER-05 y, para la lista de argumentos y el entorno del subproceso, VER-11. Ninguna
prueba lanza el CLI: se fija lo que se le pasaria.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404: se sustituye, no se lanza

import pytest

from commons.provider.claude_cli import (
    HARNESS_TOKENS,
    ClaudeCli,
    _sum_cost,
    _sum_usage,
    _tool_protocol,
    _tool_request,
    engine_env,
)
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


# ---------------------------------------------------------------- RI-62 · CLI aislado


def test_el_cli_del_motor_no_carga_configuracion_de_usuario_ni_de_proyecto() -> None:
    """RI-62, VER-11. La lista de argumentos, fijada: ni ajustes, ni plugins, ni MCP, ni skills."""
    cmd = ClaudeCli().command("claude", system="sistema")
    # Ninguna fuente de ajustes: ni usuario, ni proyecto, ni local.
    i = cmd.index("--setting-sources")
    assert cmd[i + 1] == ""
    # CLAUDE.md, skills, plugins, hooks y servidores MCP desactivados.
    assert "--safe-mode" in cmd
    assert "--disable-slash-commands" in cmd
    assert "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--mcp-config") + 1] == '{"mcpServers":{}}'
    # Nada que vuelva a cargar lo que se acaba de quitar.
    for prohibida in ("--settings", "--plugin-dir", "--plugin-url", "--add-dir", "--agents"):
        assert prohibida not in cmd
    assert cmd[:2] == ["claude", "-p"]


def test_el_entorno_del_cli_no_lleva_langfuse_ni_otel() -> None:
    """RI-62. Sin estas variables, ni un plugin ni la telemetria del CLI exportan la llamada."""
    entorno = engine_env(
        {
            "PATH": "/usr/bin",
            "LANGFUSE_PUBLIC_KEY": "TU_CLAVE_AQUI",
            "LANGFUSE_SECRET_KEY": "TU_CLAVE_AQUI",  # nosec B105: de mentira
            "langfuse_base_url": "http://localhost:9",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:9",
            "HOME": "/home/x",
        }
    )
    assert entorno == {"PATH": "/usr/bin", "HOME": "/home/x", "MAX_THINKING_TOKENS": "0"}


def test_el_cli_del_motor_no_razona_aunque_el_entorno_lo_pida() -> None:
    """D-133. Sin razonamiento en ningun agente: el del proceso no se hereda."""
    assert engine_env({"PATH": "/usr/bin", "MAX_THINKING_TOKENS": "31999"}) == {
        "PATH": "/usr/bin",
        "MAX_THINKING_TOKENS": "0",
    }


class _Proc:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = 0


def _respuesta(**extra: object) -> str:
    base: dict[str, object] = {
        "result": "hola",
        "usage": {"input_tokens": 10, "cache_read_input_tokens": 5, "output_tokens": 3},
        "stop_reason": "end_turn",
    }
    base.update(extra)
    return json.dumps(base)


def test_el_subproceso_se_lanza_con_esa_lista_y_ese_entorno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RI-62. Lo que de verdad llega a `subprocess.run`, sin lanzar nada."""
    visto: dict[str, object] = {}

    def fake_run(cmd: list[str], **kw: object) -> _Proc:
        visto["cmd"] = cmd
        visto["env"] = kw.get("env")
        return _Proc(_respuesta())

    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "TU_CLAVE_AQUI")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(ClaudeCli, "_resolve", lambda self: "claude")
    ClaudeCli().complete_once(
        cacheable_prefix="s", packet="p", instruction="i", output_schema="", max_output_tokens=10
    )
    assert visto["cmd"] == ClaudeCli().command("claude", system="s")
    env = visto["env"]
    assert isinstance(env, dict)
    assert not any(k.upper().startswith(("LANGFUSE_", "OTEL_")) for k in env)


# ---------------------------------------------------------------- RF-235 · coste


def test_el_coste_y_el_modelo_salen_del_json_del_cli() -> None:
    c = ClaudeCli()._completion(
        json.loads(
            _respuesta(
                total_cost_usd=0.0042,
                modelUsage={
                    "claude-haiku-4-5-20251001": {"outputTokens": 3},
                    "claude-otro": {"outputTokens": 0},
                },
            )
        ),
        json_schema=None,
    )
    assert c.cost_usd == 0.0042
    assert c.model == "claude-haiku-4-5-20251001"
    assert c.usage.total_input == 15


def test_sin_coste_en_el_json_el_coste_es_nulo() -> None:
    """RF-235: nunca se calcula con una tabla propia."""
    c = ClaudeCli()._completion(json.loads(_respuesta()), json_schema=None)
    assert c.cost_usd is None
    assert c.model == "haiku"
    assert (
        ClaudeCli()
        ._completion(json.loads(_respuesta(total_cost_usd="gratis")), json_schema=None)
        .cost_usd
        is None
    )


def test_en_el_bucle_un_turno_sin_coste_deja_el_total_nulo() -> None:
    assert _sum_cost(0.1, 0.2) == pytest.approx(0.3)
    assert _sum_cost(0.1, None) is None


def test_el_protocolo_ensena_el_esquema_que_da_el_servidor() -> None:
    """RF-230: el esquema tal cual, no una descripcion en prosa."""
    esquema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"x": {"type": "string"}},
    }
    texto = _tool_protocol(("canon.lookup",), {"canon.lookup": esquema})
    assert json.dumps(esquema, ensure_ascii=False, sort_keys=True) in texto
