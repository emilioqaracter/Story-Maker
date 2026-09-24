"""El bucle. Del brief al cierre de obra, sin intervencion.

RF-13, RF-18, RF-19, RF-22, RF-23, RF-107, RNF-01 a RNF-03. `architecture.md`
§7.1 a §7.3.

Encadena lo que los tramos anteriores construyeron:

    brief -> escaleta -> [por capitulo: especificaciones -> escenas ->
             Continuista + examen -> reparacion -> delta + arbitraje ->
             congelacion -> puerta de acto] -> condicion de cierre

**Ningun punto espera a nadie.** Cuando algo falla, la escalera de reintentos
decide: reintentar la escena, reescribir su especificacion, rehacer el
capitulo, replanificar el tramo o recalcular el arco. No existe "pendiente de
aprobacion".

Lo que este modulo NO hace, y conviene saberlo antes de leerlo: no decide nada
por su cuenta. Los umbrales son de `retries` y de `verification/gates`, las
puertas de `planning` y `verification`, la escritura de `canon`. Aqui solo esta
el orden.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import JsonValue

from canon.arbiter import entries, refreeze
from canon.arbiter import retcon as retcon_rules
from canon.archivist import proscription
from canon.archivist.extract import DeltaProposal, EmptyDeltaError, quotes_by_event, to_events
from canon.brief import Brief, load_brief
from canon.db import connection
from canon.freeze import rows as freeze_rows
from canon.freeze.freeze import PreparedChapter, SceneToFreeze, commit_chapter, prepare
from canon.skills import read
from canon.skills.read import WorldState
from canon.summaries import levels
from commons.tracing.trace import Trace
from commons.types.primitives import Defect
from commons.types.scene import SceneSpec
from generation.sports.simulate import MatchResult
from generation.writer import drafts
from orchestration.checkpoint import (
    ResumePoint,
    load,
    load_outline,
    save,
    save_budget,
    save_outline,
)
from orchestration.retries import (
    ARC_REPLANS,
    CHAPTER_ATTEMPTS,
    SCENE_ATTEMPTS,
    Action,
    Budget,
    Level,
    may_start_chapter,
    on_failure,
)
from planning.act_gate.gate import check_act, closes_an_act, replan_target, tension_conforms
from planning.ledger.setups import debt
from planning.outline.arcs import arcs_closed_by, chapters_of_arc
from planning.outline.check import OutlineDefect
from planning.outline.check import check as check_outline
from planning.outline.types import NOVELA, LengthProfile, Outline
from supervision import metrics as health_metrics
from supervision.prompts import HealthVerdict, clamp
from verification.checks import forbidden
from verification.checks.deterministic import check_chapter_length
from verification.continuity.review import Anchored, scene_of, scene_offsets
from verification.gates import chapter_gate, scene_gate
from verification.jury.verdict import JuryVerdict
from verification.quiz import build as quiz_build
from verification.quiz import grade as quiz_grade
from verification.quiz.build import Question
from verification.repair.targeted import evaluate
from verification.style import drift as style_drift
from verification.style.fingerprint import Fingerprint

SEPARATOR = "\n\n"


class RunAbortedError(RuntimeError):
    """La tirada no puede continuar.

    Solo se llega aqui cuando se agota el ultimo peldano de la escalera: el
    recalculo del arco. No es "esperar a alguien", es haber probado todo lo que
    el diseno contempla.
    """


@dataclass
class SceneResult:
    spec: SceneSpec
    text: str
    defects: list[Defect] = field(default_factory=list)
    attempts: int = 1
    match: MatchResult | None = None
    repairs: int = 0

    @property
    def blocking(self) -> bool:
        """RF-22. La puerta de escena es cero defectos graves."""
        return not scene_gate(self.defects).passed


@dataclass
class ChapterResult:
    number: int
    scenes: list[SceneResult]
    frozen: bool = False
    #: RF-60. Hechos del delta que el canon congelado no admitio. Cada uno dejo
    #: un defecto S1 con cita y paso por el bucle de reparacion.
    rejected_facts: list[Defect] = field(default_factory=list)
    events_applied: int = 0
    chapter_attempts: int = 1
    discarded_citations: int = 0
    #: T20, T21. El veredicto del Jurado y la huella del capitulo aprobado.
    jury: JuryVerdict | None = None
    fingerprint: Fingerprint | None = None
    style_reverted: bool = False

    @property
    def words(self) -> int:
        return sum(len(s.text.split()) for s in self.scenes)

    @property
    def texts(self) -> list[str]:
        return [s.text for s in self.scenes]

    @property
    def specs(self) -> list[SceneSpec]:
        return [s.spec for s in self.scenes]


@dataclass
class RunReport:
    """Lo que paso en una tirada. Es lo que se traza y lo que se lee despues."""

    novel_id: str
    chapters: list[ChapterResult] = field(default_factory=list)
    closed: bool = False
    reason: str = ""

    @property
    def words(self) -> int:
        return sum(c.words for c in self.chapters)


#: Firmas de las piezas que el bucle usa. Se inyectan en vez de importarse para
#: que el bucle se pueda ejercitar entero sin gastar una sola llamada de modelo:
#: un doble deterministico ocupa su sitio y las puertas siguen siendo las mismas.
WriteScene = Callable[[SceneSpec, Sequence[Defect]], str]
VerifyScene = Callable[[SceneSpec, str], list[Defect]]
SummarizeScene = Callable[[SceneSpec, str], str]
SummarizeChapter = Callable[[Sequence[str]], str]
SummarizeHigher = Callable[[Sequence[str]], str]
ExtractDelta = Callable[[Sequence[SceneSpec], Sequence[str], WorldState], DeltaProposal]
ReplanAct = Callable[[Outline, int, int, Sequence[str], Sequence[str]], Outline]
Respec = Callable[[Sequence[SceneSpec], Sequence[Defect]], Sequence[SceneSpec]]
SimulateMatch = Callable[[SceneSpec], MatchResult]
NarrateMatch = Callable[[SceneSpec, MatchResult, Sequence[Defect]], str]
VerifyMatch = Callable[[SceneSpec, str, MatchResult], list[Defect]]
ReviewChapter = Callable[[Sequence[SceneSpec], Sequence[str]], Anchored]
AnswerQuiz = Callable[[str, Sequence[Question]], Sequence[str]]
RepairScene = Callable[[SceneSpec, str, Sequence[Defect]], str]
JudgeChapter = Callable[[Sequence[SceneSpec], Sequence[str]], JuryVerdict]
PolishChapter = Callable[[Sequence[SceneSpec], Sequence[str], Sequence[Defect]], Sequence[str]]
FingerprintOf = Callable[[str], Fingerprint]
GoldenCheck = Callable[[], float]
ProposeRetcon = Callable[[entries.Rejection, Sequence[str]], retcon_rules.RetconProposal]
RetconRewrite = Callable[
    [str, str, retcon_rules.RetconPlan], tuple[refreeze.RefrozenScene, Sequence[Defect]]
]
Supervise = Callable[[int, int, Outline, Sequence[freeze_rows.MetricRow]], HealthVerdict]


@dataclass(frozen=True)
class Engine:
    """Las piezas que necesitan un modelo detras, y las que lo rodean.

    Cada una es un agente de `architecture.md` §6 o la mitad determinista que
    lo acompana. El bucle no sabe cual es cual: solo sabe el orden en que se
    llaman y que hacer cuando una falla.
    """

    #: RF-27. El tercer argumento son los defectos del intento anterior.
    plan_outline: Callable[[Brief, int, Sequence[OutlineDefect]], Outline]
    replan_act: ReplanAct
    respec: Respec
    write_scene: WriteScene
    simulate_match: SimulateMatch
    narrate_match: NarrateMatch
    verify_scene: VerifyScene
    verify_match: VerifyMatch
    review_chapter: ReviewChapter
    answer_quiz: AnswerQuiz
    repair_scene: RepairScene
    summarize_scene: SummarizeScene
    summarize_chapter: SummarizeChapter
    summarize_arc: SummarizeHigher
    summarize_work: SummarizeHigher
    extract_delta: ExtractDelta
    embed: object
    judge_chapter: JudgeChapter
    polish_chapter: PolishChapter
    fingerprint: FingerprintOf
    golden_check: GoldenCheck
    supervise: Supervise
    propose_retcon: ProposeRetcon
    retcon_rewrite: RetconRewrite


def run(
    path: Path,
    brief: Brief,
    engine: Engine,
    *,
    novel_id: str,
    chapters: int,
    specs_for: Callable[[Outline, int], Sequence[SceneSpec]],
    trace: Trace | None = None,
    after_freeze: Callable[[], object] | None = None,
) -> RunReport:
    """Ejecuta la tirada completa.

    `specs_for` convierte el tramo de escaleta de un capitulo en
    especificaciones. Se inyecta porque el Planificador puede ser un modelo o
    una funcion deterministica segun lo que se este probando, y el bucle no
    tiene por que enterarse.

    `trace` es la traza de la tirada (RI-16). Toda decision del bucle queda en
    ella con su regla aplicada (RF-24).

    `after_freeze` corre tras cada capitulo congelado y al cerrar la obra: es
    donde el Orquestador aplica las enmiendas pendientes (`specs/srs-backend-v3.md`
    RF-223).
    """
    trace = trace or Trace.disabled()
    report = RunReport(novel_id=novel_id)
    _trace_forbidden_levels(path, brief, trace)
    try:
        congeladas, outline = _run_chapters(
            path, brief, engine, report, chapters, specs_for, trace, after_freeze
        )
    except RunAbortedError as exc:
        # RF-238: el motivo del aborto llega a quien encargo. RI-03 lee `reason`
        # del ultimo `work.close`; sin este registro, una tirada parada por el
        # guardarrail se veria como una que nunca termino.
        trace.emit("work.close", closed=False, reason=str(exc), words=report.words, aborted=True)
        raise

    report.closed, report.reason = _work_closes(outline, brief, report, congeladas, path)
    trace.emit("work.close", closed=report.closed, reason=report.reason, words=report.words)
    if after_freeze is not None:
        after_freeze()
    return report


def _run_chapters(
    path: Path,
    brief: Brief,
    engine: Engine,
    report: RunReport,
    chapters: int,
    specs_for: Callable[[Outline, int], Sequence[SceneSpec]],
    trace: Trace,
    after_freeze: Callable[[], object] | None,
) -> tuple[set[str], Outline]:
    """La escaleta y los capitulos, en orden. Devuelve lo congelado y la escaleta final.

    Reanudar es relanzar esto sobre el mismo fichero. Lo que la tirada sabia
    antes de caer lo lee del punto de reanudacion (`architecture.md` §7.4): el
    capitulo y la escena, los reintentos consumidos y la escaleta vigente.
    """
    # RD-10: hacia delante, en escritura. Un fichero de una version anterior del
    # esquema sube antes de que el punto escriba sus columnas nuevas.
    with connection.canon_writer(path):
        pass

    # R1. Reanudar sigue con la escaleta vigente, con sus replanificaciones. Solo
    # una tirada que aun no la tiene se la pide al Arquitecto.
    guardada = load_outline(path)
    if guardada is None:
        outline = _plan_with_gate(brief, engine, chapters=chapters, trace=trace)
        save_outline(path, outline.model_dump_json())
    else:
        outline = Outline.model_validate_json(guardada)
        trace.emit("outline.resumed", scenes=len(outline.scenes))

    punto = load(path) or ResumePoint(chapter=1)
    congeladas: set[str] = _frozen_scene_ids(path)

    for numero in range(punto.chapter, chapters + 1):
        # RF-107. No se empieza un capitulo con el anterior sin congelar: el
        # siguiente necesita su prosa literal y su estado del mundo, y sin
        # congelar no existe para el sistema.
        anterior_ok = numero == 1 or _chapter_frozen(path, numero - 1)
        if not may_start_chapter(previous_frozen=anterior_ok):
            raise RunAbortedError(
                f"el capitulo {numero - 1} no esta congelado; el {numero} no puede "
                "empezar porque necesita su prosa y su estado del mundo"
            )

        if _chapter_frozen(path, numero):
            # B1. La tirada cayo despues de congelarlo y antes de avanzar el
            # punto. Reescribirlo sustituiria prosa congelada y duplicaria su
            # delta en el registro: se sigue desde su puerta de acto.
            trace.emit("chapter.resumed", chapter=numero, frozen=True)
        else:
            # RF-18, §7.3: la escalera es por capitulo. Lo que el anterior
            # consumio no se le descuenta a este (medido en la tercera tirada
            # real: el capitulo 2 dio por agotada su primera escena al primer
            # fallo). Lo que este mismo capitulo gasto antes de una caida, si
            # (§7.4, B4): reanudar no regala una escalera.
            presupuesto = (
                Budget(chapter_attempts=punto.chapter_attempts, arc_replans=punto.arc_replans)
                if numero == punto.chapter
                else Budget()
            )
            capitulo, _presupuesto, outline = _write_chapter(
                path, outline, numero, engine, specs_for, presupuesto, trace
            )
            report.chapters.append(capitulo)
            congeladas |= {s.spec.identity.scene_id for s in capitulo.scenes}

        outline = _close_act_if_needed(outline, numero, congeladas, engine, brief, trace, path)
        outline = _supervise(path, outline, numero, chapters, engine, brief, trace)
        save_outline(path, outline.model_dump_json())
        # RF-134, T53. Cada cinco capitulos, o al cierre si el perfil lo pide.
        cada = levels.WORK_SUMMARY_EVERY
        if brief.profile().periodic_due(numero, last_chapter=chapters, every=cada):
            _golden_check(engine, numero, trace)
        save(path, ResumePoint(chapter=numero + 1))
        # `specs/srs-backend-v3.md` RF-223: las enmiendas pendientes se aplican
        # entre congelaciones, y el capitulo siguiente ya las ve.
        if after_freeze is not None:
            after_freeze()
    return congeladas, outline


def _trace_forbidden_levels(path: Path, brief: Brief, trace: Trace) -> None:
    """RF-239. Cuantas prohibidas hay por nivel, y que termino colapso en otro.

    Un termino del cliente que ya estaba en la lista global se guardo como
    global (D-91). Se dice aqui, al arrancar la tirada, porque la novela se crea
    antes de que exista su traza.
    """
    with connection.reader(path) as con:
        terminos = forbidden.read_terms(con)
    niveles = {forbidden.normalize(t.term): t.level for t in terminos}
    colapsos: list[JsonValue] = [
        f"{w.strip().lower()}: cliente -> {niveles[forbidden.normalize(w.strip().lower())]}"
        for w in brief.forbidden_words
        if niveles.get(forbidden.normalize(w.strip().lower()), "cliente") != "cliente"
    ]
    trace.emit(
        "guardrail.levels",
        levels={n: sum(1 for t in terminos if t.level == n) for n in forbidden.FORBIDDEN_LEVELS},
        collapsed=colapsos,
    )


def _emit_matches(
    trace: Trace,
    defects: Sequence[Defect],
    *,
    chapter: int,
    scene: int | None,
    attempt: int,
    decision: str,
    stage: str,
) -> None:
    """RF-240. Un `guardrail.match` por coincidencia de `check.forbidden`.

    `decision` es lo que el bucle hace con ella: `reintentar` la escena,
    `reparar` el capitulo o `abortar` la tirada. `stage` dice donde se vio.
    """
    for d in defects:
        hit = forbidden.describe(d)
        if hit is None:
            continue
        trace.emit(
            "guardrail.match",
            chapter=chapter,
            scene=scene,
            attempt=attempt,
            term=hit.term,
            level=hit.level,
            quote=d.evidence.quote,
            offset=d.evidence.offset,
            decision=decision,
            stage=stage,
        )


def _golden_check(engine: Engine, chapter: int, trace: Trace) -> None:
    """RF-134. Cada cinco capitulos, el Jurado contra el conjunto dorado.

    Por debajo del 90 % la senal pasa a alarma y la recoge el Supervisor. No
    detiene la tirada: mide si el juez sigue viendo, no juzga el capitulo.
    """
    from verification.jury.golden import DETECTION_FLOOR

    try:
        tasa = engine.golden_check()
    except Exception as exc:  # una comprobacion que no corre cuenta como fallida
        trace.emit("golden", chapter=chapter, rate=None, alarm=True, error=str(exc)[:200])
        return
    trace.emit("golden", chapter=chapter, rate=round(tasa, 3), alarm=tasa < DETECTION_FLOOR)


def _json_list(items: Sequence[str]) -> list[JsonValue]:
    return list(items)


def _frozen_scene_ids(path: Path) -> set[str]:
    with connection.reader(path) as con:
        return {r["id"] for r in con.execute("SELECT id FROM prose_scene")}


def _chapter_frozen(path: Path, chapter: int) -> bool:
    with connection.reader(path) as con:
        row = con.execute(
            "SELECT count(*) AS n FROM prose_scene WHERE chapter = ?", (chapter,)
        ).fetchone()
    return bool(row["n"])


# ------------------------------------------------------------------ escaleta


def _plan_with_gate(brief: Brief, engine: Engine, *, chapters: int, trace: Trace) -> Outline:
    """RF-25, RF-27. La escaleta vuelve al Arquitecto hasta que pasa.

    El verificador es determinista, asi que los defectos se le devuelven tal
    cual: decirle "esta mal" gastaria un intento sin darle con que corregir.
    """
    presupuesto = Budget()
    defectos_previos: list[OutlineDefect] = []
    while True:
        outline = engine.plan_outline(brief, chapters, defectos_previos)
        defectos = check_outline(outline, word_range=brief.word_range(), profile=brief.profile())
        trace.emit(
            "outline.check",
            defects=[d.kind for d in defectos],
            passed=not defectos,
            # La escaleta no es canon (RI-17) y es parte del estado de la tirada:
            # `evals/` la lee de aqui para construir el conjunto dorado.
            # Tambien la rechazada, con el motivo de cada defecto: diagnosticar
            # una escaleta que no pasa sin verla es adivinar.
            outline=outline.model_dump_json(),
            messages=_json_list([f"{d.kind} [{d.where}]: {d.message}" for d in defectos][:10]),
        )
        if not defectos:
            return outline

        # Acumulados, no solo los del ultimo intento: con solo los ultimos, el
        # Arquitecto arregla uno y reintroduce el anterior (medido en la
        # primera tirada real). Se deduplican por tipo y sitio.
        vistos = {(d.kind, d.where) for d in defectos_previos}
        defectos_previos = [
            *defectos_previos,
            *(d for d in defectos if (d.kind, d.where) not in vistos),
        ]
        decision = on_failure(presupuesto, level=Level.ARC)
        presupuesto = decision.budget
        trace.emit(
            "retry", level=str(decision.level), action=str(decision.action), reason=decision.reason
        )
        # RF-18: la escaleta tiene los mismos intentos que cualquier
        # replanificacion de arco (`_replan`), no un numero propio.
        if decision.action is Action.RECOMPUTE_ARC and presupuesto.arc_replans > ARC_REPLANS:
            raise RunAbortedError(
                "la escaleta no pasa la verificacion estructural tras varios "
                f"intentos: {[d.kind for d in defectos]}"
            )


# ------------------------------------------------------------------ capitulo


def _write_chapter(
    path: Path,
    outline: Outline,
    numero: int,
    engine: Engine,
    specs_for: Callable[[Outline, int], Sequence[SceneSpec]],
    presupuesto: Budget,
    trace: Trace,
) -> tuple[ChapterResult, Budget, Outline]:
    """Escribe, verifica, repara y congela un capitulo. La escalera entera.

    Las escenas van **en serie** y no en paralelo: el paquete del Escritor lleva
    la prosa literal de la anterior, asi que escribir la n exige tener escrita
    la n-1 (RF-45).

    Cuando el capitulo no pasa su puerta y la reparacion no lo arregla, la
    cuarentena lo **rehace de inmediato** (D-26): con especificaciones mas
    estrictas la primera vez, con el tramo replanificado la segunda. Nunca se
    salta al siguiente.
    """
    specs = list(specs_for(outline, numero))
    intento_capitulo = 0
    # RF-20. Las escenas ya cerradas de este capitulo, si la tirada se
    # interrumpio a mitad, se reutilizan en vez de regenerarse.
    cerradas = {d.scene_number: d.text for d in drafts.load_drafts(path, chapter=numero)}

    def guarda_presupuesto(b: Budget) -> None:
        # §7.4, B4. En cuanto se gasta un peldano de capitulo o de tramo, no al
        # cerrar la escena: una caida entre medias lo devolveria.
        save_budget(
            path, chapter=numero, chapter_attempts=b.chapter_attempts, arc_replans=b.arc_replans
        )

    while True:
        intento_capitulo += 1
        resultados: list[SceneResult] = []
        # PRO-I2, B3. El punto solo cubre escenas que pasaron su puerta, y todas
        # las anteriores a el tambien: tras una escena que agoto su escalera
        # sin pasar, este pase ya no avanza el punto.
        cerrado_hasta_aqui = True
        for spec in specs:
            ordinal = spec.identity.ordinal
            if ordinal in cerradas and intento_capitulo == 1:
                resultado = SceneResult(spec=spec, text=cerradas[ordinal])
                trace.emit("scene.resumed", chapter=numero, scene=ordinal)
            else:
                resultado, presupuesto = _write_scene(
                    spec, engine, presupuesto, trace, on_budget=guarda_presupuesto
                )
            resultados.append(resultado)
            cerrado_hasta_aqui = cerrado_hasta_aqui and not resultado.blocking
            if not cerrado_hasta_aqui:
                continue
            # El punto de reanudacion se escribe al cerrar CADA escena, con su
            # borrador: una caida pierde como mucho la que estaba en curso.
            drafts.save_draft(
                path,
                chapter=numero,
                scene_number=ordinal,
                attempt=resultado.attempts,
                text=resultado.text,
            )
            save(
                path,
                ResumePoint(
                    chapter=numero,
                    last_closed_scene=ordinal,
                    chapter_attempts=presupuesto.chapter_attempts,
                    arc_replans=presupuesto.arc_replans,
                ),
            )

        capitulo = ChapterResult(
            number=numero, scenes=resultados, chapter_attempts=intento_capitulo
        )
        aprobado, presupuesto, defectos = _approve_chapter(
            path,
            capitulo,
            engine,
            presupuesto,
            trace,
            frozenset(s.payoff_scene for s in outline.setups),
        )
        if aprobado is not None:
            proposal, validacion = aprobado
            _freeze(path, capitulo, engine, validacion, trace, outline)
            del proposal
            capitulo.frozen = True
            trace.emit(
                "chapter.frozen",
                chapter=numero,
                scenes=len(resultados),
                words=capitulo.words,
                events_applied=capitulo.events_applied,
                rejected_facts=len(capitulo.rejected_facts),
                attempts=intento_capitulo,
            )
            return capitulo, presupuesto, outline

        # Cuarentena de capitulo. Que se hace depende del peldano. Si el arco ya
        # se replanifico las veces que la escalera da, no hay cuarto nivel.
        if presupuesto.arc_replans >= ARC_REPLANS:
            decision = on_failure(presupuesto, level=Level.ARC)
        else:
            decision = on_failure(presupuesto, level=Level.CHAPTER)
        presupuesto = decision.budget
        trace.emit(
            "retry", level=str(decision.level), action=str(decision.action), reason=decision.reason
        )
        # D-26: la cuarentena rehace el capitulo entero, asi que ninguna escena
        # del pase que se descarta sigue cerrada. El punto vuelve al principio
        # del capitulo con el peldano ya gastado (§7.4): una caida a partir de
        # aqui reanuda el capitulo rehecho, no el que no paso.
        save(
            path,
            ResumePoint(
                chapter=numero,
                chapter_attempts=presupuesto.chapter_attempts,
                arc_replans=presupuesto.arc_replans,
            ),
        )
        # RF-238. Las prohibidas van delante: si la tirada se para, su motivo
        # nombra `check.forbidden`, el termino y el nivel aunque haya mas.
        ordenados = sorted(defectos, key=lambda d: d.kind != forbidden.KIND)
        motivos = list(dict.fromkeys(f"{d.kind}: {d.rule}" for d in ordenados))[:8]
        match decision.action:
            case Action.QUARANTINE_AND_RESPEC:
                specs = list(engine.respec(specs, defectos))
            case Action.QUARANTINE_AND_REPLAN:
                outline = _replan(
                    outline, engine, _act_of(outline, numero), numero, (), motivos, trace
                )
                # R1. La escaleta replanificada es la vigente desde ya.
                save_outline(path, outline.model_dump_json())
                specs = list(specs_for(outline, numero))
            case _:
                _emit_matches(
                    trace,
                    defectos,
                    chapter=numero,
                    scene=None,
                    attempt=intento_capitulo,
                    decision="abortar",
                    stage="capitulo",
                )
                raise RunAbortedError(
                    f"el capitulo {numero} no pasa sus puertas tras rehacerlo y replanificar "
                    f"su tramo: {motivos}"
                )


def _act_of(outline: Outline, chapter: int) -> int:
    actos = [s.act for s in outline.scenes if s.chapter == chapter]
    return min(actos) if actos else 1


def _write_scene(
    spec: SceneSpec,
    engine: Engine,
    presupuesto: Budget,
    trace: Trace,
    *,
    on_budget: Callable[[Budget], None] | None = None,
) -> tuple[SceneResult, Budget]:
    """RF-22. Escribe hasta que pase la puerta de escena o se agote la escalera.

    Una escena de encuentro se resuelve **antes** de narrarse (RF-42): el motor
    de reglas decide y el modelo dramatiza.

    Agotados los tres intentos, la escena vuelve al Planificador con una
    especificacion mas estricta y se regenera **en su sitio** (RF-19). Cuando
    tampoco eso basta, sube al nivel de capitulo.
    """
    intento = 0
    # Tres intentos por escena, no por capitulo: la escena que empieza no hereda
    # los de la anterior.
    presupuesto = presupuesto.model_copy(update={"scene_attempts": 0})
    # El reintento lleva el defecto y su evidencia (`architecture.md` §4.1).
    # Una especificacion nueva empieza limpia: sus defectos eran de la vieja.
    anteriores: list[Defect] = []
    while True:
        intento += 1
        match_result: MatchResult | None = None
        if spec.is_match:
            match_result = engine.simulate_match(spec)
            texto = engine.narrate_match(spec, match_result, anteriores)
            defectos = engine.verify_match(spec, texto, match_result)
        else:
            texto = engine.write_scene(spec, anteriores)
            defectos = engine.verify_scene(spec, texto)
        resultado = SceneResult(
            spec=spec, text=texto, defects=defectos, attempts=intento, match=match_result
        )
        trace.emit(
            "scene.attempt",
            chapter=spec.identity.chapter,
            scene=spec.identity.ordinal,
            attempt=intento,
            words=len(texto.split()),
            defects=[f"{d.kind}:{d.severity}" for d in defectos],
            passed=not resultado.blocking,
            is_match=spec.is_match,
        )

        if not resultado.blocking:
            return resultado, presupuesto

        decision = on_failure(presupuesto, level=Level.SCENE)
        presupuesto = decision.budget
        trace.emit(
            "retry", level=str(decision.level), action=str(decision.action), reason=decision.reason
        )
        # RF-238, RF-240. La escena con una prohibida vuelve a escribirse: con
        # el defecto y su cita en el reintento, o con la especificacion nueva,
        # o subiendo al capitulo. En los tres casos se reintenta.
        _emit_matches(
            trace,
            defectos,
            chapter=spec.identity.chapter,
            scene=spec.identity.ordinal,
            attempt=intento,
            decision="reintentar",
            stage="escena",
        )
        if decision.action is Action.RETRY:
            anteriores = list(defectos)
            continue
        # Agotada la escena se gasta un intento de capitulo: quien llama lo
        # guarda en el punto de reanudacion antes de seguir (§7.4).
        if on_budget is not None:
            on_budget(presupuesto)
        if presupuesto.chapter_attempts >= CHAPTER_ATTEMPTS:
            # La escena ya se reespecifico y sigue sin pasar: el problema esta
            # mas arriba. Se devuelve con sus defectos y el capitulo escala.
            return resultado, presupuesto
        spec = next(iter(engine.respec([spec], defectos)))
        anteriores = []
        trace.emit("respec", chapter=spec.identity.chapter, scene=spec.identity.ordinal)


# ------------------------------------------------------------ puerta de capitulo


def _approve_chapter(
    path: Path,
    capitulo: ChapterResult,
    engine: Engine,
    presupuesto: Budget,
    trace: Trace,
    payoffs: frozenset[str] = frozenset(),
) -> tuple[tuple[DeltaProposal, entries.DeltaValidation] | None, Budget, list[Defect]]:
    """La puerta de capitulo con su bucle de reparacion (RF-22, RF-54, RF-60).

    Orden: escenas ya pasaron su puerta; Continuista mas examen de comprension;
    si pasa, el Archivero extrae el delta y el Arbitro lo valida; un hecho
    rechazado es un S1 que vuelve a la reparacion. Solo con todo limpio se
    devuelve lo necesario para congelar.

    Cada pase de reparacion consume un intento de escena de la escalera; al
    agotarse, devuelve `None` y el capitulo entra en cuarentena.
    """
    if any(s.blocking for s in capitulo.scenes):
        return None, presupuesto, [d for s in capitulo.scenes for d in s.defects]

    nombres = _names(path)
    preguntas = quiz_build.build(capitulo.specs, nombres)
    # Los pases de reparacion tienen sus tres intentos, no los que dejo la
    # ultima escena escrita.
    presupuesto = presupuesto.model_copy(update={"scene_attempts": 0})

    while True:
        texto_capitulo = SEPARATOR.join(capitulo.texts)
        anclados = engine.review_chapter(capitulo.specs, capitulo.texts)
        capitulo.discarded_citations += len(anclados.discarded)
        for cita in anclados.discarded:
            trace.emit(
                "process.defect", agent="continuista", chapter=capitulo.number, quote=cita[:80]
            )

        respuestas = engine.answer_quiz(texto_capitulo, preguntas) if preguntas else []
        s2_examen = quiz_grade.grade(
            preguntas,
            respuestas,
            scene_texts={s.spec.identity.scene_id: s.text for s in capitulo.scenes},
        )
        trace.emit("quiz", chapter=capitulo.number, questions=len(preguntas), wrong=len(s2_examen))

        # RF-232, D-97. Lo escrito, no lo planificado, frente a EST-07. Es S2 de
        # `check.format` y cuenta en el maximo de 2 S2 de esta puerta, sin
        # umbral propio.
        longitud = check_chapter_length(
            texto_capitulo, word_range=load_brief(path).profile().chapter_words
        )
        defectos: list[Defect] = [*anclados.defects, *s2_examen, *longitud]
        puerta = chapter_gate(defectos)
        trace.emit(
            "chapter.gate",
            chapter=capitulo.number,
            passed=puerta.passed,
            s1=puerta.s1,
            s2=puerta.s2,
            reason=puerta.reason(),
            # Que marco la puerta, con su cita: sin esto una tirada que no pasa
            # no se puede diagnosticar leyendo la traza (§11).
            defects=[
                f"{d.severity}:{d.kind}: {d.rule[:120]} «{d.evidence.quote[:60]}»"
                for d in defectos
                if d.severity.value in ("S1", "S2")
            ],
        )

        if puerta.passed:
            # RF-132. La puerta recupera su componente de voz: el Jurado.
            jurado = engine.judge_chapter(capitulo.specs, capitulo.texts)
            capitulo.jury = jurado
            for instancia, cita in jurado.discarded:
                trace.emit(
                    "process.defect", agent=instancia, chapter=capitulo.number, quote=cita[:80]
                )
            trace.emit(
                "jury",
                chapter=capitulo.number,
                passed=jurado.passed,
                rounds=jurado.rounds,
                levels={d.dimension.value: d.level for d in jurado.dimensions},
                spreads={d.dimension.value: d.spread for d in jurado.dimensions},
                discarded=len(jurado.discarded),
                # RI-36: cada veredicto de juez con su instancia y sus puntuaciones.
                # Las citas descartadas ya van, una a una, como `process.defect`.
                scores=[
                    f"{s.instance}:{s.dimension.value}:{s.level}:{s.scene}"
                    for d in jurado.dimensions
                    for s in d.scores
                ],
            )
            if not jurado.passed:
                defectos = jurado.defects()
            else:
                _polish(path, capitulo, engine, trace)
                proposal, validacion = _extract_and_validate(path, capitulo, engine, trace, payoffs)
                if validacion.clean:
                    # RF-236, D-90. La segunda red, sobre el capitulo entero y
                    # despues de reparaciones y pase de estilo: entre esto y
                    # `_freeze` ya no cambia ni una letra. Una coincidencia aqui
                    # es un S1 que vuelve a reparacion, nunca una congelacion.
                    defectos = _forbidden_before_freeze(path, capitulo, trace)
                    if not defectos:
                        return (proposal, validacion), presupuesto, []
                else:
                    defectos = [r.defect for r in validacion.rejections]
                    capitulo.rejected_facts.extend(defectos)

        presupuesto, agotado = _repair_pass(capitulo, defectos, engine, presupuesto, trace)
        if agotado:
            return None, presupuesto, defectos


def _forbidden_before_freeze(path: Path, capitulo: ChapterResult, trace: Trace) -> list[Defect]:
    """`check.forbidden` sobre el capitulo unido, con citas en el capitulo.

    Coge lo que `verify_scene` no pudo ver: un borrador reanudado, que no se
    reverifica, o un termino de varias palabras partido entre dos escenas.
    """
    with connection.reader(path) as con:
        terminos = forbidden.read_terms(con)
    texto = SEPARATOR.join(capitulo.texts)
    defectos = forbidden.check_forbidden(texto, terms=terminos)
    offsets = scene_offsets(capitulo.texts, SEPARATOR)
    for d in defectos:
        escena = capitulo.scenes[_scene_index_for(d, capitulo, offsets)]
        _emit_matches(
            trace,
            [d],
            chapter=capitulo.number,
            scene=escena.spec.identity.ordinal,
            attempt=capitulo.chapter_attempts,
            decision="reparar",
            stage="congelacion",
        )
    return defectos


def _polish(path: Path, capitulo: ChapterResult, engine: Engine, trace: Trace) -> None:
    """RF-139 a RF-142. El pase de estilo, su reverificacion y la huella.

    El capitulo pulido vuelve al Continuista y a los verificadores: si el pase
    abre un S1 que no estaba, se revierte entero (RF-141, RF-54). Despues se mide
    la huella; fuera de tolerancia frente a la referencia, el Estilista tiene
    una segunda pasada, y si persiste se congela igual y la deriva queda en la
    traza para el Supervisor (RF-142), que es quien puede actuar sobre el tramo.
    """
    with connection.reader(path) as con:
        referencia = style_drift.reference([_as_fp(r) for r in freeze_rows.read_fingerprints(con)])

    for pase in (1, 2):
        repeticiones = [
            d for s in capitulo.scenes for d in s.defects if d.kind == "check.repetition"
        ]
        pulidos = list(engine.polish_chapter(capitulo.specs, capitulo.texts, repeticiones))
        nuevos_s1 = _new_s1_after(capitulo, pulidos, engine)
        trace.emit(
            "style.polish",
            chapter=capitulo.number,
            attempt=pase,
            reverted=bool(nuevos_s1),
            new_s1=[f"{d.kind}: {d.rule}"[:120] for d in nuevos_s1],
        )
        if nuevos_s1:
            # RF-240. Un pase de estilo que mete una prohibida se revierte
            # entero; el capitulo sigue por la reparacion con el texto previo.
            _emit_matches(
                trace,
                nuevos_s1,
                chapter=capitulo.number,
                scene=None,
                attempt=pase,
                decision="reparar",
                stage="estilo",
            )
            capitulo.style_reverted = True
            break
        for escena, texto in zip(capitulo.scenes, pulidos, strict=True):
            escena.text = texto
        huella = engine.fingerprint(SEPARATOR.join(capitulo.texts))
        capitulo.fingerprint = huella
        if referencia is None:
            # RI-36: la huella de todo capitulo va a la traza, tambien de los
            # que forman la referencia y no tienen contra que desviarse.
            trace.emit(
                "style.fingerprint",
                chapter=capitulo.number,
                attempt=pase,
                deviation=None,
                out_of_tolerance=False,
                mean_sentence_len=round(huella.mean_sentence_len, 3),
                adj_noun_ratio=round(huella.adj_noun_ratio, 3),
                lexical_richness=round(huella.lexical_richness, 3),
            )
            break
        desviacion = style_drift.deviation(huella, referencia)
        trace.emit(
            "style.fingerprint",
            chapter=capitulo.number,
            attempt=pase,
            deviation=round(desviacion.max_abs, 3),
            out_of_tolerance=desviacion.out_of_tolerance,
            mean_sentence_len=round(huella.mean_sentence_len, 3),
            adj_noun_ratio=round(huella.adj_noun_ratio, 3),
            lexical_richness=round(huella.lexical_richness, 3),
        )
        if not desviacion.out_of_tolerance:
            break
    if capitulo.fingerprint is None:
        capitulo.fingerprint = engine.fingerprint(SEPARATOR.join(capitulo.texts))


def _new_s1_after(capitulo: ChapterResult, pulidos: Sequence[str], engine: Engine) -> list[Defect]:
    """Los S1 que el pase de estilo abre y que antes no estaban."""
    antes = {
        (d.kind, d.rule) for s in capitulo.scenes for d in s.defects if d.severity.value == "S1"
    }
    nuevos: list[Defect] = []
    for escena, texto in zip(capitulo.scenes, pulidos, strict=True):
        despues = (
            engine.verify_match(escena.spec, texto, escena.match)
            if escena.match is not None
            else engine.verify_scene(escena.spec, texto)
        )
        nuevos += [d for d in despues if d.severity.value == "S1" and (d.kind, d.rule) not in antes]
    revision = engine.review_chapter(capitulo.specs, pulidos)
    nuevos += [d for d in revision.defects if d.severity.value == "S1"]
    return nuevos


def _as_fp(row: freeze_rows.FingerprintRow) -> Fingerprint:
    return Fingerprint(
        mean_sentence_len=row.mean_sentence_len,
        var_sentence_len=row.var_sentence_len,
        adj_noun_ratio=row.adj_noun_ratio,
        top_ngrams=row.top_ngrams,
        lexical_richness=row.lexical_richness,
    )


def _verdict_rows(capitulo: ChapterResult) -> list[freeze_rows.SceneVerdictRow]:
    """RD-20. Cada puntuacion anclada, en la escena que cita."""
    if capitulo.jury is None:
        return []
    out: list[freeze_rows.SceneVerdictRow] = []
    for d in capitulo.jury.dimensions:
        for s in d.scores:
            out.append(
                freeze_rows.SceneVerdictRow(
                    scene_id=s.scene,
                    dimension=d.dimension.value,
                    level=d.level,
                    dispersion=d.spread,
                    valid=d.valid,
                    instance=s.instance,
                    seed=s.seed,
                    score=s.level,
                    quote=s.evidence.quote,
                    offset=s.evidence.offset,
                )
            )
    return out


def _fingerprint_row(path: Path, capitulo: ChapterResult) -> freeze_rows.FingerprintRow | None:
    """RD-21. La huella, marcada como referencia en los tres primeros capitulos."""
    if capitulo.fingerprint is None:
        return None
    with connection.reader(path) as con:
        previas = freeze_rows.read_fingerprints(con)
    referencia = style_drift.reference([_as_fp(r) for r in previas])
    desviacion = (
        style_drift.deviation(capitulo.fingerprint, referencia).max_abs if referencia else None
    )
    fp = capitulo.fingerprint
    return freeze_rows.FingerprintRow(
        chapter=capitulo.number,
        mean_sentence_len=fp.mean_sentence_len,
        var_sentence_len=fp.var_sentence_len,
        adj_noun_ratio=fp.adj_noun_ratio,
        top_ngrams=fp.top_ngrams,
        lexical_richness=fp.lexical_richness,
        deviation=desviacion,
        is_reference=len(previas) < style_drift.REFERENCE_CHAPTERS,
    )


def _repair_pass(
    capitulo: ChapterResult,
    defectos: Sequence[Defect],
    engine: Engine,
    presupuesto: Budget,
    trace: Trace,
) -> tuple[Budget, bool]:
    """Un pase del Reparador sobre las escenas con defectos (RF-53, RF-54).

    Devuelve el presupuesto y si la escalera de escena se agoto. Una reparacion
    que abre defectos S1 nuevos se **revierte**: rige RF-54.
    """
    decision = on_failure(presupuesto, level=Level.SCENE)
    trace.emit("retry", level="reparacion", action=str(decision.action), reason=decision.reason)
    if decision.action is not Action.RETRY:
        # Agotados los pases de reparacion. Que hacer con el capitulo lo decide
        # su propio peldano en `_write_chapter`, asi que aqui solo se reinicia
        # el contador de escena y no se consume el de capitulo dos veces.
        return presupuesto.model_copy(update={"scene_attempts": 0}), True
    presupuesto = decision.budget

    offsets = scene_offsets(capitulo.texts, SEPARATOR)
    por_escena: dict[int, list[Defect]] = {}
    for d in defectos:
        idx = _scene_index_for(d, capitulo, offsets)
        por_escena.setdefault(idx, []).append(d)

    for idx, lista in sorted(por_escena.items()):
        escena = capitulo.scenes[idx]
        # La cita viaja con su posicion dentro del capitulo; el Reparador recibe
        # la escena, asi que la posicion se traslada a ella.
        locales = [
            d.model_copy(
                update={
                    "evidence": d.evidence.model_copy(
                        update={"offset": max(0, d.evidence.offset - offsets[idx])}
                    )
                }
            )
            for d in lista
        ]
        nuevo = engine.repair_scene(escena.spec, escena.text, locales)
        antes = escena.defects
        despues = (
            engine.verify_match(escena.spec, nuevo, escena.match)
            if escena.match is not None
            else engine.verify_scene(escena.spec, nuevo)
        )
        resultado = evaluate(antes, despues, blocking_only=True)
        aceptada = resultado.accepted and not scene_gate(despues).s1
        # RF-240. Una reparacion que deja una prohibida no se acepta, y el
        # capitulo sigue en su bucle de reparacion.
        _emit_matches(
            trace,
            despues,
            chapter=capitulo.number,
            scene=escena.spec.identity.ordinal,
            attempt=escena.repairs + 1,
            decision="reparar",
            stage="reparacion",
        )
        trace.emit(
            "repair",
            chapter=capitulo.number,
            scene=escena.spec.identity.ordinal,
            defects=len(lista),
            accepted=aceptada,
            reason=resultado.reason(),
        )
        if aceptada:
            escena.text = nuevo
            escena.defects = despues
            escena.repairs += 1
    return presupuesto, False


def _scene_index_for(d: Defect, capitulo: ChapterResult, offsets: Sequence[int]) -> int:
    """A que escena pertenece un defecto citado sobre el capitulo entero."""
    if d.kind == "quiz" and d.evidence.quote:
        # El examen cita el arranque de su escena: se localiza por el texto.
        for i, s in enumerate(capitulo.scenes):
            if s.text.startswith(d.evidence.quote[:40]):
                return i
    return scene_of(d.evidence.offset, offsets)


def _names(path: Path) -> Mapping[str, str]:
    with connection.reader(path) as con:
        return {r["id"]: r["name"] for r in con.execute("SELECT id, name FROM entity")}


# ------------------------------------------------------------------ congelacion


def _extract_and_validate(
    path: Path,
    capitulo: ChapterResult,
    engine: Engine,
    trace: Trace,
    payoffs: frozenset[str] = frozenset(),
) -> tuple[DeltaProposal, entries.DeltaValidation]:
    """El Archivero propone y el Arbitro valida (RF-55, RF-56, RF-59, RF-60)."""
    with connection.reader(path) as con:
        estado_antes = read.state_at(con, capitulo.specs[0].identity.world_time)

    proposal = _extract_with_retries(engine, capitulo.specs, capitulo.texts, estado_antes, trace)

    with connection.reader(path) as con:
        eventos = to_events(proposal, con, chapter=capitulo.number)
        validacion = entries.validate_delta(
            con,
            eventos,
            quotes=quotes_by_event(proposal, eventos),
            chapter_text=SEPARATOR.join(capitulo.texts),
        )

    for rechazo in validacion.rejections:
        trace.emit(
            "arbitration",
            chapter=capitulo.number,
            fact=rechazo.arbitration.incumbent.fact_key,
            frozen_value=rechazo.arbitration.incumbent.value,
            rejected_value=rechazo.arbitration.challenger.value,
            rule=str(rechazo.arbitration.rule),
        )
    # RF-151. Antes de dar la razon al congelado, el Arbitro puede proponer un
    # retcon; la regla dura decide. Lo que no se retconea sigue siendo un S1.
    restantes = [
        r
        for r in validacion.rejections
        if not _try_retcon(path, r, capitulo, engine, payoffs, trace)
    ]
    if len(restantes) != len(validacion.rejections):
        validacion = validacion.model_copy(update={"rejections": tuple(restantes)})
    return proposal, validacion


def _try_retcon(
    path: Path,
    rechazo: entries.Rejection,
    capitulo: ChapterResult,
    engine: Engine,
    payoffs: frozenset[str],
    trace: Trace,
) -> bool:
    """RF-151 a RF-154. `True` si el retcon se aplico y el rechazo desaparece."""
    with connection.reader(path) as con:
        plan = retcon_rules.plan(con, rechazo, payoff_scenes=payoffs)
    if plan is None:
        return False
    try:
        propuesta = engine.propose_retcon(rechazo, plan.scenes)
    except Exception as exc:  # proponer no es obligatorio: sin propuesta, gana el canon
        trace.emit("process.defect", agent="arbitro", chapter=capitulo.number, error=str(exc)[:200])
        return False
    trace.emit(
        "retcon.proposal",
        chapter=capitulo.number,
        fact=plan.fact_key,
        propose=propuesta.propose,
        admissible=plan.admissible,
        reason=plan.reason(),
        passages=list(plan.scenes),
    )
    if not propuesta.propose or not plan.admissible:
        return False

    from canon.prose_index.reindex import scene_texts

    with connection.reader(path) as con:
        textos = scene_texts(con)
        capitulos = {
            r["id"]: r["chapter"] for r in con.execute("SELECT id, chapter FROM prose_scene")
        }
    nuevas: list[refreeze.RefrozenScene] = []
    for sid in plan.scenes:
        escena, defectos = engine.retcon_rewrite(sid, textos.get(sid, ""), plan)
        sigue = plan.previous_value.lower() in escena.text.lower()
        if sigue or any(d.severity.value == "S1" for d in defectos):
            # RF-153: cada escena reescrita se reverifica. Una que sigue
            # sosteniendo el hecho antiguo, o que abre un S1, tumba el retcon.
            trace.emit("retcon.aborted", chapter=capitulo.number, scene=sid, still_old=sigue)
            return False
        nuevas.append(escena)

    afectados = sorted({capitulos[s] for s in plan.scenes if s in capitulos})
    reescritas = {e.scene_id: e.summary for e in nuevas}
    resumenes: dict[int, str] = {}
    with connection.reader(path) as con:
        for c in afectados:
            partes = [
                reescritas.get(r["id"], r["summary"])
                for r in con.execute(
                    "SELECT id, summary FROM prose_scene WHERE chapter = ? ORDER BY scene_number",
                    (c,),
                )
            ]
            resumenes[c] = engine.summarize_chapter(partes)
    preparado = refreeze.prepare(nuevas, embed=engine.embed)
    with connection.canon_writer(path) as con:
        evento = retcon_rules.event_for(con, plan, chapter=capitulo.number)
        refreeze.commit(
            con,
            preparado,
            retcon=plan,
            event=evento,
            chapter_summaries=resumenes,
            rule="retcon-admisible: no cobrado y <= 3 pasajes",
            chapter_origin=capitulo.number,
        )
    trace.emit(
        "retcon.applied",
        chapter=capitulo.number,
        fact=plan.fact_key,
        previous=plan.previous_value,
        new=plan.new_value,
        refrozen=list(plan.scenes),
    )
    return True


def _extract_with_retries(
    engine: Engine,
    specs: Sequence[SceneSpec],
    textos: Sequence[str],
    estado_antes: WorldState,
    trace: Trace,
) -> DeltaProposal:
    """RF-56, trampa 12. Un delta vacio consume un reintento, no congela."""
    for intento in range(1, SCENE_ATTEMPTS + 1):
        proposal = engine.extract_delta(specs, textos, estado_antes)
        if not proposal.is_empty:
            return proposal
        trace.emit(
            "retry",
            level="archivero",
            action="reintentar",
            reason=f"delta vacio en el intento {intento} de {SCENE_ATTEMPTS}",
        )
    raise EmptyDeltaError(
        f"el Archivero devolvio un delta vacio {SCENE_ATTEMPTS} veces sobre un capitulo aprobado"
    )


def _freeze(
    path: Path,
    capitulo: ChapterResult,
    engine: Engine,
    validacion: entries.DeltaValidation,
    trace: Trace,
    outline: Outline,
) -> None:
    """RF-57. Todo junto o nada.

    Lo caro --trocear, resumir, vectorizar-- fuera de la transaccion; el resto
    dentro. El delta ya llega validado: aqui solo se escribe lo aceptado. Los
    resumenes de escena van primero y el de capitulo se construye desde ellos,
    nunca desde el texto completo (RF-90).
    """
    resumenes = [engine.summarize_scene(s.spec, s.text) for s in capitulo.scenes]
    resumen_capitulo = engine.summarize_chapter(resumenes)

    with connection.reader(path) as con:
        congelado = [r["text"] for r in con.execute("SELECT text FROM prose_chunk")]
        superiores = _higher_summaries(
            con,
            capitulo.number,
            resumen_capitulo,
            engine,
            outline,
            trace,
            profile=load_brief(path).profile(),
        )
        lugares = _place_ids(con, [s.spec.identity.place for s in capitulo.scenes])
    proscritos = proscription.repeated_ngrams(capitulo.texts, frozen_texts=congelado)

    escenas = [
        SceneToFreeze(
            id=s.spec.identity.scene_id,
            chapter=s.spec.identity.chapter,
            scene_number=s.spec.identity.ordinal,
            pov_entity=s.spec.identity.pov,
            place_entity=lugares.get(s.spec.identity.place),
            world_time=s.spec.identity.world_time,
            function=str(s.spec.function.function),
            text=s.text,
            summary=resumen,
            present=s.spec.content.cast,
        )
        for s, resumen in zip(capitulo.scenes, resumenes, strict=True)
    ]

    huella = _fingerprint_row(path, capitulo)
    preparado: PreparedChapter = prepare(
        escenas,
        chapter=capitulo.number,
        chapter_summary=resumen_capitulo,
        embed=engine.embed,
        delta=validacion.accepted,
        new_proscribed=proscritos,
        higher_summaries=superiores,
        verdicts=_verdict_rows(capitulo),
        fingerprint=huella,
        metrics=_metric_rows(path, capitulo, outline, huella, trace),
    )
    with connection.canon_writer(path) as con:
        commit_chapter(con, preparado)
    capitulo.events_applied = len(validacion.accepted)
    trace.emit("proscription", chapter=capitulo.number, terms=len(proscritos))


def _place_ids(con: object, places: Sequence[str]) -> dict[str, str]:
    """El lugar de la especificacion como entidad, por identificador o por nombre.

    El indice guarda el lugar como clave ajena a `entity` (RD-06): un lugar que
    el canon no conoce se deja sin entidad, y el cupo de lugar no puede usarlo.
    """
    import sqlite3

    assert isinstance(con, sqlite3.Connection)
    out: dict[str, str] = {}
    for lugar in set(places):
        row = con.execute(
            "SELECT id FROM entity WHERE id = ? OR lower(name) = lower(?) LIMIT 1", (lugar, lugar)
        ).fetchone()
        if row is not None:
            out[lugar] = row["id"]
    return out


def _higher_summaries(
    con: object,
    chapter: int,
    chapter_summary: str,
    engine: Engine,
    outline: Outline,
    trace: Trace,
    *,
    profile: LengthProfile = NOVELA,
) -> list[levels.SummaryToWrite]:
    """RF-116, RF-117. Arco al cerrarse, obra cada cinco capitulos.

    Se generan aqui, fuera de la transaccion, con lo que ya esta congelado mas
    el resumen del capitulo que esta a punto de congelarse: es el ultimo que el
    arco o la obra cubren.
    """
    import sqlite3

    assert isinstance(con, sqlite3.Connection)
    out: list[levels.SummaryToWrite] = []
    for arc_id in arcs_closed_by(outline, chapter):
        caps = [c for c in chapters_of_arc(outline, arc_id) if c < chapter]
        partes = [*levels.chapter_summaries(con, caps), chapter_summary]
        cuerpo = engine.summarize_arc(partes)
        out.append(
            levels.SummaryToWrite(level="arc", ref_id=arc_id, body=cuerpo, covers_to=chapter)
        )
        trace.emit("summary", level="arc", ref=arc_id, chapter=chapter, parts=len(partes))
    ultimo = max(s.chapter for s in outline.scenes)
    if profile.periodic_due(chapter, last_chapter=ultimo, every=levels.WORK_SUMMARY_EVERY):
        arcos = [*levels.arc_summaries(con), *(s.body for s in out)]
        caps = list(range(1, chapter))
        partes = [*arcos, *levels.chapter_summaries(con, caps), chapter_summary]
        cuerpo = engine.summarize_work(partes)
        out.append(
            levels.SummaryToWrite(level="work", ref_id="work", body=cuerpo, covers_to=chapter)
        )
        trace.emit("summary", level="work", ref="work", chapter=chapter, parts=len(partes))
    return out


# --------------------------------------------------------------- las puertas


def _close_act_if_needed(
    outline: Outline,
    numero: int,
    congeladas: set[str],
    engine: Engine,
    brief: Brief,
    trace: Trace,
    path: Path,
) -> Outline:
    """RF-105, RF-106, RF-148. La puerta de acto corre al cerrar su ultimo capitulo.

    Dos mitades: la deuda, determinista, y la curva de tension realizada frente
    a la planificada, con el ritmo del Jurado. Si falla cualquiera, se
    replanifica el acto **siguiente**. Nunca se toca el acto que se acaba de
    cerrar.
    """
    acto = closes_an_act(outline, numero)
    if acto is None:
        return outline

    veredicto = check_act(outline, acto, frozenset(congeladas))
    plan = next((a.tension for a in outline.acts if a.number == acto), ())
    capitulos = sorted({s.chapter for s in outline.scenes if s.act == acto})
    realizada = _realized_pacing(path, capitulos)
    curva_ok = tension_conforms(plan, realizada)
    trace.emit(
        "act.gate",
        act=acto,
        passed=veredicto.passed and curva_ok,
        unpaid=list(veredicto.unpaid),
        tension_conforms=curva_ok,
        planned=list(plan),
        realized=list(realizada),
    )
    if veredicto.passed and curva_ok:
        return outline

    siguiente = replan_target(outline, acto)
    if siguiente is None:
        # Sin acto siguiente no hay donde cobrar lo que falta. No se para: lo
        # recoge la condicion de cierre de obra, que es quien tiene que verlo.
        return outline

    desde = min(s.chapter for s in outline.scenes if s.act == siguiente)
    motivos = [veredicto.reason()] if not veredicto.passed else []
    if not curva_ok:
        motivos.append(
            f"la tension realizada del acto {acto} ({realizada}) baja donde la planificada "
            f"({list(plan)}) sube: el acto siguiente tiene que recuperarla"
        )
    return _replan(
        outline,
        engine,
        siguiente,
        desde,
        veredicto.unpaid,
        motivos,
        trace,
        word_range=brief.word_range(),
        profile=brief.profile(),
    )


def _realized_pacing(path: Path, chapters: Sequence[int]) -> list[int | None]:
    """Nivel resultante de ritmo del Jurado por capitulo, o `None` sin veredicto."""
    out: list[int | None] = []
    with connection.reader(path) as con:
        for c in chapters:
            row = con.execute(
                "SELECT max(v.level) AS lvl FROM scene_verdict v JOIN prose_scene s ON s.id = v.scene_id "
                "WHERE s.chapter = ? AND v.dimension = 'pacing' AND v.valid = 1",
                (c,),
            ).fetchone()
            out.append(int(row["lvl"]) if row and row["lvl"] is not None else None)
    return out


def _metric_rows(
    path: Path,
    capitulo: ChapterResult,
    outline: Outline,
    huella: freeze_rows.FingerprintRow | None,
    trace: Trace,
) -> list[freeze_rows.MetricRow]:
    """RF-144, RD-22. Las trece senales, calculadas antes de la transaccion."""
    with connection.reader(path) as con:
        historia = freeze_rows.read_metrics(con)
        previas = freeze_rows.read_fingerprints(con)
        congeladas = {r["id"] for r in con.execute("SELECT id FROM prose_scene")}
    congeladas |= {s.spec.identity.scene_id for s in capitulo.scenes}
    deuda = debt(outline, frozenset(congeladas))
    acto = _act_of(outline, capitulo.number)
    anterior = capitulo.number - 1
    cuarentenas_previas = next(
        (
            int(r.value or 0)
            for r in historia
            if r.chapter == anterior
            and r.signal == "quarantines_in_act"
            and _act_of(outline, anterior) == acto
        ),
        0,
    )
    desviaciones = [r.deviation for r in previas] + [huella.deviation if huella else None]
    return health_metrics.compute(
        capitulo.number,
        health_metrics.since_last_freeze(trace.records()),
        historia,
        open_setups=len(deuda.open_setups),
        act_quarantines=cuarentenas_previas,
        deviations=desviaciones,
        after_first_act=acto > min((a.number for a in outline.acts), default=1),
    )


def _supervise(
    path: Path,
    outline: Outline,
    numero: int,
    chapters: int,
    engine: Engine,
    brief: Brief,
    trace: Trace,
) -> Outline:
    """RF-146, RF-147, RF-149. Tras cada congelacion.

    Un veredicto que no llega cuenta como sano y consta como fallo de proceso
    (D-45). Uno de deriva replanifica el tramo que el Supervisor senala, acotado
    a lo que aun no se ha escrito.
    """
    with connection.reader(path) as con:
        filas = [r for r in freeze_rows.read_metrics(con) if r.chapter == numero]
    try:
        veredicto = engine.supervise(numero, chapters, outline, filas)
    except Exception as exc:  # RF-149: no bloquea
        trace.emit("process.defect", agent="supervisor", chapter=numero, error=str(exc)[:200])
        trace.emit("health", chapter=numero, healthy=True, fallback=True)
        return outline
    tramo = clamp(veredicto, last_frozen=numero, total_chapters=chapters)
    trace.emit(
        "health",
        chapter=numero,
        healthy=veredicto.healthy,
        signal=veredicto.signal,
        from_chapter=tramo.from_chapter if tramo else None,
        reason=veredicto.reason[:300],
    )
    if tramo is None or tramo.from_chapter is None:
        return outline
    acto = tramo.act or _act_of(outline, tramo.from_chapter)
    if not any(s.act == acto and s.chapter >= tramo.from_chapter for s in outline.scenes):
        acto = _act_of(outline, tramo.from_chapter)
    return _replan(
        outline,
        engine,
        acto,
        tramo.from_chapter,
        (),
        [f"Supervisor: {tramo.signal}: {tramo.reason}"],
        trace,
        word_range=brief.word_range(),
        profile=brief.profile(),
    )


def _replan(
    outline: Outline,
    engine: Engine,
    act: int,
    from_chapter: int,
    unpaid: Sequence[str],
    reasons: Sequence[str],
    trace: Trace,
    *,
    word_range: tuple[int, int] | None = None,
    profile: LengthProfile = NOVELA,
) -> Outline:
    """`replan.arc` con su verificacion determinista detras (RF-27, RF-106).

    La escaleta replanificada vuelve a `outline.check` como la primera. Se le
    dan a la replanificacion los intentos del arco; agotados, la tirada se para
    con motivo: no hay cuarto nivel.
    """
    presupuesto = Budget()
    motivos = list(reasons)
    while True:
        nueva = engine.replan_act(outline, act, from_chapter, unpaid, motivos)
        rango = word_range or _word_range_of(outline)
        defectos = check_outline(nueva, word_range=rango, profile=profile)
        trace.emit(
            "replan",
            act=act,
            from_chapter=from_chapter,
            unpaid=list(unpaid),
            passed=not defectos,
            defects=[d.kind for d in defectos],
            outline=nueva.model_dump_json() if not defectos else None,
        )
        if not defectos:
            return nueva
        decision = on_failure(presupuesto, level=Level.ARC)
        presupuesto = decision.budget
        if presupuesto.arc_replans > ARC_REPLANS:
            raise RunAbortedError(
                f"la replanificacion del acto {act} no pasa la verificacion "
                f"estructural: {[d.kind for d in defectos]}"
            )
        motivos = [*motivos, *(f"{d.kind}: {d.message}" for d in defectos[:5])]


def _word_range_of(outline: Outline) -> tuple[int, int]:
    """Rango de palabras que la escaleta ya realiza, para la replanificacion de
    un tramo cuando el brief no viaja hasta aqui."""
    total = sum(s.target_words for s in outline.scenes)
    return (int(total * 0.5), int(total * 1.5))


def _work_closes(
    outline: Outline,
    brief: Brief,
    report: RunReport,
    congeladas: set[str],
    path: Path,
) -> tuple[bool, str]:
    """RF-23. Las cuatro condiciones de cierre de obra."""
    deuda = debt(outline, frozenset(congeladas))
    low, high = brief.word_range()
    abiertos = [a for a in outline.arcs if a.resolution_scene is None and not a.left_open]
    palabras = report.words or _frozen_words(path)

    fallos: list[str] = []
    if not deuda.is_clear:
        fallos.append(
            f"{len(deuda.open_setups)} promesas sin cobrar y {len(deuda.planned)} sin plantar"
        )
    if abiertos:
        fallos.append(f"{len(abiertos)} arcos sin resolver")
    if not low <= palabras <= high:
        fallos.append(f"{palabras} palabras, fuera del rango {low}-{high}")

    if fallos:
        return False, "; ".join(fallos)
    return True, "deuda cero, arcos resueltos y longitud en rango"


def _frozen_words(path: Path) -> int:
    with connection.reader(path) as con:
        rows = con.execute("SELECT text FROM prose_chunk").fetchall()
    return sum(len(r["text"].split()) for r in rows)


def as_json(report: RunReport) -> str:
    """El informe, para trazarlo o leerlo."""
    return json.dumps(
        {
            "novel_id": report.novel_id,
            "closed": report.closed,
            "reason": report.reason,
            "words": report.words,
            "chapters": [
                {
                    "number": c.number,
                    "frozen": c.frozen,
                    "words": c.words,
                    "attempts": c.chapter_attempts,
                    "events_applied": c.events_applied,
                    "rejected_facts": len(c.rejected_facts),
                    "scenes": [
                        {
                            "id": s.spec.identity.scene_id,
                            "words": len(s.text.split()),
                            "attempts": s.attempts,
                            "repairs": s.repairs,
                            "defects": [
                                {"kind": d.kind, "severity": str(d.severity), "rule": d.rule}
                                for d in s.defects
                            ],
                        }
                        for s in c.scenes
                    ],
                }
                for c in report.chapters
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
