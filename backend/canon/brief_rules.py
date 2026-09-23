"""Contradicciones del brief que se comprueban sin juicio.

RF-201, RF-247, D-75. Tres reglas y ninguna mas: las que se deciden con codigo. Las usan
la carga del brief (RI-01 rechaza un brief contradictorio, `srs-frontend-v1.md`
RI-41) y la entrevista, que las aplica al borrador mientras se escribe
(RF-216). Viven en `canon/` porque las dos las necesitan y `canon/` es de donde
toda funcionalidad puede leer.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from canon import normalize

#: **Propuesta** (D-75). La franja PEGI 12 es la primera que la clasificacion
#: europea separa de las edades infantiles.
MIN_AGE_FOR_ADULT = 12
#: RF-247, D-75. Generos y tonos que la regla de edad considera adultos. Lista
#: cerrada y **una sola para los dos campos**: un tono erotico es tan inadecuado
#: para un nino como un genero erotico. Se compara por palabra normalizada con
#: sus variantes (RF-237): «eróticas», «EROTICO» y «Macabro» casan; «aterrorizado»
#: no casa con «terror».
ADULT_TERMS = ("terror", "erótico", "erótica", "gore", "violento", "macabro")


class Contradiction(BaseModel):
    """Dos campos que no pueden ser ciertos a la vez, y la regla que lo dice."""

    model_config = ConfigDict(frozen=True)

    fields: tuple[str, str]
    rule: str
    message: str


def fold(text: str) -> str:
    """Minusculas y sin acentos: `Erótica` y `erotica` son la misma palabra.

    Es la normalizacion de RF-237 (`canon/normalize.py`), la unica del backend;
    se conserva el nombre porque la usa la interpretacion de solicitudes.
    """
    return normalize.normalize(text)


def _adult_term(text: str) -> str | None:
    """El primer termino de la lista adulta que aparece en `text`, o `None`."""
    return next((t for t in ADULT_TERMS if normalize.contains(text, t)), None)


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

    if age is not None and age < MIN_AGE_FOR_ADULT:
        if _adult_term(genre) is not None:
            out.append(
                Contradiction(
                    fields=("recipient.age", "genre"),
                    rule="edad-genero",
                    message=f"El destinatario tiene {age} años y el género «{genre}» es para mayores de {MIN_AGE_FOR_ADULT}.",
                )
            )
        if _adult_term(tone) is not None:
            out.append(
                Contradiction(
                    fields=("recipient.age", "tone"),
                    rule="edad-tono",
                    message=f"El destinatario tiene {age} años y el tono «{tone}» es para mayores de {MIN_AGE_FOR_ADULT}.",
                )
            )

    places = (("title", title), ("dedication", dedication), *(("entities", n) for n in names))
    for word in forbidden_words:
        if not normalize.key(word):
            continue
        for field, text in places:
            if normalize.contains(text, word):
                out.append(
                    Contradiction(
                        fields=("forbidden_words", field),
                        rule="prohibida-presente",
                        message=f"«{word}» está prohibida y aparece en {_label(field)}.",
                    )
                )

    g, t = normalize.key(genre), normalize.key(tone)
    for theme in forbidden_themes:
        th = normalize.key(theme)
        if not th:
            continue
        if th == g:
            out.append(
                Contradiction(
                    fields=("forbidden_themes", "genre"),
                    rule="tema-es-genero",
                    message=f"El tema «{theme}» está prohibido y es el propio género.",
                )
            )
        if th == t:
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
