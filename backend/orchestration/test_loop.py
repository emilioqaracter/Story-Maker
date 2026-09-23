"""El bucle completo, de punta a punta.

RF-13, RF-22, RF-23, RF-107, RNF-01 a RNF-03. Metodo VER-18.

Corre con **motores deterministas**: un doble escribe la prosa, otro la
verifica, otro la resume. Eso no es un atajo, es lo que permite comprobar el
ORDEN --que es lo que este modulo aporta-- sin que el resultado dependa de lo
que un modelo decida devolver ese dia.

Las llamadas a modelo real son evals, no pruebas (RNF-17).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from canon.arbiter.refreeze import RefrozenScene
from canon.arbiter.retcon import RetconProposal
from canon.archivist.extract import DeltaProposal, EmptyDeltaError, ProposedEvent
from canon.brief import Brief, BriefEntity, create_novel
from canon.db import connection
from canon.events.types import AttributeSet
from canon.skills import read
from commons.provider.port import Embedding
from commons.settings import Settings
from commons.tracing.trace import Trace
from commons.types.primitives import Defect, Evidence, Severity, WorldTime
from commons.types.scene import SceneFunction, SceneSpec
from generation.sports.simulate import MatchResult, Milestone, MilestoneKind
from orchestration.checkpoint import load
from orchestration.loop import Engine, RunAbortedError, as_json, run
from orchestration.routes import _state
from planning.outline.types import ActPlan, Arc, ArcKind, Outline, SceneEntry, Setup
from planning.scene_spec.spec import from_entry
from supervision.prompts import HealthVerdict
from verification.checks import forbidden
from verification.continuity.review import Anchored
from verification.jury.verdict import JuryVerdict
from verification.quiz.build import Question
from verification.style.fingerprint import Fingerprint

START = WorldTime(stamp="2026-08-01")


# ------------------------------------------------------------------- fixtures


def _brief() -> Brief:
    return Brief(
        title="Prueba corta",
        start=START,
        entities=(
            BriefEntity(
                id="marcos", kind="person", name="Marcos", attributes=(("estado", "sano"),)
            ),
            BriefEntity(id="tecnico", kind="person", name="Aurelio"),
        ),
        style_guide="Tercera persona, pasado.",
        target_words=3_600,
        word_tolerance=0.5,
    )


def _escena(cap: int, pos: int, act: int, func: SceneFunction, dia: int) -> SceneEntry:
    return SceneEntry(
        id=f"c{cap}e{pos}",
        chapter=cap,
        ordinal=pos,
        act=act,
        function=func,
        pov="marcos",
        value_change="de la duda a la decision",
        world_time=WorldTime(stamp=f"2026-08-{dia:02d}", seq=0),
        target_words=900,
    )


def _outline() -> Outline:
    """Dos capitulos, dos actos, doble arco resuelto en escenas distintas."""
    escenas = (
        _escena(1, 1, 1, SceneFunction.ESTABLISH, 10),
        _escena(1, 2, 1, SceneFunction.COMPLICATE, 11),
        _escena(2, 1, 2, SceneFunction.CULMINATE, 20),
        _escena(2, 2, 2, SceneFunction.ASSIMILATE, 21),
    )
    return Outline(
        arcs=(
            Arc(
                id="comp",
                kind=ArcKind.COMPETITIVE,
                subject="marcos",
                start_scene="c1e1",
                crisis_scene="c1e2",
                resolution_scene="c2e1",
            ),
            Arc(
                id="int",
                kind=ArcKind.INTERNAL,
                subject="marcos",
                start_scene="c1e1",
                crisis_scene="c1e2",
                resolution_scene="c2e2",
            ),
        ),
        acts=(ActPlan(number=1, tension=(3,)), ActPlan(number=2, tension=(8,))),
        scenes=escenas,
        setups=(
            Setup(id="la-lista", planted_scene="c1e1", payoff_scene="c2e1", description="La lista"),
        ),
    )


def _specs(outline: Outline, numero: int) -> Sequence[SceneSpec]:
    return [
        from_entry(
            e,
            place="vestuario",
            cast=("marcos", "tecnico"),
            beats=("entra", "descubre"),
            objective="saber",
            obstacle="nadie habla",
            ends_with="sale sin saber",
        )
        for e in outline.chapters().get(numero, [])
    ]


class _Embedder:
    """Doble del modelo local: vectores de tamano fijo, sin cargar pesos."""

    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        return [Embedding(values=(0.1, 0.2, 0.3), model_id="doble", dimension=3) for _ in texts]


CITA = "palabra palabra palabra palabra palabra palabra palabra palabra"


def _delta(specs: Sequence[SceneSpec], _t: Sequence[str], _e: object) -> DeltaProposal:
    """Doble del Archivero: en cada capitulo, Marcos cambia de estado."""
    primera = specs[0]
    return DeltaProposal(
        events=(
            ProposedEvent(
                world_time=primera.identity.world_time,
                payload=AttributeSet(
                    entity_id="marcos",
                    name="estado",
                    value=f"tras-capitulo-{primera.identity.chapter}",
                ),
                quote=CITA,
            ),
        )
    )


def _match(spec: SceneSpec) -> MatchResult:
    return MatchResult(
        home_team="casa",
        away_team="fuera",
        home_goals=1,
        away_goals=0,
        at=spec.identity.world_time,
        milestones=(
            Milestone(minute=10, kind=MilestoneKind.GOAL, team_id="casa", player_id="marcos"),
        ),
    )


def _perfect_reader(_texto: str, preguntas: Sequence[Question]) -> Sequence[str]:
    """Doble del lector sin contexto que siempre acierta."""
    return [q.expected for q in preguntas]


def _jury_ok(specs: Sequence[SceneSpec], textos: Sequence[str]) -> JuryVerdict:
    """Doble del Jurado que aprueba: tres instancias de acuerdo en 4, con cita real."""
    from commons.types.rubrics import Dimension
    from verification.jury.verdict import AnchoredScore, judge

    sid = specs[0].identity.scene_id
    ev = Evidence(quote=textos[0][:40] or "x", offset=0)
    scores = [
        AnchoredScore(instance=f"j{i}", seed=i, dimension=d, level=4, scene=sid, evidence=ev)
        for i in range(3)
        for d in Dimension
    ]
    return JuryVerdict(dimensions=tuple(judge(scores)))


def _fp(texto: str) -> Fingerprint:
    return Fingerprint(
        mean_sentence_len=float(len(texto.split()) % 17 + 5),
        var_sentence_len=3.0,
        adj_noun_ratio=0.3,
        top_ngrams=(),
        lexical_richness=0.5,
    )


def _engine(**kw: object) -> Engine:
    base: dict[str, object] = {
        "plan_outline": lambda _b, _c, _d: _outline(),
        "replan_act": lambda outline, _a, _f, _u, _r: outline,
        "respec": lambda specs, _d: specs,
        "write_scene": lambda spec, _p: " ".join(["palabra"] * spec.output.target_words),
        "simulate_match": _match,
        "narrate_match": lambda spec, _r, _p: " ".join(["gol"] * spec.output.target_words),
        "verify_scene": lambda _s, _t: [],
        "verify_match": lambda _s, _t, _r: [],
        "review_chapter": lambda _s, _t: Anchored(defects=(), discarded=()),
        "answer_quiz": _perfect_reader,
        "repair_scene": lambda _s, texto, _d: texto,
        "summarize_scene": lambda s, _t: f"resumen de {s.identity.scene_id}",
        "summarize_chapter": lambda partes: " ".join(partes),
        "summarize_arc": lambda partes: "ARCO: " + " | ".join(partes),
        "summarize_work": lambda partes: "OBRA: " + " | ".join(partes),
        "extract_delta": _delta,
        "embed": _Embedder(),
        "judge_chapter": _jury_ok,
        "polish_chapter": lambda _s, textos, _r: list(textos),
        "fingerprint": _fp,
        "golden_check": lambda: 1.0,
        "supervise": lambda _n, _t, _o, _m: HealthVerdict(healthy=True),
        "propose_retcon": lambda _r, _p: RetconProposal(propose=False),
        "retcon_rewrite": lambda sid, texto, plan: (
            RefrozenScene(
                scene_id=sid,
                text=texto.replace(plan.previous_value, plan.new_value),
                summary=f"resumen retcon {sid}",
            ),
            [],
        ),
    }
    base.update(kw)
    return Engine(**base)  # type: ignore[arg-type]


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    return path


# ------------------------------------------------------------ el camino feliz


def test_una_tirada_completa_cierra_sola(novela: Path) -> None:
    """RNF-03. Del brief al cierre sin que nadie apruebe nada."""
    informe = run(novela, _brief(), _engine(), novel_id="p", chapters=2, specs_for=_specs)

    assert len(informe.chapters) == 2
    assert all(c.frozen for c in informe.chapters)
    assert informe.closed, informe.reason


def test_lo_congelado_queda_consultable(novela: Path) -> None:
    """La prosa entra al indice y el capitulo se puede leer despues."""
    run(novela, _brief(), _engine(), novel_id="p", chapters=2, specs_for=_specs)

    with connection.reader(novela) as con:
        escenas = con.execute("SELECT id, chapter FROM prose_scene ORDER BY id").fetchall()
        fragmentos = con.execute("SELECT count(*) AS n FROM prose_chunk").fetchone()["n"]
        resumenes = con.execute(
            "SELECT count(*) AS n FROM summary WHERE level='chapter'"
        ).fetchone()["n"]

    assert len(escenas) == 4
    assert fragmentos > 0
    assert resumenes == 2


def test_la_purga_deja_la_memoria_de_trabajo_vacia(novela: Path) -> None:
    """PRO-I1. Tras congelar no queda ninguna fila de borrador."""
    run(novela, _brief(), _engine(), novel_id="p", chapters=2, specs_for=_specs)

    with connection.reader(novela) as con:
        assert con.execute("SELECT count(*) AS n FROM wm_draft").fetchone()["n"] == 0


def test_el_punto_de_reanudacion_avanza(novela: Path) -> None:
    """Se escribe al cerrar cada escena y sobrevive a la congelacion."""
    run(novela, _brief(), _engine(), novel_id="p", chapters=2, specs_for=_specs)
    punto = load(novela)
    assert punto is not None
    assert punto.chapter == 3


# ------------------------------------------------------------ el camino malo


def test_una_escaleta_que_no_pasa_no_arranca(novela: Path) -> None:
    """RF-27. La verificacion estructural es determinista y no se negocia."""
    rota = _outline().model_copy(update={"acts": (ActPlan(number=1, tension=(9, 1)),)})
    with pytest.raises(RunAbortedError, match="verificacion estructural"):
        run(
            novela,
            _brief(),
            _engine(plan_outline=lambda _b, _c, _d: rota),
            novel_id="p",
            chapters=2,
            specs_for=_specs,
        )


def test_una_escena_con_defecto_grave_se_reintenta(novela: Path) -> None:
    """RF-22, RF-18. Tres intentos de escena antes de subir de nivel."""
    intentos: list[int] = []

    def verifica(_s: SceneSpec, _t: str) -> list[Defect]:
        intentos.append(1)
        # Solo la primera escena falla, y solo las dos primeras veces.
        if len(intentos) <= 2:
            return [
                Defect(
                    kind="check.format",
                    severity=Severity.S1,
                    evidence=Evidence(quote="x", offset=0),
                    rule="en presente",
                )
            ]
        return []

    informe = run(
        novela, _brief(), _engine(verify_scene=verifica), novel_id="p", chapters=2, specs_for=_specs
    )
    assert informe.chapters[0].scenes[0].attempts == 3


def test_cada_capitulo_empieza_con_su_escalera_entera(novela: Path) -> None:
    """RF-18, §7.3: el capitulo 2 no hereda los intentos que gasto el 1."""
    vistas: dict[str, int] = {}

    def verifica(s: SceneSpec, _t: str) -> list[Defect]:
        sid = s.identity.scene_id
        vistas[sid] = vistas.get(sid, 0) + 1
        # La primera escena de cada capitulo falla dos veces y pasa a la tercera.
        if sid in ("c1e1", "c2e1") and vistas[sid] <= 2:
            return [
                Defect(
                    kind="check.format",
                    severity=Severity.S1,
                    evidence=Evidence(quote="x", offset=0),
                    rule="en presente",
                )
            ]
        return []

    informe = run(
        novela, _brief(), _engine(verify_scene=verifica), novel_id="p", chapters=2, specs_for=_specs
    )
    assert informe.closed, informe.reason
    assert [c.scenes[0].attempts for c in informe.chapters] == [3, 3]
    assert all(c.chapter_attempts == 1 for c in informe.chapters), "ninguna cuarentena"


def test_el_reintento_lleva_el_defecto_del_intento_anterior(novela: Path) -> None:
    """`architecture.md` §4.1: el reintento anade el defecto y su evidencia."""
    vistos: list[list[str]] = []
    intentos: list[int] = []

    def escribe(spec: SceneSpec, previos: Sequence[Defect]) -> str:
        vistos.append([d.rule for d in previos])
        return " ".join(["palabra"] * spec.output.target_words)

    def verifica(_s: SceneSpec, _t: str) -> list[Defect]:
        intentos.append(1)
        if len(intentos) == 1:
            return [
                Defect(
                    kind="check.format",
                    severity=Severity.S1,
                    evidence=Evidence(quote="x", offset=0),
                    rule="en presente",
                )
            ]
        return []

    run(
        novela,
        _brief(),
        _engine(write_scene=escribe, verify_scene=verifica),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    assert vistos[0] == [], "el primer intento no arrastra nada"
    assert vistos[1] == ["en presente"], "el segundo sabe por que se rechazo el primero"
    assert vistos[2] == [], "la escena siguiente empieza limpia"


def test_la_instruccion_del_escritor_nombra_el_defecto_y_su_cita() -> None:
    from generation.writer.prompts import instruction

    spec = _specs(_outline(), 1)[0]
    d = Defect(
        kind="check.format",
        severity=Severity.S1,
        evidence=Evidence(quote="Dani esta aqui", offset=0),
        rule="la narracion va en presente y la guia pide pasado",
    )
    texto = instruction(spec, [d])
    assert "SE RECHAZO" in texto and "pide pasado" in texto and "Dani esta aqui" in texto
    assert "SE RECHAZO" not in instruction(spec)


def test_la_obra_no_cierra_con_promesas_sin_cobrar(novela: Path) -> None:
    """RF-23. Deuda cero es una de las cuatro condiciones.

    La deuda real no es una promesa que apunta a ninguna parte --eso lo rechaza
    antes la verificacion estructural, y con razon-- sino una cuya escena de
    cobro existe en la escaleta y nunca llega a congelarse. Aqui se consigue
    planificando tres capitulos y escribiendo solo dos.
    """
    # Dos escenas en el capitulo 3: una sola quedaria por debajo del minimo de
    # capitulo y la verificacion estructural lo rechazaria antes de llegar aqui.
    escenas = (
        *_outline().scenes,
        _escena(3, 1, 2, SceneFunction.ASSIMILATE, 30),
        _escena(3, 2, 2, SceneFunction.ASSIMILATE, 31),
    )
    largo = _outline().model_copy(
        update={
            "scenes": escenas,
            "acts": (ActPlan(number=1, tension=(3,)), ActPlan(number=2, tension=(8, 8))),
            "setups": (
                Setup(
                    id="tardia",
                    planted_scene="c1e1",
                    payoff_scene="c3e1",
                    description="Se cobra en el capitulo que no se escribe",
                ),
            ),
        }
    )
    informe = run(
        novela,
        _brief(),
        _engine(plan_outline=lambda _b, _c, _d: largo),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    assert not informe.closed
    assert "promesas sin cobrar" in informe.reason


def test_la_obra_no_cierra_fuera_de_rango(novela: Path) -> None:
    """Una novela corta de mas no esta terminada por muchos arcos que resuelva."""
    informe = run(
        novela,
        _brief(),
        _engine(write_scene=lambda _s, _p: "muy corta"),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    assert not informe.closed
    assert "palabras" in informe.reason


def test_el_informe_es_legible(novela: Path) -> None:
    """Lo que se traza tiene que poder leerse sin reconstruir la ejecucion."""
    informe = run(novela, _brief(), _engine(), novel_id="p", chapters=2, specs_for=_specs)
    import json

    datos = json.loads(as_json(informe))
    assert datos["novel_id"] == "p"
    assert len(datos["chapters"]) == 2
    assert datos["chapters"][0]["scenes"][0]["id"] == "c1e1"


# ------------------------------------------------------ el canon evoluciona


def test_congelar_hace_evolucionar_el_canon(novela: Path) -> None:
    """RF-55, RF-56. Sin esto el sistema es un generador con memoria de prosa."""
    with connection.reader(novela) as con:
        antes = con.execute("SELECT count(*) AS n FROM event").fetchone()["n"]

    run(novela, _brief(), _engine(), novel_id="p", chapters=2, specs_for=_specs)

    with connection.reader(novela) as con:
        despues = con.execute("SELECT count(*) AS n FROM event").fetchone()["n"]
        estado = read.state_at(con, WorldTime(stamp="2026-08-25"))
    marcos = next(c for c in estado.cards if c.entity_id == "marcos")

    assert despues == antes + 2, "un evento por capitulo congelado"
    assert ("estado", "tras-capitulo-2") in marcos.attributes


def test_un_archivero_que_no_extrae_nada_no_congela(novela: Path) -> None:
    """Trampa 12: el delta vacio es un fallo, no una congelacion limpia."""

    def vacio(_s: Sequence[SceneSpec], _t: Sequence[str], _e: object) -> DeltaProposal:
        return DeltaProposal()

    with pytest.raises(EmptyDeltaError):
        run(
            novela,
            _brief(),
            _engine(extract_delta=vacio),
            novel_id="p",
            chapters=2,
            specs_for=_specs,
        )


def test_un_hecho_que_reescribe_el_pasado_se_arbitra_y_se_repara(novela: Path) -> None:
    """RF-59, RF-60. El canon congelado gana, el capitulo vuelve al Reparador con
    un S1 citado, y solo congela cuando el delta ya no contradice nada."""

    def reescribe(specs: Sequence[SceneSpec], textos: Sequence[str], _e: object) -> DeltaProposal:
        cap = specs[0].identity.chapter
        # El capitulo 2, hasta que se repara, afirma algo sobre el dia 1 que el
        # brief ya fijo. Reparado, afirma algo de su propio dia.
        reparado = textos[0].startswith("REPARADO")
        stamp = "2026-08-01" if cap == 2 and not reparado else specs[0].identity.world_time.stamp
        return DeltaProposal(
            events=(
                ProposedEvent(
                    world_time=WorldTime(stamp=stamp, seq=0),
                    payload=AttributeSet(entity_id="marcos", name="estado", value=f"v{cap}"),
                    quote=CITA,
                ),
            )
        )

    traza = Trace.disabled()
    informe = run(
        novela,
        _brief(),
        _engine(extract_delta=reescribe, repair_scene=lambda _s, t, _d: "REPARADO " + t),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )

    segundo = informe.chapters[1]
    assert segundo.frozen
    assert len(segundo.rejected_facts) == 1
    assert segundo.rejected_facts[0].severity is Severity.S1
    assert segundo.events_applied == 1, "el delta reparado si entra"
    assert segundo.scenes[0].text.startswith("REPARADO")


def test_la_traza_recoge_cada_decision(novela: Path, tmp_path: Path) -> None:
    """RI-16, RF-24. Una linea por llamada, reintento, arbitraje y congelacion."""
    traza = Trace(tmp_path / "p.trace.jsonl")
    run(novela, _brief(), _engine(), novel_id="p", chapters=2, specs_for=_specs, trace=traza)

    tipos = {r.kind for r in traza.records()}
    assert {"outline.check", "scene.attempt", "chapter.frozen", "work.close"} <= tipos
    intentos = traza.records("scene.attempt")
    assert len(intentos) == 4
    assert all({"chapter", "scene", "attempt", "passed"} <= set(r.fields) for r in intentos)


# ------------------------------------------------- la puerta de capitulo


def _s1(texto: str, quote: str) -> Defect:
    return Defect(
        kind="continuity.state",
        severity=Severity.S1,
        evidence=Evidence(quote=quote, offset=texto.find(quote)),
        rule="el canon dice otra cosa",
    )


def test_un_defecto_del_continuista_se_repara_y_el_capitulo_congela(novela: Path) -> None:
    """RF-51, RF-53, RF-54. Detectar con cita, reparar, revalidar, congelar."""
    revisiones: list[int] = []

    def revisa(_specs: Sequence[SceneSpec], textos: Sequence[str]) -> Anchored:
        revisiones.append(1)
        capitulo = "\n\n".join(textos)
        if "REPARADO" in capitulo or (len(revisiones) > 1 and textos[0].startswith("REPARADO")):
            return Anchored(defects=(), discarded=())
        return Anchored(defects=(_s1(capitulo, capitulo[:60]),), discarded=())

    def repara(_spec: SceneSpec, texto: str, defectos: Sequence[Defect]) -> str:
        assert defectos, "el Reparador siempre recibe el defecto con su cita"
        return "REPARADO " + texto

    traza = Trace.disabled()
    informe = run(
        novela,
        _brief(),
        _engine(review_chapter=revisa, repair_scene=repara),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )

    assert all(c.frozen for c in informe.chapters)
    assert informe.chapters[0].scenes[0].repairs == 1
    assert informe.chapters[0].scenes[0].text.startswith("REPARADO")


def test_una_reparacion_que_abre_un_s1_se_revierte(novela: Path) -> None:
    """RF-54. La escena anterior con su defecto conocido vale mas que una nueva rota."""

    def revisa(_specs: Sequence[SceneSpec], textos: Sequence[str]) -> Anchored:
        capitulo = "\n\n".join(textos)
        # Solo el primer intento del capitulo 1 tiene defecto; despues, limpio.
        if textos[0].startswith("palabra") and "REPARADO" not in capitulo and revisa.veces == 0:  # type: ignore[attr-defined]
            revisa.veces += 1  # type: ignore[attr-defined]
            return Anchored(defects=(_s1(capitulo, capitulo[:60]),), discarded=())
        return Anchored(defects=(), discarded=())

    revisa.veces = 0  # type: ignore[attr-defined]

    def verifica(_s: SceneSpec, texto: str) -> list[Defect]:
        if texto.startswith("ROTO"):
            return [
                Defect(
                    kind="check.format",
                    severity=Severity.S1,
                    evidence=Evidence(quote="ROTO", offset=0),
                    rule="en presente",
                )
            ]
        return []

    informe = run(
        novela,
        _brief(),
        _engine(
            review_chapter=revisa, verify_scene=verifica, repair_scene=lambda _s, t, _d: "ROTO " + t
        ),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    assert informe.chapters[0].scenes[0].repairs == 0
    assert not informe.chapters[0].scenes[0].text.startswith("ROTO")


def test_tres_respuestas_erroneas_del_examen_no_pasan_la_puerta(novela: Path) -> None:
    """RF-112, RF-115. Cada error es un S2; mas de dos, el capitulo se repara."""
    lecturas: list[int] = []

    def lector(_texto: str, preguntas: Sequence[Question]) -> Sequence[str]:
        lecturas.append(1)
        # La primera lectura del capitulo 1 no entiende nada; la segunda, todo.
        if len(lecturas) == 1:
            return ["no se sabe"] * len(preguntas)
        return [q.expected for q in preguntas]

    traza = Trace(novela.with_suffix(".trace.jsonl"))
    informe = run(
        novela,
        _brief(),
        _engine(answer_quiz=lector),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )

    puertas = traza.records("chapter.gate")
    assert puertas[0].fields["passed"] is False and puertas[0].fields["s2"] == 6
    assert informe.chapters[0].frozen
    assert traza.records("repair"), "hubo un pase de reparacion"


def test_agotada_la_escalera_el_capitulo_se_rehace_y_luego_se_replanifica(novela: Path) -> None:
    """RF-19, D-26. Cuarentena: reespecificar, replanificar, y no hay cuarto nivel."""
    llamadas = {"respec": 0, "replan": 0}

    def respec(specs: Sequence[SceneSpec], _d: Sequence[Defect]) -> Sequence[SceneSpec]:
        llamadas["respec"] += 1
        return specs

    def replan(outline: Outline, _a: int, _f: int, _u: Sequence[str], _r: Sequence[str]) -> Outline:
        llamadas["replan"] += 1
        return outline

    def siempre_mal(_specs: Sequence[SceneSpec], textos: Sequence[str]) -> Anchored:
        capitulo = "\n\n".join(textos)
        return Anchored(defects=(_s1(capitulo, capitulo[:60]),), discarded=())

    with pytest.raises(RunAbortedError, match="no pasa sus puertas"):
        run(
            novela,
            _brief(),
            _engine(review_chapter=siempre_mal, respec=respec, replan_act=replan),
            novel_id="p",
            chapters=2,
            specs_for=_specs,
        )

    assert llamadas["respec"] >= 1
    assert llamadas["replan"] >= 1


def test_una_escena_de_encuentro_se_resuelve_antes_de_narrarse(novela: Path) -> None:
    """RF-42, RF-44. El motor decide, el modelo dramatiza, el verificador contrasta."""
    escenas = tuple(
        e.model_copy(update={"is_match": True}) if e.id == "c2e1" else e for e in _outline().scenes
    )
    con_partido = _outline().model_copy(update={"scenes": escenas})
    vistos: list[MatchResult] = []

    def verifica_partido(_s: SceneSpec, _t: str, r: MatchResult) -> list[Defect]:
        vistos.append(r)
        return []

    informe = run(
        novela,
        _brief(),
        _engine(plan_outline=lambda _b, _c, _d: con_partido, verify_match=verifica_partido),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    escena = informe.chapters[1].scenes[0]
    assert escena.match is not None and escena.match.home_goals == 1
    assert escena.text.startswith("gol")
    # Una al escribir y otra al reverificar tras el Estilista (RF-141), sobre el mismo resultado.
    assert len(vistos) == 2 and vistos[0] == vistos[1]


def test_una_cita_del_continuista_que_no_ancla_no_cuenta_contra_el_texto(novela: Path) -> None:
    """RF-111. Defecto de proceso, trazado, y la tirada sigue."""

    def revisa(_specs: Sequence[SceneSpec], _t: Sequence[str]) -> Anchored:
        return Anchored(defects=(), discarded=("una cita que el modelo se invento entera",))

    traza = Trace.disabled()
    informe = run(
        novela,
        _brief(),
        _engine(review_chapter=revisa),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )
    assert all(c.frozen for c in informe.chapters)
    assert informe.chapters[0].discarded_citations == 1


# ------------------------------------------------------------ reanudacion


def test_reanudar_da_el_mismo_manuscrito_que_no_interrumpir(tmp_path: Path) -> None:
    """RF-20, RNF-08, RNF-09. Se reanuda desde la ultima escena cerrada; la
    escena en curso se pierde y nada mas; el resultado es identico."""
    vistas: set[str] = set()

    def escribe_y_cae(spec: SceneSpec, _p: object) -> str:
        # La primera vez que toca c2e2, el proceso "cae".
        if spec.identity.scene_id == "c2e2" and "c2e2" not in vistas:
            vistas.add("c2e2")
            raise RuntimeError("caida simulada")
        return f"{spec.identity.scene_id} " + " ".join(["palabra"] * spec.output.target_words)

    interrumpida = tmp_path / "a.sqlite"
    create_novel(interrumpida, _brief())
    traza = Trace(tmp_path / "a.trace.jsonl")
    with pytest.raises(RuntimeError, match="caida simulada"):
        run(
            interrumpida,
            _brief(),
            _engine(write_scene=escribe_y_cae),
            novel_id="a",
            chapters=2,
            specs_for=_specs,
            trace=traza,
        )
    punto = load(interrumpida)
    assert punto is not None and punto.chapter == 2 and punto.last_closed_scene == 1

    informe = run(
        interrumpida,
        _brief(),
        _engine(write_scene=escribe_y_cae),
        novel_id="a",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )
    assert informe.closed
    assert traza.records("scene.resumed"), "c2e1 se reutilizo en vez de regenerarse"

    limpia = tmp_path / "b.sqlite"
    create_novel(limpia, _brief())
    run(
        limpia,
        _brief(),
        _engine(
            write_scene=lambda s, _p: (
                f"{s.identity.scene_id} " + " ".join(["palabra"] * s.output.target_words)
            )
        ),
        novel_id="b",
        chapters=2,
        specs_for=_specs,
    )

    def prosa(path: Path) -> list[tuple[str, str]]:
        with connection.reader(path) as con:
            return [
                (r["scene_id"], r["text"])
                for r in con.execute(
                    "SELECT scene_id, text FROM prose_chunk ORDER BY scene_id, ordinal"
                )
            ]

    assert prosa(interrumpida) == prosa(limpia)


# ---------------------------------------------------- resumenes de arco y obra


def test_al_cerrar_un_arco_se_escribe_su_resumen_desde_los_de_capitulo(novela: Path) -> None:
    """RF-116, RF-120, RD-23. El arco se resume al congelar el capitulo que lo cierra."""
    run(novela, _brief(), _engine(), novel_id="p", chapters=2, specs_for=_specs)
    with connection.reader(novela) as con:
        arcos = {
            r["ref_id"]: r["body"]
            for r in con.execute("SELECT ref_id, body FROM summary WHERE level='arc'")
        }
        versiones = con.execute(
            "SELECT count(*) AS n FROM summary_version WHERE level='arc'"
        ).fetchone()["n"]
    assert set(arcos) == {"comp", "int"}
    assert all(b.startswith("ARCO:") for b in arcos.values())
    assert versiones == 2


def test_el_resumen_de_obra_llega_cada_cinco_capitulos() -> None:
    """RF-117."""
    from canon.summaries.levels import work_due

    assert [c for c in range(1, 11) if work_due(c)] == [5, 10]


def test_la_escaleta_rechazada_vuelve_con_sus_defectos(novela: Path) -> None:
    """RF-27. El segundo intento del Arquitecto recibe lo que fallo en el primero."""
    recibidos: list[int] = []
    rota = _outline().model_copy(update={"acts": (ActPlan(number=1, tension=(9, 1)),)})

    def arquitecto(_b: Brief, _c: int, defectos: Sequence[object]) -> Outline:
        recibidos.append(len(defectos))
        return rota if len(recibidos) == 1 else _outline()

    run(
        novela,
        _brief(),
        _engine(plan_outline=arquitecto),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    assert recibidos[0] == 0
    assert recibidos[1] > 0


# ------------------------------------------------------------- Jurado y Estilista


def test_un_jurado_bajo_umbral_manda_a_reparar_y_vuelve_a_juzgar(novela: Path) -> None:
    """RF-132. Bajo umbral, los defectos van al Reparador y el capitulo vuelve."""
    from commons.types.rubrics import Dimension
    from verification.jury.verdict import AnchoredScore, judge

    veces: list[int] = []

    def jurado(specs: Sequence[SceneSpec], textos: Sequence[str]) -> JuryVerdict:
        veces.append(1)
        if len(veces) > 1:
            return _jury_ok(specs, textos)
        ev = Evidence(quote=textos[0][:40], offset=0)
        scores = [
            AnchoredScore(
                instance=f"j{i}",
                seed=i,
                dimension=d,
                level=2,
                scene=specs[0].identity.scene_id,
                evidence=ev,
            )
            for i in range(3)
            for d in Dimension
        ]
        return JuryVerdict(dimensions=tuple(judge(scores)))

    traza = Trace(novela.with_suffix(".trace.jsonl"))
    informe = run(
        novela,
        _brief(),
        _engine(judge_chapter=jurado, repair_scene=lambda _s, t, _d: "REPARADO " + t),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )
    assert informe.chapters[0].frozen
    assert traza.records("jury")[0].fields["passed"] is False
    assert any(r.fields.get("accepted") for r in traza.records("repair"))


def test_un_pase_de_estilo_que_abre_un_s1_se_revierte(novela: Path) -> None:
    """RF-141, RF-54."""

    def verifica(_s: SceneSpec, texto: str) -> list[Defect]:
        if "ESTILO" in texto:
            return [
                Defect(
                    kind="check.format",
                    severity=Severity.S1,
                    evidence=Evidence(quote="ESTILO", offset=0),
                    rule="rompe el tiempo verbal",
                )
            ]
        return []

    informe = run(
        novela,
        _brief(),
        _engine(verify_scene=verifica, polish_chapter=lambda _s, t, _r: ["ESTILO " + x for x in t]),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    assert all(c.style_reverted for c in informe.chapters)
    assert not any("ESTILO" in s.text for c in informe.chapters for s in c.scenes)


def test_la_congelacion_guarda_veredictos_y_huella(novela: Path) -> None:
    """RD-20, RD-21."""
    run(novela, _brief(), _engine(), novel_id="p", chapters=2, specs_for=_specs)
    with connection.reader(novela) as con:
        veredictos = con.execute("SELECT count(*) AS n FROM scene_verdict").fetchone()["n"]
        huellas = con.execute(
            "SELECT chapter, is_reference FROM chapter_fingerprint ORDER BY chapter"
        ).fetchall()
    assert veredictos == 30, "5 dimensiones x 3 instancias x 2 capitulos"
    assert [(h["chapter"], h["is_reference"]) for h in huellas] == [(1, 1), (2, 1)]


# ------------------------------------------------------------------ Supervisor


def test_la_congelacion_guarda_las_trece_senales(novela: Path) -> None:
    """RF-144, RD-22."""
    run(
        novela,
        _brief(),
        _engine(),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=Trace(novela.with_suffix(".trace.jsonl")),
    )
    with connection.reader(novela) as con:
        n = con.execute("SELECT count(*) AS n FROM chapter_metrics").fetchone()["n"]
    assert n == 26, "trece senales por capitulo congelado"


def test_un_supervisor_que_falla_cuenta_como_sano_y_consta(novela: Path) -> None:
    """RF-149, D-45."""

    def roto(_n: int, _t: int, _o: Outline, _m: object) -> HealthVerdict:
        raise RuntimeError("el modelo no respondio")

    traza = Trace(novela.with_suffix(".trace.jsonl"))
    informe = run(
        novela,
        _brief(),
        _engine(supervise=roto),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )
    assert all(c.frozen for c in informe.chapters)
    assert all(r.fields.get("fallback") for r in traza.records("health"))
    assert any(r.fields.get("agent") == "supervisor" for r in traza.records("process.defect"))


def test_una_deriva_replanifica_solo_lo_que_queda(novela: Path) -> None:
    """RF-147. El tramo empieza despues del ultimo congelado."""
    tramos: list[int] = []

    def supervisor(n: int, _t: int, _o: Outline, _m: object) -> HealthVerdict:
        return HealthVerdict(
            healthy=n != 1, signal="narrative_debt", act=1, from_chapter=1, reason="la deuda crece"
        )

    def replan(
        outline: Outline, _a: int, desde: int, _u: Sequence[str], _r: Sequence[str]
    ) -> Outline:
        tramos.append(desde)
        return outline

    run(
        novela,
        _brief(),
        _engine(supervise=supervisor, replan_act=replan),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    assert tramos == [2], "pidio desde el 1, pero el 1 ya estaba congelado"


# -------------------------------------------------------------------- retcon


def test_un_retcon_admisible_se_aplica_y_el_capitulo_congela_limpio(novela: Path) -> None:
    """RF-151 a RF-154. El Arbitro propone, la regla admite, se recongela y consta."""

    def reescribe(specs: Sequence[SceneSpec], _t: Sequence[str], _e: object) -> DeltaProposal:
        cap = specs[0].identity.chapter
        stamp = "2026-08-01" if cap == 2 else specs[0].identity.world_time.stamp
        return DeltaProposal(
            events=(
                ProposedEvent(
                    world_time=WorldTime(stamp=stamp, seq=0),
                    payload=AttributeSet(entity_id="marcos", name="estado", value=f"v{cap}"),
                    quote=CITA,
                ),
            )
        )

    traza = Trace(novela.with_suffix(".trace.jsonl"))
    informe = run(
        novela,
        _brief(),
        _engine(
            extract_delta=reescribe, propose_retcon=lambda _r, _p: RetconProposal(propose=True)
        ),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )

    assert informe.chapters[1].frozen
    assert informe.chapters[1].rejected_facts == []
    assert traza.records("retcon.applied")
    with connection.reader(novela) as con:
        assert con.execute("SELECT count(*) AS n FROM retcon").fetchone()["n"] == 1
        estado = dict(read.query(con, ["marcos"], at=WorldTime(stamp="2026-08-25"))[0].attributes)
    assert estado["estado"] == "v2"


def test_sin_propuesta_gana_el_canon_como_en_la_version_1(novela: Path) -> None:
    """RF-152: si el Arbitro no propone, nada cambia en el pasado."""

    def reescribe(specs: Sequence[SceneSpec], textos: Sequence[str], _e: object) -> DeltaProposal:
        cap = specs[0].identity.chapter
        reparado = textos[0].startswith("REPARADO")
        stamp = "2026-08-01" if cap == 2 and not reparado else specs[0].identity.world_time.stamp
        return DeltaProposal(
            events=(
                ProposedEvent(
                    world_time=WorldTime(stamp=stamp, seq=0),
                    payload=AttributeSet(entity_id="marcos", name="estado", value=f"v{cap}"),
                    quote=CITA,
                ),
            )
        )

    run(
        novela,
        _brief(),
        _engine(extract_delta=reescribe, repair_scene=lambda _s, t, _d: "REPARADO " + t),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    with connection.reader(novela) as con:
        assert con.execute("SELECT count(*) AS n FROM retcon").fetchone()["n"] == 0


def test_b2_un_retcon_con_la_version_2_creada_no_cambia_la_1(novela: Path) -> None:
    """B2, `PreviousVersionPreserved`, RD-34, PRO-08. El capitulo 1 congela, una
    enmienda que no toca ninguna escena crea la version 2, y el capitulo 2
    dispara un retcon que reescribe las del 1. La version 1 se sigue leyendo
    como era; la 2, la vigente, ya lleva el retcon y lo marca."""
    from canon import manuscript

    def escribe(spec: SceneSpec, _p: Sequence[Defect]) -> str:
        return f"Marcos v1 {spec.identity.scene_id} " + " ".join(
            ["palabra"] * spec.output.target_words
        )

    def reescribe(specs: Sequence[SceneSpec], _t: Sequence[str], _e: object) -> DeltaProposal:
        cap = specs[0].identity.chapter
        stamp = "2026-08-01" if cap == 2 else specs[0].identity.world_time.stamp
        return DeltaProposal(
            events=(
                ProposedEvent(
                    world_time=WorldTime(stamp=stamp, seq=0),
                    payload=AttributeSet(entity_id="marcos", name="estado", value=f"v{cap}"),
                    quote=CITA,
                ),
            )
        )

    def enmienda_sin_escenas() -> None:
        # Lo que deja `commit_amendment` cuando el hecho no se nombra en ninguna
        # escena congelada: la version 2, sin historia de texto.
        with connection.canon_writer(novela) as con:
            if manuscript.current_version(con) == 1:
                con.execute(
                    "INSERT INTO manuscript_version (version, cause, changed_chapters, "
                    "max_chapter, created_at) VALUES (2, NULL, '[]', 1, datetime('now'))"
                )

    traza = Trace(novela.with_suffix(".trace.jsonl"))
    run(
        novela,
        _brief(),
        _engine(
            write_scene=escribe,
            extract_delta=reescribe,
            propose_retcon=lambda _r, _p: RetconProposal(propose=True),
        ),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
        after_freeze=enmienda_sin_escenas,
    )

    [aplicado] = traza.records("retcon.applied")
    assert aplicado.fields["refrozen"] == ["c1e1", "c1e2"]
    with connection.reader(novela) as con:
        v1 = manuscript.chapter_at(con, 1, 1) or []
        v2 = manuscript.chapter_at(con, 1, 2) or []
    assert [s.text.split()[1] for s in v1] == ["v1", "v1"], "la version 1 no cambio"
    assert [s.text.split()[1] for s in v2] == ["v2", "v2"], "la vigente lleva el retcon"
    assert all(s.changed for s in v2) and not any(s.changed for s in v1)


# ------------------------------------------- guardarrail de prohibidas (T41)


def _novela_con_prohibida(tmp_path: Path, *words: str) -> tuple[Path, Brief]:
    brief = _brief().model_copy(update={"forbidden_words": words or ("linimento",)})
    path = tmp_path / "prohibida.sqlite"
    create_novel(path, brief, global_terms=())
    return path, brief


def _verifica_prohibidas(path: Path) -> Callable[[SceneSpec, str], list[Defect]]:
    """`verify_scene` con el `check.forbidden` real y las prohibidas de la novela."""

    def verifica(_s: SceneSpec, texto: str) -> list[Defect]:
        with connection.reader(path) as con:
            terminos = forbidden.read_terms(con)
        return forbidden.check_forbidden(texto, terms=terminos)

    return verifica


def _prosa(spec: SceneSpec, *, con: str = "") -> str:
    palabras = ["palabra"] * spec.output.target_words
    if con:
        palabras[5] = con
    return " ".join(palabras)


def _congelado_con(path: Path, palabra: str) -> int:
    with connection.reader(path) as con:
        return int(
            con.execute(
                "SELECT count(*) AS n FROM prose_chunk WHERE lower(text) LIKE ?", (f"%{palabra}%",)
            ).fetchone()["n"]
        )


def test_forbidden_bloquea_la_escena_y_el_reintento_lleva_su_cita(tmp_path: Path) -> None:
    """RF-236, RF-238, RF-240: S1, vuelve al Escritor con la cita, y consta en la traza."""
    path, brief = _novela_con_prohibida(tmp_path)
    previos: list[list[Defect]] = []

    def escribe(spec: SceneSpec, anteriores: Sequence[Defect]) -> str:
        previos.append(list(anteriores))
        primera = spec.identity.scene_id == "c1e1" and len(previos) == 1
        return _prosa(spec, con="LINIMENTO" if primera else "")

    traza = Trace(tmp_path / "t.jsonl")
    informe = run(
        path,
        brief,
        _engine(write_scene=escribe, verify_scene=_verifica_prohibidas(path)),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )

    assert informe.closed, informe.reason
    assert informe.chapters[0].scenes[0].attempts == 2
    [defecto] = previos[1]
    assert defecto.kind == "check.forbidden" and defecto.evidence.quote == "LINIMENTO"
    [registro] = traza.records("guardrail.match")
    assert registro.fields == {
        "chapter": 1,
        "scene": 1,
        "attempt": 1,
        "term": "linimento",
        "level": "cliente",
        "quote": "LINIMENTO",
        "offset": defecto.evidence.offset,
        "decision": "reintentar",
        "stage": "escena",
    }
    assert _congelado_con(path, "linimento") == 0


def test_forbidden_agotada_la_escalera_aborta_con_termino_y_nivel(tmp_path: Path) -> None:
    """RF-238: agotada la escalera, `RunAbortedError` nombra verificador, termino y nivel.

    Y RI-03 lo muestra en `reason`: la ruta de estado lee el ultimo `work.close`.
    """
    settings = Settings(runs_dir=tmp_path)
    brief = _brief().model_copy(update={"forbidden_words": ("linimento",)})
    path = settings.novel_path("prohibida")
    create_novel(path, brief, global_terms=())
    escrituras: list[int] = []

    def escribe(spec: SceneSpec, _p: Sequence[Defect]) -> str:
        escrituras.append(1)
        return _prosa(spec, con="linimentos")

    traza = Trace(settings.trace_path("prohibida"))
    with pytest.raises(RunAbortedError) as exc:
        run(
            path,
            brief,
            _engine(write_scene=escribe, verify_scene=_verifica_prohibidas(path)),
            novel_id="prohibida",
            chapters=2,
            specs_for=_specs,
            trace=traza,
        )

    motivo = str(exc.value)
    assert "check.forbidden" in motivo and "«linimento»" in motivo and "cliente" in motivo
    # La escalera es finita: tres intentos por escena, y cada peldano la repite.
    assert 3 <= len(escrituras) <= 40
    assert _congelado_con(path, "linimento") == 0
    decisiones = {r.fields["decision"] for r in traza.records("guardrail.match")}
    assert decisiones == {"reintentar", "abortar"}
    [cierre] = traza.records("work.close")
    assert cierre.fields["closed"] is False and "check.forbidden" in str(cierre.fields["reason"])
    estado = _state(settings, "prohibida")
    assert estado.closed is False and "«linimento»" in estado.reason


def test_forbidden_antes_de_congelar_vuelve_a_reparacion(tmp_path: Path) -> None:
    """RF-236: la segunda red. Un termino partido entre dos escenas no lo ve ninguna sola."""
    path, brief = _novela_con_prohibida(tmp_path, "silencio sepulcral")
    reparadas: list[list[str]] = []

    def escribe(spec: SceneSpec, _p: Sequence[Defect]) -> str:
        texto = _prosa(spec)
        if spec.identity.scene_id == "c1e1":
            return texto + " silencio"
        if spec.identity.scene_id == "c1e2":
            return "Sepulcral " + texto
        return texto

    def repara(_s: SceneSpec, texto: str, defectos: Sequence[Defect]) -> str:
        reparadas.append([d.kind for d in defectos])
        return texto.replace(" silencio", "")

    traza = Trace(tmp_path / "t.jsonl")
    informe = run(
        path,
        brief,
        _engine(write_scene=escribe, verify_scene=_verifica_prohibidas(path), repair_scene=repara),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )

    assert informe.chapters[0].frozen
    assert reparadas[0] == ["check.forbidden"]
    [registro] = traza.records("guardrail.match")
    assert registro.fields["stage"] == "congelacion" and registro.fields["decision"] == "reparar"
    assert registro.fields["scene"] == 1 and registro.fields["level"] == "cliente"
    assert _congelado_con(path, "silencio") == 0


def test_forbidden_antes_de_congelar_sin_reparacion_no_congela(tmp_path: Path) -> None:
    """Un verificador de escena que no mira las prohibidas no basta para congelar una."""
    path, brief = _novela_con_prohibida(tmp_path)
    with pytest.raises(RunAbortedError, match=r"check\.forbidden"):
        run(
            path,
            brief,
            _engine(write_scene=lambda spec, _p: _prosa(spec, con="linimento")),
            novel_id="p",
            chapters=2,
            specs_for=_specs,
        )
    assert _congelado_con(path, "linimento") == 0


def test_la_traza_dice_cuantas_hay_por_nivel_y_que_colapso(tmp_path: Path) -> None:
    """RF-239, D-91: un termino del cliente que ya era global se queda global."""
    brief = _brief().model_copy(update={"forbidden_words": ("Linimento", "sangre")})
    path = tmp_path / "n.sqlite"
    create_novel(path, brief, global_terms=("linimento",))
    traza = Trace(tmp_path / "t.jsonl")
    run(path, brief, _engine(), novel_id="p", chapters=2, specs_for=_specs, trace=traza)
    [niveles] = traza.records("guardrail.levels")
    assert niveles.fields["levels"] == {"global": 1, "cliente": 1, "novela": 0}
    assert niveles.fields["collapsed"] == ["linimento: cliente -> global"]


# ------------------------------------------- longitud de capitulo (RF-232)


def _dos_s2(textos: Sequence[str]) -> Anchored:
    capitulo = "\n\n".join(textos)
    return Anchored(
        defects=tuple(
            Defect(
                kind="continuity.state",
                severity=Severity.S2,
                evidence=Evidence(quote=capitulo[:30], offset=0),
                rule=f"matiz {i}",
            )
            for i in (1, 2)
        ),
        discarded=(),
    )


def test_un_capitulo_escrito_de_1200_palabras_no_pasa_la_puerta(novela: Path) -> None:
    """RF-232, D-97: S2 de `check.format` que cuenta en el maximo de 2 S2 de la puerta.

    Con los dos S2 del Continuista el capitulo corto ya no pasa, y `chapter.gate`
    cita la cifra y el rango. Con la longitud en rango, los mismos dos pasan.
    """
    revisiones: list[int] = []

    def continuista(_s: Sequence[SceneSpec], textos: Sequence[str]) -> Anchored:
        revisiones.append(1)
        return _dos_s2(textos) if len(revisiones) == 1 else Anchored(defects=(), discarded=())

    traza = Trace(novela.with_suffix(".trace.jsonl"))
    informe = run(
        novela,
        _brief(),
        _engine(write_scene=lambda _s, _p: " ".join(["palabra"] * 600), review_chapter=continuista),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )

    primera = traza.records("chapter.gate")[0]
    assert primera.fields["passed"] is False and primera.fields["s2"] == 3
    citas = " ".join(str(d) for d in primera.fields["defects"])  # type: ignore[union-attr]
    assert "check.format" in citas and "1200 palabras" in citas and "1500-4000" in citas
    assert traza.records("repair"), "fuera de la puerta, el capitulo va a reparacion"
    assert informe.chapters[0].frozen


def test_con_la_longitud_en_rango_los_mismos_dos_s2_pasan(novela: Path) -> None:
    traza = Trace(novela.with_suffix(".trace.jsonl"))
    run(
        novela,
        _brief(),
        _engine(review_chapter=lambda _s, textos: _dos_s2(textos)),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )
    primera = traza.records("chapter.gate")[0]
    assert primera.fields["passed"] is True and primera.fields["s2"] == 2
