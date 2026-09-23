"""Rutas HTTP que sirve `verification/`. RI-29, RI-30.

Solo lectura y solo lo congelado (RF-65): el veredicto del Jurado de un
capitulo ya congelado, con su evidencia anclada, y la huella estilistica de
cada capitulo. Nada de borradores ni de veredictos en curso.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Path as PathParam
from pydantic import BaseModel, ConfigDict, Field

from canon.db import connection
from canon.freeze.rows import FingerprintRow, read_fingerprints
from commons.settings import NOVEL_ID_PATTERN, InvalidNovelIdError, Settings

router = APIRouter(tags=["verification"])


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


class ScoreOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    scene_id: str
    instance: str
    seed: int
    score: int
    quote: str
    offset: int


class DimensionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: str
    level: int | None
    dispersion: int
    valid: bool
    scores: tuple[ScoreOut, ...]
    discarded_instances: tuple[str, ...] = Field(
        default=(),
        description="Instancias del Jurado sin puntuacion anclada en esta dimension (RF-129)",
    )


class ChapterVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapter: int
    dimensions: tuple[DimensionOut, ...]


class StyleReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    novel_id: str
    chapters: tuple[FingerprintRow, ...]


def _path(settings: Settings, novel_id: str):  # type: ignore[no-untyped-def]
    try:
        path = settings.novel_path(novel_id)
    except InvalidNovelIdError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la novela {novel_id!r}")
    return path


@router.get("/novels/{novel_id}/chapters/{number}/verdict", responses=_ERRORS)
def get_verdict(novel_id: NovelId, number: int, settings: SettingsDep) -> ChapterVerdict:
    """RI-29. El veredicto del Jurado sobre un capitulo congelado."""
    with connection.reader(_path(settings, novel_id)) as con:
        filas = con.execute(
            "SELECT v.* FROM scene_verdict v JOIN prose_scene s ON s.id = v.scene_id "
            "WHERE s.chapter = ? ORDER BY v.dimension, v.instance",
            (number,),
        ).fetchall()
    if not filas:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"el capitulo {number} no tiene veredicto congelado"
        )
    por_dim: dict[str, list[object]] = {}
    for f in filas:
        por_dim.setdefault(f["dimension"], []).append(f)
    # Las instancias que juzgaron el capitulo son las que dejaron alguna fila;
    # la que falta en una dimension es la que se descarto ahi (RF-129).
    instancias = sorted({f["instance"] for f in filas})
    dims = []
    for dim, fs in sorted(por_dim.items()):
        primera = fs[0]
        presentes = {f["instance"] for f in fs}  # type: ignore[index]
        dims.append(
            DimensionOut(
                dimension=dim,
                level=primera["level"],  # type: ignore[index]
                dispersion=primera["dispersion"],  # type: ignore[index]
                valid=bool(primera["valid"]),  # type: ignore[index]
                scores=tuple(
                    ScoreOut(
                        scene_id=f["scene_id"],  # type: ignore[index]
                        instance=f["instance"],  # type: ignore[index]
                        seed=f["seed"],  # type: ignore[index]
                        score=f["score"],  # type: ignore[index]
                        quote=f["quote"],  # type: ignore[index]
                        offset=f["offset"],  # type: ignore[index]
                    )
                    for f in fs
                ),
                discarded_instances=tuple(i for i in instancias if i not in presentes),
            )
        )
    return ChapterVerdict(chapter=number, dimensions=tuple(dims))


@router.get("/novels/{novel_id}/style", responses=_ERRORS)
def get_style(novel_id: NovelId, settings: SettingsDep) -> StyleReport:
    """RI-30. Huella de referencia y la de cada capitulo, con su desviacion."""
    with connection.reader(_path(settings, novel_id)) as con:
        filas = read_fingerprints(con)
    return StyleReport(novel_id=novel_id, chapters=tuple(filas))
