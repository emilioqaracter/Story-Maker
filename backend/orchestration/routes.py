"""Rutas HTTP que sirve `orchestration/`.

RI-02, RI-03, RI-27, RF-65, RF-66. El arranque y el estado de la tirada, y la
traza. Desde la version 3, la lista de novelas (RI-37) y las solicitudes de
cambio (RI-47 a RI-49), que aplica el Orquestador. Ninguna aprueba, corrige ni desbloquea: la API observa y arranca.

**El arranque es idempotente** (RF-66): si la tirada ya corre, devuelve su
estado. Y corre dentro del proceso, en un hilo, sin cola ni proceso aparte:
una novela es una unidad aislada y el unico paralelismo real son los tres
jueces.

Lo que sale de aqui es lo que el frontend leera: capitulo y escena en curso,
capitulos congelados, cuarentenas, condicion de cierre. Nada de borradores ni
de veredictos en crudo (RF-65).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Path as PathParam
from pydantic import BaseModel, ConfigDict, Field

from brief.interpret import Interpreter, model_interpreter
from canon import manuscript
from canon.db import connection
from commons.settings import NOVEL_ID_PATTERN, InvalidNovelIdError, Settings
from commons.tracing.trace import Trace, TraceRecord
from orchestration import amend
from orchestration.checkpoint import load

router = APIRouter(tags=["orchestration"])


class ErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    detail: str


_Responses = dict[int | str, dict[str, object]]
_NOT_FOUND: _Responses = {status.HTTP_404_NOT_FOUND: {"model": ErrorDetail}}
_BAD_ID: _Responses = {status.HTTP_400_BAD_REQUEST: {"model": ErrorDetail}}


def get_settings() -> Settings:
    return Settings.from_env()


SettingsDep = Annotated[Settings, Depends(get_settings)]
NovelId = Annotated[
    str, PathParam(pattern=NOVEL_ID_PATTERN, description="Identificador de la novela")
]

#: Lo que arranca una tirada: recibe el fichero, el identificador y la traza, y
#: corre hasta el cierre. La implementacion real compone el motor sobre el CLI;
#: las pruebas inyectan una con dobles. Se resuelve como dependencia para que la
#: sustitucion no sea un parche global.
Runner = Callable[[Path, str, Trace], object]


def get_runner() -> Runner:
    from orchestration.compose import run_novel

    return run_novel


RunnerDep = Annotated[Runner, Depends(get_runner)]


class RunState(BaseModel):
    """RI-03. El estado de la tirada, solo lo que un lector puede ver."""

    model_config = ConfigDict(frozen=True)

    novel_id: str
    running: bool
    chapter_in_progress: int | None = None
    last_closed_scene: int | None = None
    frozen_chapters: int = Field(ge=0)
    closed: bool | None = Field(
        default=None, description="`None` mientras la tirada no ha terminado"
    )
    reason: str = ""
    quarantines: int = Field(ge=0, description="Veces que un capitulo se rehizo entero")
    error: str = ""


class TracePage(BaseModel):
    model_config = ConfigDict(frozen=True)

    novel_id: str
    records: tuple[TraceRecord, ...]


class _Registry:
    """Las tiradas en curso, por novela. Una por novela y en este proceso."""

    def __init__(self) -> None:
        self._threads: dict[str, threading.Thread] = {}
        self._errors: dict[str, str] = {}
        self._lock = threading.Lock()

    def running(self, novel_id: str) -> bool:
        t = self._threads.get(novel_id)
        return t is not None and t.is_alive()

    def error(self, novel_id: str) -> str:
        return self._errors.get(novel_id, "")

    def start(self, novel_id: str, target: Callable[[], object]) -> bool:
        with self._lock:
            if self.running(novel_id):
                return False

            def guarded() -> None:
                try:
                    target()
                except Exception as exc:  # la tirada acaba con motivo, no en silencio
                    self._errors[novel_id] = f"{type(exc).__name__}: {exc}"

            hilo = threading.Thread(target=guarded, name=f"run-{novel_id}", daemon=True)
            self._errors.pop(novel_id, None)
            self._threads[novel_id] = hilo
            hilo.start()
            return True


REGISTRY = _Registry()


def _path(settings: Settings, novel_id: str) -> Path:
    try:
        path = settings.novel_path(novel_id)
    except InvalidNovelIdError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la novela {novel_id!r}")
    return path


def _state(settings: Settings, novel_id: str) -> RunState:
    path = _path(settings, novel_id)
    punto = load(path)
    with connection.reader(path) as con:
        congelados = con.execute("SELECT count(DISTINCT chapter) AS n FROM prose_scene").fetchone()[
            "n"
        ]
    traza = Trace(settings.trace_path(novel_id))
    cierre = traza.records("work.close")
    cuarentenas = sum(1 for r in traza.records("retry") if r.fields.get("level") == "capitulo")
    ultimo = cierre[-1] if cierre else None
    corriendo = REGISTRY.running(novel_id)
    return RunState(
        novel_id=novel_id,
        running=corriendo,
        chapter_in_progress=punto.chapter if punto and corriendo else None,
        last_closed_scene=punto.last_closed_scene if punto and corriendo else None,
        frozen_chapters=int(congelados),
        closed=bool(ultimo.fields.get("closed")) if ultimo and not corriendo else None,
        reason=str(ultimo.fields.get("reason", "")) if ultimo and not corriendo else "",
        quarantines=cuarentenas,
        error=REGISTRY.error(novel_id),
    )


@router.post(
    "/novels/{novel_id}/run",
    status_code=status.HTTP_202_ACCEPTED,
    responses={**_BAD_ID, **_NOT_FOUND},
)
def start_run(novel_id: NovelId, settings: SettingsDep, runner: RunnerDep) -> RunState:
    """RI-02. Arranca la tirada. Idempotente: si ya corre, devuelve el estado."""
    path = _path(settings, novel_id)
    traza = Trace(settings.trace_path(novel_id))
    REGISTRY.start(novel_id, lambda: runner(path, novel_id, traza))
    return _state(settings, novel_id)


@router.get("/novels/{novel_id}", responses={**_BAD_ID, **_NOT_FOUND})
def get_state(novel_id: NovelId, settings: SettingsDep) -> RunState:
    """RI-03. Capitulo y escena en curso, congelados, cuarentenas, cierre."""
    return _state(settings, novel_id)


@router.get("/novels/{novel_id}/trace", responses={**_BAD_ID, **_NOT_FOUND})
def get_trace(
    novel_id: NovelId,
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=5_000)] = 500,
    kind: Annotated[str | None, Query(max_length=40)] = None,
) -> TracePage:
    """RI-27. Los registros de la traza, en orden de escritura."""
    _path(settings, novel_id)
    traza = Trace(settings.trace_path(novel_id))
    registros = traza.records(kind)
    return TracePage(novel_id=novel_id, records=tuple(registros[-limit:]))


# ---------------------------------------------- novelas y enmiendas · v3 §4.4


class NovelEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    novel_id: str
    title: str
    state: RunState
    versions: int = Field(ge=1)


class NovelList(BaseModel):
    model_config = ConfigDict(frozen=True)

    novels: tuple[NovelEntry, ...]


class ChangeRequestIn(BaseModel):
    """RI-47. La peticion y su ancla: un fragmento de la lectura o un hecho de la ficha."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1, max_length=2_000, description="Texto no confiable")
    anchor: Annotated[amend.FragmentAnchor | amend.FactAnchor, Field(discriminator="kind")]


