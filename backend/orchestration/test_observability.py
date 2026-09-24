"""La puerta de T48: Langfuse completo, con un cliente doble y sin red.

`specs/srs-backend-v4.md` RF-262 a RF-266, RD-46, D-86. Metodo VER-05 y VER-09.
Una novela entera por las rutas y el motor con dobles: su entrevista, su tirada
y una solicitud de cambio. Lo que se comprueba es lo que dice la puerta:

- las tres comparten sesion, la de la novela;
- cada agente sale con su rol, `<rol>.<agente>`;
- cada herramienta es hija de su generation;
- cada verificador de la traza tiene su score, en la traza correcta.

Publicar los prompts dos veces sin cambios esta en `test_prompts_sync.py`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from brief.extract import model_extractor
from brief.interpret import model_interpreter
from brief.routes import get_extractor
from brief.routes import get_settings as brief_settings
from canon.routes import get_settings as canon_settings
from commons.provider.port import Completion, Usage
from commons.settings import Settings
from commons.tokens.counter import TokenCounter
from commons.tokens.factors import DEFAULT_FACTOR, ModelFactors
from commons.tracing import langfuse_export as lf
from commons.tracing.trace import Trace
from context.packing import recipes
from orchestration import engine
from orchestration.app import create_app
from orchestration.compose import run_novel
from orchestration.routes import get_amender, get_interpreter
from orchestration.routes import get_settings as orchestration_settings
from orchestration.test_compose import FAKE_ENV, _brief_largo, _compose

NOVELA = "mi-novela"


class _InterviewerPort:
    """El proveedor de las dos llamadas del entrevistador: una respuesta fija, como el CLI."""

    def __init__(self, text: str) -> None:
        self._text = text

    def complete_once(self, **_kw: object) -> Completion:
        return Completion(
            text=self._text,
            usage=Usage(input_tokens=120, cache_read_tokens=30, output_tokens=40),
            stop_reason="end_turn",
            cost_usd=0.0004,
            model="claude-haiku-4-5",
        )


class LangfuseDouble:
    """El cliente doble: guarda lo enviado y lo aplica como Langfuse, por identificador.

    Un objeto con un identificador ya visto actualiza los campos que trae y deja
    los que no, como la ingestion de Langfuse.
    """

    def __init__(self) -> None:
        self.sent: list[lf.LangfuseObject] = []
        self.store: dict[tuple[str, str], lf.LangfuseObject] = {}

    def send(self, objects: Sequence[lf.LangfuseObject]) -> None:
        for o in objects:
            self.sent.append(o)
            clave = (type(o).__name__, o.id)
            previo = self.store.get(clave)
            cambios = {k: v for k, v in o if v is not None}
            self.store[clave] = previo.model_copy(update=cambios) if previo else o

    def of(self, kind: type) -> list:  # type: ignore[type-arg]
        return [o for o in self.store.values() if isinstance(o, kind)]


def observation(objs: Sequence[lf.LangfuseObservation], name: str) -> lf.LangfuseObservation:
    """La observacion de ese nombre, que tiene que existir."""
    return next(o for o in objs if o.name == name)


def _counter() -> TokenCounter:
    return TokenCounter(ModelFactors(factors={"haiku": DEFAULT_FACTOR}))


_HECHOS = json.dumps(
    {
        "facts": [
            {
                "target": "entity.place",
                "value": "el vestuario",
                "quote": "el vestuario del barrio",
            }
        ]
    }
)
_INTERPRETACION = json.dumps(
    {
        "entity_id": "marcos",
        "attribute": "nombre",
        "new_value": "Mario Vela",
        "ambiguous": False,
        "reason": "",
    }
)


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    lf.uninstall_live_export()
    yield
    lf.uninstall_live_export()


@pytest.fixture
def novela(tmp_path: Path) -> tuple[LangfuseDouble, Trace]:
    """Entrevista, creacion con `origin_interview`, tirada y solicitud de una novela."""
    cliente = LangfuseDouble()
    live = lf.install_live_export(FAKE_ENV, client_factory=lambda: cliente)
    assert live is not None
    settings = Settings(runs_dir=tmp_path)
    app = create_app()
    for dep in (brief_settings, canon_settings, orchestration_settings):
        app.dependency_overrides[dep] = lambda: settings
    app.dependency_overrides[get_extractor] = lambda: model_extractor(
        _InterviewerPort(_HECHOS),  # type: ignore[arg-type]
        _counter(),
        "haiku",
    )
    app.dependency_overrides[get_interpreter] = lambda: model_interpreter(
        _InterviewerPort(_INTERPRETACION),  # type: ignore[arg-type]
        _counter(),
        "haiku",
    )
    app.dependency_overrides[get_amender] = lambda: lambda _p, _n, _t: None

    with TestClient(app) as c:
        iid = c.post("/interviews").json()["interview_id"]
        turno = c.post(
            f"/interviews/{iid}/turns",
            json={"free_text": "Marcos Vela se cambiaba en el vestuario del barrio."},
        )
        assert turno.status_code == 200 and turno.json()["proposed"]
        brief = _brief_largo().model_copy(update={"origin_interview": iid})
        creada = c.post("/novels", params={"novel_id": NOVELA}, json=brief.model_dump(mode="json"))
        assert creada.status_code == 201

        traza = Trace(settings.trace_path(NOVELA))
        run_novel(settings.novel_path(NOVELA), NOVELA, traza, compose=_compose)

        solicitud = c.post(
            f"/novels/{NOVELA}/change-requests",
            json={
                "text": "que se llame Mario Vela",
                "anchor": {"kind": "fact", "entity_id": "marcos", "attribute": "nombre"},
            },
        )
        assert solicitud.status_code == 201 and solicitud.json()["status"] == "queued"
    assert live.drain(10)
    assert not traza.records("export.failed")
    return cliente, traza


def test_entrevista_tirada_y_solicitud_comparten_sesion(
    novela: tuple[LangfuseDouble, Trace],
) -> None:
    """RF-262, D-86: la sesion es la novela, desde la entrevista hasta la solicitud."""
    cliente, _traza = novela
    trazas = cliente.of(lf.LangfuseTrace)
    nombres = {t.name for t in trazas}
    assert {"interview", "run", "change_request"} <= nombres
    assert {t.session_id for t in trazas} == {NOVELA}
    # La entrevista fue primero con su propia sesion, y paso a la de la novela al crearla.
    entrevista = [
        o for o in cliente.sent if isinstance(o, lf.LangfuseTrace) and o.name == "interview"
    ]
    assert entrevista[0].session_id != NOVELA and entrevista[-1].session_id == NOVELA


def test_cada_agente_sale_con_su_rol(novela: tuple[LangfuseDouble, Trace]) -> None:
    """RF-263: `<rol>.<agente>`, con capitulo, escena, intento y el prompt que uso."""
    cliente, _traza = novela
    generaciones = [o for o in cliente.of(lf.LangfuseObservation) if o.type == "generation"]
    roles = set()
    for g in generaciones:
        rol, _, agente = g.name.partition(".")
        assert lf.ROLES[agente] == rol, g.name
        roles.add(rol)
        # RF-266: enlaza su prompt por nombre y etiqueta, la de `prompts_sync`.
        assert (g.prompt_name, g.prompt_label) == (agente, engine.prompt_version(agente))
    assert {"interviewer", "planner", "writer", "editor", "canon"} <= roles

    por_traza = {t.id: t.name for t in cliente.of(lf.LangfuseTrace)}
    trazas_de = {g.name: por_traza[g.trace_id] for g in generaciones}
    assert trazas_de["interviewer.brief.extract"] == "interview"
    assert trazas_de["interviewer.amend.interpret"] == "change_request"
    escritor = observation(generaciones, "writer.escritor")
    assert escritor.parent_observation_id is not None
    assert {"chapter", "scene", "attempt", "prompt_version"} <= set(escritor.metadata)


def test_cada_herramienta_es_hermana_de_su_generation(
    novela: tuple[LangfuseDouble, Trace],
) -> None:
    """RF-264, D-106: una observacion por registro `tool`, junto a la generation que la pidio."""
    cliente, traza = novela
    observaciones = cliente.of(lf.LangfuseObservation)
    herramientas = [o for o in observaciones if o.type in ("tool", "retriever")]
    assert herramientas and len(herramientas) == len(traza.records("tool"))
    generaciones = [o for o in observaciones if o.type == "generation"]
    por_call = {
        lf.call_observation_id(g.trace_id, str(g.metadata["call_id"])): g
        for g in generaciones
        if g.metadata.get("call_id")
    }
    for h in herramientas:
        pidio = por_call[lf.call_observation_id(h.trace_id, str(h.metadata["call"]))]
        assert h.metadata["agent"] == pidio.metadata["agent"]
        assert h.parent_observation_id == pidio.parent_observation_id


def test_cada_verificador_de_la_traza_tiene_su_score(novela: tuple[LangfuseDouble, Trace]) -> None:
    """RF-265: sobre la traza o el span que evaluo, en la traza que le toca."""
    cliente, traza = novela
    scores = cliente.of(lf.LangfuseScore)
    trazas = {t.id for t in cliente.of(lf.LangfuseTrace)}
    spans = {(o.trace_id, o.id) for o in cliente.of(lf.LangfuseObservation) if o.type == "span"}
    verificadores = [r for r in traza.records() if r.kind in lf.SCORERS]
    kinds = {r.kind for r in verificadores}
    assert {"scene.checks", "scene.attempt", "chapter.gate", "outline.check", "work.close"} <= kinds
    for r in verificadores:
        suyos = [
            s
            for s in scores
            if s.metadata.get("record") == r.kind and s.metadata.get("seq") == r.seq
        ]
        assert suyos, f"{r.kind} (seq {r.seq}) sin score"
    for s in scores:
        assert s.trace_id in trazas
        if s.observation_id is not None:
            assert (s.trace_id, s.observation_id) in spans, s.name
    assert {"gate.scene", "gate.chapter", "work.close", "outline.check"} <= {s.name for s in scores}
    assert any(s.name.startswith("check.") for s in scores)


def test_todo_agente_del_motor_tiene_rol() -> None:
    """RF-263: un agente sin rol haria fallar la exportacion; aqui falla antes, la prueba."""
    agentes = {*engine.PROMPT_MODULES, *engine.INTERVIEWER_MODULES, *recipes.BUDGETS}
    sin_rol = sorted(agentes - set(lf.ROLES))
    assert not sin_rol, f"agentes sin rol en architecture.md 11: {sin_rol}"
