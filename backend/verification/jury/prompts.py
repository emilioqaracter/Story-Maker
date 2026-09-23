"""Instruccion de las instancias del Jurado: `voice.audit`, `pacing.audit`,
`subtext.audit`, `theme.audit`.

RF-126 a RF-129, RNF-32. `architecture.md` §4.9 y §9.2. Cada instancia recibe
exactamente su paquete: **invariantes sin guia de estilo** --un juez que ve la
guia puntua la guia--, las rubricas, el capitulo entero y las fichas de voz de
los POV. Nunca el paquete del Escritor, ni su razonamiento, ni los defectos ya
detectados.

Tres instancias con **semillas distintas**. El CLI no expone semilla de
muestreo, asi que la semilla gobierna lo que si se puede variar sin cambiar el
encargo: el orden en que se presentan las dimensiones y el angulo de lectura de
la instancia. Es lo que hace que las tres no sean la misma llamada tres veces,
que es justo lo que la dispersion necesita para significar algo.
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from commons.types.rubrics import Dimension, RubricSet
from commons.types.scene import SceneSpec

#: Invariantes reducidos, §4.9 Jurado: 500 tokens y sin guia de estilo.
JUDGE_INVARIANTS = """- Juzgas SOLO lo que tienes delante: el capitulo. No sabes como se escribio.
- Toda puntuacion cita un pasaje LITERAL del capitulo, de 8 a 25 palabras, de
  un solo parrafo y que aparezca una sola vez. Copialo caracter a caracter: sin
  corregir erratas, sin cambiar nombres, sin unir parrafos, sin recortar con
  puntos suspensivos. Sin cita literal, la puntuacion no existe.
- Puntuas de 1 a 5 con la rubrica. El 3 es "cumple". No redondees hacia arriba."""

SYSTEM = f"""Eres una instancia del Jurado de una novela. Eres un componente de un
sistema automatico: devuelves JSON y nada mas.

{JUDGE_INVARIANTS}"""

#: Angulos de lectura. La semilla elige uno por instancia.
_ANGLES = (
    "Lee como un editor que busca lo que sobra.",
    "Lee como un lector que llega por primera vez a la obra.",
    "Lee como un escritor que busca lo que se podria haber hecho mejor.",
    "Lee como un corrector que desconfia de la primera impresion.",
)


class Score(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: Dimension
    level: int = Field(ge=1, le=5)
    scene: str = Field(min_length=1, description="Identificador de la escena citada")
    quote: str = Field(min_length=1)
    justification: str = Field(default="")


class InstanceVerdict(BaseModel):
    """Lo que devuelve una instancia."""

    model_config = ConfigDict(frozen=True)

    scores: tuple[Score, ...]


def schema() -> str:
    ejemplo = {
        "scores": [
            {
                "dimension": "voice",
                "level": 3,
                "scene": "c1e1",
                "quote": "Marcos entro el ultimo y nadie levanto la vista del suelo",
                "justification": "El narrador suena igual que Marcos en este tramo.",
            }
        ]
    }
    return (
        "Objeto con la clave scores: una puntuacion por dimension. dimension es una de "
        f"{', '.join(d.value for d in Dimension)}; level de 1 a 5; scene el identificador "
        "de la escena citada; quote la cita literal.\nEjemplo:\n"
        + json.dumps(ejemplo, ensure_ascii=False, indent=1)
    )


def rubric_text(rubrics: RubricSet, order: Sequence[Dimension]) -> str:
    partes = []
    for d in order:
        r = rubrics.get(d)
        niveles = "\n".join(f"    {i}. {texto}" for i, texto in enumerate(r.levels, 1))
        partes.append(f"- {d.value} ({r.skill}): {r.question}\n{niveles}")
    return f"RUBRICAS (version {rubrics.version})\n" + "\n".join(partes)


def order_for(seed: int) -> list[Dimension]:
    """El orden de las dimensiones para esta semilla. Determinista."""
    dims = list(Dimension)
    random.Random(seed).shuffle(dims)  # nosec B311 - no es criptografico
    return dims


def instruction(
    specs: Sequence[SceneSpec],
    texts: Sequence[str],
    *,
    rubrics: RubricSet,
    voice_cards: str,
    seed: int,
) -> str:
    orden = order_for(seed)
    angulo = _ANGLES[seed % len(_ANGLES)]
    capitulo = "\n\n".join(
        f"### {s.identity.scene_id} · POV {s.identity.pov}\n\n{t}"
        for s, t in zip(specs, texts, strict=True)
    )
    return f"""Evalua este capitulo. {angulo}

{rubric_text(rubrics, orden)}

FICHAS DE VOZ DE LOS PUNTOS DE VISTA:
{voice_cards or "(sin fichas)"}

CAPITULO:

{capitulo}

Una puntuacion por dimension, en este orden: {", ".join(d.value for d in orden)}.
Devuelve SOLO el JSON."""


def parse(raw: str) -> InstanceVerdict:
    return InstanceVerdict.model_validate_json(raw)
