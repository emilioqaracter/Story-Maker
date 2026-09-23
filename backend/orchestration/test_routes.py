"""Las rutas de `orchestration/`. RI-02, RI-03, RI-27, RF-65, RF-66. VER-05."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from canon.brief import Brief, BriefEntity, create_novel
from canon.routes import get_settings as canon_settings
from commons.settings import Settings
from commons.tracing.trace import Trace
from orchestration.app import create_app
from orchestration.routes import REGISTRY, get_runner, get_settings


def _brief() -> Brief:
    return Brief(
        title="Prueba",
        start={"stamp": "2026-01-01"},  # type: ignore[arg-type]
        entities=(BriefEntity(id="marcos", kind="person", name="Marcos"),),
        style_guide="Tercera persona.",
        target_words=1000,
    )


class _Runner:
    """Doble de la tirada: tarda un poco y deja una traza con cierre."""

    def __init__(self) -> None:
        self.started = 0

    def __call__(self, path: Path, novel_id: str, trace: Trace) -> None:
        self.started += 1
        time.sleep(0.3)
        trace.emit("work.close", closed=True, reason="deuda cero", words=1000)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, _Runner, Path]]:
    app = create_app()
    settings = Settings(runs_dir=tmp_path)
    runner = _Runner()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[canon_settings] = lambda: settings
    app.dependency_overrides[get_runner] = lambda: runner
    create_novel(settings.novel_path("prueba-uno"), _brief())
    with TestClient(app) as c:
        yield c, runner, tmp_path


def test_arrancar_es_idempotente(client: tuple[TestClient, _Runner, Path]) -> None:
    """RF-66. Dos arranques seguidos, una sola tirada."""
    c, runner, _tmp = client
    r1 = c.post("/novels/prueba-uno/run")
    r2 = c.post("/novels/prueba-uno/run")
    assert r1.status_code == 202 and r2.status_code == 202
    assert r1.json()["running"] is True
    for _ in range(50):
        if not REGISTRY.running("prueba-uno"):
            break
        time.sleep(0.05)
    assert runner.started == 1


def test_el_estado_refleja_el_cierre_y_la_traza_se_lee(
    client: tuple[TestClient, _Runner, Path],
) -> None:
    """RI-03, RI-27."""
    c, _runner, _tmp = client
    c.post("/novels/prueba-uno/run")
    for _ in range(50):
        if not REGISTRY.running("prueba-uno"):
            break
        time.sleep(0.05)
    estado = c.get("/novels/prueba-uno").json()
    assert estado["running"] is False
    assert estado["closed"] is True
    assert estado["reason"] == "deuda cero"

    traza = c.get("/novels/prueba-uno/trace", params={"kind": "work.close"}).json()
    assert len(traza["records"]) == 1
    assert traza["records"][0]["fields"]["closed"] is True


def test_una_novela_inexistente_da_error_explicito(
    client: tuple[TestClient, _Runner, Path],
) -> None:
    """RI-10."""
    c, _runner, _tmp = client
    assert c.get("/novels/no-existe").status_code == 404
    assert c.post("/novels/no-existe/run").status_code == 404
    assert c.get("/novels/no-existe/trace").status_code == 404
