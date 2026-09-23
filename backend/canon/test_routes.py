"""Las rutas del canon.

RI-01, RI-04 a RI-06, RI-09, RI-10, RF-65. Lo que se comprueba no es solo que
respondan: es que **no dejan salir nada que no este congelado** y que un
identificador inexistente da error explicito y no una coleccion vacia.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from canon.brief import Brief, BriefEntity
from canon.routes import get_settings, router
from commons.settings import Settings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    # Se monta solo el router de `canon/`, sin pasar por la composicion de
    # `orchestration/`: una funcionalidad no importa de la raiz de composicion,
    # y sus pruebas tampoco. La app entera se prueba desde alli.
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: Settings(runs_dir=tmp_path)
    with TestClient(app) as c:
        yield c


def _brief_payload() -> dict[str, object]:
    return Brief(
        title="Prueba",
        start={"stamp": "2026-01-01"},  # type: ignore[arg-type]
        entities=(
            BriefEntity(
                id="marcos", kind="person", name="Marcos", attributes=(("estado", "sano"),)
            ),
        ),
        style_guide="Tercera persona.",
        target_words=1000,
    ).model_dump(mode="json")


def test_crear_una_novela_carga_el_brief(client: TestClient) -> None:
    r = client.post("/novels?novel_id=prueba-uno", json=_brief_payload())
    assert r.status_code == 201
    assert r.json()["events_loaded"] > 0


def test_no_se_crea_dos_veces_la_misma(client: TestClient) -> None:
    client.post("/novels?novel_id=prueba-uno", json=_brief_payload())
    r = client.post("/novels?novel_id=prueba-uno", json=_brief_payload())
    assert r.status_code == 409


def test_identificador_peligroso_se_rechaza(client: TestClient) -> None:
    """Un identificador acaba siendo un nombre de fichero: nada que `..` pueda
    aprovechar para salirse del directorio de tiradas.

    Lo rechaza el contrato antes de entrar a la funcion --de ahi el 422-- y la
    validacion de `Settings` sigue detras como segunda linea, por si alguna via
    futura no pasa por aqui.
    """
    r = client.post("/novels?novel_id=../../etc/passwd", json=_brief_payload())
    assert r.status_code == 422


def test_novela_inexistente_da_error_y_no_lista_vacia(client: TestClient) -> None:
    """RI-10. Confundir 'no existe' con 'no tiene nada' hace que un fallo de
    configuracion pase por un estado legitimo."""
    r = client.get("/novels/no-existe/chapters")
    assert r.status_code == 404


def test_sin_capitulos_congelados_la_lista_esta_vacia(client: TestClient) -> None:
    client.post("/novels?novel_id=prueba-uno", json=_brief_payload())
    r = client.get("/novels/prueba-uno/chapters")
    assert r.status_code == 200
    assert r.json()["chapters"] == []


def test_un_capitulo_no_congelado_no_se_sirve(client: TestClient) -> None:
    """RF-65. Nada que todavia pueda desaparecer sale por la API."""
    client.post("/novels?novel_id=prueba-uno", json=_brief_payload())
    assert client.get("/novels/prueba-uno/chapters/1").status_code == 404


def test_el_estado_del_mundo_necesita_instante(client: TestClient) -> None:
    client.post("/novels?novel_id=prueba-uno", json=_brief_payload())
    assert client.get("/novels/prueba-uno/state").status_code == 422

    r = client.get("/novels/prueba-uno/state?at=2026-06-01")
    assert r.status_code == 200
    assert r.json()["cards"][0]["entity_id"] == "marcos"


def test_instante_mal_formado_se_rechaza(client: TestClient) -> None:
    """El formato esta en el contrato, asi que el rechazo ocurre en el borde."""
    r = client.get("/novels/prueba-uno/state?at=el-martes")
    assert r.status_code == 422
