"""`quiz.build`. Preguntas y solucionario desde lo que se encargo.

RF-112, RF-113. `verification.md` §5.12. **Las preguntas salen de la
especificacion de escena, nunca del capitulo ni de su delta.** Generadas desde
lo que el capitulo dijo, la pregunta seria "¿dijiste lo que dijiste?": circular
y aprueba siempre. Generadas desde lo que se encargo, es "¿entregaste lo que se
te pidio?".

Y no las escribe un modelo: una pregunta sin solucionario garantizado devuelve
esto a la condicion de juez, que es justo lo que se evita. Cada pregunta tiene
**claves** --nombres de entidad, cifras-- que la respuesta correcta contiene, y
la correccion es una comprobacion de presencia, determinista.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from commons.types.scene import SceneSpec


class Question(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    scene_id: str
    text: str
    keys: tuple[str, ...] = Field(
        min_length=1, description="Terminos que la respuesta correcta contiene, todos"
    )
    expected: str = Field(description="El solucionario, legible")


def build(specs: Sequence[SceneSpec], names: Mapping[str, str]) -> list[Question]:
    """Una bateria por capitulo. Solo preguntas con solucionario cerrado.

    Se pregunta por lo que tiene clave comprobable: quien cuenta, donde, quien
    esta. Lo que no tiene clave --que quiere el POV, como termina-- no entra,
    porque corregirlo exigiria juicio y esto es un examen, no un jurado.
    """
    out: list[Question] = []
    for spec in specs:
        sid = spec.identity.scene_id
        pov = names.get(spec.identity.pov, spec.identity.pov)
        lugar = names.get(spec.identity.place, spec.identity.place)
        elenco = tuple(names.get(c, c) for c in spec.content.cast)

        out.append(
            Question(
                id=f"{sid}-pov",
                scene_id=sid,
                text=f"En la escena {spec.identity.ordinal}, ¿desde el punto de vista de quien se cuenta?",
                keys=(pov,),
                expected=pov,
            )
        )
        out.append(
            Question(
                id=f"{sid}-lugar",
                scene_id=sid,
                text=f"¿Donde ocurre la escena {spec.identity.ordinal}?",
                keys=(lugar,),
                expected=lugar,
            )
        )
        if len(elenco) > 1:
            out.append(
                Question(
                    id=f"{sid}-elenco",
                    scene_id=sid,
                    text=f"¿Que personajes estan presentes en la escena {spec.identity.ordinal}? Nombra a todos.",
                    keys=elenco,
                    expected=", ".join(elenco),
                )
            )
    return out
