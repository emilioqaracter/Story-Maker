"""`quiz.grade`. Corrige las respuestas contra el solucionario.

RF-112, RF-115. Determinista: una respuesta es correcta si contiene **todas**
las claves de su pregunta, normalizadas. Cada respuesta erronea es un defecto
**S2** que entra por la puerta de capitulo que ya existe, sin puerta nueva y sin
umbral propio.

La cita del defecto es el arranque de la escena examinada: no hay pasaje que
citar cuando el fallo es que la informacion no llego a la pagina, y el
Reparador necesita saber al menos que escena tocar.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence

from commons.types.primitives import Defect, Evidence, Severity
from verification.quiz.build import Question


def _normalize(text: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


#: Palabras de un nombre que no lo identifican: "el vestuario del Molinon" se
#: reconoce por "vestuario" o por "molinon", nunca por "el" o por "del".
_NAME_FILLERS = frozenset(
    {"el", "la", "los", "las", "de", "del", "y", "en", "un", "una", "unos", "unas", "al"}
    # D-64: fuera de articulos y preposiciones; las de tres letras o mas son las
    # que el corte por longitud no filtra solo.
    | {"con", "por", "para", "sin", "sobre", "entre", "hacia", "desde", "hasta", "tras"}
    | {"contra", "segun", "ante", "bajo"}
)


def _key_found(key: str, answer: str) -> bool:
    """Una clave aparece si aparece entera o alguna de sus palabras distintivas.

    Un lector que responde "Marcos" a quien cuenta la escena de "Marcos Vela"
    ha entendido el capitulo. Exigir el nombre completo mide la memoria del
    lector para los apellidos, no si la informacion llego a la pagina (medido en
    la primera tirada real: 5 de 6 respuestas correctas dadas por falladas).
    """
    k = _normalize(key)
    if k in answer:
        return True
    palabras = [w for w in re.findall(r"\w+", k) if w not in _NAME_FILLERS and len(w) >= 3]
    return any(re.search(rf"\b{re.escape(w)}\b", answer) for w in palabras)


def is_correct(question: Question, answer: str) -> bool:
    plano = _normalize(answer)
    return all(_key_found(k, plano) for k in question.keys)


def grade(
    questions: Sequence[Question],
    answers: Sequence[str],
    *,
    scene_texts: Mapping[str, str],
) -> list[Defect]:
    """Un S2 por respuesta erronea. Una respuesta que falta cuenta como erronea."""
    out: list[Defect] = []
    for i, q in enumerate(questions):
        respuesta = answers[i] if i < len(answers) else ""
        if is_correct(q, respuesta):
            continue
        texto = scene_texts.get(q.scene_id, "")
        out.append(
            Defect(
                kind="quiz",
                severity=Severity.S2,
                evidence=Evidence(quote=texto[:80] or q.text, offset=0),
                rule=(
                    f"el capitulo no transmite lo que se encargo: a «{q.text}» se esperaba "
                    f"«{q.expected}» y el lector sin contexto respondio «{respuesta[:80]}»"
                ),
            )
        )
    return out
