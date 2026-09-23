"""`prose.retrieve`. El camino de lectura completo, sin una llamada de modelo.

RF-75 a RF-85, RNF-20. `architecture.md` §4.4: consulta desde el canon, dos
piernas sobre el indice, fusion por rangos, seleccion por cupos. Lo unico que
podria salir de la maquina es el vector de la consulta, y con el modelo local
ni eso.

Es una funcion de su peticion y del canon: el mismo fichero y la misma
peticion dan la misma seleccion (RF-77, RNF-23). Si la pierna semantica no
aporta --fragmentos sin vector, o de otro modelo-- se degrada a una pierna y se
marca, sin fallo cerrado (RF-78): recuperar peor no es generar sobre un hecho
falso.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from commons.types.primitives import Quota
from commons.types.scene import SceneSpec
from context.query.build import RetrievalRequest
from context.retrieval import candidates
from context.retrieval.fusion import RRF_K, reciprocal_rank_fusion
from context.retrieval.legs import lexical, semantic
from context.retrieval.quotas import Selection, select


class Retrieval(BaseModel):
    model_config = ConfigDict(frozen=True)

    selection: Selection
    degraded: bool
    fused: int


def retrieve(
    con: sqlite3.Connection,
    req: RetrievalRequest,
    spec: SceneSpec,
    *,
    query_vector: Sequence[float] | None,
    estimate: Callable[[str], int],
    setups_by_scene: Mapping[str, Sequence[str]] | None = None,
    recent_voice_scenes: frozenset[str] = frozenset(),
    literal_scenes: frozenset[str] = frozenset(),
    quotas: Sequence[Quota] = tuple(Quota),
    fusion_k: int = RRF_K,
) -> Retrieval:
    """Fragmentos para el bloque de recuperacion de una escena."""
    lex = lexical(con, req)
    sem = semantic(con, req, query_vector)
    # Degradado es que la pierna semantica no pudo ejecutarse (`architecture.md`
    # §4.4, §11): sin vector de consulta, o con fragmentos que no devuelve
    # --sin vector, o de otro modelo--. Un indice vacio no es degradacion: al
    # empezar la obra no hay prosa congelada y las dos piernas vuelven vacias.
    hay_prosa = con.execute("SELECT 1 FROM prose_chunk LIMIT 1").fetchone() is not None
    degraded = query_vector is None or (not sem and hay_prosa)

    fusionados = reciprocal_rank_fusion([lex, sem] if sem else [lex], k=fusion_k)
    ids = [cid for cid, _ in fusionados]
    cands = candidates.load(con, ids, estimate=estimate, setups_by_scene=setups_by_scene)

    seleccion = select(
        cands,
        token_budget=req.token_budget,
        place=spec.identity.place,
        pov=spec.identity.pov,
        function=str(spec.function.function),
        entities=req.entities,
        setups_to_pay=frozenset(spec.content.setups_to_pay),
        recent_voice_scenes=recent_voice_scenes,
        current_scene=spec.identity.scene_id,
        literal_scenes=literal_scenes,
        quotas=quotas,
    )
    return Retrieval(selection=seleccion, degraded=degraded, fused=len(ids))