class ChangeRequestList(BaseModel):
    model_config = ConfigDict(frozen=True)

    requests: tuple[manuscript.ChangeRequest, ...]


def get_interpreter() -> Interpreter | None:
    """`amend.interpret` sobre el CLI. Las pruebas lo sustituyen por un doble (RI-59)."""
    from commons.provider.claude_cli import ClaudeCli
    from commons.tokens.counter import TokenCounter
    from commons.tokens.factors import DEFAULT_FACTOR, ModelFactors

    modelo = "haiku"
    return model_interpreter(
        ClaudeCli(model=modelo),
        TokenCounter(ModelFactors(factors={modelo: DEFAULT_FACTOR})),
        modelo,
    )


def get_amender() -> amend.Amender:
    """El que aplica fuera de una tirada: el motor real. Las pruebas lo sustituyen."""
    from orchestration.compose import amend_novel

    return amend_novel


InterpreterDep = Annotated[Interpreter | None, Depends(get_interpreter)]
AmenderDep = Annotated[amend.Amender, Depends(get_amender)]


def _novel_entry(settings: Settings, fichero: Path) -> NovelEntry | None:
    """`None` si el fichero no es una novela: uno ajeno no rompe la lista."""
    from canon.brief import load_brief

    novel_id = fichero.stem
    try:
        settings.novel_path(novel_id)
        titulo = load_brief(fichero).title
        with connection.reader(fichero) as con:
            versiones = manuscript.current_version(con)
    except Exception:  # un fichero ajeno o de otra version del esquema se salta
        return None
    return NovelEntry(
        novel_id=novel_id, title=titulo, state=_state(settings, novel_id), versions=versiones
    )


