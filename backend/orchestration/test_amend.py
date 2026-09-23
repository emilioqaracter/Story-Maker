"""Solicitudes de cambio, de la peticion a la version nueva. RF-221 a RF-227. VER-05, VER-17."""

from __future__ import annotations

import time
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from brief.interpret import Candidate, RawInterpretation
from canon import manuscript
from canon.arbiter.refreeze import RefrozenScene
from canon.arbiter.retcon import RetconPlan
from canon.brief import create_novel
from canon.db import connection
from canon.test_manuscript import _brief, _congelar, _escena
from commons.settings import Settings
from commons.tracing.trace import Trace
from commons.types.primitives import Defect, Evidence, Severity
from orchestration import amend
from orchestration.amend import FactAnchor, FragmentAnchor
from orchestration.test_loop import _engine


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "rex-uno.sqlite"
    create_novel(path, _brief())
    _congelar(
        path,
        1,
        [
            _escena(1, 1, "Lucía llegó al parque con Rex.", ("lucia", "rex")),
            _escena(1, 2, "Lucía miró las nubes sola.", ("lucia",)),
        ],
    )
    _congelar(path, 2, [_escena(2, 1, "Rex ladró al ver la pelota.", ("lucia",))])
    return path


def _nala(texto: str, _ancla: str, candidatas: Sequence[Candidate]) -> RawInterpretation:
    assert "IGNORA" not in _ancla  # la peticion no viaja en el ancla
    return RawInterpretation(entity_id="rex", attribute="nombre", new_value="Nala")


def _pedir(path: Path, interpreter=_nala, anchor=None) -> manuscript.ChangeRequest:  # type: ignore[no-untyped-def]
    ancla = anchor or FragmentAnchor(version=1, chapter=1, scene_id="c1e1", quote="con Rex")
    return amend.create_request(
        path, "el perro se llama Nala", ancla, interpreter, Trace.disabled()
    )


def test_una_peticion_interpretable_queda_en_cola_con_su_interpretacion(novela: Path) -> None:
    """RF-221, RF-222, D-82."""
    s = _pedir(novela)
    assert s.status == "queued"
    assert s.interpretation is not None
    assert (s.interpretation.previous_value, s.interpretation.new_value) == ("Rex", "Nala")


def test_lo_que_no_ancla_o_no_se_entiende_se_rechaza_en_la_misma_llamada(novela: Path) -> None:
    """RF-222, RI-52 del frontend: el sistema nunca elige por quien pide."""
    fuera = _pedir(
        novela, anchor=FragmentAnchor(version=1, chapter=1, scene_id="c1e1", quote="con Toby")
    )
    assert fuera.status == "rejected" and "no aparece tal cual" in fuera.reason

    ambigua = _pedir(
        novela, interpreter=lambda *_: RawInterpretation(ambiguous=True, reason="hay dos")
    )
    assert ambigua.status == "rejected" and "ambigua" in ambigua.reason

    def roto(*_a: object) -> RawInterpretation:
        raise RuntimeError("el CLI no respondio")

    caido = _pedir(novela, interpreter=roto)
    assert caido.status == "rejected" and "no respondió" in caido.reason

    hecho = _pedir(novela, anchor=FactAnchor(entity_id="nadie", attribute="nombre"))
    assert hecho.status == "rejected"


def test_aplicar_un_cambio_de_nombre_crea_la_version_2_y_conserva_la_1(novela: Path) -> None:
    """RF-223, RF-224, RF-210. El perro se llama Nala en toda escena que lo nombra."""
    _pedir(novela)
    antes = _textos(novela, 1)
    assert amend.apply_pending(novela, _engine(), Trace.disabled()) == [2]
    assert _textos(novela, 1) == antes
    assert _textos(novela, 2) == [
        "Lucía llegó al parque con Nala.",
        "Lucía miró las nubes sola.",
        "Nala ladró al ver la pelota.",
    ]
    with connection.reader(novela) as con:
        s = manuscript.request(con, 1)
        nombre = con.execute("SELECT name FROM entity WHERE id = 'rex'").fetchone()[0]
    assert (
        s is not None and s.status == "applied" and s.version == 2 and s.changed_chapters == (1, 2)
    )
    assert nombre == "Nala"


