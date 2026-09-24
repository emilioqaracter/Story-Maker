"""Composicion de la aplicacion FastAPI.

`orchestration/` es la raiz de composicion: conoce a todas las funcionalidades y
ninguna lo conoce a el. Es el **unico** sitio donde existe el objeto de
aplicacion, y lo unico que hace con cada funcionalidad es montar su router.

No hay carpeta `api/` transversal a proposito: seria una capa tecnica con otro
nombre, y es justo lo que la organizacion por funcionalidad evita.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from brief.extract import Extractor, model_extractor
from brief.routes import get_extractor
from brief.routes import router as brief_router
from canon.routes import get_settings as canon_settings
from canon.routes import router as canon_router
from commons.tracing.langfuse_export import install_live_export, link_interviews
from orchestration.routes import router as orchestration_router
from planning.routes import router as planning_router
from supervision.routes import router as supervision_router
from verification.routes import router as verification_router


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
    app.include_router(planning_router)
    app.include_router(orchestration_router)
    app.include_router(verification_router)
    app.include_router(supervision_router)
    app.include_router(brief_router)
    # RI-59: `brief/` no conoce el transporte del modelo; se lo da la raiz.
    app.dependency_overrides[get_extractor] = _extractor
    # D-85. El espejo de Langfuse en vivo, si hay claves: toda traza que abran
    # las rutas o las tiradas queda observada. Sin claves no engancha nada y el
    # sistema es el mismo (RI-60).
    install_live_export()
    _link_interviews_on_create(app)
    _mount_frontend(app, FRONTEND_DIST)
    return app


def _link_interviews_on_create(app: FastAPI) -> None:
    """RF-262. Al crear una novela con `origin_interview`, su entrevista pasa a su sesion.

    Se engancha aqui y no en `canon/`, que no sabe nada del espejo: la raiz de
    composicion es la unica que conoce a los dos. Solo actua tras un RI-01 que
    creo la novela, y sin espejo instalado no hace nada.
    """

    @app.middleware("http")
    async def link(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        novel_id = request.query_params.get("novel_id")
        if (
            request.method == "POST"
            and request.url.path == "/novels"
            and response.status_code == status.HTTP_201_CREATED
            and novel_id
        ):
            settings = app.dependency_overrides.get(canon_settings, canon_settings)()
            await run_in_threadpool(link_interviews, novel_id, settings.runs_dir)
        return response


def _extractor() -> Extractor:
    """`brief.extract` sobre el CLI, con el mismo modelo que los agentes (`architecture.md` §4.8)."""
    from commons.provider.claude_cli import ClaudeCli
    from commons.tokens.counter import TokenCounter
    from commons.tokens.factors import DEFAULT_FACTOR, ModelFactors

    modelo = "haiku"
    return model_extractor(
        ClaudeCli(model=modelo),
        TokenCounter(ModelFactors(factors={modelo: DEFAULT_FACTOR})),
        modelo,
    )


#: El sitio estatico que `npm run build` deja en `frontend/dist/`.
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Sirve el frontend bajo `/app/` (`specs/srs-frontend-v1.md` D-67).

    Bajo una base propia y no en la raiz, porque `/novels/{id}` es a la vez
    direccion de la aplicacion y ruta RI-03. Toda direccion que no sea un
    fichero del sitio devuelve `index.html`: el router del navegador la resuelve.
    Sin `dist/` no monta nada, y el backend sigue siendo el sistema completo
    (`architecture.md` 2.1). Queda fuera del esquema: no es contrato.
    """
    index = dist / "index.html"
    if not index.is_file():
        return
    root = dist.resolve()

    @app.get("/app/{rest:path}", include_in_schema=False)
    def frontend(rest: str) -> FileResponse:
        candidate = (dist / rest).resolve()
        if rest and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
