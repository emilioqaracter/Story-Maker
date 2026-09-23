"""RI-29, RI-30. VER-05."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from canon.brief import Brief, BriefEntity, create_novel
from commons.settings import Settings
from verification.routes import get_settings, router


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(router)
    settings = Settings(runs_dir=tmp_path)
    app.dependency_overrides[get_settings] = lambda: settings
    create_novel(
        settings.novel_path("prueba-uno"),
        Brief(
            title="p",
            start={"stamp": "2026-01-01"},  # type: ignore[arg-type]
            entities=(BriefEntity(id="m", kind="person", name="M"),),
            style_guide="x",
            target_words=1000,
        ),
    )
    with TestClient(app) as c:
        yield c


def test_un_capitulo_sin_veredicto_da_error_explicito(client: TestClient) -> None:
    """RI-10: nunca una coleccion vacia que parezca un veredicto."""
    assert client.get("/novels/prueba-uno/chapters/1/verdict").status_code == 404
    assert client.get("/novels/no-existe/chapters/1/verdict").status_code == 404


def test_la_huella_de_una_novela_sin_capitulos_es_una_lista_vacia(client: TestClient) -> None:
    r = client.get("/novels/prueba-uno/style")
    assert r.status_code == 200
    assert r.json()["chapters"] == []
