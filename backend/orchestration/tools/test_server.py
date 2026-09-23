"""Las dos herramientas del camino de tiron.

RF-91 a RF-100. Lo que se comprueba: la lista es cerrada, el candidato se mide
antes de entregarse, nunca se trunca, y todo resultado lleva procedencia.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from canon.brief import Brief, BriefEntity, create_novel
from commons.provider.claude_cli import ClaudeCli
from commons.provider.port import Completion, ToolCall, Usage
from commons.tokens.counter import TokenCounter
from commons.tokens.factors import ModelFactors
from commons.types.primitives import BlockProvenance, WorldTime
from orchestration.tools.server import (
    LOOKUP_INPUT_SCHEMA,
    CallBudget,
    LookupArgs,
    ToolArgumentsError,
    ToolNotAllowedError,
    ToolServer,
)

MODEL = "claude-haiku-4-5"
AT = WorldTime(stamp="2026-06-01")


@pytest.fixture
def con(tmp_path: Path):  # type: ignore[no-untyped-def]
    path = tmp_path / "n.sqlite"
    create_novel(
        path,
        Brief(
            title="P",
            start=WorldTime(stamp="2026-01-01"),
            entities=(
                BriefEntity(
                    id="marcos", kind="person", name="Marcos", attributes=(("estado", "sano"),)
                ),
                BriefEntity(id="elena", kind="person", name="Elena"),
            ),
            style_guide="g",
            target_words=1000,
        ),
    )
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def _server(con: sqlite3.Connection, *, quota: int = 10_000, allowed=None) -> ToolServer:  # type: ignore[no-untyped-def]
    factors = ModelFactors()
    factors.set(MODEL, 1.35)
    return ToolServer(
        con,
        CallBudget(ceiling=100_000, quota=quota),
        allowed=allowed if allowed is not None else ["context.budget", "canon.lookup"],
        at=AT,
        estimate=TokenCounter(factors),
        model_id=MODEL,
    )


def test_una_herramienta_fuera_de_lista_se_rechaza(con: sqlite3.Connection) -> None:
    """RF-91. No es un despiste: es el modelo saliendose de su contrato."""
    s = _server(con, allowed=["context.budget"])
    with pytest.raises(ToolNotAllowedError, match="no esta en la lista"):
        s.serve(ToolCall(name="canon.lookup", arguments="{}"))


def test_el_contador_devuelve_un_numero_medido(con: sqlite3.Connection) -> None:
    """RF-92. Lo que el agente sabe de si mismo es exacto: viene del recuento
    real de la respuesta anterior, no de una estimacion."""
    s = _server(con)
    r = s.serve(ToolCall(name="context.budget", arguments="{}"))
    assert "disponible" in r.content
    assert r.tokens == 0


def test_la_consulta_devuelve_canon_con_procedencia(con: sqlite3.Connection) -> None:
    """RF-95. Sin la etiqueta, un fragmento de prosa se lee igual que un hecho
    canonico."""
    s = _server(con)
    r = s.serve(
        ToolCall(
            name="canon.lookup",
            arguments=json.dumps({"kind": "entity", "entity_ids": ["marcos"]}),
        )
    )
    assert "Marcos" in r.content
    assert r.provenance is BlockProvenance.CANON
    assert r.tokens > 0


def test_un_resultado_que_no_cabe_se_niega_no_se_trunca(con: sqlite3.Connection) -> None:
    """RF-93, RF-94. Media ficha es peor que ninguna: el agente no sabe que le
    falta y se fia de lo que llego."""
    s = _server(con, quota=1)
    r = s.serve(
        ToolCall(
            name="canon.lookup",
            arguments=json.dumps({"kind": "entity", "entity_ids": ["marcos", "elena"]}),
        )
    )
    assert r.refused
    assert "no cabe" in r.content
    assert "Acota" in r.content
    assert r.tokens == 0


def test_el_cupo_se_consume_y_no_se_amplia(con: sqlite3.Connection) -> None:
    """RF-97. Un cupo que se estira no acota nada."""
    s = _server(con, quota=200)
    antes = s._budget.available
    s.serve(
        ToolCall(
            name="canon.lookup", arguments=json.dumps({"kind": "entity", "entity_ids": ["marcos"]})
        )
    )
    assert s._budget.available < antes


def test_el_conocimiento_se_consulta_en_un_instante(con: sqlite3.Connection) -> None:
    s = _server(con)
    r = s.serve(
        ToolCall(
            name="canon.lookup", arguments=json.dumps({"kind": "knowledge", "entity_id": "marcos"})
        )
    )
    assert r.provenance is BlockProvenance.CANON


def test_un_tipo_de_consulta_desconocido_se_rechaza(con: sqlite3.Connection) -> None:
    s = _server(con)
    with pytest.raises(ToolArgumentsError, match="kind"):
        s.serve(ToolCall(name="canon.lookup", arguments=json.dumps({"kind": "magia"})))


# ------------------------------------------------ argumentos contra esquema

#: Cada caso es un argumento mal pasado y la ruta del campo que lo delata. Un
#: argumento mal tipado no se coerciona: se devuelve al modelo con el motivo.
_MAL_TIPADOS = [
    pytest.param('{"kind": "entity", "entity_ids": 5}', "entity_ids", id="lista-como-numero"),
    pytest.param(
        '{"kind": "entity", "entity_ids": "marcos"}', "entity_ids", id="lista-como-cadena"
    ),
    pytest.param('{"kind": "entity", "entity_ids": [1, 2]}', "entity_ids.0", id="ids-numericos"),
    pytest.param('{"kind": "entity", "entity_ids": null}', "entity_ids", id="lista-nula"),
    pytest.param(
        '{"kind": "entity", "entity_ids": ["marcos"], "full": "no"}', "full", id="bool-como-cadena"
    ),
    pytest.param('{"kind": "entity", "full": 1}', "full", id="bool-como-numero"),
    pytest.param('{"kind": "knowledge", "entity_id": 7}', "entity_id", id="id-como-numero"),
    pytest.param('{"kind": 3}', "kind", id="kind-como-numero"),
    pytest.param('{"entity_ids": ["marcos"]}', "kind", id="sin-kind"),
    pytest.param('{"kind": "entity", "foo": 1}', "foo", id="clave-de-mas"),
    pytest.param('["entity"]', "(raiz)", id="no-es-objeto"),
    pytest.param("{no json", "(raiz)", id="json-malformado"),
    pytest.param("", "(raiz)", id="vacio"),
]


@pytest.mark.parametrize(("arguments", "campo"), _MAL_TIPADOS)
def test_un_argumento_mal_pasado_se_rechaza_con_su_campo(
    con: sqlite3.Connection, arguments: str, campo: str
) -> None:
    """RF-91, VER-12. Antes `"full": "no"` valia True y `entity_ids: 5` pasaba
    a `["5"]`: el modelo recibia algo que no habia pedido y no se enteraba."""
    s = _server(con)
    with pytest.raises(ToolArgumentsError) as exc:
        s.serve(ToolCall(name="canon.lookup", arguments=arguments))
    assert campo in str(exc.value)
    assert "canon.lookup" in str(exc.value)


def test_un_rechazo_por_argumentos_no_consume_cupo_ni_escribe(con: sqlite3.Connection) -> None:
    s = _server(con)
    antes = s._budget.available
    eventos = con.execute("SELECT count(*) AS n FROM event").fetchone()["n"]
    with pytest.raises(ToolArgumentsError):
        s.serve(ToolCall(name="canon.lookup", arguments='{"kind": "entity", "full": "no"}'))
    assert s._budget.available == antes
    assert con.execute("SELECT count(*) AS n FROM event").fetchone()["n"] == eventos


def test_el_contador_no_admite_argumentos(con: sqlite3.Connection) -> None:
    """`context.budget` no lleva argumentos: uno de mas se rechaza igual."""
    s = _server(con)
    with pytest.raises(ToolArgumentsError, match=r"context[.]budget"):
        s.serve(ToolCall(name="context.budget", arguments='{"full": true}'))
    with pytest.raises(ToolArgumentsError, match=r"context[.]budget"):
        s.serve(ToolCall(name="context.budget", arguments="{no json"))


def test_los_argumentos_validos_siguen_pasando(con: sqlite3.Connection) -> None:
    s = _server(con)
    r = s.serve(
        ToolCall(
            name="canon.lookup",
            arguments=json.dumps({"kind": "entity", "entity_ids": ["marcos"], "full": True}),
        )
    )
    assert "Marcos" in r.content
    r = s.serve(
        ToolCall(name="canon.lookup", arguments=json.dumps({"kind": "related", "entity_ids": []}))
    )
    assert r.provenance is BlockProvenance.CANON


def test_el_esquema_publicado_es_el_del_modelo_que_valida() -> None:
    """El esquema que se le puede dar al modelo y el que valida son el mismo
    objeto: dos copias se desincronizan."""
    assert LookupArgs.model_json_schema() == LOOKUP_INPUT_SCHEMA
    assert LOOKUP_INPUT_SCHEMA["additionalProperties"] is False
    assert LOOKUP_INPUT_SCHEMA["properties"]["full"]["type"] == "boolean"
    assert LOOKUP_INPUT_SCHEMA["properties"]["entity_ids"]["type"] == "array"
    assert set(LOOKUP_INPUT_SCHEMA["properties"]["kind"]["enum"]) == {
        "entity",
        "knowledge",
        "related",
    }


def test_un_rechazo_por_argumentos_vuelve_al_modelo_y_la_llamada_sigue(
    con: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El rechazo es un error de la llamada, no una excepcion que tumbe la
    tirada: el bucle de herramientas se lo devuelve al modelo con el motivo y
    el modelo concluye en el turno siguiente."""
    salidas = iter(
        [
            '{"tool": "canon.lookup", "arguments": {"kind": "entity", "full": "no"}}',
            '{"respuesta": "final"}',
        ]
    )
    entradas: list[str] = []

    def _run(self: ClaudeCli, *, system: str, stdin: str, **_: object) -> Completion:
        entradas.append(stdin)
        return Completion(
            text=next(salidas),
            usage=Usage(input_tokens=10, output_tokens=5),
            stop_reason="end_turn",
        )

    monkeypatch.setattr(ClaudeCli, "_run", _run)
    r = ClaudeCli().complete_with_tools(
        cacheable_prefix="sistema",
        packet="paquete",
        instruction="instruccion",
        output_schema="{}",
        max_output_tokens=100,
        tools=["canon.lookup"],
        server=_server(con),
    )
    assert r.text == '{"respuesta": "final"}'
    assert len(r.tool_calls) == 1
    assert "rechazado" in entradas[1]
    assert "full" in entradas[1]


def test_ninguna_herramienta_escribe(con: sqlite3.Connection) -> None:
    """RF-96. La congelacion sigue siendo la unica operacion que toca el canon."""
    s = _server(con)
    antes = con.execute("SELECT count(*) AS n FROM event").fetchone()["n"]
    s.serve(
        ToolCall(
            name="canon.lookup", arguments=json.dumps({"kind": "related", "entity_ids": ["marcos"]})
        )
    )
    assert con.execute("SELECT count(*) AS n FROM event").fetchone()["n"] == antes
