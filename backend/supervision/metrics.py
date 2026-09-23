"""`metrics.report`. Las trece senales de salud de `architecture.md` §11.

RF-144, RF-145, RD-22. Codigo, determinista y recomputable: todo sale de los
registros de la traza del capitulo, de la serie de capitulos anteriores y de
tres datos que el Orquestador ya tiene --deuda abierta, cuarentenas del acto,
huellas--. Ningun numero nuevo: los umbrales son los de §11 leidos como fija
RF-145.

| Senal de §11 | Alarma |
|---|---|
| Defectos S1 por 1.000 palabras | Tres capitulos seguidos al alza |
| Tasa de reparacion | Por encima de 0,30 |
| Capitulos en cuarentena | Mas de uno en el acto |
| Deriva de huella | Fuera de tolerancia tres capitulos seguidos (RF-138) |
| Deuda narrativa | Tres capitulos seguidos al alza |
| Dispersion del jurado | Tres capitulos seguidos al alza |
| Ocupacion por bloque | Algun bloque desplazado tres capitulos seguidos |
| Ocupacion concurrente maxima | 85.000 o mas tres capitulos seguidos |
| Aciertos sobre el conjunto dorado | Por debajo de 0,90 (D-41) |
| Real frente a estimado | Cualquiera |
| Recuperaciones degradadas | Cualquiera |
| Cupos vacios | Mayoria vacia tres capitulos seguidos, pasado el primer acto (D-63) |
| Fragmentos sustituidos por resumen | Tres capitulos seguidos al alza |
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from itertools import pairwise

from canon.freeze.rows import MetricRow
from commons.tracing.trace import TraceRecord

#: RF-145. "Tendencia creciente" y "sostenida" son tres capitulos.
SUSTAINED = 3
#: §11, literal.
REPAIR_RATE_MAX = 0.30
QUARANTINES_PER_ACT_MAX = 1
#: RF-145: el presupuesto de ensamblaje de §4.1.
CONCURRENCY_ALARM = 85_000
#: D-41.
GOLDEN_FLOOR = 0.90
#: D-42.
DRIFT_SIGMAS = 2.0
#: D-63. "Muchos" cupos vacios se lee como la mayoria.
EMPTY_QUOTAS_MAJORITY = 0.5

SIGNALS = (
    "s1_per_1000",
    "repair_rate",
    "quarantines_in_act",
    "style_drift",
    "narrative_debt",
    "jury_dispersion",
    "displaced_blocks",
    "max_concurrent",
    "golden_hit_rate",
    "estimate_short",
    "degraded_retrievals",
    "empty_quotas",
    "summaries_substituted",
)


def since_last_freeze(records: Sequence[TraceRecord]) -> list[TraceRecord]:
    """Los registros del capitulo en curso: los posteriores a la ultima congelacion."""
    ultimo = max((r.seq for r in records if r.kind == "chapter.frozen"), default=-1)
    return [r for r in records if r.seq > ultimo]


def _items(value: object) -> list[object]:
    """Una lista de la traza, o vacia: la traza es JSON y no trae tipos."""
    return list(value) if isinstance(value, list | tuple) else []


def _mapping_values(value: object) -> list[object]:
    return list(value.values()) if isinstance(value, dict) else []


def _history(history: Sequence[MetricRow], signal: str) -> list[float | None]:
    return [r.value for r in sorted(history, key=lambda r: r.chapter) if r.signal == signal]


def _rising(prev: Sequence[float | None], current: float | None) -> bool:
    serie = [*prev, current][-SUSTAINED:]
    if len(serie) < SUSTAINED or any(v is None for v in serie):
        return False
    vals = [float(v) for v in serie if v is not None]
    return all(b > a for a, b in pairwise(vals))


def _sustained(
    prev: Sequence[float | None], current: float | None, cond: Callable[[float], bool]
) -> bool:
    serie = [*prev, current][-SUSTAINED:]
    return len(serie) == SUSTAINED and all(v is not None and cond(float(v)) for v in serie)


def compute(
    chapter: int,
    records: Sequence[TraceRecord],
    history: Sequence[MetricRow],
    *,
    open_setups: int,
    act_quarantines: int,
    deviations: Sequence[float | None],
    after_first_act: bool,
) -> list[MetricRow]:
    """Las trece senales del capitulo, con su estado.

    `records` son los del capitulo (ver `since_last_freeze`); `history`, las
    filas de los capitulos anteriores; `deviations`, la desviacion de la huella
    de cada capitulo congelado mas la de este, en orden.
    """
    intentos = [r for r in records if r.kind == "scene.attempt"]
    aprobados = [r for r in intentos if r.fields.get("passed")]
    palabras = sum(int(str(r.fields.get("words", 0))) for r in aprobados)
    s1 = sum(1 for r in intentos for d in _items(r.fields.get("defects")) if str(d).endswith("S1"))
    reparaciones = sum(1 for r in records if r.kind == "repair")
    cuarentenas = sum(
        1 for r in records if r.kind == "retry" and r.fields.get("level") == "capitulo"
    )
    jurados = [r for r in records if r.kind == "jury"]
    dispersiones = [
        float(v)
        for r in jurados
        for v in _mapping_values(r.fields.get("spreads"))
        if isinstance(v, int | float)
    ]
    paquetes = [r for r in records if r.kind == "packet"]
    desplazados = sum(
        1 for p in paquetes for b in _items(p.fields.get("blocks")) if str(b).endswith(":0")
    )
    en_vuelo = [int(str(r.fields.get("in_flight", 0))) for r in records if r.kind == "admission"]
    dorado = [r.fields.get("rate") for r in records if r.kind == "golden"]
    llamadas = [r for r in records if r.kind == "call"]
    elegidos = sum(len(_items(p.fields.get("quotas"))) for p in paquetes)
    vacios = sum(len(_items(p.fields.get("empty_quotas"))) for p in paquetes)
    resumidos = sum(int(str(p.fields.get("summaries", 0))) for p in paquetes)

    valores: dict[str, float | None] = {
        "s1_per_1000": (s1 * 1000.0 / palabras) if palabras else 0.0,
        "repair_rate": (reparaciones / len(aprobados)) if aprobados else 0.0,
        "quarantines_in_act": float(act_quarantines + cuarentenas),
        "style_drift": deviations[-1] if deviations else None,
        "narrative_debt": float(open_setups),
        "jury_dispersion": (sum(dispersiones) / len(dispersiones)) if dispersiones else None,
        "displaced_blocks": float(desplazados),
        "max_concurrent": float(max(en_vuelo)) if en_vuelo else 0.0,
        "golden_hit_rate": float(dorado[-1])
        if dorado and isinstance(dorado[-1], int | float)
        else None,
        "estimate_short": float(sum(1 for c in llamadas if c.fields.get("estimate_short"))),
        "degraded_retrievals": float(sum(1 for p in paquetes if p.fields.get("degraded"))),
        "empty_quotas": (vacios / (vacios + elegidos)) if (vacios + elegidos) else None,
        "summaries_substituted": float(resumidos),
    }

    def h(signal: str) -> list[float | None]:
        return _history(history, signal)

    alarmas: dict[str, tuple[bool, str]] = {
        "s1_per_1000": (
            _rising(h("s1_per_1000"), valores["s1_per_1000"]),
            "tres capitulos al alza",
        ),
        "repair_rate": ((valores["repair_rate"] or 0.0) > REPAIR_RATE_MAX, f"> {REPAIR_RATE_MAX}"),
        "quarantines_in_act": (
            (valores["quarantines_in_act"] or 0.0) > QUARANTINES_PER_ACT_MAX,
            f"> {QUARANTINES_PER_ACT_MAX} por acto",
        ),
        "style_drift": (
            len(deviations) >= SUSTAINED
            and all(d is not None and d > DRIFT_SIGMAS for d in deviations[-SUSTAINED:]),
            f"> {DRIFT_SIGMAS} sigmas tres capitulos",
        ),
        "narrative_debt": (
            _rising(h("narrative_debt"), valores["narrative_debt"]),
            "tres capitulos al alza",
        ),
        "jury_dispersion": (
            _rising(h("jury_dispersion"), valores["jury_dispersion"]),
            "tres capitulos al alza",
        ),
        "displaced_blocks": (
            _sustained(h("displaced_blocks"), valores["displaced_blocks"], lambda v: v > 0),
            "> 0 tres capitulos",
        ),
        "max_concurrent": (
            _sustained(
                h("max_concurrent"), valores["max_concurrent"], lambda v: v >= CONCURRENCY_ALARM
            ),
            f">= {CONCURRENCY_ALARM} tres capitulos",
        ),
        "golden_hit_rate": (
            valores["golden_hit_rate"] is not None and valores["golden_hit_rate"] < GOLDEN_FLOOR,
            f"< {GOLDEN_FLOOR}",
        ),
        "estimate_short": ((valores["estimate_short"] or 0.0) > 0, "> 0"),
        "degraded_retrievals": ((valores["degraded_retrievals"] or 0.0) > 0, "> 0"),
        "empty_quotas": (
            after_first_act
            and _sustained(
                h("empty_quotas"), valores["empty_quotas"], lambda v: v > EMPTY_QUOTAS_MAJORITY
            ),
            f"> {EMPTY_QUOTAS_MAJORITY} tres capitulos tras el primer acto",
        ),
        "summaries_substituted": (
            _rising(h("summaries_substituted"), valores["summaries_substituted"]),
            "tres capitulos al alza",
        ),
    }

    out: list[MetricRow] = []
    for signal in SIGNALS:
        alarma, umbral = alarmas[signal]
        valor = valores[signal]
        estado = "alarm" if alarma else ("unknown" if valor is None else "ok")
        out.append(
            MetricRow(chapter=chapter, signal=signal, value=valor, threshold=umbral, state=estado)
        )
    return out


def alarms(rows: Sequence[MetricRow]) -> list[MetricRow]:
    return [r for r in rows if r.state == "alarm"]
