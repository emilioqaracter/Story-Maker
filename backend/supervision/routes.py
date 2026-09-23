"""RI-28. El cuadro de mando: las trece senales por capitulo congelado.

Solo lectura, como toda ruta de lectura (RF-65): sale un agregado recomputable
desde la traza y el canon, nunca la traza en crudo ni nada que no este
congelado.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Path as PathParam
from pydantic import BaseModel, ConfigDict

from canon.db import connection
from canon.freeze.rows import MetricRow, read_metrics
from commons.settings import NOVEL_ID_PATTERN, InvalidNovelIdError, Settings

router = APIRouter(tags=["supervision"])


class ErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    detail: str


_Responses = dict[int | str, dict[str, object]]
_ERRORS: _Responses = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorDetail},
    status.HTTP_404_NOT_FOUND: {"model": ErrorDetail},
}


def get_settings() -> Settings:
    return Settings.from_env()


SettingsDep = Annotated[Settings, Depends(get_settings)]
NovelId = Annotated[
    str, PathParam(pattern=NOVEL_ID_PATTERN, description="Identificador de la novela")
]


class ChapterHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapter: int
    signals: tuple[MetricRow, ...]
    alarms: int


class Health(BaseModel):
    model_config = ConfigDict(frozen=True)

    novel_id: str
    chapters: tuple[ChapterHealth, ...]


@router.get("/novels/{novel_id}/health", responses=_ERRORS)
def get_health(novel_id: NovelId, settings: SettingsDep) -> Health:
    try:
        path = settings.novel_path(novel_id)
    except InvalidNovelIdError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la novela {novel_id!r}")
    with connection.reader(path) as con:
        filas = read_metrics(con)
    por_capitulo: dict[int, list[MetricRow]] = {}
    for f in filas:
        por_capitulo.setdefault(f.chapter, []).append(f)
    return Health(
        novel_id=novel_id,
        chapters=tuple(
            ChapterHealth(
                chapter=c, signals=tuple(fs), alarms=sum(1 for f in fs if f.state == "alarm")
            )
            for c, fs in sorted(por_capitulo.items())
        ),
    )
