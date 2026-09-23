"""Instruccion del Estilista: `style.polish`.

RF-139. Recibe el capitulo **ya aprobado** por el Continuista y el Jurado, la
guia de estilo completa, la lista de proscripcion completa, la huella de
referencia y la del capitulo, muestras modelicas y las repeticiones detectadas.
Devuelve el capitulo pulido: poda, proscripcion, voz. No cambia hechos.

Despues del Estilista el capitulo vuelve al Continuista (RF-141): un pase de
estilo que abre un defecto de continuidad se revierte. Por eso la instruccion
insiste en que no toque lo que pasa, solo como se cuenta.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from commons.types.scene import SceneSpec

SYSTEM = """Eres el Estilista de una novela. Eres un componente de un sistema
automatico: devuelves JSON y nada mas.

Recibes un capitulo que ya paso la verificacion de continuidad y el jurado.
Haces un pase de estilo: poda, precision, ritmo de frase, fidelidad a la guia.

REGLAS QUE NO SE NEGOCIAN

1. No cambias NINGUN hecho: quien hace que, donde, cuando, en que orden, que se
   sabe. Si una frase lleva un hecho, el hecho sigue ahi despues de tu pase.
2. Mismo punto de vista, mismo tiempo verbal, misma persona por escena.
3. Eliminas toda aparicion de los terminos proscritos y de las repeticiones
   senaladas, sustituyendolas por algo propio de esta escena, no por un
   sinonimo del cliche.
4. Acercas la huella del capitulo a la de referencia: si la frase media es mas
   larga, acortas; si hay mas adjetivos de la cuenta, podas.
5. Longitud parecida: ni mas del 10 % ni menos del 10 % de palabras por escena.
6. Devuelves TODAS las escenas, en el mismo orden, con su identificador."""


class PolishedScene(BaseModel):
    model_config = ConfigDict(frozen=True)

    scene: str = Field(min_length=1)
    text: str = Field(min_length=1)


class Polished(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenes: tuple[PolishedScene, ...]


def schema() -> str:
    return (
        "Objeto con la clave scenes: lista de {scene, text}, una por escena, en orden.\n"
        "Ejemplo:\n"
        + json.dumps(
            {"scenes": [{"scene": "c1e1", "text": "Marcos entro el ultimo."}]}, ensure_ascii=False
        )
    )


def instruction(
    specs: Sequence[SceneSpec],
    texts: Sequence[str],
    *,
    proscribed: Sequence[str],
    repetitions: Sequence[str],
    reference: str,
    current: str,
    samples: Sequence[str] = (),
    voice_cards: str = "",
) -> str:
    capitulo = "\n\n".join(
        f"### {s.identity.scene_id} · POV {s.identity.pov}\n\n{t}"
        for s, t in zip(specs, texts, strict=True)
    )
    muestras = "\n\n".join(f"--- muestra {i}\n{m}" for i, m in enumerate(samples, 1)) or (
        "(aun no hay: primeros capitulos)"
    )
    return f"""Haz el pase de estilo de este capitulo.

TERMINOS PROSCRITOS: {", ".join(proscribed) or "(ninguno)"}
REPETICIONES DETECTADAS: {", ".join(repetitions) or "(ninguna)"}

HUELLA DE REFERENCIA: {reference or "(aun no hay: primeros capitulos)"}
HUELLA DEL CAPITULO: {current}

MUESTRAS MODELICAS DE LA OBRA, el tono al que volver:
{muestras}

FICHAS DE VOZ DE LOS PUNTOS DE VISTA:
{voice_cards or "(sin fichas)"}

CAPITULO:

{capitulo}

Devuelve SOLO el JSON con todas las escenas."""


def parse(raw: str, specs: Sequence[SceneSpec]) -> list[str]:
    """Los textos pulidos en el orden de las escenas. Falta una: error (RI-18)."""
    data = Polished.model_validate_json(raw)
    por_id = {s.scene: s.text for s in data.scenes}
    faltan = [s.identity.scene_id for s in specs if s.identity.scene_id not in por_id]
    if faltan:
        raise ValueError(f"el Estilista no devolvio las escenas {faltan}")
    return [por_id[s.identity.scene_id] for s in specs]