def test_un_s1_que_no_es_la_enmienda_la_rechaza_sin_tocar_nada(novela: Path) -> None:
    """RF-225, RNF-50: invariante duro gana, y no queda version a medias."""
    _pedir(novela)

    def reescribe_mal(sid: str, texto: str, plan: object) -> tuple[RefrozenScene, list[Defect]]:
        d = Defect(
            kind="check.timeline",
            severity=Severity.S1,
            evidence=Evidence(quote="aquel martes", offset=0),
            rule="fecha fuera del calendario",
        )
        return RefrozenScene(scene_id=sid, text=texto.replace("Rex", "Nala"), summary="r"), [d]

    assert (
        amend.apply_pending(novela, _engine(retcon_rewrite=reescribe_mal), Trace.disabled()) == []
    )
    with connection.reader(novela) as con:
        s = manuscript.request(con, 1)
        assert manuscript.current_version(con) == 1
    assert s is not None and s.status == "rejected" and "fecha fuera del calendario" in s.reason
    assert _textos(novela, 1)[0] == "Lucía llegó al parque con Rex."


def test_un_defecto_que_cita_el_valor_nuevo_es_la_enmienda_misma(novela: Path) -> None:
    """D-78. `check.lexicon` ve «Nala» como nombre desconocido: no cuenta."""
    _pedir(novela)

    def con_lexico(sid: str, texto: str, plan: object) -> tuple[RefrozenScene, list[Defect]]:
        d = Defect(
            kind="check.lexicon",
            severity=Severity.S1,
            evidence=Evidence(quote="Nala", offset=0),
            rule="nombre desconocido",
        )
        return RefrozenScene(scene_id=sid, text=texto.replace("Rex", "Nala"), summary="r"), [d]

    assert amend.apply_pending(novela, _engine(retcon_rewrite=con_lexico), Trace.disabled()) == [2]


def test_si_el_reparador_deja_el_valor_anterior_se_rechaza(novela: Path) -> None:
    _pedir(novela)

    def no_cambia(sid: str, texto: str, plan: object) -> tuple[RefrozenScene, list[Defect]]:
        return RefrozenScene(scene_id=sid, text=texto, summary="r"), []

    amend.apply_pending(novela, _engine(retcon_rewrite=no_cambia), Trace.disabled())
    with connection.reader(novela) as con:
        s = manuscript.request(con, 1)
    assert s is not None and s.status == "rejected" and "Rex" in s.reason


class _Espia:
    """Un Reparador de reemplazo literal que anota que escenas le piden reescribir."""

    def __init__(self) -> None:
        self.escenas: list[str] = []

    def __call__(
        self, sid: str, texto: str, plan: RetconPlan
    ) -> tuple[RefrozenScene, list[Defect]]:
        self.escenas.append(sid)
        nuevo = texto.replace(plan.previous_value, plan.new_value)
        return RefrozenScene(scene_id=sid, text=nuevo, summary=f"resumen retcon {sid}"), []


def test_un_cambio_de_atributo_solo_toca_escenas_donde_esta_la_entidad(tmp_path: Path) -> None:
    """RF-224. «negro» sin Rex en el elenco no se toca."""
    path = tmp_path / "rex-color.sqlite"
    create_novel(path, _brief())
    _congelar(path, 1, [_escena(1, 1, "Rex, negro como el carbón, corrió.", ("lucia", "rex"))])
    # «negro» esta, pero Rex no es POV, lugar ni elenco: el valor no habla de el.
    _congelar(path, 2, [_escena(2, 1, "Lucía miró el cielo negro sin luna.", ("lucia",))])
    antes = _textos(path, 1)
    s = amend.create_request(
        path,
        "Rex es blanco",
        FactAnchor(entity_id="rex", attribute="color"),
        lambda *_: RawInterpretation(entity_id="rex", attribute="color", new_value="blanco"),
        Trace.disabled(),
    )
    assert s.status == "queued"
    espia = _Espia()
    assert amend.apply_pending(path, _engine(retcon_rewrite=espia), Trace.disabled()) == [2]
    assert espia.escenas == ["c1e1"]
    assert _textos(path, 2) == ["Rex, blanco como el carbón, corrió.", antes[1]]
    with connection.reader(path) as con:
        solicitud = manuscript.request(con, 1)
        color = con.execute(
            "SELECT value FROM attribute WHERE entity_id = 'rex' AND name = 'color' AND valid_to IS NULL"
        ).fetchone()[0]
        prov = con.execute(
            "SELECT e.provenance FROM attribute a JOIN event e ON e.id = a.source_event "
            "WHERE a.entity_id = 'rex' AND a.name = 'color' AND a.valid_to IS NULL"
        ).fetchone()[0]
        cap2 = manuscript.chapter_at(con, 2, 2) or []
    assert solicitud is not None and solicitud.changed_chapters == (1,)
    assert cap2 and not any(e.changed for e in cap2)
    assert color == "blanco" and prov == "brief"


