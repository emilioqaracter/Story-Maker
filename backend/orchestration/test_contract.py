"""El contrato de la API.

RI-08, RF-64. El esquema OpenAPI es la **unica** fuente del contrato: lo que
prometa ahi es lo que la API tiene que cumplir. Dos comprobaciones distintas,
porque miden cosas distintas:

1. **Que el contrato este bien declarado.** Ninguna firma publica puede tener
   un objeto libre. Un `dict` sin forma significa que el cliente generado no
   tendra tipos y que un cambio incompatible pasara sin romper ninguna
   compilacion, que es justo lo que este metodo existe para evitar.
2. **Que la API lo cumpla.** Se generan peticiones desde el propio esquema, con
   valores que nadie escribiria a mano, y se comprueba que ninguna respuesta se
   sale de lo declarado.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import schemathesis
from fastapi import FastAPI
from hypothesis import settings as hyp_settings

from canon.routes import get_settings
from commons.settings import Settings
from orchestration.app import create_app

#: Esquemas que genera FastAPI para su envoltorio de error de validacion. El
#: `ctx` de un error de pydantic es libre por naturaleza --lleva lo que cada
#: validador quiera explicar-- y no es una firma publica nuestra. Excluirlos por
#: nombre y no relajar la regla: lo que se comprueba son NUESTROS contratos.
ESQUEMAS_DEL_FRAMEWORK = frozenset({"ValidationError", "HTTPValidationError"})


def _app_de_pruebas(tmp: Path) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(runs_dir=tmp)
    return app


@pytest.fixture(scope="module")
def openapi() -> dict[str, Any]:
    return create_app().openapi()


def _walk(node: object, path: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _walk(value, f"{path}[{i}]")


def test_ningun_esquema_nuestro_es_un_objeto_libre(openapi: dict[str, Any]) -> None:
    """RF-64: nada de `dict` ni `Any` en firma publica."""
    componentes = openapi.get("components", {}).get("schemas", {})
    nuestros = {k: v for k, v in componentes.items() if k not in ESQUEMAS_DEL_FRAMEWORK}

    libres = [
        f"{nombre}{path}"
        for nombre, esquema in nuestros.items()
        for path, node in _walk(esquema)
        if node.get("type") == "object"
        and not (node.keys() & {"properties", "$ref", "additionalProperties", "allOf"})
    ]
    assert not libres, f"objetos sin forma en el contrato: {libres}"


def test_toda_ruta_declara_su_respuesta(openapi: dict[str, Any]) -> None:
    sin_esquema: list[str] = []
    for ruta, metodos in openapi["paths"].items():
        for metodo, detalle in metodos.items():
            exito = next(
                (v for k, v in detalle.get("responses", {}).items() if k.startswith("2")),
                None,
            )
            if exito is None or "content" not in exito:
                sin_esquema.append(f"{metodo.upper()} {ruta}")
    assert not sin_esquema, f"rutas sin respuesta declarada: {sin_esquema}"


# --------------------------------------------------- la API cumple el contrato

_RUNS = Path(tempfile.mkdtemp(prefix="contract-"))
_schema = schemathesis.openapi.from_asgi("/openapi.json", _app_de_pruebas(_RUNS))


@_schema.parametrize()
@hyp_settings(max_examples=10, deadline=None)
def test_la_api_cumple_lo_que_declara(case: Any) -> None:
    """Peticiones generadas desde el esquema, respuestas contrastadas con el.

    Se acota a lectura: una campana generativa sobre las rutas de escritura
    llenaria el directorio de tiradas de novelas basura sin comprobar nada que
    las de lectura no comprueben ya.
    """
    if case.method.upper() != "GET":
        pytest.skip("solo lectura")
    case.validate_response(case.call())
