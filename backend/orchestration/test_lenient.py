"""El modo permisivo de `breve` y `prueba`: escribir y congelar antes que parar.

`specs/srs-backend-v4.md` RF-284, D-136. Metodo VER-05. Corre con los dobles de
`test_loop`: un Continuista, un Jurado, un Arbitro y un Lean que siempre fallan
y aun asi la obra entera se congela y cierra, con cada degradacion en la traza.
Con el perfil estricto, los mismos dobles siguen parando la tirada.

Las pruebas sobre la escaleta de `test_loop` usan `novela` con `lenient`
encendido, porque es la forma que ya tienen sus dobles; que `breve` y `prueba`
lo lleven encendido lo fija la primera prueba.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

import pytest

from canon.archivist.extract import DeltaProposal
from canon.brief import create_novel
from commons.tracing.trace import Trace
from commons.types import length
from commons.types.length import BREVE, NOVELA, PRUEBA, LengthProfileName
from commons.types.primitives import Defect, Evidence, Severity
from commons.types.scene import SceneSpec
from orchestration import loop
from orchestration.loop import RunAbortedError, run
from orchestration.test_loop import _brief, _engine, _outline, _s1, _specs
from planning.outline.types import Outline
from verification.continuity.review import Anchored
from verification.formal.check import LeanResult
from verification.jury.verdict import JuryVerdict


@pytest.fixture
def permisivo(monkeypatch: pytest.MonkeyPatch) -> None:
    """`novela` con `lenient`, para usar la escaleta de dos capitulos de `test_loop`."""
    monkeypatch.setitem(
        length.PROFILES, LengthProfileName.NOVELA, dataclasses.replace(NOVELA, lenient=True)
    )


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    return path


def _continuista_mal(_specs: Sequence[SceneSpec], textos: Sequence[str]) -> Anchored:
    capitulo = "\n\n".join(textos)
    return Anchored(defects=(_s1(capitulo, capitulo[:60]),), discarded=())


def _jurado_mal(specs: Sequence[SceneSpec], textos: Sequence[str]) -> JuryVerdict:
    """Tres instancias de acuerdo en 1: todas las dimensiones bajo umbral."""
    from commons.types.rubrics import Dimension
    from verification.jury.verdict import AnchoredScore, judge

    ev = Evidence(quote=textos[0][:40], offset=0)
    scores = [
        AnchoredScore(
            justification="justificada en la cita",
            instance=f"j{i}",
            seed=i,
            dimension=d,
            level=1,
            scene=specs[0].identity.scene_id,
            evidence=ev,
        )
        for i in range(3)
        for d in Dimension
    ]
    return JuryVerdict(dimensions=tuple(judge(scores)))


def _lean_mal(_path: Path, _pending: object) -> LeanResult:
    return LeanResult(passed=False, reason="la cronologia no demuestra")


def _check_s1(texto: str) -> Defect:
    return Defect(
        kind="check.timeline",
        severity=Severity.S1,
        evidence=Evidence(quote=texto[:40], offset=0),
        rule="fecha imposible",
    )


def _run(path: Path, trace: Trace, **kw: object) -> loop.RunReport:
    return run(
        path,
        _brief(),
        _engine(**kw),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=trace,
    )


# -------------------------------------------------------------------- perfiles


def test_breve_y_prueba_son_permisivos_y_novela_estricta() -> None:
    assert BREVE.lenient and PRUEBA.lenient
    assert not NOVELA.lenient


# ------------------------------------------------------------ puerta de capitulo


def test_continuista_y_jurado_que_siempre_fallan_no_paran_la_obra(
    permisivo: None, novela: Path, tmp_path: Path
) -> None:
    """D-136. Solo bloquea un S1 determinista: los de modelo constan y no reparan."""
    reparaciones: list[int] = []

    def repara(_s: SceneSpec, texto: str, _d: Sequence[Defect]) -> str:
        reparaciones.append(1)
        return texto

    traza = Trace(tmp_path / "t.jsonl")
    informe = _run(
        novela,
        traza,
        review_chapter=_continuista_mal,
        judge_chapter=_jurado_mal,
        repair_scene=repara,
    )

    assert all(c.frozen for c in informe.chapters) and len(informe.chapters) == 2
    assert informe.closed, informe.reason
    assert reparaciones == []
    puertas = traza.records("chapter.gate")
    assert all(r.fields["passed"] is True and r.fields["s1"] == 1 for r in puertas)
    assert all(r.fields["passed"] is False for r in traza.records("jury"))


def test_con_el_perfil_estricto_los_mismos_dobles_paran(novela: Path) -> None:
    """RF-18, D-26. `novela` sigue la escalera entera y aborta."""
    with pytest.raises(RunAbortedError):
        _run(novela, Trace.disabled(), review_chapter=_continuista_mal)


def test_agotada_la_reparacion_se_congela_el_ultimo_intento(
    permisivo: None, novela: Path, tmp_path: Path
) -> None:
    """D-136. Un S1 determinista que no se repara --Lean que nunca demuestra--
    congela el capitulo con `chapter.forced`: ni cuarentena ni replanificacion."""
    replans: list[int] = []

    def replan(outline: Outline, _a: int, _f: int, _u: Sequence[str], _r: Sequence[str]) -> Outline:
        replans.append(1)
        return outline

    traza = Trace(tmp_path / "t.jsonl")
    informe = _run(novela, traza, formal_check=_lean_mal, replan_act=replan)

    assert all(c.frozen for c in informe.chapters) and len(informe.chapters) == 2
    forzados = traza.records("chapter.forced")
    assert [r.fields["chapter"] for r in forzados] == [1, 2]
    assert all("check.formal" in str(r.fields["defects"]) for r in forzados)
    assert replans == []


# ------------------------------------------------------------------- escena


def test_agotada_la_escena_se_acepta_con_sus_defectos(
    permisivo: None, novela: Path, tmp_path: Path
) -> None:
    """D-136. Tres intentos y la escena se acepta: sin reespecificar ni escalar."""
    respecs: list[int] = []

    def respec(specs: Sequence[SceneSpec], _d: Sequence[Defect]) -> Sequence[SceneSpec]:
        respecs.append(1)
        return specs

    traza = Trace(tmp_path / "t.jsonl")
    informe = _run(
        novela,
        traza,
        verify_scene=lambda _s, texto: [_check_s1(texto)],
        respec=respec,
    )

    assert all(c.frozen for c in informe.chapters)
    assert respecs == []
    assert len(traza.records("scene.forced")) == 4
    assert all(s.attempts == 3 for c in informe.chapters for s in c.scenes)


# ------------------------------------------------------------ Archivero y Arbitro


def test_un_delta_siempre_vacio_congela_sin_hechos(
    permisivo: None, novela: Path, tmp_path: Path
) -> None:
    """D-136. Tres deltas vacios: se congela sin hechos en vez de `EmptyDeltaError`."""
    traza = Trace(tmp_path / "t.jsonl")
    informe = _run(novela, traza, extract_delta=lambda _s, _t, _e: DeltaProposal())

    assert all(c.frozen and c.events_applied == 0 for c in informe.chapters)
    motivos = [str(r.fields.get("reason")) for r in traza.records("process.defect")]
    assert any("delta vacio" in m for m in motivos)


def test_un_hecho_que_el_arbitro_rechaza_se_descarta_y_congela(
    permisivo: None, novela: Path, tmp_path: Path
) -> None:
    """D-136. El rechazo se descarta, sin retcon ni reparacion."""
    from canon.archivist.extract import ProposedEvent
    from canon.events.types import AttributeSet
    from commons.types.primitives import WorldTime
    from orchestration.test_loop import CITA

    def reescribe(specs: Sequence[SceneSpec], _t: Sequence[str], _e: object) -> DeltaProposal:
        # El capitulo 2 afirma algo sobre el dia 1, que el brief ya fijo.
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

    reparaciones: list[int] = []

    def repara(_s: SceneSpec, texto: str, _d: Sequence[Defect]) -> str:
        reparaciones.append(1)
        return texto

    traza = Trace(tmp_path / "t.jsonl")
    informe = _run(novela, traza, extract_delta=reescribe, repair_scene=repara)

    assert all(c.frozen for c in informe.chapters)
    assert reparaciones == []
    assert len(informe.chapters[1].rejected_facts) == 1
    assert informe.chapters[1].events_applied == 0
    assert traza.records("arbitration"), "el Arbitro llego a rechazar el hecho"
    assert any(r.fields.get("agent") == "arbitro" for r in traza.records("process.defect"))


# ---------------------------------------------------------- escaleta y tramo


def test_una_escaleta_fuera_de_rango_arranca(permisivo: None, novela: Path) -> None:
    """D-136. Los defectos de rango no bloquean la escaleta."""
    corta = _outline()
    corta = corta.model_copy(
        update={"scenes": tuple(s.model_copy(update={"target_words": 300}) for s in corta.scenes)}
    )
    informe = run(
        novela,
        _brief(),
        _engine(plan_outline=lambda _b, _c, _d: corta),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    assert all(c.frozen for c in informe.chapters)


def test_la_misma_escaleta_fuera_de_rango_para_con_el_perfil_estricto(novela: Path) -> None:
    corta = _outline()
    corta = corta.model_copy(
        update={"scenes": tuple(s.model_copy(update={"target_words": 300}) for s in corta.scenes)}
    )
    with pytest.raises(RunAbortedError, match="verificacion estructural"):
        run(
            novela,
            _brief(),
            _engine(plan_outline=lambda _b, _c, _d: corta),
            novel_id="p",
            chapters=2,
            specs_for=_specs,
        )


def _duplicada() -> Outline:
    """Una escaleta con un defecto duro, `escena-duplicada`."""
    base = _outline()
    return base.model_copy(update={"scenes": (*base.scenes, base.scenes[-1])})


def test_agotada_la_replanificacion_se_conserva_la_escaleta(tmp_path: Path) -> None:
    """D-136. Sin cuarto nivel, pero sin abortar: `replan.kept` y la vigente."""
    traza = Trace(tmp_path / "t.jsonl")
    vigente = _outline()
    motor = _engine(replan_act=lambda _o, _a, _f, _u, _r: _duplicada())

    nueva = loop._replan(
        vigente, motor, 2, 2, (), ["motivo"], traza, word_range=(1, 10_000), profile=BREVE
    )
    assert nueva is vigente
    [kept] = traza.records("replan.kept")
    assert kept.fields["act"] == 2 and "escena-duplicada" in kept.fields["defects"]  # type: ignore[operator]

    with pytest.raises(RunAbortedError, match="verificacion estructural"):
        loop._replan(
            vigente, motor, 2, 2, (), ["motivo"], traza, word_range=(1, 10_000), profile=NOVELA
        )


def test_la_replanificacion_de_la_cuarentena_usa_el_perfil_de_la_obra(
    novela: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RF-274, D-129. La cuarentena replanifica contra el perfil y el rango del
    brief, como las otras dos replanificaciones: contra `novela` por defecto, una
    obra `breve` no pasaria nunca."""
    vistos: list[dict[str, object]] = []
    original = loop._replan

    def espia(*args: object, **kwargs: object) -> Outline:
        vistos.append(kwargs)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(loop, "_replan", espia)
    with pytest.raises(RunAbortedError):
        _run(novela, Trace.disabled(), review_chapter=_continuista_mal)

    assert vistos, "la escalera llego a replanificar el tramo"
    assert vistos[0]["profile"] == _brief().profile()
    assert vistos[0]["word_range"] == _brief().word_range()


