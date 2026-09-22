"""Construccion de la peticion de recuperacion.

RF-72 a RF-74. **Cero llamadas de modelo.** La expansion de consulta no es una
llamada: es una lectura del canon.

Dos decisiones estan metidas aqui y conviene verlas:

1. **Los sinonimos los da la tabla de alias, no un modelo.** Un modelo
   expandiendo "el Chino" a "el asiatico" mete ruido y ademas puede meter un
   termino que en esta obra no ha usado nadie. La tabla de alias dice
   exactamente como se ha llamado a esa persona, que es justo lo que la
   busqueda lexica necesita.
2. **La especificacion de escena ya es la consulta.** No hace falta redactar
   una: el artefacto que describe lo que se va a escribir es la mejor
   descripcion de lo que conviene recuperar.
"""

from __future__ import annotations

import sqlite3

from pydantic import BaseModel, ConfigDict, Field

from canon.skills import read
from commons.types.primitives import Quota, WorldTime
from commons.types.scene import SceneSpec


class RetrievalRequest(BaseModel):
    """Lo que se le pide al indice de prosa.

    Contrato de spec §3.5: filtros, terminos lexicos, texto semantico,
    exclusiones, cupos pedidos y presupuesto en tokens.
    """

    model_config = ConfigDict(frozen=True)

    # --- filtros, desde la especificacion
    entities: frozenset[str] = Field(description="Elenco ampliado por el grafo")
    place: str | None = None
    before: WorldTime | None = Field(
        default=None, description="Solo prosa anterior a este instante"
    )
    arcs: tuple[str, ...] = Field(default_factory=tuple)
    excluded_scenes: frozenset[str] = Field(
        default_factory=frozenset,
        description="Las que ya viajan literales en el paquete",
    )

    # --- las dos piernas
    lexical_terms: tuple[str, ...] = Field(
        description="Nombres canonicos y alias vigentes, mas lexico del mundo"
    )
    semantic_text: str = Field(description="La propia especificacion de escena")

    # --- que se espera de vuelta
    quotas: tuple[Quota, ...] = Field(default=tuple(Quota))
    token_budget: int = Field(gt=0)


def build(
    con: sqlite3.Connection,
    spec: SceneSpec,
    *,
    token_budget: int,
    excluded_scenes: frozenset[str] = frozenset(),
    world_lexicon: tuple[str, ...] = (),
) -> RetrievalRequest:
    """Construye la peticion leyendo el canon. Ninguna llamada de modelo."""
    at = spec.identity.world_time

    # El grafo amplia el conjunto: quien mas cuenta en esta escena aunque no
    # salga en ella. Sus nombres entran en los terminos lexicos (RF-74).
    ampliado = read.related(con, list(spec.content.cast), at=at)

    cards = read.query(con, sorted(ampliado), at=at)
    terminos: list[str] = []
    for card in cards:
        terminos.append(card.name)
        terminos.extend(card.aliases)
    terminos.extend(world_lexicon)

    return RetrievalRequest(
        entities=ampliado,
        place=spec.identity.place,
        before=at,
        arcs=spec.function.arcs,
        excluded_scenes=excluded_scenes,
        # Ordenados y sin repetir: la peticion tiene que ser identica para el
        # mismo canon, o la fusion deja de ser determinista y con ella la
        # reproducibilidad del camino de empuje.
        lexical_terms=tuple(sorted(set(terminos))),
        semantic_text=spec.semantic_query(),
        token_budget=token_budget,
    )
