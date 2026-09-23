"""La entrevista: un turno cambia el borrador y devuelve el estado entero.

RF-211 a RF-220. `specs/srs-backend-v3.md` §4.3. Un turno puede traer cualquier
combinacion de respuesta, texto libre, ediciones y decisiones sobre hechos
propuestos (RI-39 del frontend). El estado que vuelve es lo que el frontend
pinta: el frontend no calcula nada (D-51 del frontend).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brief.draft import (
    BY_NAME,
    Draft,
    ExtraEntity,
    FieldName,
    Missing,
    ParseError,
    draft_contradictions,
    missing,
    next_field,
    parse,
    suggested_novel_id,
    to_brief,
    value_of,
    with_value,
)
from brief.extract import Extraction, Extractor, RawFact, Target, TooLongError, anchor
from canon.brief import Brief
from canon.brief_rules import Contradiction


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["interviewer", "person"]
    kind: Literal["question", "answer", "free_text", "note"]
    text: str


class Question(BaseModel):
    model_config = ConfigDict(frozen=True)

    field: FieldName
    text: str


class ProposedFact(BaseModel):
    """RF-174 del frontend: un hecho sacado del texto libre, con su cita."""

    model_config = ConfigDict(frozen=True)

    fact_id: str
    target: Target
    value: str
    quote: str
    status: Literal["proposed", "accepted", "discarded"] = "proposed"


class InterviewState(BaseModel):
    """RI-39, RI-40 del frontend."""

    model_config = ConfigDict(frozen=True)

    interview_id: str
    messages: tuple[Message, ...]
    question: Question | None
    draft: Draft
    missing: tuple[Missing, ...]
    contradictions: tuple[Contradiction, ...]
    proposed: tuple[ProposedFact, ...]
    discarded_quotes: int = Field(ge=0, description="Citas descartadas por no aparecer literales")
    complete: bool
    brief: Brief | None = Field(description="En la forma de RI-01, solo si el brief esta completo")
    novel_id: str | None = Field(description="Identificador sugerido para RI-01 (D-81)")


class FieldEdit(BaseModel):
    """RF-214. Un campo por nombre; los de lista, separados por comas."""

    model_config = ConfigDict(frozen=True)

    field: FieldName
    value: str = Field(max_length=4_000)


class TurnIn(BaseModel):
    """RI-39. Todo opcional: un turno puede traer cualquier combinacion."""

    model_config = ConfigDict(frozen=True)

    answer: str | None = Field(default=None, max_length=4_000)
    free_text: str | None = Field(
        default=None,
        max_length=200_000,
        description="Texto no confiable: una anecdota, una carta. Nunca instruye al sistema",
    )
    edits: tuple[FieldEdit, ...] = Field(default=(), max_length=20)
    accept: tuple[str, ...] = Field(default=(), max_length=100)
    discard: tuple[str, ...] = Field(default=(), max_length=100)


def _summary(draft: Draft) -> str:
    return (
        "\n".join(
            f"{f.label}: {value_of(draft, f.name)}"
            for f in BY_NAME.values()
            if value_of(draft, f.name) not in ("", None, ())
        )
        or "(vacio)"
    )


def _finish(
    interview_id: str,
    draft: Draft,
    messages: list[Message],
    proposed: Sequence[ProposedFact],
    discarded: int,
) -> InterviewState:
    """Recalcula todo lo derivado y anade la siguiente pregunta."""
    faltan = missing(draft)
    choques = draft_contradictions(draft)
    brief = to_brief(draft)
    siguiente = next_field(draft)
    pregunta = Question(field=siguiente.name, text=siguiente.question(draft)) if siguiente else None
    if choques:
        messages.append(
            Message(
                role="interviewer",
                kind="note",
                text="Hay algo que no encaja: " + " ".join(c.message for c in choques),
            )
        )
    if brief is not None and pregunta is None:
        messages.append(
            Message(
                role="interviewer",
                kind="question",
                text="El encargo está completo. Cuando quieras, crea la novela.",
            )
        )
    elif brief is not None and pregunta is not None:
        messages.append(
            Message(
                role="interviewer",
                kind="question",
                text=f"El encargo ya está completo y puedes crear la novela. Si quieres afinarlo: {pregunta.text}",
            )
        )
    elif pregunta is not None:
        messages.append(Message(role="interviewer", kind="question", text=pregunta.text))
    return InterviewState(
        interview_id=interview_id,
        messages=tuple(messages),
        question=pregunta,
        draft=draft,
        missing=tuple(faltan),
        contradictions=tuple(choques),
        proposed=tuple(proposed),
        discarded_quotes=discarded,
        complete=brief is not None,
        brief=brief,
        novel_id=suggested_novel_id(draft, interview_id) if brief is not None else None,
    )


def new(interview_id: str) -> InterviewState:
    """RF-211."""
    return _finish(
        interview_id,
        Draft(),
        [
            Message(
                role="interviewer", kind="note", text="Vamos a preparar el encargo de la novela."
            )
        ],
        (),
        0,
    )


def _apply_fact(draft: Draft, fact: ProposedFact) -> Draft:
    if fact.target == "recipient.traits":
        return with_value(draft, "recipient.traits", (*draft.recipient_traits, fact.value))
    if fact.target == "recipient.memories":
        return with_value(draft, "recipient.memories", (*draft.recipient_memories, fact.value))
    kind: Literal["person", "place"] = "person" if fact.target == "entity.person" else "place"
    if any(e.name == fact.value for e in draft.entities):
        return draft
    return draft.model_copy(
        update={"entities": (*draft.entities, ExtraEntity(kind=kind, name=fact.value))}
    )


def turn(state: InterviewState, incoming: TurnIn, extractor: Extractor | None) -> InterviewState:
    """RF-213, RF-214, RF-217, RF-218. Pura salvo la llamada del extractor."""
    draft = state.draft
    messages = list(state.messages)
    proposed = list(state.proposed)
    discarded = state.discarded_quotes

    for edit in incoming.edits:
        spec = BY_NAME[edit.field]
        try:
            draft = with_value(draft, edit.field, parse(spec, edit.value))
        except ParseError as exc:
            messages.append(Message(role="interviewer", kind="note", text=str(exc)))

    decididos = dict.fromkeys(incoming.accept, "accepted") | dict.fromkeys(
        incoming.discard, "discarded"
    )
    for n, fact in enumerate(proposed):
        nuevo = decididos.get(fact.fact_id)
        if nuevo is None or fact.status != "proposed":
            continue
        proposed[n] = fact.model_copy(update={"status": nuevo})
        if nuevo == "accepted":
            draft = _apply_fact(draft, fact)

    if incoming.answer is not None and incoming.answer.strip():
        messages.append(Message(role="person", kind="answer", text=incoming.answer))
        if state.question is not None:
            spec = BY_NAME[state.question.field]
            try:
                draft = with_value(draft, spec.name, parse(spec, incoming.answer))
            except ParseError as exc:
                messages.append(Message(role="interviewer", kind="note", text=str(exc)))

    if incoming.free_text is not None and incoming.free_text.strip():
        texto = incoming.free_text
        messages.append(Message(role="person", kind="free_text", text=texto))
        crudos: Sequence[RawFact] = ()
        invalidos = 0
        try:
            if extractor is None:
                raise RuntimeError("sin proveedor")
            salida = extractor(texto, _summary(draft))
            if isinstance(salida, Extraction):
                crudos, invalidos = salida.facts, salida.invalid
            else:
                crudos = salida
        except TooLongError as exc:
            messages.append(Message(role="interviewer", kind="note", text=str(exc)))
        except Exception:  # un fallo del modelo no para la entrevista (RF-217)
            messages.append(
                Message(
                    role="interviewer",
                    kind="note",
                    text="No pude sacar hechos del texto: el modelo no respondió. Puedes seguir con la entrevista.",
                )
            )
        anclados = anchor(crudos, texto)
        discarded += len(anclados.discarded) + invalidos
        base = len(proposed)
        for i, f in enumerate(anclados.kept, start=1):
            proposed.append(
                ProposedFact(fact_id=f"p{base + i}", target=f.target, value=f.value, quote=f.quote)
            )
        if crudos or invalidos:
            nota = f"Del texto saqué {len(anclados.kept)} hechos propuestos. Acepta los que quieras incluir."
            if anclados.discarded:
                nota += f" Descarté {len(anclados.discarded)} porque su cita no aparece tal cual en el texto."
            if invalidos:
                nota += f" Descarté {invalidos} que no eran de ningún tipo que el encargo admita."

            messages.append(Message(role="interviewer", kind="note", text=nota))

    return _finish(state.interview_id, draft, messages, proposed, discarded)
