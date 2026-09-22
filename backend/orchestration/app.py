"""Composicion de la aplicacion FastAPI.

`orchestration/` es la raiz de composicion: conoce a todas las funcionalidades y
ninguna lo conoce a el. Es el **unico** sitio donde existe el objeto de
aplicacion, y lo unico que hace con cada funcionalidad es montar su router.

No hay carpeta `api/` transversal a proposito: seria una capa tecnica con otro
nombre, y es justo lo que la organizacion por funcionalidad evita.
"""

from __future__ import annotations

from fastapi import FastAPI

from canon.routes import router as canon_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Story Maker",
        version="0.1.0",
        description=(
            "Sistema autonomo de generacion de novelas largas. "
            "La API observa y arranca; no aprueba, no corrige y no desbloquea."
        ),
    )
    app.include_router(canon_router)
    return app


app = create_app()