@router.get("/novels")
def list_novels(settings: SettingsDep) -> NovelList:
    """RI-37. Las novelas del directorio de tiradas, con su estado y sus versiones.

    Vive aqui y no en `canon/` porque el estado de la tirada es del Orquestador.
    """
    carpeta = settings.runs_dir
    ficheros = sorted(carpeta.glob("*.sqlite")) if carpeta.exists() else []
    out = [e for e in (_novel_entry(settings, f) for f in ficheros) if e is not None]
    return NovelList(novels=tuple(out))


@router.post(
    "/novels/{novel_id}/change-requests",
    status_code=status.HTTP_201_CREATED,
    responses={**_BAD_ID, **_NOT_FOUND},
)
def create_change_request(
    novel_id: NovelId,
    incoming: ChangeRequestIn,
    settings: SettingsDep,
    interpreter: InterpreterDep,
    amender: AmenderDep,
) -> manuscript.ChangeRequest:
    """RI-47. Interpreta en la misma llamada (D-82) y deja la solicitud en cola o rechazada.

    Con la tirada en marcha, el bucle la aplica tras el siguiente capitulo
    congelado. Sin tirada, el Orquestador la aplica enseguida en su hilo (D-77).
    """
    path = _path(settings, novel_id)
    traza = Trace(settings.trace_path(novel_id))
    solicitud = amend.create_request(path, incoming.text, incoming.anchor, interpreter, traza)
    if solicitud.status == "queued" and not REGISTRY.running(novel_id):
        REGISTRY.start(novel_id, lambda: amender(path, novel_id, traza))
    return solicitud


@router.get("/novels/{novel_id}/change-requests", responses={**_BAD_ID, **_NOT_FOUND})
def list_change_requests(novel_id: NovelId, settings: SettingsDep) -> ChangeRequestList:
    """RI-48. Todas las solicitudes con su estado."""
    with connection.reader(_path(settings, novel_id)) as con:
        return ChangeRequestList(requests=tuple(manuscript.requests(con)))


@router.get("/novels/{novel_id}/change-requests/{request_id}", responses={**_BAD_ID, **_NOT_FOUND})
def get_change_request(
    novel_id: NovelId, request_id: Annotated[int, PathParam(ge=1)], settings: SettingsDep
) -> manuscript.ChangeRequest:
    """RI-49. Estado, interpretacion y, si se aplico, la version que produjo."""
    with connection.reader(_path(settings, novel_id)) as con:
        solicitud = manuscript.request(con, request_id)
    if solicitud is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la solicitud {request_id}")
    return solicitud
