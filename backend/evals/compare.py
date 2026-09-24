"""Comparar dos tiradas. Lo que decide una promocion en VER-16.

RF-125, RF-157. Dos ficheros con su traza, sobre el mismo brief, y las mismas
medidas para los dos: acierto de recuperacion, defectos por 1.000 palabras,
tasa de reparacion, ocupacion por bloque, y las dimensiones de CAL-01 cuando
hay veredictos. Una dimension peor y el cambio no se promociona.

Todo sale de la traza y del canon, que es lo que hace que la comparacion no
dependa de quien la mire.

**Por version de prompt** (RF-266). Cada registro `call` lleva el
`prompt_version` del agente, la misma etiqueta con que `prompts_sync` lo publica
en Langfuse. La comparacion dice que version uso cada tirada, cuales cambiaron
entre las dos y, por agente y version, cuantas llamadas hubo, cuantas fallaron y
cuanto costaron: es lo que deja atribuir una mejora o un empeoramiento a un
cambio de prompt y no a otro.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from canon.db import connection
from commons.tracing.trace import Trace, TraceRecord


class PromptStats(BaseModel):
    """RF-266. Lo que dieron las llamadas de un agente con una version de prompt."""

    model_config = ConfigDict(frozen=True)

    calls: int = Field(ge=0)
    failed: int = Field(ge=0, description="Salidas que no encajaron con su esquema")
    output_tokens_mean: float = Field(ge=0.0)
    duration_ms_mean: float = Field(ge=0.0)
    cost_usd: float | None = Field(default=None, ge=0.0)


class RunMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    words: int = Field(ge=0)
    chapters: int = Field(ge=0)
    closed: bool | None
    defects_per_1000: float = Field(ge=0.0)
    s1_per_1000: float = Field(ge=0.0)
    repair_rate: float = Field(ge=0.0, description="Pases de reparacion por escena")
    quarantines: int = Field(ge=0)
    discarded_citations: int = Field(ge=0)
    packet_tokens_mean: float = Field(ge=0.0)
    block_tokens_mean: dict[str, float] = Field(default_factory=dict)
    dimensions: dict[str, float] = Field(
        default_factory=dict, description="Nivel medio del Jurado por dimension"
    )
    calls: int = Field(ge=0)
    estimate_short: int = Field(ge=0)
    prompt_versions: dict[str, tuple[str, ...]] = Field(
        default_factory=dict, description="RF-266. Versiones de prompt usadas, por agente"
    )
    by_prompt: dict[str, dict[str, PromptStats]] = Field(
        default_factory=dict, description="RF-266. Resultados por agente y version de prompt"
    )


class Comparison(BaseModel):
    model_config = ConfigDict(frozen=True)

    reference: RunMetrics
    candidate: RunMetrics
    worse: tuple[str, ...] = Field(description="Medidas en las que el candidato empeora")
    changed_prompts: tuple[str, ...] = Field(
        default=(), description="RF-266. Agentes cuya version de prompt difiere entre las dos"
    )

    @property
    def promotable(self) -> bool:
        return not self.worse


def by_prompt(records: Iterable[TraceRecord]) -> dict[str, dict[str, PromptStats]]:
    """RF-266. Las llamadas agrupadas por agente y `prompt_version`."""
    grupos: dict[tuple[str, str], list[TraceRecord]] = defaultdict(list)
    for r in records:
        version = r.fields.get("prompt_version")
        agente = r.fields.get("agent")
        if r.kind == "call" and isinstance(version, str) and isinstance(agente, str):
            grupos[(agente, version)].append(r)
    out: dict[str, dict[str, PromptStats]] = defaultdict(dict)
    for (agente, version), llamadas in sorted(grupos.items()):
        costes = [
            float(c)
            for c in (x.fields.get("cost_usd") for x in llamadas)
            if isinstance(c, int | float) and not isinstance(c, bool)
        ]
        out[agente][version] = PromptStats(
            calls=len(llamadas),
            failed=sum(1 for x in llamadas if x.fields.get("ok") is False),
            output_tokens_mean=sum(_num(x.fields.get("output_tokens")) for x in llamadas)
            / len(llamadas),
            duration_ms_mean=sum(_num(x.fields.get("duration_ms")) for x in llamadas)
            / len(llamadas),
            cost_usd=round(sum(costes), 6) if costes else None,
        )
    return dict(out)


def _num(value: object) -> float:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0


def changed_prompts(reference: RunMetrics, candidate: RunMetrics) -> tuple[str, ...]:
    """RF-266. Los agentes cuya version de prompt no es la misma en las dos tiradas."""
    agentes = set(reference.prompt_versions) | set(candidate.prompt_versions)
    return tuple(
        sorted(
            a
            for a in agentes
            if reference.prompt_versions.get(a, ()) != candidate.prompt_versions.get(a, ())
        )
    )


def measure(path: Path, trace_path: Path) -> RunMetrics:
    traza = Trace(trace_path)
    registros = list(traza.read())
    intentos = [r for r in registros if r.kind == "scene.attempt" and r.fields.get("passed")]
    palabras = sum(int(str(r.fields.get("words", 0))) for r in intentos)
    defectos: Counter[str] = Counter()
    for r in registros:
        if r.kind == "scene.attempt":
            for d in r.fields.get("defects", []) or []:  # type: ignore[union-attr]
                sev = str(d).split(":")[-1]
                defectos[sev] += 1
    reparaciones = sum(1 for r in registros if r.kind == "repair")
    cuarentenas = sum(
        1 for r in registros if r.kind == "retry" and r.fields.get("level") == "capitulo"
    )
    descartes = sum(1 for r in registros if r.kind == "process.defect")
    paquetes = [r for r in registros if r.kind == "packet"]
    bloques: dict[str, list[float]] = {}
    for p in paquetes:
        for b in p.fields.get("blocks", []) or []:  # type: ignore[union-attr]
            nombre, _, toks = str(b).rpartition(":")
            bloques.setdefault(nombre, []).append(float(toks or 0))
    cierre = [r for r in registros if r.kind == "work.close"]
    llamadas = [r for r in registros if r.kind == "call"]
    por_prompt = by_prompt(llamadas)

    with connection.reader(path) as con:
        capitulos = int(
            con.execute("SELECT count(DISTINCT chapter) AS n FROM prose_scene").fetchone()["n"]
        )
        dimensiones: dict[str, float] = {}
        if con.execute("SELECT name FROM sqlite_master WHERE name = 'scene_verdict'").fetchone():
            for r in con.execute(
                "SELECT dimension, avg(level) AS m FROM scene_verdict WHERE valid = 1 AND level IS NOT NULL GROUP BY dimension"
            ):
                dimensiones[r["dimension"]] = float(r["m"])

    por_mil = 1000.0 / palabras if palabras else 0.0
    return RunMetrics(
        words=palabras,
        chapters=capitulos,
        closed=bool(cierre[-1].fields.get("closed")) if cierre else None,
        defects_per_1000=sum(defectos.values()) * por_mil,
        s1_per_1000=defectos.get("S1", 0) * por_mil,
        repair_rate=(reparaciones / len(intentos)) if intentos else 0.0,
        quarantines=cuarentenas,
        discarded_citations=descartes,
        packet_tokens_mean=(
            sum(float(str(p.fields.get("tokens", 0))) for p in paquetes) / len(paquetes)
        )
        if paquetes
        else 0.0,
        block_tokens_mean={k: sum(v) / len(v) for k, v in bloques.items() if v},
        dimensions=dimensiones,
        calls=len(llamadas),
        estimate_short=sum(1 for c in llamadas if c.fields.get("estimate_short")),
        prompt_versions={a: tuple(sorted(v)) for a, v in por_prompt.items()},
        by_prompt=por_prompt,
    )


def compare(reference: RunMetrics, candidate: RunMetrics) -> Comparison:
    """Que empeora. Menos defectos y reparaciones es mejor; mas nivel del Jurado es mejor."""
    peores: list[str] = []
    if candidate.closed is False and reference.closed:
        peores.append("cierre")
    if candidate.s1_per_1000 > reference.s1_per_1000:
        peores.append("s1_por_1000")
    if candidate.defects_per_1000 > reference.defects_per_1000:
        peores.append("defectos_por_1000")
    if candidate.repair_rate > reference.repair_rate:
        peores.append("tasa_de_reparacion")
    if candidate.quarantines > reference.quarantines:
        peores.append("cuarentenas")
    if candidate.estimate_short > reference.estimate_short:
        peores.append("estimado_corto")
    for dim, valor in reference.dimensions.items():
        if dim in candidate.dimensions and candidate.dimensions[dim] < valor:
            peores.append(f"dimension:{dim}")
    return Comparison(
        reference=reference,
        candidate=candidate,
        worse=tuple(peores),
        changed_prompts=changed_prompts(reference, candidate),
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Compara dos tiradas: referencia y candidata.")
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--reference-trace", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--candidate-trace", required=True, type=Path)
    args = parser.parse_args(argv)
    c = compare(
        measure(args.reference, args.reference_trace), measure(args.candidate, args.candidate_trace)
    )
    print(json.dumps(c.model_dump(), ensure_ascii=False, indent=1))
    return 0 if c.promotable else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
