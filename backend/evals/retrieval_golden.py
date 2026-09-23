"""Conjunto dorado de recuperacion, construido sin intervencion.

RF-121, CAL-10. Para cada escena congelada, los fragmentos que la escaleta y el
canon hacen **relevantes** son los esperados de sus cupos:

- **promesa**: los fragmentos de la escena donde se planto cada setup que esta
  escena cobra;
- **lugar**: los de las escenas anteriores en el mismo lugar;
- **voz**: los que llevan dialogo de escenas anteriores del mismo POV;
- **espejo**: los de escenas anteriores con la misma funcion que comparten
  alguna entidad.

Nadie marca nada a mano: lo esperado se deriva de lo que la escaleta declara y
el canon registra. Es lo que hace que el conjunto se pueda regenerar para
cualquier tirada y que medir no dependa de nadie.

La escaleta se lee de la traza (el ultimo `outline.check` que paso), porque la
escaleta no es canon (RI-17) y la traza es parte del estado de la tirada.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from canon.db import connection
from commons.tracing.trace import Trace
from commons.types.primitives import Quota, WorldTime
from commons.types.scene import (
    DramaticFunction,
    ExpectedOutput,
    SceneConstraints,
    SceneContent,
    SceneFunction,
    SceneIdentity,
    SceneSpec,
)
from context.retrieval.candidates import has_dialogue
from planning.outline.types import Outline


class GoldenQuery(BaseModel):
    """Una escena congelada con lo que su recuperacion deberia traer."""

    model_config = ConfigDict(frozen=True)

    spec: SceneSpec
    expected: Mapping[Quota, frozenset[str]] = Field(description="Por cupo, fragmentos esperados")
    literal_scenes: frozenset[str] = Field(default_factory=frozenset)

    @property
    def has_expectations(self) -> bool:
        return any(self.expected.values())


def outline_from_trace(trace: Trace) -> Outline:
    """La ultima escaleta que paso su verificacion, tal como la traza la guardo."""
    escaletas = [
        r
        for r in trace.records("outline.check")
        if r.fields.get("passed") and r.fields.get("outline")
    ]
    escaletas += [
        r for r in trace.records("replan") if r.fields.get("passed") and r.fields.get("outline")
    ]
    if not escaletas:
        raise ValueError("la traza no guarda ninguna escaleta que pasara su verificacion")
    ultima = max(escaletas, key=lambda r: r.seq)
    return Outline.model_validate_json(str(ultima.fields["outline"]))


def _scene_rows(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT id, chapter, scene_number, pov_entity, place_entity, world_time, world_seq, function, summary "
        "FROM prose_scene ORDER BY chapter, scene_number"
    ).fetchall()


def _chunks_of(
    con: sqlite3.Connection, scene_id: str, *, dialogue_only: bool = False
) -> frozenset[str]:
    rows = con.execute(
        "SELECT id, text FROM prose_chunk WHERE scene_id = ?", (scene_id,)
    ).fetchall()
    return frozenset(r["id"] for r in rows if not dialogue_only or has_dialogue(r["text"]))


def _cast_of(con: sqlite3.Connection, scene_id: str) -> tuple[str, ...]:
    rows = con.execute(
        "SELECT entity_id FROM prose_scene_character WHERE scene_id = ? ORDER BY entity_id",
        (scene_id,),
    ).fetchall()
    return tuple(r["entity_id"] for r in rows)


def build(path: Path, outline: Outline) -> list[GoldenQuery]:
    """El conjunto dorado de una novela congelada."""
    out: list[GoldenQuery] = []
    with connection.reader(path) as con:
        escenas = _scene_rows(con)
        anteriores: list[sqlite3.Row] = []
        for fila in escenas:
            sid = fila["id"]
            entrada = outline.scene(sid)
            elenco = _cast_of(con, sid) or (fila["pov_entity"],)
            if fila["pov_entity"] not in elenco:
                elenco = (fila["pov_entity"], *elenco)
            cobra = tuple(s.id for s in outline.setups if s.payoff_scene == sid)
            spec = SceneSpec(
                identity=SceneIdentity(
                    scene_id=sid,
                    chapter=fila["chapter"],
                    ordinal=fila["scene_number"],
                    pov=fila["pov_entity"],
                    place=fila["place_entity"] or "desconocido",
                    world_time=WorldTime(stamp=fila["world_time"], seq=fila["world_seq"]),
                ),
                function=DramaticFunction(
                    function=SceneFunction(fila["function"]),
                    value_change=entrada.value_change if entrada else "sin escaleta",
                    arcs=entrada.arcs if entrada else (),
                    objective="lo que la escena persigue",
                    obstacle="lo que se lo impide",
                ),
                content=SceneContent(
                    cast=elenco, beats=(fila["summary"] or "escena",), setups_to_pay=cobra
                ),
                output=ExpectedOutput(target_words=900, ends_with=fila["summary"] or "cierra"),
                constraints=SceneConstraints(),
            )

            plantadas = {s.planted_scene for s in outline.setups if s.id in cobra}
            promesa: set[str] = set()
            for p in plantadas:
                promesa |= _chunks_of(con, p)
            lugar: set[str] = set()
            voz: set[str] = set()
            espejo: set[str] = set()
            for ant in anteriores:
                if fila["place_entity"] and ant["place_entity"] == fila["place_entity"]:
                    lugar |= _chunks_of(con, ant["id"])
                if ant["pov_entity"] == fila["pov_entity"]:
                    voz |= _chunks_of(con, ant["id"], dialogue_only=True)
                if ant["function"] == fila["function"] and set(_cast_of(con, ant["id"])) & set(
                    elenco
                ):
                    espejo |= _chunks_of(con, ant["id"])
            # La escena inmediatamente anterior viaja literal en el paquete y se
            # excluye de la recuperacion: tampoco puede esperarse de ella.
            literal = frozenset({anteriores[-1]["id"]}) if anteriores else frozenset()
            excluir: set[str] = set()
            for lid in literal:
                excluir |= _chunks_of(con, lid)

            out.append(
                GoldenQuery(
                    spec=spec,
                    expected={
                        Quota.PROMISE: frozenset(promesa - excluir),
                        Quota.PLACE: frozenset(lugar - excluir),
                        Quota.VOICE: frozenset(voz - excluir),
                        Quota.MIRROR: frozenset(espejo - excluir),
                    },
                    literal_scenes=literal,
                )
            )
            anteriores.append(fila)
    return [q for q in out if q.has_expectations]


def dump(queries: list[GoldenQuery]) -> str:
    return json.dumps(
        [
            {
                "scene": q.spec.identity.scene_id,
                "expected": {k.value: sorted(v) for k, v in q.expected.items()},
            }
            for q in queries
        ],
        ensure_ascii=False,
        indent=1,
    )
