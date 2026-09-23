"""El borrador del brief y todo lo que se decide sobre el sin modelo.

RF-212 a RF-216, RF-219. `specs/srs-backend-v3.md` §4.3. Que campos hay, en que
orden se preguntan, como se lee una respuesta, que falta, que se contradice y
como queda el brief que RI-01 acepta: todo es codigo (D-73, D-51 del frontend).
El modelo solo interviene al extraer hechos del texto libre (`extract.py`).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from canon.brief import Brief, BriefEntity, Recipient
from canon.brief_rules import Contradiction, contradictions
from commons.types.primitives import WorldTime

FieldName = Literal[
    "title",
    "recipient.name",
    "recipient.age",
    "recipient.role",
    "premise",
    "genre",
    "tone",
    "target_words",
    "start",
    "dedication",
    "recipient.traits",
    "recipient.memories",
    "forbidden_words",
    "forbidden_themes",
]

Kind = Literal["text", "int", "date", "list"]


class ExtraEntity(BaseModel):
    """Un personaje o un lugar que entro al aceptar un hecho propuesto (RF-218)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["person", "place"]
    name: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=300)


class Draft(BaseModel):
    """RF-169 del frontend: lo que el panel muestra. Vacio al empezar."""

    model_config = ConfigDict(frozen=True)

    title: str = ""
    recipient_name: str = ""
    recipient_age: int | None = None
    recipient_role: str = ""
    recipient_traits: tuple[str, ...] = ()
    recipient_memories: tuple[str, ...] = ()
    premise: str = ""
    genre: str = ""
    tone: str = ""
    target_words: int | None = None
    start: str = ""
    dedication: str = ""
    forbidden_words: tuple[str, ...] = ()
    forbidden_themes: tuple[str, ...] = ()
    entities: tuple[ExtraEntity, ...] = ()
    #: Opcionales ya contestados, aunque fuera con «ninguno» (RF-212).
    answered: tuple[FieldName, ...] = ()


@dataclass(frozen=True)
class FieldSpec:
    name: FieldName
    label: str
    kind: Kind
    required: bool
    question: Callable[[Draft], str]


def _who(d: Draft) -> str:
    return d.recipient_name or "la persona a quien va dedicada"


#: RF-212. El orden es el de las preguntas: los obligatorios primero.
FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("title", "Título", "text", True, lambda d: "¿Qué título quieres para la novela?"),
    FieldSpec(
        "recipient.name",
        "Nombre del destinatario",
        "text",
        True,
        lambda d: "¿Para quién es la novela? Dime su nombre.",
    ),
    FieldSpec(
        "recipient.age",
        "Edad del destinatario",
        "int",
        True,
        lambda d: f"¿Cuántos años tiene {_who(d)}? Escríbelo con cifras.",
    ),
    FieldSpec(
        "recipient.role",
        "Papel en la historia",
        "text",
        True,
        lambda d: (
            f"¿Qué papel tiene {_who(d)} en la historia? Por ejemplo: protagonista, narrador, el mejor amigo del protagonista."
        ),
    ),
    FieldSpec(
        "premise",
        "Premisa",
        "text",
        True,
        lambda d: "¿De qué trata la historia? Cuéntamelo en dos o tres frases.",
    ),
    FieldSpec(
        "genre",
        "Género",
        "text",
        True,
        lambda d: "¿Qué género quieres? Por ejemplo: épica deportiva, aventura, misterio.",
    ),
    FieldSpec(
        "tone",
        "Tono",
        "text",
        True,
        lambda d: "¿Qué tono? Por ejemplo: luminoso, emotivo, con humor.",
    ),
    FieldSpec(
        "target_words",
        "Extensión en palabras",
        "int",
        True,
        lambda d: "¿Qué extensión aproximada quieres, en palabras? Escríbela con cifras.",
    ),
    FieldSpec(
        "start",
        "Fecha en que arranca la historia",
        "date",
        True,
        lambda d: "¿En qué fecha empieza la historia? Escríbela como AAAA-MM-DD.",
    ),
    FieldSpec(
        "dedication",
        "Dedicatoria",
        "text",
        True,
        lambda d: "¿Qué dedicatoria quieres en la portada?",
    ),
    FieldSpec(
        "recipient.traits",
        "Rasgos del destinatario",
        "list",
        False,
        lambda d: (
            f"¿Algún rasgo de {_who(d)} que la historia deba reflejar? Sepáralos por comas, o responde «ninguno»."
        ),
    ),
    FieldSpec(
        "recipient.memories",
        "Recuerdos que puede usar",
        "list",
        False,
        lambda d: (
            f"¿Algún recuerdo compartido con {_who(d)} que quieras que aparezca? Sepáralos por comas, o responde «ninguno»."
        ),
    ),
    FieldSpec(
        "forbidden_words",
        "Palabras que no deben aparecer",
        "list",
        False,
        lambda d: (
            "¿Hay palabras que no deban aparecer en la novela? Sepáralas por comas, o responde «ninguna»."
        ),
    ),
    FieldSpec(
        "forbidden_themes",
        "Temas que no deben tocarse",
        "list",
        False,
        lambda d: "¿Hay temas que no deban tocarse? Sepáralos por comas, o responde «ninguno».",
    ),
)
BY_NAME = {f.name: f for f in FIELDS}

