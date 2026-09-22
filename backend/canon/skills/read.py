"""Skills de lectura del canon: `canon.query`, `state-at`, `knowledge-of`, `related`.

RF-03, RF-06, RF-07, RF-09, RF-67. Son la **excepcion de lectura** de
`architecture.md` 2.3: cualquier funcionalidad puede importarlas, y ninguna
abre la base por su cuenta.

Todas proyectan en un instante. Ese parametro no es comodidad: es lo que hace
que se pueda responder "que sabia el protagonista en la jornada 14" sin
reconstruir la novela, y lo que impide que un personaje mencione un hecho que
todavia no conocia.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from commons.types.primitives import WorldTime

# Vigente en `t`: empezo en o antes, y no ha terminado o termina despues.
# `valid_to` es exclusivo, por eso `>` y no `>=`: si no, el instante de cierre
# devolveria las dos versiones y CTX-15 aparecia justo en la frontera.
_ALIVE = "valid_from <= :t AND (valid_to IS NULL OR valid_to > :t)"


class EntityCard(BaseModel):
    """Ficha de entidad. CTX-05 en su forma compacta.

    Compacta y completa se diferencian en cuanto traen, no en su forma: seis
    compactas caben en 1.600 tokens y una completa en 800 (RF-09).
    """

    model_config = ConfigDict(frozen=True)

    entity_id: str
    kind: str
    name: str
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    attributes: tuple[tuple[str, str], ...] = Field(default_factory=tuple)
    competences: tuple[tuple[str, str], ...] = Field(default_factory=tuple)


class WorldState(BaseModel):
    """MUN-10. Estado del mundo en un instante."""

    model_config = ConfigDict(frozen=True)

    at: WorldTime
    cards: tuple[EntityCard, ...]


def query(
    con: sqlite3.Connection,
    entity_ids: Sequence[str],
    *,
    at: WorldTime,
    full: bool = False,
) -> list[EntityCard]:
    """`canon.query`. Fichas de las entidades pedidas, vigentes en `at`.

    `full` anade competencias y todos los atributos; la compacta se queda en lo
    minimo accionable para una escena.
    """
    if not entity_ids:
        return []

    marks = ",".join("?" * len(entity_ids))
    rows = con.execute(
        f"SELECT id, kind, name FROM entity WHERE id IN ({marks}) ORDER BY id",
        list(entity_ids),
    ).fetchall()

    cards: list[EntityCard] = []
    for row in rows:
        eid = row["id"]
        aliases = tuple(
            r["alias"]
            for r in con.execute(
                f"SELECT alias FROM entity_alias WHERE entity_id = :e AND {_ALIVE} "
                "ORDER BY alias",
                {"e": eid, "t": at.stamp},
            )
        )
        attributes = tuple(
            (r["name"], r["value"])
            for r in con.execute(
                f"SELECT name, value FROM attribute WHERE entity_id = :e AND {_ALIVE} "
                "ORDER BY name",
                {"e": eid, "t": at.stamp},
            )
        )
        competences = (
            tuple(
                (r["name"], r["level"])
                for r in con.execute(
                    f"SELECT name, level FROM competence WHERE entity_id = :e AND {_ALIVE} "
                    "ORDER BY name",
                    {"e": eid, "t": at.stamp},
                )
            )
            if full
            else ()
        )
        cards.append(
            EntityCard(
                entity_id=eid,
                kind=row["kind"],
                name=row["name"],
                aliases=aliases,
                attributes=attributes,
                competences=competences,
            )
        )
    return cards


def state_at(con: sqlite3.Connection, at: WorldTime) -> WorldState:
    """`canon.state-at`. El mundo entero en un instante (RF-03)."""
    ids = [r["id"] for r in con.execute("SELECT id FROM entity ORDER BY id")]
    return WorldState(at=at, cards=tuple(query(con, ids, at=at, full=True)))


def knowledge_of(con: sqlite3.Connection, entity_id: str, at: WorldTime) -> frozenset[str]:
    """`canon.knowledge-of`. Que sabe un personaje en `at` (RF-07, PER-I1).

    Solo hechos que un evento le hizo conocer **en o antes** de `at`. Es la base
    de `check.knowledge`: una mencion de algo que no esta aqui es un defecto S1,
    no un matiz de estilo.
    """
    rows = con.execute(
        "SELECT fact_key FROM knowledge WHERE entity_id = ? AND known_from <= ?",
        (entity_id, at.stamp),
    )
    return frozenset(r["fact_key"] for r in rows)


def related(
    con: sqlite3.Connection,
    seeds: Sequence[str],
    *,
    at: WorldTime,
    max_depth: int = 2,
) -> frozenset[str]:
    """`canon.related`. Recorre el grafo de entidades con CTE recursivo (RF-67).

    Solo aristas **vigentes** en `at`, y en los dos sentidos: la relacion se
    guarda dirigida, pero para saber quien mas cuenta en una escena es
    simetrica. Por eso el CTE construye primero un `edge` bidireccional.

    `max_depth` acota a proposito. Sin tope, en una obra con muchas relaciones
    el conjunto ampliado acaba siendo el reparto entero, y ampliar a todos es lo
    mismo que no ampliar a nadie: los terminos lexicos de la consulta dejarian
    de discriminar.

    El `UNION` del paso recursivo --y no `UNION ALL`-- es lo que corta los
    ciclos: un grafo de relaciones los tiene por construccion, y con `UNION ALL`
    la consulta no terminaria.
    """
    if not seeds:
        return frozenset()

    # Todo posicional: sqlite no admite mezclar marcadores nombrados y
    # posicionales en la misma sentencia, y las semillas son variables.
    seed_values = ",".join(["(?)"] * len(seeds))
    sql = f"""
        WITH RECURSIVE
          seed(id) AS (VALUES {seed_values}),
          edge(a, b) AS (
                SELECT source_id, target_id FROM relation
                 WHERE valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)
            UNION
                SELECT target_id, source_id FROM relation
                 WHERE valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)
          ),
          reach(id, depth) AS (
                SELECT id, 0 FROM seed
            UNION
                SELECT edge.b, reach.depth + 1
                  FROM reach JOIN edge ON edge.a = reach.id
                 WHERE reach.depth < ?
          )
        SELECT DISTINCT id FROM reach
    """

    t = at.stamp
    rows = con.execute(sql, (*seeds, t, t, t, t, max_depth)).fetchall()
    return frozenset(r["id"] for r in rows)
