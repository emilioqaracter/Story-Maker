"""Rutas HTTP que sirve `planning/`.

RI-07. Una sola: la deuda narrativa vigente. Es de lectura, como todas salvo las
dos que la arquitectura autoriza a escribir, y sirve para observar la salud
estructural de una tirada sin tocarla.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict

from commons.settings import NOVEL_ID_PATTERN, Settings
from planning.ledger.setups import Debt

router = APIRouter(tags=["planning"])


class ErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    detail: str


_Responses = dict[int | str, dict[str, object]]
_NOT_FOUND: _Responses = {status.HTTP_404_NOT_FOUND: {"model": ErrorDetail}}

NovelId = Annotated[str, Path(pattern=NOVEL_ID_PATTERN)]


def get_settings() -> Settings:
    return Settings.from_env()


def get_debt(novel_id: str, settings: Settings) -> Debt:
    """Resuelve la deuda de una novela.

    Sale como dependencia y no dentro de la ruta porque la escaleta congelada
    todavia no tiene almacen propio: cuando lo tenga, cambia esto y no la ruta.
    """
    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        f"la novela {novel_id!r} no tiene escaleta congelada todavia",
    )


@router.get("/novels/{novel_id}/debt", responses={**_NOT_FOUND})
def read_debt(
    novel_id: NovelId,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Debt:
    """RI-07. Setups abiertos y compromisos sin plantar."""
    return get_debt(novel_id, settings)
