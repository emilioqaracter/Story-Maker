"""Rutas de versiones y fichas. RI-42 a RI-46, RI-57, RI-58. `specs/srs-backend-v3.md` §4.2. VER-05."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from canon.brief import create_novel
from canon.routes import get_settings, router
from canon.test_manuscript import _brief, _congelar, _escena, _rename
from commons.settings import Settings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    path = tmp_path / "rex-uno.sqlite"
    create_novel(path, _brief())
    _congelar(path, 1, [_escena(1, 1, "Lucía llegó al parque con Rex.", ("lucia", "rex"))])
    _congelar(path, 2, [_escena(2, 1, "Lucía volvió sola a casa.", ("lucia",))])
    _rename(path, "el perro se llama Nala", "Rex", "Nala")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: Settings(runs_dir=tmp_path)
    with TestClient(app) as c:
        yield c


def test_versiones_manifiesto_y_capitulo_por_version(client: TestClient) -> None:
    versiones = client.get("/novels/rex-uno/versions").json()["versions"]
    assert [(v["number"], v["current"]) for v in versiones] == [(1, False), (2, True)]

    m = client.get("/novels/rex-uno/versions/2").json()
    assert m["title"] == "El verano de Rex" and m["dedication"] == "Para Lucía"
    assert [(c["number"], c["changed"]) for c in m["chapters"]] == [(1, True), (2, False)]

    v1 = client.get("/novels/rex-uno/versions/1/chapters/1").json()["scenes"]
    v2 = client.get("/novels/rex-uno/versions/2/chapters/1").json()["scenes"]
    assert v1[0]["text"].endswith("con Rex.") and not v1[0]["changed"]
    assert v2[0]["text"].endswith("con Nala.") and v2[0]["changed"]
    assert v2[0]["scene_id"] == "c1e1"


def test_una_version_o_capitulo_que_no_existe_es_404(client: TestClient) -> None:
    assert client.get("/novels/rex-uno/versions/3").status_code == 404
    assert client.get("/novels/rex-uno/versions/3/chapters/1").status_code == 404
    assert client.get("/novels/rex-uno/versions/1/chapters/9").status_code == 404
    assert client.get("/novels/no-existe/versions").status_code == 404


def test_entidades_y_ficha(client: TestClient) -> None:
    todas = client.get("/novels/rex-uno/entities").json()["entities"]
    assert {e["entity_id"]: e["name"] for e in todas}["rex"] == "Nala"
    lugares = client.get("/novels/rex-uno/entities", params={"type": "place"}).json()["entities"]
    assert [e["entity_id"] for e in lugares] == ["parque"]
    assert client.get("/novels/rex-uno/entities", params={"type": "otro"}).status_code == 422

    ficha = client.get("/novels/rex-uno/entities/lucia").json()
    assert ficha["entity"]["chapters"] == [1, 2]
    assert ficha["facts"] == [
        {"attribute": "edad", "value": "10", "provenance": "brief", "valid_from": "2026-08-01"}
    ]
    assert client.get("/novels/rex-uno/entities/nadie").status_code == 404


def test_el_estado_lleva_relaciones_y_los_capitulos_su_instante(client: TestClient) -> None:
    """RI-57, RI-58."""
    caps = client.get("/novels/rex-uno/chapters").json()["chapters"]
    assert [(c["chapter"], c["scenes"], c["ends_at"]) for c in caps] == [
        (1, 1, "2026-08-11"),
        (2, 1, "2026-08-21"),
    ]
    estado = client.get("/novels/rex-uno/state", params={"at": "2026-08-21"}).json()
    assert "relations" in estado
