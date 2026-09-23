"""Contradicciones del brief que se comprueban sin juicio.

RF-201, D-75. Tres reglas y ninguna mas: las que se deciden con codigo. Las usan
la carga del brief (RI-01 rechaza un brief contradictorio, `srs-frontend-v1.md`
RI-41) y la entrevista, que las aplica al borrador mientras se escribe
(RF-216). Viven en `canon/` porque las dos las necesitan y `canon/` es de donde
toda funcionalidad puede leer.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

#: **Propuesta** (D-75). La franja PEGI 12 es la primera que la clasificacion
#: europea separa de las edades infantiles.
MIN_AGE_FOR_ADULT = 12
#: Generos y tonos que la regla de edad considera adultos. Lista cerrada.
ADULT_GENRES = ("terror", "erotico", "erotica", "gore")
ADULT_TONES = ("violento", "macabro")


class Contradiction(BaseModel):
    """Dos campos que no pueden ser ciertos a la vez, y la regla que lo dice."""

    model_config = ConfigDict(frozen=True)

    fields: tuple[str, str]
    rule: str
    message: str


def fold(text: str) -> str:
    """Minusculas y sin acentos: `Erótica` y `erotica` son la misma palabra."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", fold(text)))


def contradictions(
    *,
    age: int | None,
    genre: str,
    tone: str,
    title: str,
    dedication: str,
    names: Sequence[str],
    forbidden_words: Sequence[str],
    forbidden_themes: Sequence[str],
) -> list[Contradiction]:
    """Las contradicciones de un brief o de un borrador. Pura."""
    out: list[Contradiction] = []
    g, t = fold(genre), fold(tone)

    if age is not None and age < MIN_AGE_FOR_ADULT:
        for word in ADULT_GENRES:
            if word in _words(g):
                out.append(
                    Contradiction(
                        fields=("recipient.age", "genre"),
                        rule="edad-genero",
                        message=f"El destinatario tiene {age} años y el género «{genre}» es para mayores de {MIN_AGE_FOR_ADULT}.",
                    )
                )
                break
        for word in ADULT_TONES:
            if word in _words(t):
                out.append(
                    Contradiction(
                        fields=("recipient.age", "tone"),
                        rule="edad-tono",
                        message=f"El destinatario tiene {age} años y el tono «{tone}» es para mayores de {MIN_AGE_FOR_ADULT}.",
                    )
                )
                break

    places = (("title", title), ("dedication", dedication), *(("entities", n) for n in names))
    for word in forbidden_words:
        w = fold(word).strip()
        if not w:
            continue
        for field, text in places:
            if w in _words(text) or (" " in w and w in fold(text)):
                out.append(
                    Contradiction(
                        fields=("forbidden_words", field),
                        rule="prohibida-presente",
                        message=f"«{word}» está prohibida y aparece en {_label(field)}.",
                    )
                )

    for theme in forbidden_themes:
        th = fold(theme).strip()
        if not th:
            continue
        if th == g.strip():
            out.append(
                Contradiction(
                    fields=("forbidden_themes", "genre"),
                    rule="tema-es-genero",
                    message=f"El tema «{theme}» está prohibido y es el propio género.",
                )
            )
        if th == t.strip():
            out.append(
                Contradiction(
                    fields=("forbidden_themes", "tone"),
                    rule="tema-es-tono",
                    message=f"El tema «{theme}» está prohibido y es el propio tono.",
                )
            )
    return out


def _label(field: str) -> str:
    return {"title": "el título", "dedication": "la dedicatoria", "entities": "un nombre"}.get(
        field, field
    )
