"""La medida de acierto de la recuperacion.

RF-122. Fraccion de fragmentos esperados presentes en el bloque de recuperacion
del paquete del Escritor, por cupo y agregada. Determinista dada la misma base:
es lo que permite comparar dos configuraciones sin que el resultado dependa del
dia.

No mide si los fragmentos "gustan": mide si lo que la escaleta y el canon hacen
relevante llega al paquete. Es la unica medida que se puede calcular sin
juicio, y por eso es la que fija los parametros.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from canon.db import connection
from commons.types.primitives import Quota
from context.query import build as query_build
from context.retrieval.fusion import RRF_K
from context.retrieval.retrieve import retrieve
from evals.retrieval_golden import GoldenQuery

#: Presupuesto del bloque de recuperacion del Escritor, §4.3 bloque 7.
RETRIEVAL_BUDGET = 3_000


class Score(BaseModel):
    model_config = ConfigDict(frozen=True)

    per_quota: dict[str, float] = Field(description="Acierto por cupo, 0 a 1")
    aggregate: float = Field(ge=0.0, le=1.0)
    queries: int = Field(ge=0)
    degraded: int = Field(ge=0, description="Consultas que fueron con una sola pierna")


def score(
    path: Path,
    queries: Sequence[GoldenQuery],
    *,
    estimate: Callable[[str], int],
    embed: object,
    fusion_k: int = RRF_K,
    quotas: Sequence[Quota] = tuple(Quota),
    setups_by_scene: dict[str, list[str]] | None = None,
) -> Score:
    aciertos: dict[Quota, list[float]] = {q: [] for q in Quota}
    degradadas = 0
    with connection.reader(path) as con:
        for q in queries:
            req = query_build.build(
                con, q.spec, token_budget=RETRIEVAL_BUDGET, excluded_scenes=q.literal_scenes
            )
            vec = embed.embed([req.semantic_text], is_query=True)  # type: ignore[attr-defined]
            rec = retrieve(
                con,
                req,
                q.spec,
                query_vector=vec[0].values if vec else None,
                estimate=estimate,
                setups_by_scene=setups_by_scene,
                literal_scenes=q.literal_scenes,
                quotas=quotas,
                fusion_k=fusion_k,
            )
            degradadas += int(rec.degraded)
            traidos = {s.candidate.chunk_id for s in rec.selection.chosen}
            for cupo, esperados in q.expected.items():
                if not esperados:
                    continue
                aciertos[cupo].append(len(esperados & traidos) / len(esperados))

    por_cupo = {q.value: (sum(v) / len(v) if v else 0.0) for q, v in aciertos.items() if v}
    todos = [x for v in aciertos.values() for x in v]
    return Score(
        per_quota=por_cupo,
        aggregate=(sum(todos) / len(todos)) if todos else 0.0,
        queries=len(queries),
        degraded=degradadas,
    )