# ------------------------------------------------------------------- cierre


def test_la_obra_cierra_con_lo_pendiente_en_el_motivo(
    permisivo: None, novela: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-136. Con todo congelado cierra; lo que la condicion estricta echaria en
    falta va en el motivo."""
    corta = _outline()
    corta = corta.model_copy(
        update={"scenes": tuple(s.model_copy(update={"target_words": 300}) for s in corta.scenes)}
    )
    informe = run(
        novela,
        _brief(),
        _engine(plan_outline=lambda _b, _c, _d: corta),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    assert informe.closed
    assert informe.reason.startswith("pendiente:")
    assert "permisivo" not in informe.reason
    assert "fuera del rango" in informe.reason


# ----------------------------------------------------------- juez del motor


def test_una_cita_del_jurado_que_no_ancla_no_gasta_otra_llamada(
    permisivo: None, tmp_path: Path
) -> None:
    """D-136. Con el motor real y un juez que recorta sus citas: sin reintentos
    por cita, la cita se descarta como `process.defect` y la obra cierra."""
    from commons.tokens.counter import TokenCounter
    from commons.tokens.factors import ModelFactors
    from orchestration.admission import Admission
    from orchestration.engine import Composer, specs_provider
    from orchestration.test_engine import _brief as brief_motor
    from orchestration.test_engine import _Embedder as EmbedderMotor
    from orchestration.test_engine import _SloppyJudgePort

    path = tmp_path / "n.sqlite"
    create_novel(path, brief_motor())
    traza = Trace(tmp_path / "n.trace.jsonl")
    factores = ModelFactors()
    factores.set("haiku", 1.35)
    c = Composer(
        port=_SloppyJudgePort(),
        path=path,
        brief=brief_motor(),
        embedder=EmbedderMotor(),
        counter=TokenCounter(factores),
        model_id="haiku",
        trace=traza,
        admission=Admission(trace=traza),
    )
    informe = run(
        path,
        brief_motor(),
        c.engine(),
        novel_id="p",
        chapters=2,
        specs_for=specs_provider(c),
        trace=traza,
    )
    assert informe.closed, informe.reason
    reintentos = [r for r in traza.records("retry") if "sin anclar" in str(r.fields.get("reason"))]
    assert reintentos == []
    assert all(ch.frozen for ch in informe.chapters)


def test_una_escaleta_con_los_dos_arcos_en_la_misma_escena_arranca(
    permisivo: None, novela: Path
) -> None:
    """D-136. `doble-arco-colapsado` es calidad narrativa: en modo permisivo no
    bloquea. Es lo que paro la primera tirada `prueba` con modelo real: con 3
    escenas, el Arquitecto resolvio los dos arcos en la ultima."""
    colapsada = _outline()
    comp, intern = colapsada.arcs
    colapsada = colapsada.model_copy(
        update={
            "arcs": (comp, intern.model_copy(update={"resolution_scene": comp.resolution_scene}))
        }
    )
    informe = run(
        novela,
        _brief(),
        _engine(plan_outline=lambda _b, _c, _d: colapsada),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
    )
    assert all(c.frozen for c in informe.chapters)


def test_una_escaleta_con_una_escena_duplicada_sigue_parando(permisivo: None, novela: Path) -> None:
    """D-136. Lo estructural sigue bloqueando tambien en modo permisivo."""
    with pytest.raises(RunAbortedError, match="escena-duplicada"):
        run(
            novela,
            _brief(),
            _engine(plan_outline=lambda _b, _c, _d: _duplicada()),
            novel_id="p",
            chapters=2,
            specs_for=_specs,
        )


# ------------------------------------------------------ elenco fuera del canon


def test_un_elenco_con_una_entidad_inventada_no_tumba_la_congelacion(
    novela: Path, tmp_path: Path
) -> None:
    """D-140. `prose_scene_character` apunta a `entity`: lo que el elenco nombre
    sin existir se queda fuera del indice con su registro, y el capitulo congela.
    Es lo que paro la tirada `corta` del 2026-09-24 con `FOREIGN KEY constraint
    failed`. Vale tambien en el perfil estricto: es un choque, no una puerta."""
    from planning.scene_spec.spec import from_entry

    def specs(outline: Outline, numero: int) -> Sequence[SceneSpec]:
        return [
            from_entry(
                e,
                place="vestuario",
                cast=("marcos", "tripulacion"),
                beats=("entra", "descubre"),
                objective="saber",
                obstacle="nadie habla",
                ends_with="sale sin saber",
            )
            for e in outline.chapters().get(numero, [])
        ]

    traza = Trace(tmp_path / "t.jsonl")
    informe = run(
        novela, _brief(), _engine(), novel_id="p", chapters=2, specs_for=specs, trace=traza
    )

    assert all(c.frozen for c in informe.chapters)
    from canon.db import connection

    with connection.reader(novela) as con:
        presentes = {
            r["entity_id"] for r in con.execute("SELECT entity_id FROM prose_scene_character")
        }
    assert presentes == {"marcos"}
    avisos = [r for r in traza.records("process.defect") if r.fields.get("agent") == "planificador"]
    assert avisos and all(r.fields["entities"] == ["tripulacion"] for r in avisos)
