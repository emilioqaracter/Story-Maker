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


def test_la_traza_dice_donde_se_rompe_la_cadena(
    client: tuple[TestClient, _Runner, Path],
) -> None:
    """RI-65. `chain_broken_at` nulo con la cadena entera y la linea rota si no."""
    c, _runner, tmp = client
    path = Settings(runs_dir=tmp).trace_path("prueba-uno")
    traza = Trace(path)
    for i in range(3):
        traza.emit("call", agent=f"a{i}")

    entera = c.get("/novels/prueba-uno/trace").json()
    assert entera["chain_broken_at"] is None
    assert entera["records"][1]["prev_hash"]

    lineas = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    path.write_text(lineas[0] + "\n" + lineas[2] + "\n", encoding="utf-8")
    rota = c.get("/novels/prueba-uno/trace").json()
    assert rota["chain_broken_at"] == 2
    assert len(rota["records"]) == 2


def test_rf285_el_tiempo_de_redaccion_es_reloj_por_invocacion() -> None:
    """RF-285. Cada invocacion, de su primer registro a su `work.cost`; la en
    curso, hasta ahora; una caida sin `work.cost`, hasta su ultimo registro."""
    from datetime import UTC, datetime

    from commons.tracing.trace import TraceRecord
    from orchestration.routes import writing_ms

    def r(seq: int, at: str, kind: str = "call") -> TraceRecord:
        return TraceRecord(seq=seq, at=f"2026-09-24T{at}+00:00", kind=kind)

    dos = [
        r(0, "10:00:00", "calibration"),
        r(1, "10:05:00"),
        r(2, "10:10:00", "work.cost"),
        r(0, "11:00:00", "calibration"),
        r(1, "11:01:30", "work.cost"),
    ]
    assert writing_ms(dos, running=False) == (600 + 90) * 1000

    en_curso = [*dos, r(0, "12:00:00", "calibration"), r(1, "12:00:10")]
    ahora = datetime(2026, 9, 24, 12, 0, 40, tzinfo=UTC)
    assert writing_ms(en_curso, running=True, now=ahora) == (690 + 40) * 1000
    assert writing_ms(en_curso, running=False) == (690 + 10) * 1000
    assert writing_ms([], running=False) == 0


def test_rf285_el_estado_trae_coste_y_tiempo_de_la_traza(tmp_path: Path) -> None:
    """RF-285. RI-03 suma el coste de las llamadas y el reloj de la invocacion."""
    from orchestration.routes import _state

    settings = Settings(runs_dir=tmp_path)
    create_novel(settings.novel_path("coste"), _brief())
    traza = Trace(settings.trace_path("coste"))
    traza.emit("calibration", model="haiku")
    traza.emit("call", agent="escritor", cost_usd=0.5, duration_ms=1000)
    traza.emit("call", agent="juez", cost_usd=0.25, duration_ms=1000)
    traza.emit("work.cost", invocation="run")

    estado = _state(settings, "coste")
    assert estado.cost_usd == 0.75
    assert estado.writing_ms >= 0