_ATTR = {
    "title": "title",
    "recipient.name": "recipient_name",
    "recipient.age": "recipient_age",
    "recipient.role": "recipient_role",
    "recipient.traits": "recipient_traits",
    "recipient.memories": "recipient_memories",
    "premise": "premise",
    "genre": "genre",
    "tone": "tone",
    "target_words": "target_words",
    "start": "start",
    "dedication": "dedication",
    "forbidden_words": "forbidden_words",
    "forbidden_themes": "forbidden_themes",
}

_NONE = {"ninguno", "ninguna", "nada", "no", "ningunos", "ningunas"}


class ParseError(ValueError):
    """La respuesta no se entiende para ese campo. El mensaje lo dice en palabras."""


def parse(field: FieldSpec, raw: str) -> object:
    """RF-213. Pura: entero, fecha `AAAA-MM-DD`, lista por comas o texto."""
    text = raw.strip()
    if field.kind == "list":
        if _fold(text) in _NONE or not text:
            return ()
        return tuple(p.strip() for p in text.split(",") if p.strip())
    if not text:
        raise ParseError(f"No entendí la respuesta para «{field.label}»: está vacía.")
    if field.kind == "int":
        digits = text.replace(".", "").replace(" ", "")
        if not re.fullmatch(r"\d{1,7}", digits):
            raise ParseError(f"No entendí «{field.label}»: escríbelo solo con cifras.")
        value = int(digits)
        if field.name == "recipient.age" and value > 120:
            raise ParseError("Esa edad no parece posible: escríbela con cifras.")
        if field.name == "target_words" and value < 1:
            raise ParseError("La extensión tiene que ser mayor que cero.")
        return value
    if field.kind == "date":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            raise ParseError("Escribe la fecha como AAAA-MM-DD, por ejemplo 2026-08-01.")
        try:
            date.fromisoformat(text)
        except ValueError as exc:
            raise ParseError("Esa fecha no existe en el calendario.") from exc
        return text
    return text[:2000]


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def value_of(draft: Draft, name: FieldName) -> object:
    return getattr(draft, _ATTR[name])


def with_value(draft: Draft, name: FieldName, value: object) -> Draft:
    answered = draft.answered if name in draft.answered else (*draft.answered, name)
    return draft.model_copy(update={_ATTR[name]: value, "answered": answered})


def _empty(value: object) -> bool:
    return value is None or value == "" or value == ()


