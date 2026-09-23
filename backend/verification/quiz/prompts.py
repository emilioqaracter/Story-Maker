"""Instruccion de `quiz.answer`: el lector sin contexto.

RF-112, RF-114. La unica llamada de modelo que **no recibe prefijo cacheable**,
ni canon, ni fichas, ni rubrica: su valor entero depende de que el lector no
tenga delante nada mas que el capitulo. Un lector que ve el canon examina lo
que ya sabia.

La dispara el Orquestador, en codigo, al cerrar el capitulo y antes de su
puerta: un examen que el examinado decide si se presenta no es un examen.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from verification.quiz.build import Question

#: Sin prefijo: lo que el sistema no le da al lector es la mitad del metodo.
SYSTEM = """Lees un capitulo de una novela y respondes preguntas sobre el, SOLO con
lo que el capitulo dice. No tienes ningun otro contexto y no lo necesitas: si el
capitulo no lo dice, respondes "no se sabe".

Respuestas breves y concretas, con nombres. Devuelves JSON y nada mas."""


class Answers(BaseModel):
    model_config = ConfigDict(frozen=True)

    answers: dict[str, str] = Field(description="id de pregunta -> respuesta")


def schema() -> str:
    return (
        "Objeto con la clave answers: un objeto id_de_pregunta -> respuesta.\n"
        "Ejemplo:\n"
        + json.dumps(
            {"answers": {"c1e1-pov": "Marcos", "c1e1-lugar": "el vestuario"}}, ensure_ascii=False
        )
    )


def instruction(chapter_text: str, questions: Sequence[Question]) -> str:
    lista = "\n".join(f"  {q.id}: {q.text}" for q in questions)
    return f"""CAPITULO:

{chapter_text}

PREGUNTAS:
{lista}

Responde SOLO con el JSON."""


def parse(raw: str, questions: Sequence[Question]) -> list[str]:
    """Respuestas en el orden de las preguntas; la que falta, vacia."""
    data = Answers.model_validate_json(raw)
    return [data.answers.get(q.id, "") for q in questions]