def test_un_cambio_de_nombre_solo_marca_los_capitulos_que_lo_nombran(tmp_path: Path) -> None:
    """RF-224, D-48. El impacto de la enmienda son las escenas que nombran el hecho, ni una mas.

    Tres capitulos, «Rex» en el 1 y el 3. El 2 no se reescribe, no se marca y
    se lee igual en las dos versiones.
    """
    path = tmp_path / "rex-tres.sqlite"
    create_novel(path, _brief())
    _congelar(
        path,
        1,
        [
            _escena(1, 1, "Lucía llegó al parque con Rex.", ("lucia", "rex")),
            _escena(1, 2, "Lucía miró las nubes sola.", ("lucia",)),
        ],
    )
    _congelar(path, 2, [_escena(2, 1, "Lucía corrió sola hasta la fuente.", ("lucia",))])
    _congelar(path, 3, [_escena(3, 1, "Rex volvió a casa con Lucía.", ("lucia", "rex"))])
    _pedir(path)
    espia = _Espia()

    assert amend.apply_pending(path, _engine(retcon_rewrite=espia), Trace.disabled()) == [2]

    assert espia.escenas == ["c1e1", "c3e1"]
    with connection.reader(path) as con:
        solicitud = manuscript.request(con, 1)
        version = manuscript.versions(con)[-1]
        cap1 = manuscript.chapter_at(con, 1, 2) or []
        cap2_v1 = manuscript.chapter_at(con, 2, 1) or []
        cap2_v2 = manuscript.chapter_at(con, 2, 2) or []
    assert solicitud is not None and solicitud.status == "applied"
    assert solicitud.changed_chapters == (1, 3)
    assert (version.number, version.changed_chapters) == (2, (1, 3))
    assert [e.changed for e in cap1] == [True, False]
    assert cap2_v2 and not any(e.changed for e in cap2_v2)
    assert [e.text for e in cap2_v2] == [e.text for e in cap2_v1]


def _textos(path: Path, version: int) -> list[str]:
    with connection.reader(path) as con:
        return [
            s.text
            for c in manuscript.chapters_in(con, version)
            for s in manuscript.chapter_at(con, c, version) or []
        ]


# -------------------------------------------------------------------- rutas


@pytest.fixture
def client(novela: Path) -> Iterator[TestClient]:
    from brief.routes import get_extractor
    from brief.routes import get_settings as brief_settings
    from canon.routes import get_settings as canon_settings
    from orchestration.app import create_app
    from orchestration.routes import get_amender, get_interpreter
    from orchestration.routes import get_settings as orch_settings

    app = create_app()
    for dep in (canon_settings, orch_settings, brief_settings):
        app.dependency_overrides[dep] = lambda: Settings(runs_dir=novela.parent)
    app.dependency_overrides[get_extractor] = lambda: None
    app.dependency_overrides[get_interpreter] = lambda: _nala
    app.dependency_overrides[get_amender] = lambda: (
        lambda p, _n, t: amend.drain(p, lambda: amend.apply_pending(p, _engine(), t))
    )
    with TestClient(app) as c:
        yield c


def test_por_las_rutas_una_solicitud_se_aplica_sola_y_produce_la_version_2(
    client: TestClient,
) -> None:
    """RI-47 a RI-49, RI-37, RF-223: sin tirada, el Orquestador la aplica en su hilo."""
    from orchestration.routes import REGISTRY

    r = client.post(
        "/novels/rex-uno/change-requests",
        json={
            "text": "el perro se llama Nala",
            "anchor": {
                "kind": "fragment",
                "version": 1,
                "chapter": 1,
                "scene_id": "c1e1",
                "quote": "con Rex",
            },
        },
    )
    assert r.status_code == 201 and r.json()["status"] == "queued"
    rid = r.json()["request_id"]
    for _ in range(200):
        if not REGISTRY.running("rex-uno"):
            break
        time.sleep(0.02)
    s = client.get(f"/novels/rex-uno/change-requests/{rid}").json()
    assert s["status"] == "applied" and s["version"] == 2 and s["changed_chapters"] == [1, 2]
    assert [
        x["request_id"] for x in client.get("/novels/rex-uno/change-requests").json()["requests"]
    ] == [rid]
    novelas = client.get("/novels").json()["novels"]
    assert [(n["novel_id"], n["title"], n["versions"]) for n in novelas] == [
        ("rex-uno", "El verano de Rex", 2)
    ]


