"""Skills de lectura, comprobadas contra la vigencia.

RF-07, RF-09, RF-67. Metodo VER-05/VER-06. Lo que se comprueba aqui es que
**todo se lee en un instante**: una lectura que ignore la vigencia devuelve
hechos que en esa escena todavia no eran ciertos, y eso entra al paquete como
canon sin que nada lo marque.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from canon.db import connection
from canon.events import log
from canon.events.types import (
    AliasAdded,
    AttributeSet,
    EntityCreated,
    Event,
    KnowledgeGained,
    RelationSet,
)
from canon.projections import rebuild
from canon.skills import read
from commons.types.primitives import Provenance, WorldTime

T0 = WorldTime(stamp="2026-01-01")
T_MID = WorldTime(stamp="2026-03-01")
T_LATE = WorldTime(stamp="2026-09-01")


# Contador de desempate por instante. El esquema exige que la pareja
# (instante, desempate) sea unica (RD-19), asi que las fixtures tampoco pueden
# apoyarse en el empate: antes se apoyaban, y por eso esta restriccion las
# rompio al entrar. Que las rompiera es la restriccion haciendo su trabajo.
_SEQ: dict[str, int] = {}


def _ev(payload: object, stamp: str, ent: set[str], chapter: int | None = 1) -> Event:
    seq = _SEQ.get(stamp, 0)
    _SEQ[stamp] = seq + 1
    return Event(
        world_time=WorldTime(stamp=stamp, seq=seq),
        payload=payload,  # type: ignore[arg-type]
        provenance=Provenance.BRIEF if chapter is None else Provenance.PROSE,
        chapter_origin=chapter,
        entities=frozenset(ent),
    )


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    _SEQ.clear()
    path = tmp_path / "n.sqlite"
    connection.create(path)
    with connection.canon_writer(path) as con:
        log.append(
            con,
            [
                _ev(EntityCreated(entity_id=e, kind="person", name=e.upper()), "2026-01-01", {e}, None)
                for e in ("marcos", "elena", "tecnico", "rival")
            ],
        )
        log.append(
            con,
            [
                _ev(AliasAdded(entity_id="marcos", alias="el Chino"), "2026-01-01", {"marcos"}),
                _ev(AttributeSet(entity_id="marcos", name="estado", value="sano"), "2026-01-01", {"marcos"}),
                _ev(AttributeSet(entity_id="marcos", name="estado", value="lesionado"), "2026-06-01", {"marcos"}, 8),
                _ev(KnowledgeGained(entity_id="marcos", fact_key="elena.se.va"), "2026-05-01", {"marcos"}, 7),
                _ev(RelationSet(source_id="marcos", target_id="elena", kind="pareja"), "2026-01-01", {"marcos", "elena"}),
                _ev(RelationSet(source_id="elena", target_id="tecnico", kind="hija"), "2026-01-01", {"elena", "tecnico"}),
                _ev(RelationSet(source_id="tecnico", target_id="rival", kind="rivalidad", valid_to=WorldTime(stamp="2026-02-01")), "2026-01-01", {"tecnico", "rival"}),
            ],
        )
        rebuild.rebuild(con)
    return path


def test_la_ficha_trae_lo_vigente_en_ese_instante(novela: Path) -> None:
    with connection.reader(novela) as con:
        [antes] = read.query(con, ["marcos"], at=T_MID)
        [despues] = read.query(con, ["marcos"], at=T_LATE)
    assert dict(antes.attributes)["estado"] == "sano"
    assert dict(despues.attributes)["estado"] == "lesionado"


def test_los_alias_salen_del_canon(novela: Path) -> None:
    """RF-73: los sinonimos los da la tabla de alias, no los inventa nadie."""
    with connection.reader(novela) as con:
        [card] = read.query(con, ["marcos"], at=T_MID)
    assert "el Chino" in card.aliases


def test_el_conocimiento_no_se_adelanta(novela: Path) -> None:
    """PER-I1. Antes del capitulo 7 no lo sabe, y mencionarlo seria S1."""
    with connection.reader(novela) as con:
        assert read.knowledge_of(con, "marcos", T_MID) == frozenset()
        assert "elena.se.va" in read.knowledge_of(con, "marcos", T_LATE)


def test_el_grafo_es_bidireccional_y_acotado(novela: Path) -> None:
    """RF-67. La relacion se guarda dirigida pero se recorre en los dos sentidos."""
    with connection.reader(novela) as con:
        prof1 = read.related(con, ["marcos"], at=T_MID, max_depth=1)
        prof2 = read.related(con, ["marcos"], at=T_MID, max_depth=2)
    assert prof1 == {"marcos", "elena"}
    assert prof2 == {"marcos", "elena", "tecnico"}


def test_el_grafo_ignora_aristas_no_vigentes(novela: Path) -> None:
    """La rivalidad cerro en febrero: en marzo ya no amplia."""
    with connection.reader(novela) as con:
        assert "rival" not in read.related(con, ["tecnico"], at=T_MID, max_depth=2)
        assert "rival" in read.related(con, ["tecnico"], at=T0, max_depth=2)


def test_estado_del_mundo_recorre_todas_las_entidades(novela: Path) -> None:
    with connection.reader(novela) as con:
        estado = read.state_at(con, T_MID)
    assert {c.entity_id for c in estado.cards} == {"marcos", "elena", "tecnico", "rival"}


def test_sin_semillas_no_hay_consulta(novela: Path) -> None:
    with connection.reader(novela) as con:
        assert read.related(con, [], at=T_MID) == frozenset()
        assert read.query(con, [], at=T_MID) == []
