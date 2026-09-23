"""Rutas de la entrevista. RI-38 a RI-40, RD-32. VER-05."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from brief import store
from brief.extract import RawFact
from brief.routes import get_extractor, get_settings, router
from brief.test_interview import ANSWERS
from canon.brief import Brief
from commons.settings import Settings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_settings] = lambda: Settings(runs_dir=tmp_path)

    def extract(texto: str, _b: str) -> Sequence[RawFact]:
        return [RawFact(target="entity.place", value="La Alameda", quote="el parque de la Alameda")]

    app.dependency_overrides[get_extractor] = lambda: extract
    with TestClient(app) as c:
        yield c


def test_una_entrevista_por_las_rutas_llega_a_un_brief_que_ri01_acepta(
    client: TestClient, tmp_path: Path
) -> None:
    r = client.post("/interviews")
    assert r.status_code == 201
    iid = r.json()["interview_id"]
    estado = r.json()
    while estado["question"] and estado["question"]["field"] in ANSWERS:
        estado = client.post(
            f"/interviews/{iid}/turns", json={"answer": ANSWERS[estado["question"]["field"]]}
        ).json()
    assert estado["complete"] and estado["novel_id"].startswith("el-verano-de-lucia-")
    Brief.model_validate(estado["brief"])

    estado = client.post(
        f"/interviews/{iid}/turns", json={"free_text": "jugaba en el parque de la Alameda"}
    ).json()
    assert [p["value"] for p in estado["proposed"]] == ["La Alameda"]

    # RI-40: reanudar devuelve el mismo estado.
    assert client.get(f"/interviews/{iid}").json() == estado


def test_una_entrevista_que_no_existe_es_404(client: TestClient) -> None:
    assert client.get("/interviews/000000000000").status_code == 404
    assert client.post("/interviews/000000000000/turns", json={}).status_code == 404
    assert client.get("/interviews/no-es-un-id").status_code == 422


def test_los_turnos_se_guardan_y_no_se_reescriben(client: TestClient, tmp_path: Path) -> None:
    """RD-32."""
    iid = client.post("/interviews").json()["interview_id"]
    client.post(f"/interviews/{iid}/turns", json={"answer": "Un título"})
    con = sqlite3.connect(tmp_path / store.FILENAME)
    assert con.execute("SELECT count(*) FROM interview_turn").fetchone()[0] == 1
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM interview_turn")