def test_rutas_de_solicitudes_con_identificadores_que_no_existen(client: TestClient) -> None:
    assert client.get("/novels/rex-uno/change-requests/99").status_code == 404
    assert (
        client.post(
            "/novels/no-existe/change-requests",
            json={
                "text": "x",
                "anchor": {"kind": "fact", "entity_id": "rex", "attribute": "nombre"},
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/novels/rex-uno/change-requests",
            json={
                "text": "",
                "anchor": {"kind": "fact", "entity_id": "rex", "attribute": "nombre"},
            },
        ).status_code
        == 422
    )


def test_el_bucle_llama_a_las_enmiendas_tras_cada_congelacion(tmp_path: Path) -> None:
    """RF-223: con tirada en marcha, entre congelaciones y al cerrar."""
    from orchestration.loop import run
    from orchestration.test_loop import _brief as brief_loop
    from orchestration.test_loop import _specs

    path = tmp_path / "n.sqlite"
    create_novel(path, brief_loop())
    llamadas: list[int] = []
    run(
        path,
        brief_loop(),
        _engine(),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        after_freeze=lambda: llamadas.append(1),
    )
    assert len(llamadas) == 3


def test_las_formas_de_un_nombre_son_el_completo_y_sus_palabras_que_se_van() -> None:
    """D-83."""
    from canon.manuscript import Interpretation

    def formas(prev: str, new: str, attr: str = "nombre") -> list[str]:
        return amend.old_forms(
            Interpretation(entity_id="x", attribute=attr, previous_value=prev, new_value=new)
        )

    assert formas("Marcos Vela", "Mateo") == ["Marcos Vela", "Marcos", "Vela"]
    assert formas("Marcos Vela", "Marcos Ruiz") == ["Marcos Vela", "Vela"]
    assert formas("Rex", "Nala") == ["Rex"]
    assert formas("negro", "blanco", "color") == ["negro"]


def test_un_cambio_de_nombre_encuentra_las_escenas_que_usan_solo_el_nombre_de_pila(
    tmp_path: Path,
) -> None:
    """D-83: el canon dice «Aurelio Pena» y la prosa, «Aurelio»."""
    from canon.brief import Brief, BriefEntity
    from commons.types.primitives import WorldTime

    path = tmp_path / "t.sqlite"
    create_novel(
        path,
        Brief(
            title="t",
            start=WorldTime(stamp="2026-08-01"),
            entities=(
                BriefEntity(id="lucia", kind="person", name="Lucía"),
                BriefEntity(id="tecnico", kind="person", name="Aurelio Pena"),
                BriefEntity(id="parque", kind="place", name="el parque"),
            ),
            style_guide="x",
            target_words=1000,
        ),
    )
    _congelar(
        path, 1, [_escena(1, 1, "Aurelio silbó y Lucía echó a correr.", ("lucia", "tecnico"))]
    )
    amend.create_request(
        path,
        "el entrenador se llama Tomás",
        FactAnchor(entity_id="tecnico", attribute="nombre"),
        lambda *_: RawInterpretation(entity_id="tecnico", attribute="nombre", new_value="Tomás"),
        Trace.disabled(),
    )

    def reparador(sid: str, texto: str, plan: object) -> tuple[RefrozenScene, list[Defect]]:
        return RefrozenScene(scene_id=sid, text=texto.replace("Aurelio", "Tomás"), summary="r"), []

    assert amend.apply_pending(path, _engine(retcon_rewrite=reparador), Trace.disabled()) == [2]
    assert _textos(path, 2) == ["Tomás silbó y Lucía echó a correr."]


def test_si_el_motor_no_se_compone_lo_pendiente_se_rechaza_con_motivo(novela: Path) -> None:
    """RF-226. Medido con el modelo real: un fichero sin brief guardado no compone el motor."""
    _pedir(novela)
    amend.reject_queued(
        novela, "No se pudo preparar el sistema para aplicarla: sin brief", Trace.disabled()
    )
    with connection.reader(novela) as con:
        s = manuscript.request(con, 1)
    assert s is not None and s.status == "rejected" and "sin brief" in s.reason


def test_un_defecto_que_ya_estaba_antes_de_reescribir_no_cuenta(novela: Path) -> None:
    """D-84. Medido con el modelo real: un nombre que la version 1 ya tenia no tumba la enmienda."""
    _pedir(novela)

    def previo(sid: str, texto: str, plan: object) -> tuple[RefrozenScene, list[Defect]]:
        # «parque» ya estaba en c1e1 antes de reescribirla: el defecto es previo.
        d = Defect(
            kind="check.lexicon",
            severity=Severity.S1,
            evidence=Evidence(quote="parque", offset=0),
            rule="'parque' no es una entidad del canon",
        )
        nuevo = RefrozenScene(scene_id=sid, text=texto.replace("Rex", "Nala"), summary="r")
        return nuevo, [d] if sid == "c1e1" else []

    assert amend.apply_pending(novela, _engine(retcon_rewrite=previo), Trace.disabled()) == [2]


def test_que_defectos_cuentan_contra_la_enmienda() -> None:
    assert not amend.counts("con Nala", "Nala", "antes")
    assert not amend.counts("Alcorcón", "Mateo", "vivía en Alcorcón")
    assert amend.counts("Alcorcón", "Mateo", "vivía en Madrid")