class Missing(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: FieldName
    label: str


def missing(draft: Draft) -> list[Missing]:
    """RF-215. Los obligatorios vacios, en el orden de las preguntas."""
    return [
        Missing(field=f.name, label=f.label)
        for f in FIELDS
        if f.required and _empty(value_of(draft, f.name))
    ]


def next_field(draft: Draft) -> FieldSpec | None:
    """RF-212. El primer obligatorio vacio; si no hay, el primer opcional sin contestar."""
    for f in FIELDS:
        if f.required and _empty(value_of(draft, f.name)):
            return f
    for f in FIELDS:
        if not f.required and f.name not in draft.answered:
            return f
    return None


def draft_contradictions(draft: Draft) -> list[Contradiction]:
    """RF-216. Las reglas de RF-201 sobre el borrador, con los nombres de campo del borrador."""
    found = contradictions(
        age=draft.recipient_age,
        genre=draft.genre,
        tone=draft.tone,
        title=draft.title,
        dedication=draft.dedication,
        names=[n for n in (draft.recipient_name, *(e.name for e in draft.entities)) if n],
        forbidden_words=draft.forbidden_words,
        forbidden_themes=draft.forbidden_themes,
    )
    rename = {"entities": "recipient.name"}
    return [
        c.model_copy(update={"fields": tuple(rename.get(f, f) for f in c.fields)}) for c in found
    ]


def slug(text: str, *, limit: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", _fold(text)).strip("-")
    return s[:limit].strip("-")


def suggested_novel_id(draft: Draft, interview_id: str) -> str:
    """D-81. Cumple el patron de identificador de RI-01 y no choca entre dos titulos iguales."""
    base = slug(draft.title) or "novela"
    return f"{base}-{interview_id[:4]}"


def style_guide(draft: Draft) -> str:
    """RF-219. La guia de estilo compuesta, que es lo que el Arquitecto y el Escritor leen."""
    partes = [
        f"Premisa: {draft.premise}",
        f"Género: {draft.genre}. Tono: {draft.tone}.",
        f"La novela está escrita para {draft.recipient_name}, de {draft.recipient_age} años, "
        f"que en la historia es {draft.recipient_role}.",
    ]
    if draft.recipient_traits:
        partes.append("Rasgos que la historia refleja: " + "; ".join(draft.recipient_traits) + ".")
    if draft.recipient_memories:
        partes.append(
            "Recuerdos que la historia puede usar: " + "; ".join(draft.recipient_memories) + "."
        )
    if draft.forbidden_words:
        partes.append("Palabras que no deben aparecer: " + ", ".join(draft.forbidden_words) + ".")
    if draft.forbidden_themes:
        partes.append("Temas que no deben tocarse: " + ", ".join(draft.forbidden_themes) + ".")
    return "\n".join(partes)


def to_brief(draft: Draft) -> Brief | None:
    """RF-219. El brief en la forma que RI-01 acepta, o `None` si falta algo o se contradice."""
    if missing(draft) or draft_contradictions(draft):
        return None
    assert draft.recipient_age is not None and draft.target_words is not None
    recipient_id = slug(draft.recipient_name) or "destinatario"
    entidades = [
        BriefEntity(
            id=recipient_id,
            kind="person",
            name=draft.recipient_name,
            attributes=(("edad", str(draft.recipient_age)), ("papel", draft.recipient_role)),
        )
    ]
    usados = {recipient_id}
    for extra in draft.entities:
        base = slug(extra.name) or extra.kind
        eid, n = base, 2
        while eid in usados:
            eid, n = f"{base}-{n}", n + 1
        usados.add(eid)
        entidades.append(
            BriefEntity(
                id=eid,
                kind=extra.kind,
                name=extra.name,
                attributes=(("nota", extra.note),) if extra.note else (),
            )
        )
    return Brief(
        title=draft.title,
        start=WorldTime(stamp=draft.start),
        entities=tuple(entidades),
        style_guide=style_guide(draft),
        target_words=draft.target_words,
        genre=draft.genre,
        tone=draft.tone,
        dedication=draft.dedication,
        recipient=Recipient(
            entity_id=recipient_id,
            age=draft.recipient_age,
            traits=draft.recipient_traits,
            memories=draft.recipient_memories,
            role=draft.recipient_role,
        ),
        forbidden_words=draft.forbidden_words,
        forbidden_themes=draft.forbidden_themes,
    )
