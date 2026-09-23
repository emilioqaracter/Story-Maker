"""La malla: medir antes de tocar.

RF-123, RF-124, RD-27. Tamano de fragmento, constante de la fusion y reparto de
cupos se recorren en una malla acotada y se elige la combinacion que maximiza
el acierto sin que ningun paquete supere su presupuesto. El resultado queda en
`retrieval_params` del fichero medido y, como decision, en `architecture.md`
§4.4 y §13, por el proceso B: aqui se mide, alli se decide.

Cada tamano de fragmento exige reindexar, y se reindexa una **copia** del
fichero: la medida no toca la novela.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from canon.db import connection
from canon.prose_index.reindex import reindex, write_params
from commons.types.primitives import Quota
from evals.retrieval_golden import GoldenQuery
from evals.retrieval_score import Score, score

#: La malla. Acotada a proposito: el valor de partida de cada eje es el de
#: `architecture.md` (450, 60, el orden de §4.4) y se prueba a cada lado.
CHUNK_TOKENS = (300, 450, 600)
FUSION_K = (20, 60, 100)
QUOTA_ORDERS: dict[str, tuple[Quota, ...]] = {
    "lugar-voz-promesa-espejo-libre": (
        Quota.PLACE,
        Quota.VOICE,
        Quota.PROMISE,
        Quota.MIRROR,
        Quota.FREE,
    ),
    "promesa-primero": (Quota.PROMISE, Quota.PLACE, Quota.VOICE, Quota.MIRROR, Quota.FREE),
    "libre-primero": (Quota.FREE, Quota.PLACE, Quota.VOICE, Quota.PROMISE, Quota.MIRROR),
}


class GridPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    chunk_tokens: int
    fusion_k: int
    quota_order: str
    score: Score


class GridResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    points: tuple[GridPoint, ...]
    best: GridPoint
    baseline: GridPoint | None = Field(default=None, description="450, 60 y el orden de §4.4")

    def as_table(self) -> str:
        filas = ["| fragmento | k | cupos | acierto | degradadas |", "|---:|---:|---|---:|---:|"]
        for p in sorted(self.points, key=lambda p: -p.score.aggregate):
            filas.append(
                f"| {p.chunk_tokens} | {p.fusion_k} | {p.quota_order} | {p.score.aggregate:.3f} | {p.score.degraded} |"
            )
        return "\n".join(filas)


def run_grid(
    path: Path,
    queries: Sequence[GoldenQuery],
    *,
    estimate: Callable[[str], int],
    embed: object,
    workdir: Path,
    chunk_tokens: Sequence[int] = CHUNK_TOKENS,
    fusion_k: Sequence[int] = FUSION_K,
    quota_orders: dict[str, tuple[Quota, ...]] | None = None,
    setups_by_scene: dict[str, list[str]] | None = None,
) -> GridResult:
    """Recorre la malla sobre copias del fichero. Devuelve todos los puntos y el mejor."""
    quota_orders = quota_orders or QUOTA_ORDERS
    workdir.mkdir(parents=True, exist_ok=True)
    puntos: list[GridPoint] = []

    for ct in chunk_tokens:
        copia = workdir / f"grid-{ct}.sqlite"
        shutil.copyfile(path, copia)
        for sufijo in ("-wal", "-shm"):
            extra = Path(str(path) + sufijo)
            if extra.exists():
                shutil.copyfile(extra, Path(str(copia) + sufijo))
        reindex(copia, chunk_tokens=ct, embed=embed, fusion_k=fusion_k[0])
        for k in fusion_k:
            for nombre, orden in quota_orders.items():
                s = score(
                    copia,
                    queries,
                    estimate=estimate,
                    embed=embed,
                    fusion_k=k,
                    quotas=orden,
                    setups_by_scene=setups_by_scene,
                )
                puntos.append(GridPoint(chunk_tokens=ct, fusion_k=k, quota_order=nombre, score=s))

    # Desempate determinista: mas acierto, y a igualdad, lo mas cercano a lo
    # que la arquitectura ya fija, para no mover un numero sin motivo.
    base = next(
        (
            p
            for p in puntos
            if p.chunk_tokens == 450
            and p.fusion_k == 60
            and p.quota_order == next(iter(quota_orders))
        ),
        None,
    )
    mejor = max(
        puntos,
        key=lambda p: (
            round(p.score.aggregate, 6),
            p.chunk_tokens == 450,
            p.fusion_k == 60,
            -p.chunk_tokens,
        ),
    )
    return GridResult(points=tuple(puntos), best=mejor, baseline=base)


def adopt(path: Path, point: GridPoint) -> None:
    """Deja los parametros elegidos en el fichero (RD-27). La reindexacion real
    la hace quien decida adoptar el tamano de fragmento."""
    with connection.canon_writer(path) as con:
        write_params(
            con,
            chunk_tokens=point.chunk_tokens,
            fusion_k=point.fusion_k,
            quotas=[q.value for q in QUOTA_ORDERS.get(point.quota_order, tuple(Quota))],
        )


def report(result: GridResult) -> str:
    return json.dumps(
        {
            "best": result.best.model_dump(),
            "baseline": result.baseline.model_dump() if result.baseline else None,
            "table": result.as_table(),
        },
        ensure_ascii=False,
        indent=1,
    )
