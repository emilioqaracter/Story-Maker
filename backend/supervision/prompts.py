"""Instruccion del Supervisor y su veredicto de salud.

RF-146, RF-147, RF-149. Tras cada congelacion el Supervisor lee las metricas
del capitulo, la serie historica, la deuda, la curva planificada frente a la
realizada y los resumenes, y devuelve **sano** o **deriva**, y en ese caso que
tramo replanificar. No toca capitulos congelados: el tramo empieza siempre
despues del ultimo congelado, y si el modelo dice otra cosa el codigo lo acota.

Un Supervisor que no responde cuenta como sano y se traza como fallo de
proceso (D-45): un Supervisor que puede parar la tirada es un aprobador con
otro nombre.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from canon.freeze.rows import MetricRow

SYSTEM = """Eres el Supervisor de una novela en produccion. Eres un componente de
un sistema automatico: devuelves JSON y nada mas.

Vigilas la salud de la obra entera, no la de un capitulo: deriva de estilo,
deuda narrativa que crece, tension que no sube, jueces que dejan de acordar.
Decides si la obra sigue sana o si hay que replanificar un tramo de lo que
queda por escribir.

REGLAS QUE NO SE NEGOCIAN

1. Solo propones replanificar capitulos TODAVIA NO ESCRITOS. Lo congelado no se
   toca nunca.
2. Una alarma aislada no es deriva. Deriva es una tendencia que, si sigue,
   rompe la obra: deuda que no se va a poder cobrar, tension que se aplana,
   voz que se pierde.
3. Si propones replanificar, dices el acto y el primer capitulo del tramo, y
   la senal que lo motiva, con su valor.
4. Si no hay motivo, la obra esta sana. No inventes problemas."""


class HealthVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    healthy: bool
    signal: str = Field(default="", description="La senal que motiva replanificar")
    act: int | None = Field(default=None, ge=1)
    from_chapter: int | None = Field(default=None, ge=1)
    reason: str = ""


def schema() -> str:
    return (
        "Objeto con healthy (true|false), signal, act, from_chapter y reason.\nEjemplos:\n"
        + json.dumps(
            {
                "healthy": True,
                "signal": "",
                "act": None,
                "from_chapter": None,
                "reason": "sin tendencias",
            }
        )
        + "\n"
        + json.dumps(
            {
                "healthy": False,
                "signal": "narrative_debt",
                "act": 2,
                "from_chapter": 6,
                "reason": "la deuda crece tres capitulos y el acto 2 no planta cobros",
            },
            ensure_ascii=False,
        )
    )


def instruction(
    *,
    chapter: int,
    total_chapters: int,
    metrics: Sequence[MetricRow],
    history: Sequence[MetricRow],
    debt: Sequence[str],
    curve: str,
    summaries: Sequence[str],
    remaining_outline: str,
) -> str:
    actual = "\n".join(
        f"  {m.signal}: {m.value} [{m.state}; umbral {m.threshold}]" for m in metrics
    )
    serie: dict[str, list[str]] = {}
    for m in sorted(history, key=lambda r: r.chapter):
        serie.setdefault(m.signal, []).append(f"{m.chapter}:{m.value}")
    historica = (
        "\n".join(f"  {s}: {', '.join(v)}" for s, v in sorted(serie.items()))
        or "  (primer capitulo)"
    )
    return f"""Capitulo {chapter} de {total_chapters} recien congelado.

METRICAS DEL CAPITULO:
{actual}

SERIE HISTORICA:
{historica}

DEUDA NARRATIVA ABIERTA:
{chr(10).join(f"  - {d}" for d in debt) or "  (ninguna)"}

CURVA DE TENSION, PLANIFICADA FRENTE A REALIZADA:
{curve or "  (sin datos del jurado)"}

RESUMENES DE LOS CAPITULOS:
{chr(10).join(summaries) or "(ninguno)"}

ESCALETA DE LO QUE QUEDA:
{remaining_outline or "(nada: es el ultimo capitulo)"}

Devuelve SOLO el JSON."""


def parse(raw: str) -> HealthVerdict:
    return HealthVerdict.model_validate_json(raw)


def clamp(verdict: HealthVerdict, *, last_frozen: int, total_chapters: int) -> HealthVerdict | None:
    """RF-147. El tramo nunca empieza en un capitulo congelado; si no queda
    ninguno por escribir, no hay nada que replanificar."""
    if verdict.healthy:
        return None
    desde = max(verdict.from_chapter or last_frozen + 1, last_frozen + 1)
    if desde > total_chapters:
        return None
    return verdict.model_copy(update={"from_chapter": desde})
