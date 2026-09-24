"""Rutas de la entrevista. RI-38 a RI-40 de `srs-frontend-v1.md` §3.2.

Son encargos (`architecture.md` §2.2): la entrevista construye el brief antes
del ciclo y no escribe canon. El brief completo lo envia el frontend a RI-01,
tal como estas rutas lo devuelven.

El extractor del texto libre llega por dependencia (RI-59): `brief/` no conoce
el transporte del modelo; lo compone `orchestration/app.py`. Sin extractor, el
texto libre se recibe y la respuesta dice que no se pudo extraer nada.

**Traza de la entrevista** (RF-262, RD-46). Cada entrevista tiene la suya en
`_interviews/<iid>.trace.jsonl`: su apertura, cada turno --solo recuentos, nunca
lo que la persona escribio-- y cada llamada de `brief.extract` con sus tokens,
coste y duracion. Al crear la novela pasa a su sesion de Langfuse.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict

from brief import interview, store
from brief.extract import Extractor
from commons.settings import Settings
from commons.tracing.trace import Trace

router = APIRouter(tags=["brief"])


class ErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    detail: str


_NOT_FOUND: dict[int | str, dict[str, object]] = {status.HTTP_404_NOT_FOUND: {"model": ErrorDetail}}


def get_settings() -> Settings:
    return Settings.from_env()


def get_extractor() -> Extractor | None:
    """Sin raiz de composicion no hay modelo. La sustituye `orchestration/app.py`."""
    return None


SettingsDep = Annotated[Settings, Depends(get_settings)]
ExtractorDep = Annotated[Extractor | None, Depends(get_extractor)]
InterviewId = Annotated[
    str, Path(pattern=store.ID_PATTERN, description="Identificador de la entrevista")
]


@router.post("/interviews", status_code=status.HTTP_201_CREATED)
def create_interview(settings: SettingsDep) -> interview.InterviewState:
    """RI-38. Una entrevista nueva con su primera pregunta."""
    state = interview.new(store.new_id())
    store.create(settings.runs_dir, state)
    _trace(settings, state.interview_id).emit("interview.created")
    return state


def _trace(settings: Settings, interview_id: str) -> Trace:
    return Trace(settings.interview_trace_path(interview_id))


def _record_turn(
    settings: Settings,
    incoming: interview.TurnIn,
    state: interview.InterviewState,
    extractor: Extractor | None,
) -> None:
    """RF-262. Las llamadas del turno y un resumen sin contenido: la traza observa."""
    traza = _trace(settings, state.interview_id)
    for campos in getattr(extractor, "calls", ()):
        traza.emit("call", **campos)
    traza.emit(
        "interview.turn",
        answered=bool(incoming.answer and incoming.answer.strip()),
        free_text=bool(incoming.free_text and incoming.free_text.strip()),
        edits=len(incoming.edits),
        accepted=len(incoming.accept),
        discarded=len(incoming.discard),
        proposed=len(state.proposed),
        missing=len(state.missing),
        contradictions=len(state.contradictions),
        complete=state.complete,
    )


def _load(settings: Settings, interview_id: str) -> interview.InterviewState:
    state = store.load(settings.runs_dir, interview_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la entrevista {interview_id!r}")
    return state


@router.post("/interviews/{interview_id}/turns", responses=_NOT_FOUND)
def send_turn(
    interview_id: InterviewId,
    incoming: interview.TurnIn,
    settings: SettingsDep,
    extractor: ExtractorDep,
) -> interview.InterviewState:
    """RI-39. Respuesta, texto libre, ediciones y decisiones sobre hechos propuestos."""
    state = interview.turn(_load(settings, interview_id), incoming, extractor)
    store.save_turn(settings.runs_dir, incoming, state)
    _record_turn(settings, incoming, state, extractor)
    return state


@router.get("/interviews/{interview_id}", responses=_NOT_FOUND)
def get_interview(interview_id: InterviewId, settings: SettingsDep) -> interview.InterviewState:
    """RI-40. El mismo estado que RI-39, para reanudar."""
    return _load(settings, interview_id)
