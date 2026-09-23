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
from commons.provider.port import ToolCall
from commons.tokens.counter import TokenCounter
from commons.tokens.factors import ModelFactors
from commons.types.primitives import BlockProvenance, WorldTime
from orchestration.tools.server import (
    CallBudget,
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
    with pytest.raises(ToolNotAllowedError, match="Validos"):
        s.serve(ToolCall(name="canon.lookup", arguments=json.dumps({"kind": "magia"})))


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
