"""La raiz de composicion: el motor real.

RF-13, RF-14, RF-16, RF-21, RF-86, RF-98, RF-99, RI-24. `architecture.md` §7.4.
Aqui es donde los prompts de cada funcionalidad, el Documentalista de
`context/`, el puerto de `commons/` y la frontera de `dispatch` se juntan en
las piezas que el bucle inyecta. Es el unico sitio que conoce a todas.

Cada agente de modelo pasa por el mismo camino y en el mismo orden:

1. el Documentalista ensambla su paquete con la receta de §4.9;
2. `context.audit` lo comprueba, y un conflicto de hechos va al Arbitro;
3. la admision reserva su entrada mas su cupo de tiron (CTX-20);
4. `dispatch` llama, valida la salida y la traza;
5. la funcionalidad duena parsea y devuelve el artefacto tipado.

Lo determinista --verificadores, motor de reglas, examen, puertas-- no pasa por
ningun modelo y se llama directo.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, JsonValue

from brief import extract as brief_extract
from brief import interpret as brief_interpret
from canon.arbiter import entries, refreeze
from canon.arbiter import retcon as retcon_rules
from canon.arbiter.precedence import Claim
from canon.archivist import extract as archivist
from canon.archivist import prompts as archivist_prompts
from canon.brief import Brief
from canon.brief import elements as brief_elements
from canon.db import connection
from canon.freeze import elements as freeze_elements
from canon.freeze import rows as freeze_rows
from canon.skills import read
from canon.skills.read import WorldState
from canon.summaries import levels
from canon.summaries import prompts as summary_prompts
from canon.summaries.prompts import Level as SummaryLevel
from commons.provider.port import ProviderError, ProviderPort
from commons.tokens.counter import TokenCounter
from commons.tracing.trace import Trace
from commons.types import rubrics as rubric_types
from commons.types.primitives import (
    BlockProvenance,
    Defect,
    Evidence,
    Provenance,
    Severity,
    WorldTime,
)
from commons.types.rubrics import Dimension, RubricSet
from commons.types.scene import (
    DramaticFunction,
    ExpectedOutput,
    SceneConstraints,
    SceneContent,
    SceneFunction,
    SceneIdentity,
    SceneSpec,
)
from context.audit.audit import audit
from context.packing import recipes
from context.packing.packet import Packet, Priority
from context.query import build as query_build
from context.retrieval.retrieve import retrieve
from generation.sports import narrate as narrate_prompts
from generation.sports.simulate import Availability, MatchResult, Player, Squad, simulate
from generation.writer import drafts
from generation.writer import prompts as writer_prompts
from orchestration.admission import Admission, reserve
from orchestration.dispatch import DispatchResult, OutputValidationError, dispatch
from orchestration.loop import Engine
from orchestration.retries import SCENE_ATTEMPTS
from orchestration.tools.server import CallBudget, ToolServer
from planning.ledger.setups import debt
from planning.outline import prompts as outline_prompts
from planning.outline.arcs import chapters_of_arc
from planning.outline.check import OutlineDefect
from planning.outline.types import Outline
from planning.replan import arc as replan
from planning.scene_spec import prompts as planner_prompts
from supervision import prompts as supervision_prompts
from supervision.prompts import HealthVerdict
from verification.checks import deterministic as checks
from verification.checks import forbidden
from verification.continuity import prompts as continuity_prompts
from verification.continuity import review
from verification.continuity.review import Anchored
from verification.formal import check as formal
from verification.formal.check import LeanResult
from verification.formal.generate import Pending
from verification.jury import golden as jury_golden
from verification.jury import prompts as jury_prompts
from verification.jury.prompts import InstanceVerdict
from verification.jury.verdict import INSTANCES, JuryVerdict, adjudicate, unanchored
from verification.quiz import prompts as quiz_prompts
from verification.quiz.build import Question
from verification.repair import prompts as repair_prompts
from verification.style import fingerprint as style_fingerprint
from verification.style import prompts as style_prompts
from verification.style.fingerprint import Fingerprint

#: Los invariantes duros que van en toda ancla (CTX-17). Son las reglas de
#: `definitions.md` que ningun agente puede romper, dichas una vez.
INVARIANTS = """- Un solo punto de vista por escena; el POV esta siempre en el elenco (EST-I1).
- Nadie actua sobre informacion que no conoce en ese instante (PER-I1).
- Nadie juega estando lesionado o sancionado en esa fecha (DEP-I2).
- Los hechos del mundo salen del canon que se te da; si algo no esta, no ocurrio.
- Donde el canon y la prosa discrepen, manda el canon (PRO-10)."""

_CAPITAL = re.compile(r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})\b")
_COMMON_CAPITALS = frozenset(
    [
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "y",
        "pero",
        "cuando",
        "donde",
        "como",
        "que",
        "porque",
        "aunque",
        "entonces",
        "luego",
        "mientras",
        "despues",
        "antes",
        "hasta",
        "desde",
        "sin",
        "con",
        "por",
        "para",
        "sobre",
        "entre",
        "hacia",
        "nadie",
        "nada",
        "todo",
        "todos",
        "alguien",
        "algo",
        "eso",
        "esto",
        "aquello",
        "aqui",
        "alli",
        "ahora",
        "hoy",
        "ayer",
        "manana",
    ]
)


#: RF-265. Los verificadores deterministas que corren sobre toda escena, y los
#: que se anaden en una de partido. Son los `kind` de sus defectos.
SCENE_CHECKS = (
    "check.format",
    "check.timeline",
    forbidden.KIND,
    "check.repetition",
    "check.lexicon",
    "check.knowledge",
)
MATCH_CHECKS = ("check.ledger", "check.availability")


#: RI-34. Los modulos de prompt de cada agente: su instruccion de sistema y sus
#: plantillas de instruccion viven ahi y en ningun otro sitio.
PROMPT_MODULES: dict[str, tuple[Any, ...]] = {
    "arquitecto": (outline_prompts, replan),
    "planificador": (planner_prompts,),
    "escritor": (writer_prompts,),
    "especialista": (narrate_prompts,),
    "continuista": (continuity_prompts,),
    "lector": (quiz_prompts,),
    "reparador": (repair_prompts,),
    "archivero": (archivist_prompts, summary_prompts),
    "arbitro": (retcon_rules,),
    "juez": (jury_prompts,),
    "estilista": (style_prompts,),
    "supervisor": (supervision_prompts,),
}


def supervisor_summaries(
    outline: Outline, by_chapter: Mapping[int, str], by_arc: Mapping[str, str]
) -> list[str]:
    """RF-118, §4.9 Supervisor. Resumenes de capitulo, compactados por arco.

    Los capitulos de un arco ya cerrado --con su resumen de arco escrito-- se
    sustituyen por ese resumen. Es lo que mantiene el bloque en 12.000 pasados
    los 30 capitulos, y es exactamente para lo que existe la jerarquia de §4.5.
    """
    cubiertos: set[int] = set()
    out: list[str] = []
    for arco in outline.arcs:
        if arco.id not in by_arc:
            continue
        caps = set(chapters_of_arc(outline, arco.id))
        if not caps:
            continue
        cubiertos |= caps
        out.append(f"Arco {arco.id} (capitulos {min(caps)} a {max(caps)}): {by_arc[arco.id]}")
    out += [f"Capitulo {n}: {t}" for n, t in sorted(by_chapter.items()) if n not in cubiertos]
    return out


#: RF-262. Los dos agentes del entrevistador. No llevan ancla ni invariantes:
#: su version es el hash de su modulo, el mismo que dejan en su registro `call`.
INTERVIEWER_MODULES: dict[str, tuple[Any, ...]] = {
    "brief.extract": (brief_extract,),
    "amend.interpret": (brief_interpret,),
}


def prompt_sources(agent: str) -> list[tuple[str, bytes]]:
    """RI-34, RF-266. Lo que forma el prompt de un agente, en orden, con su origen.

    Es lo que se hashea para `prompt_version` y lo que `prompts_sync` publica:
    una sola lista para las dos cosas, o la etiqueta dejaria de nombrar el texto.
    """
    if agent in INTERVIEWER_MODULES:
        partes: list[tuple[str, bytes]] = []
        modulos = INTERVIEWER_MODULES[agent]
    else:
        partes = [("INVARIANTS", INVARIANTS.encode("utf-8"))]
        modulos = PROMPT_MODULES.get(agent, ())
    raiz = Path(__file__).resolve().parent.parent
    for mod in modulos:
        ruta = Path(mod.__file__).resolve()
        partes.append((ruta.relative_to(raiz).as_posix(), ruta.read_bytes()))
    return partes


def prompt_version(agent: str) -> str:
    """RI-34. Hash del prefijo estable y de la plantilla de instruccion del agente.

    Se calcula sobre el fichero de prompts y no sobre el prefijo ensamblado:
    el ancla lleva el lexico de entidades, que crece durante la tirada, y con
    el la version cambiaria sin que cambiara el prompt. Dos tiradas con la
    misma version usaron el mismo texto de instrucciones; nada mas lo asegura.
    """
    h = hashlib.sha256()
    for _origen, contenido in prompt_sources(agent):
        h.update(contenido)
    return h.hexdigest()[:12]


#: D-100. Campos que cada llamada de modelo lleva en su contexto mientras dura
#: un bloque `call_context`. Hoy, el numero de solicitud de `amend._apply`: es lo
#: que cuelga sus llamadas de la traza de su solicitud en el espejo (RF-234).
_CALL_CONTEXT: ContextVar[Mapping[str, str | int | bool | float] | None] = ContextVar(
    "call_context", default=None
)


@contextmanager
def call_context(**fields: str | int | bool | float) -> Iterator[None]:
    """D-100. Anade `fields` al contexto de toda llamada de modelo del bloque."""
    token = _CALL_CONTEXT.set({**(_CALL_CONTEXT.get() or {}), **fields})
    try:
        yield
    finally:
        _CALL_CONTEXT.reset(token)


@dataclass
class Composer:
    """El estado que el motor real necesita entre llamadas.

    No es un agente: es la fabrica de los callables del `Engine`. Recuerda la
    prosa de la escena anterior y las muestras de voz usadas en las ultimas
    llamadas, que es lo minimo que §4.3 y RF-82 exigen recordar.
    """

    port: ProviderPort
    path: Path
    brief: Brief
    embedder: object
    counter: TokenCounter
    model_id: str
    trace: Trace
    admission: Admission
    outline: Outline | None = None
    _previous: dict[tuple[int, int], str] = field(default_factory=dict)
    _voice_used: list[str] = field(default_factory=list)
    #: T53. Cuantas palabras tenia la escena de cada resumen de escena escrito
    #: en esta tirada: el tope del resumen de capitulo sale del capitulo.
    _summary_sources: dict[str, int] = field(default_factory=dict)

    # ------------------------------------------------------------ utilidades

    def estimate(self, text: str) -> int:
        return self.counter.estimate(text, self.model_id) if text else 0

    def anchor(self, agent_system: str) -> str:
        with connection.reader(self.path) as con:
            lexico = [r["name"] for r in con.execute("SELECT name FROM entity")]
            lexico += [r["alias"] for r in con.execute("SELECT alias FROM entity_alias")]
        return recipes.anchor_text(
            agent_system=agent_system,
            style_guide=self.brief.style_guide,
            invariants=INVARIANTS,
            lexicon=lexico,
        )

    def _names(self) -> dict[str, str]:
        with connection.reader(self.path) as con:
            return {r["id"]: r["name"] for r in con.execute("SELECT id, name FROM entity")}

    def _call(
        self,
        agent: str,
        *,
        prefix: str,
        packet: str,
        instruction: str,
        schema: str,
        parse: type[BaseModel] | None,
        context: Mapping[str, object],
        at: WorldTime | None = None,
        validate: Callable[[str], Sequence[str]] | None = None,
    ) -> DispatchResult:
        """El camino comun: admision, dispatch, traza. RF-14, RF-16, RF-21.

        `validate` es la comprobacion que el esquema no expresa --hoy, que las
        citas del Jurado anclen (D-71)--. Lo que devuelve se trata como una
        salida que no encaja: consume un intento y vuelve al modelo con el
        motivo. En el ultimo intento la salida se devuelve igual, porque lo que
        no ancle lo descarta quien la consume (RF-129), no la llamada.
        """
        # D-100: lo que el bloque en curso anade, sin pisar lo que la llamada declara.
        context = {**(_CALL_CONTEXT.get() or {}), **context}
        budget = recipes.BUDGETS[agent]
        estimado = self.counter.estimate_many([prefix, packet, instruction], self.model_id)
        version = prompt_version(agent)
        reserva = reserve(agent=agent, packet_tokens=estimado, tool_quota=budget.tool_quota)

        server: ToolServer | None = None
        con = None
        if budget.tools:
            con = connection._connect(self.path, read_only=True)
            server = ToolServer(
                con,
                CallBudget(ceiling=budget.input_tokens, quota=budget.tool_quota),
                allowed=budget.tools,
                at=at or self.brief.start,
                estimate=self.counter,
                model_id=self.model_id,
                # RF-264: cada herramienta queda trazada con la llamada que la pidio.
                trace=self.trace,
                context={
                    "agent": agent,
                    **{k: v for k, v in context.items() if isinstance(v, str | int | bool | float)},
                },
            )
        # RI-18: una salida que no encaja cuenta como llamada fallida y consume
        # un reintento. Se le devuelve al modelo que fallo, no solo que fallo:
        # decirle "esta mal" gastaria el intento sin darle con que corregir.
        ultimo: Exception | None = None
        instruccion = instruction
        try:
            for intento in range(1, SCENE_ATTEMPTS + 1):
                try:
                    with self.admission.hold(reserva):
                        resultado = dispatch(
                            self.port,
                            agent=agent,
                            cacheable_prefix=prefix,
                            packet=packet,
                            instruction=instruccion,
                            output_schema=schema,
                            max_output_tokens=budget.output_tokens,
                            tools=budget.tools,
                            server=server,
                            parse=parse,
                            trace=self.trace,
                            estimated_input=estimado,
                            context={
                                "prompt_version": version,
                                "attempt": intento,
                                **{
                                    k: v
                                    for k, v in context.items()
                                    if isinstance(v, str | int | bool | float)
                                },
                            },
                        )
                    fallos = list(validate(resultado.raw)) if validate else []
                    # D-136. En modo permisivo una cita sin anclar no gasta otra
                    # llamada: la descarta quien la consume (RF-129). Lo que no
                    # encaja con el esquema o el proveedor caido si reintentan.
                    if not fallos or intento == SCENE_ATTEMPTS or self.brief.profile().lenient:
                        return resultado
                    self.trace.emit(
                        "retry",
                        level="llamada",
                        agent=agent,
                        action="reintentar",
                        reason=f"{len(fallos)} cita(s) sin anclar",
                    )
                    instruccion = (
                        f"{instruction}\n\nESTAS CITAS DE TU SALIDA ANTERIOR NO SON LITERALES Y SE "
                        "DESCARTARIAN. Rehaz la salida entera con citas copiadas tal cual:\n"
                        + "\n".join(fallos[:10])
                    )
                except OutputValidationError as exc:
                    ultimo = exc
                    self.trace.emit(
                        "retry",
                        level="llamada",
                        agent=agent,
                        action="reintentar",
                        reason=str(exc)[:300],
                    )
                    instruccion = (
                        f"{instruction}\n\nTU SALIDA ANTERIOR NO ENCAJABA CON EL ESQUEMA: {exc}\n"
                        "Devuelve SOLO el JSON que cumple el esquema."
                    )
                except ProviderError as exc:
                    # §4.8, D-70: que el proveedor no responda es intermitente. Mismo
                    # presupuesto; la instruccion no cambia, el modelo no fallo.
                    ultimo = exc
                    self.trace.emit(
                        "retry",
                        level="llamada",
                        agent=agent,
                        action="reintentar",
                        reason=f"proveedor: {str(exc)[:280]}",
                    )
            raise ultimo or RuntimeError("sin intentos")
        finally:
            if con is not None:
                con.close()

    def _audit_or_arbitrate(
        self, packet: Packet, facts: Sequence[tuple[str, str]], cast: Sequence[str], budget: int
    ) -> None:
        """RF-35, RF-36. Un conflicto de hechos va al Arbitro antes de generar."""
        informe = audit(packet, active_cast=cast, budget=budget, facts=facts)
        if informe.conflict:
            claims = [
                Claim(fact_key=k, value=v, provenance=Provenance.DERIVED, frozen=True)
                for k, v in facts
            ]
            _vigentes, arbitrajes = entries.resolve_claims(claims)
            for a in arbitrajes:
                self.trace.emit(
                    "arbitration",
                    agent="documentalista",
                    fact=a.incumbent.fact_key,
                    rule=str(a.rule),
                )
        bloqueantes = [
            f for f in informe.findings if f.blocking and f.kind != "conflicto-de-hechos"
        ]
        for f in bloqueantes:
            self.trace.emit("audit", finding=f.kind, detail=f.detail)

    # -------------------------------------------------------------- Arquitecto

    def plan_outline(
        self, brief: Brief, chapters: int, defects: Sequence[OutlineDefect] = ()
    ) -> Outline:
        with connection.reader(self.path) as con:
            ids = [r["id"] for r in con.execute("SELECT id FROM entity")]
            cards = read.query(con, ids, at=brief.start, full=True)
        secciones = [
            (
                "brief",
                f"TITULO: {brief.title}\nGUIA: {brief.style_guide}",
                BlockProvenance.PLAN,
                Priority.UNTOUCHABLE,
                None,
            ),
            (
                "fichas",
                recipes.cards_text(cards, full=True),
                BlockProvenance.CANON,
                Priority.SECONDARY_CARDS,
                None,
            ),
            ("reglamento", brief.rulebook, BlockProvenance.CANON, Priority.SUMMARIES, None),
        ]
        if defects and self.outline is not None:
            # §4.9, bloque "escaleta vigente": con su intento anterior delante,
            # el Arquitecto corrige lo que fallo en vez de rehacer y romper otra cosa.
            secciones.append(
                (
                    "escaleta-anterior",
                    "TU ESCALETA ANTERIOR, que corriges:\n" + self.outline.model_dump_json(),
                    BlockProvenance.PLAN,
                    Priority.SUMMARIES,
                    None,
                )
            )
        packet = recipes.simple_packet(
            "arquitecto",
            anchor=self.anchor(outline_prompts.SYSTEM),
            estimate=self.estimate,
            sections=secciones,
        )
        r = self._call(
            "arquitecto",
            prefix=packet.cacheable_prefix,
            packet=packet.body(),
            instruction=outline_prompts.instruction(brief, chapters=chapters, defects=defects),
            schema=outline_prompts.schema(brief.profile()),
            parse=Outline,
            context={"chapters": chapters, "defects": len(defects)},
        )
        self.outline = Outline.model_validate_json(r.raw)
        return self.outline

    def replan_act(
        self,
        outline: Outline,
        act: int,
        from_chapter: int,
        unpaid: Sequence[str],
        reasons: Sequence[str],
    ) -> Outline:
        packet = recipes.simple_packet(
            "arquitecto",
            anchor=self.anchor(replan.SYSTEM),
            estimate=self.estimate,
            sections=[
                (
                    "escaleta",
                    outline.model_dump_json(indent=1),
                    BlockProvenance.PLAN,
                    Priority.UNTOUCHABLE,
                    None,
                )
            ],
        )
        r = self._call(
            "arquitecto",
            prefix=packet.cacheable_prefix,
            packet=packet.body(),
            instruction=replan.instruction(
                outline,
                act=act,
                from_chapter=from_chapter,
                unpaid_setups=unpaid,
                reasons=reasons,
                profile=self.brief.profile(),
            ),
            schema=replan.schema(self.brief.profile()),
            parse=replan.ReplannedTract,
            context={"act": act, "from_chapter": from_chapter},
        )
        nueva = replan.apply(outline, replan.parse(r.raw), act=act, from_chapter=from_chapter)
        self.outline = nueva
        return nueva

    # ------------------------------------------------------------ Planificador

    def specs_for(
        self, outline: Outline, chapter: int, defects: Sequence[Defect] = ()
    ) -> list[SceneSpec]:
        self.outline = outline
        entries_ = outline.chapters().get(chapter, [])
        if not entries_:
            return []
        at = entries_[0].world_time
        with connection.reader(self.path) as con:
            ids = [r["id"] for r in con.execute("SELECT id FROM entity")]
            cards = read.query(con, ids, at=at)
            congeladas = frozenset(r["id"] for r in con.execute("SELECT id FROM prose_scene"))
            resumenes = [
                r["body"]
                for r in con.execute(
                    "SELECT body FROM summary WHERE level='chapter' ORDER BY CAST(ref_id AS INTEGER) DESC LIMIT 3"
                )
            ]
            proscritos = recipes.proscription_recent(con)
            usados = freeze_elements.used(con)
        deuda = debt(outline, congeladas, used_elements=usados)
        packet = recipes.simple_packet(
            "planificador",
            anchor=self.anchor(planner_prompts.SYSTEM),
            estimate=self.estimate,
            sections=[
                (
                    "mundo",
                    recipes.cards_text(cards),
                    BlockProvenance.CANON,
                    Priority.SECONDARY_CARDS,
                    None,
                )
            ],
        )
        r = self._call(
            "planificador",
            prefix=packet.cacheable_prefix,
            packet=packet.body(),
            instruction=planner_prompts.instruction(
                entries_,
                outline,
                cards=cards,
                debt=deuda,
                previous_summaries=resumenes,
                defects=defects,
            ),
            schema=planner_prompts.schema(),
            parse=planner_prompts.plan_model(entries_, forbidden=proscritos),
            context={"chapter": chapter, "respec": bool(defects)},
        )
        return planner_prompts.parse(r.raw, entries_, forbidden=proscritos)

    def respec(self, specs: Sequence[SceneSpec], defects: Sequence[Defect]) -> Sequence[SceneSpec]:
        if not specs or self.outline is None:
            return specs
        chapter = specs[0].identity.chapter
        nuevas = {s.identity.scene_id: s for s in self.specs_for(self.outline, chapter, defects)}
        return [nuevas.get(s.identity.scene_id, s) for s in specs]

    # ---------------------------------------------------------------- Escritor

    def _previous_prose(self, spec: SceneSpec) -> tuple[str, int | None, frozenset[str]]:
        """Bloque 6: la escena anterior literal, de borrador o congelada."""
        cap, ordinal = spec.identity.chapter, spec.identity.ordinal
        if ordinal > 1:
            texto = self._previous.get((cap, ordinal - 1))
            if texto is None:
                previos = drafts.load_drafts(self.path, chapter=cap)
                texto = next((d.text for d in previos if d.scene_number == ordinal - 1), "")
            return texto, None, frozenset()
        with connection.reader(self.path) as con:
            row = con.execute(
                "SELECT id, chapter FROM prose_scene ORDER BY chapter DESC, scene_number DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return "", None, frozenset()
            chunks = con.execute(
                "SELECT text FROM prose_chunk WHERE scene_id = ? ORDER BY ordinal", (row["id"],)
            ).fetchall()
        return "\n\n".join(c["text"] for c in chunks), row["chapter"], frozenset({row["id"]})

    def _writer_packet(self, spec: SceneSpec) -> Packet:
        b = recipes.BUDGETS["escritor"]
        anterior, cap_anterior, literales = self._previous_prose(spec)
        with connection.reader(self.path) as con:
            req = query_build.build(con, spec, token_budget=3_000, excluded_scenes=literales)
            vec = self.embedder.embed([req.semantic_text], is_query=True)  # type: ignore[attr-defined]
            setups_by_scene: dict[str, list[str]] = {}
            if self.outline is not None:
                for st in self.outline.setups:
                    setups_by_scene.setdefault(st.planted_scene, []).append(st.id)
            rec = retrieve(
                con,
                req,
                spec,
                query_vector=vec[0].values if vec else None,
                estimate=self.estimate,
                setups_by_scene=setups_by_scene,
                recent_voice_scenes=frozenset(self._voice_used[-3:]),
                literal_scenes=literales,
            )
            conocimiento = sorted(
                read.knowledge_of(con, spec.identity.pov, spec.identity.world_time)
            )
            related = read.related(con, list(spec.content.cast), at=spec.identity.world_time)
            voz = recipes.voice_sample(
                con,
                pov=spec.identity.pov,
                exclude_scenes=literales | {spec.identity.scene_id},
                recent_used=frozenset(self._voice_used[-3:]),
            )
            abiertas = []
            if self.outline is not None:
                congeladas = frozenset(r["id"] for r in con.execute("SELECT id FROM prose_scene"))
                abiertas = [
                    f"{s.id}: {s.description}"
                    for s in debt(
                        self.outline, congeladas, used_elements=freeze_elements.used(con)
                    ).open_setups
                    if s.id in spec.content.setups_to_pay or not spec.content.setups_to_pay
                ][:5]
            packet, facts = recipes.writer_packet(
                con,
                spec,
                anchor=self.anchor(writer_prompts.SYSTEM),
                estimate=self.estimate,
                retrieval=rec.selection,
                previous_prose=anterior,
                previous_chapter=cap_anterior,
                open_setups=abiertas,
                voice=voz,
                knowledge=conocimiento,
                related=related,
            )
        if voz is not None:
            self._voice_used.append(voz[0])
        packet = packet.model_copy(update={"degraded": rec.degraded})
        self.trace.emit(
            "packet",
            agent="escritor",
            chapter=spec.identity.chapter,
            scene=spec.identity.scene_id,
            tokens=packet.tokens,
            summaries=sum(1 for s in rec.selection.chosen if s.as_summary),
            blocks=[f"{bl.name}:{bl.tokens}" for bl in packet.blocks],
            quotas=[s.quota.value for s in rec.selection.chosen],
            empty_quotas=[q.value for q in rec.selection.empty_quotas],
            degraded=rec.degraded,
        )
        self._audit_or_arbitrate(packet, facts, spec.content.cast, b.input_tokens)
        return packet

    def write_scene(self, spec: SceneSpec, previous: Sequence[Defect] = ()) -> str:
        packet = self._writer_packet(spec)
        r = self._call(
            "escritor",
            prefix=packet.cacheable_prefix,
            packet=packet.body(),
            instruction=writer_prompts.instruction(
                spec, previous, min_words=self.brief.profile().scene_words[0]
            ),
            schema="",
            parse=None,
            context={"chapter": spec.identity.chapter, "scene": spec.identity.ordinal},
            at=spec.identity.world_time,
        )
        texto = r.raw.strip()
        self._previous[(spec.identity.chapter, spec.identity.ordinal)] = texto
        return texto

    # ----------------------------------------------------------- Especialista

    def _squads(self, spec: SceneSpec) -> tuple[Squad, Squad]:
        """Plantillas desde el canon: quien tiene `equipo`, con su estado y nivel.

        El equipo del POV juega en casa. Si el canon no da dos equipos, la escena
        no es un encuentro que se pueda resolver, y eso es un defecto de
        planificacion que se lanza, no se disimula.
        """
        with connection.reader(self.path) as con:
            estado = read.state_at(con, spec.identity.world_time)
        equipos: dict[str, list[Player]] = {}
        for c in estado.cards:
            attrs = dict(c.attributes)
            if "equipo" not in attrs:
                continue
            disp = Availability.AVAILABLE
            if attrs.get("estado") in {a.value for a in Availability}:
                disp = Availability(attrs["estado"])
            skill = int(attrs["nivel"]) if str(attrs.get("nivel", "")).isdigit() else 50
            equipos.setdefault(attrs["equipo"], []).append(
                Player(entity_id=c.entity_id, name=c.name, availability=disp, skill=skill)
            )
        if len(equipos) < 2:
            raise ValueError(
                f"la escena {spec.identity.scene_id} es un encuentro y el canon solo da "
                f"{len(equipos)} equipo(s): hace falta el atributo `equipo` en dos plantillas"
            )
        pov_team = next(
            (t for t, ps in equipos.items() if any(p.entity_id == spec.identity.pov for p in ps)),
            None,
        )
        casa = pov_team or sorted(equipos)[0]
        fuera = next(t for t in sorted(equipos, key=lambda t: -len(equipos[t])) if t != casa)
        return Squad(team_id=casa, players=tuple(equipos[casa])), Squad(
            team_id=fuera, players=tuple(equipos[fuera])
        )

    def simulate_match(self, spec: SceneSpec) -> MatchResult:
        casa, fuera = self._squads(spec)
        seed = int(hashlib.sha256(spec.identity.scene_id.encode()).hexdigest()[:8], 16)
        return simulate(casa, fuera, at=spec.identity.world_time, seed=seed)

    def narrate_match(
        self, spec: SceneSpec, result: MatchResult, previous: Sequence[Defect] = ()
    ) -> str:
        nombres = self._names()
        with connection.reader(self.path) as con:
            cards = read.query(con, list(spec.content.cast), at=spec.identity.world_time)
        secciones = [
            (
                "cronologia",
                narrate_prompts.chronology(result, nombres),
                BlockProvenance.CANON,
                Priority.UNTOUCHABLE,
                None,
            ),
            ("reglamento", self.brief.rulebook, BlockProvenance.CANON, Priority.SUMMARIES, None),
            (
                "fichas",
                recipes.cards_text(cards),
                BlockProvenance.CANON,
                Priority.SECONDARY_CARDS,
                None,
            ),
        ]
        packet = recipes.simple_packet(
            "especialista",
            anchor=self.anchor(narrate_prompts.SYSTEM),
            estimate=self.estimate,
            sections=secciones,
        )
        r = self._call(
            "especialista",
            prefix=packet.cacheable_prefix,
            packet=packet.body(),
            instruction=narrate_prompts.instruction(
                spec, result, nombres, previous, profile=self.brief.profile()
            ),
            schema="",
            parse=None,
            context={"chapter": spec.identity.chapter, "scene": spec.identity.ordinal},
        )
        texto = r.raw.strip()
        self._previous[(spec.identity.chapter, spec.identity.ordinal)] = texto
        return texto

    # ---------------------------------------------------------- verificadores

    def _known_names(self) -> list[str]:
        with connection.reader(self.path) as con:
            nombres = [r["name"] for r in con.execute("SELECT name FROM entity")]
            nombres += [r["alias"] for r in con.execute("SELECT alias FROM entity_alias")]
        tokens: list[str] = []
        for n in nombres:
            tokens.extend(n.split())
        return nombres + tokens

    def _name_candidates(self, text: str) -> list[str]:
        """Palabras con mayuscula que pueden ser un nombre fuera del canon.

        Dos vias. La de un nombre **nuevo**: solo cuenta lo que va detras de una
        letra o una coma --tras punto, signo de apertura, raya o comillas la
        mayuscula es ortografia, no nombre-- y solo lo que se repite, porque una
        mayuscula suelta suele ser un enfasis o un titulo.

        La de una **errata** de un nombre del canon ("Nalah", "Nála" frente a
        "Nala"): basta una aparicion, en cualquier posicion. Al principio de
        frase la mayuscula no dice nada, asi que ahi una palabra que tambien
        sale en minuscula en el texto, o una de las comunes, es vocabulario y no
        errata: "Cara a cara" no es "Carla".
        """
        conocidos = self._known_names()
        minusculas = {m.group(0) for m in re.finditer(r"\b[a-záéíóúñü]+\b", text)}
        vistos: dict[str, int] = {}
        erratas: set[str] = set()
        for m in _CAPITAL.finditer(text):
            w = m.group(1)
            if w.lower() in _COMMON_CAPITALS:
                continue
            antes = text[: m.start()].rstrip()
            en_medio = bool(antes) and (antes[-1].isalpha() or antes[-1] == ",")
            if en_medio:
                vistos[w] = vistos.get(w, 0) + 1
            elif w.lower() in minusculas:
                continue
            if checks.misspelling_of(w, conocidos) is not None:
                erratas.add(w)
        return sorted({w for w, n in vistos.items() if n >= 2} | erratas)

    def _checked(self, spec: SceneSpec, ran: Sequence[str], defects: list[Defect]) -> list[Defect]:
        """RF-265. Que verificadores corrieron sobre la escena y cuales marcaron.

        `check.<kind>` es un booleano por intento de escena: sin la lista de los
        que corrieron, un verificador que pasa no se distingue de uno que no se
        llamo.
        """
        self.trace.emit(
            "scene.checks",
            chapter=spec.identity.chapter,
            scene=spec.identity.ordinal,
            ran=list[JsonValue](ran),
            failed=list[JsonValue](sorted({d.kind for d in defects})),
        )
        return defects

    def verify_scene(self, spec: SceneSpec, text: str) -> list[Defect]:
        return self._checked(spec, SCENE_CHECKS, self._scene_defects(spec, text))

    def _scene_defects(self, spec: SceneSpec, text: str) -> list[Defect]:
        with connection.reader(self.path) as con:
            # RF-236, D-91. Las prohibidas de los tres niveles van a
            # `check.forbidden`, S1; a `check.repetition` solo le queda lo de
            # estilo. Una sola fuente por termino: dos avisos de lo mismo con
            # severidades distintas no dicen que hacer.
            prohibidas = forbidden.read_terms(con)
            estilo = forbidden.read_style_terms(con)
            fechas = [r["world_time"] for r in con.execute("SELECT DISTINCT world_time FROM event")]
            fechas += [
                r["world_time"] for r in con.execute("SELECT DISTINCT world_time FROM prose_scene")
            ]
        fechas.append(spec.identity.world_time.stamp)
        if self.outline is not None:
            fechas += [s.world_time.stamp for s in self.outline.scenes]

        defectos: list[Defect] = []
        defectos += checks.check_format(
            text,
            tense=spec.constraints.tense,
            person=spec.constraints.person,
            word_range=self.brief.profile().scene_words,
        )
        defectos += checks.check_timeline(text, allowed_dates=fechas)
        defectos += forbidden.check_forbidden(text, terms=prohibidas)
        defectos += checks.check_repetition(text, frozen_ngrams=[], proscribed=estilo)
        defectos += checks.check_lexicon(
            text, known_names=self._known_names(), candidates=self._name_candidates(text)
        )
        defectos += checks.check_knowledge(
            text,
            pov_knows=[],
            mentioned_facts=[
                (f, f) for f in spec.constraints.facts_unknown_to_pov if f and f in text
            ],
        )
        return defectos

    def verify_match(self, spec: SceneSpec, text: str, result: MatchResult) -> list[Defect]:
        nombres = self._names()
        defectos = self._scene_defects(spec, text)
        defectos += checks.check_ledger(
            text,
            expected_score=narrate_prompts.expected_score(result),
            team_names=[
                nombres.get(result.home_team, result.home_team),
                nombres.get(result.away_team, result.away_team),
            ],
        )
        defectos += checks.check_milestones(text, scorers=narrate_prompts.scorers(result, nombres))
        with connection.reader(self.path) as con:
            estado = read.state_at(con, spec.identity.world_time)
        indisponibles = [
            (c.name, dict(c.attributes)["estado"])
            for c in estado.cards
            if dict(c.attributes).get("estado")
            in {Availability.INJURED.value, Availability.SUSPENDED.value}
            and c.entity_id not in result.injuries
        ]
        defectos += checks.check_availability(text, unavailable=indisponibles)
        return self._checked(spec, (*SCENE_CHECKS, *MATCH_CHECKS), defectos)

    # ------------------------------------------------------------ Continuista

    def review_chapter(self, specs: Sequence[SceneSpec], texts: Sequence[str]) -> Anchored:
        inicio, fin = specs[0].identity.world_time, specs[-1].identity.world_time
        with connection.reader(self.path) as con:
            antes = read.state_at(con, inicio)
            despues = read.state_at(con, fin)
            conocimiento = recipes.knowledge_of_cast(
                con, sorted({s.identity.pov for s in specs}), inicio
            )
            hechos = [
                f"{r['world_time']} {r['type']} {r['payload']}"
                for r in con.execute(
                    "SELECT world_time, type, payload FROM event WHERE world_time <= ? ORDER BY world_time DESC, world_seq DESC LIMIT 40",
                    (fin.stamp,),
                )
            ]
            congeladas = frozenset(r["id"] for r in con.execute("SELECT id FROM prose_scene"))
            usados = freeze_elements.used(con)
        abiertas = (
            [
                f"{s.id}: {s.description}"
                for s in debt(self.outline, congeladas, used_elements=usados).open_setups
            ]
            if self.outline
            else []
        )
        capitulo = "\n\n".join(texts)
        # RF-118, RF-119: con resumenes de arco, el bloque de resumenes no crece
        # con la novela. Los cinco capitulos anteriores son los de §4.9.
        primero = specs[0].identity.chapter
        with connection.reader(self.path) as con:
            arcos = levels.arc_summaries(con)
            previos = levels.chapter_summaries(con, list(range(max(1, primero - 5), primero)))
        resumenes = "\n\n".join(
            [*(f"ARCO: {a}" for a in arcos), *(f"CAPITULO ANTERIOR: {c}" for c in previos)]
        )
        secciones = [
            (
                "estado-antes",
                recipes.state_text(antes),
                BlockProvenance.CANON,
                Priority.SECONDARY_CARDS,
                None,
            ),
            (
                "estado-despues",
                recipes.state_text(despues),
                BlockProvenance.CANON,
                Priority.SECONDARY_CARDS,
                None,
            ),
            ("eventos", "\n".join(hechos), BlockProvenance.CANON, Priority.SUMMARIES, None),
            ("resumenes", resumenes, BlockProvenance.CANON, Priority.SUMMARIES, None),
        ]
        packet = recipes.simple_packet(
            "continuista",
            anchor=self.anchor(continuity_prompts.SYSTEM),
            estimate=self.estimate,
            sections=secciones,
        )
        r = self._call(
            "continuista",
            prefix=packet.cacheable_prefix,
            packet=packet.body(),
            instruction=continuity_prompts.instruction(
                specs,
                texts,
                state_before=antes,
                state_after=despues,
                knowledge=conocimiento,
                frozen_facts=hechos[:20],
                open_setups=abiertas,
            ),
            schema=continuity_prompts.schema(),
            parse=review.Review,
            context={"chapter": specs[0].identity.chapter},
            at=fin,
        )
        return review.anchor_all(review.parse(r.raw), capitulo)

    # ------------------------------------------------------------------ Lector

    def answer_quiz(self, chapter_text: str, questions: Sequence[Question]) -> Sequence[str]:
        # RF-114: sin prefijo cacheable, sin canon, sin fichas.
        r = self._call(
            "lector",
            prefix=quiz_prompts.SYSTEM,
            packet="",
            instruction=quiz_prompts.instruction(chapter_text, questions),
            schema=quiz_prompts.schema(),
            parse=quiz_prompts.Answers,
            context={"questions": len(questions)},
        )
        return quiz_prompts.parse(r.raw, questions)

    # --------------------------------------------------------------- Reparador

    def repair_scene(self, spec: SceneSpec, text: str, defects: Sequence[Defect]) -> str:
        with connection.reader(self.path) as con:
            cards = read.query(con, list(spec.content.cast), at=spec.identity.world_time)
        hechos = [f"{c.name}: " + ", ".join(f"{k}={v}" for k, v in c.attributes) for c in cards]
        anterior, _cap, _lit = self._previous_prose(spec)
        cola = anterior[-700:] if anterior else ""
        secciones = [
            (
                "fichas",
                recipes.cards_text(cards),
                BlockProvenance.CANON,
                Priority.SECONDARY_CARDS,
                None,
            )
        ]
        packet = recipes.simple_packet(
            "reparador",
            anchor=self.anchor(repair_prompts.SYSTEM),
            estimate=self.estimate,
            sections=secciones,
        )
        r = self._call(
            "reparador",
            prefix=packet.cacheable_prefix,
            packet=packet.body(),
            instruction=repair_prompts.instruction(
                spec, text, defects, canon_facts=hechos, previous_tail=cola
            ),
            schema="",
            parse=None,
            context={
                "chapter": spec.identity.chapter,
                "scene": spec.identity.ordinal,
                "defects": len(defects),
            },
            at=spec.identity.world_time,
        )
        nuevo = r.raw.strip()
        self._previous[(spec.identity.chapter, spec.identity.ordinal)] = nuevo
        return nuevo

    # --------------------------------------------------------------- Archivero

    def _summarize(
        self,
        level: SummaryLevel,
        parts: Sequence[str],
        *,
        value_change: str | None = None,
        context: Mapping[str, object],
        max_words: int | None = None,
    ) -> str:
        r = self._call(
            "archivero",
            prefix=self.anchor(summary_prompts.SYSTEM),
            packet="",
            instruction=summary_prompts.instruction(
                level, parts, value_change=value_change, max_words=max_words
            ),
            schema="",
            parse=None,
            context={"level": level.value, **context},
        )
        return r.raw.strip()

    def summarize_scene(self, spec: SceneSpec, text: str) -> str:
        palabras = len(text.split())
        resumen = self._summarize(
            SummaryLevel.SCENE,
            [text],
            value_change=spec.function.value_change,
            context={"scene": spec.identity.scene_id},
            max_words=self.brief.profile().summary_cap(palabras),
        )
        self._summary_sources[resumen] = palabras
        return resumen

    def summarize_chapter(self, scene_summaries: Sequence[str]) -> str:
        # T53. El tope sale de lo que mide el capitulo. Un resumen de escena que
        # no se escribio en esta tirada --el de una escena que un retcon no
        # toco-- cuenta como el doble de sus palabras: es lo menos que puede
        # medir su escena con el mismo tope, asi que el del capitulo nunca se pasa.
        capitulo = sum(self._summary_sources.get(p, 2 * len(p.split())) for p in scene_summaries)
        return self._summarize(
            SummaryLevel.CHAPTER,
            scene_summaries,
            context={"parts": len(scene_summaries)},
            max_words=self.brief.profile().summary_cap(capitulo),
        )

    def summarize_arc(self, chapter_summaries: Sequence[str]) -> str:
        return self._summarize(
            SummaryLevel.ARC, chapter_summaries, context={"parts": len(chapter_summaries)}
        )

    def summarize_work(self, parts: Sequence[str]) -> str:
        return self._summarize(SummaryLevel.WORK, parts, context={"parts": len(parts)})

    def extract_delta(
        self, specs: Sequence[SceneSpec], texts: Sequence[str], state_before: WorldState
    ) -> archivist.DeltaProposal:
        chapter = specs[0].identity.chapter
        # RF-261. Los elementos del brief que el Archivero puede citar, del canon.
        with connection.reader(self.path) as con:
            encargo = [(e.id, e.kind, e.text) for e in freeze_elements.declared(con)]
        secciones = [
            (
                "esquema",
                archivist_prompts.schema(),
                BlockProvenance.PLAN,
                Priority.UNTOUCHABLE,
                None,
            ),
        ]
        packet = recipes.simple_packet(
            "archivero",
            anchor=self.anchor(archivist_prompts.SYSTEM),
            estimate=self.estimate,
            sections=secciones,
        )
        r = self._call(
            "archivero",
            prefix=packet.cacheable_prefix,
            packet=packet.body(),
            instruction=archivist_prompts.instruction(
                specs, texts, state_before, chapter=chapter, elements=encargo
            ),
            schema=archivist_prompts.schema(),
            parse=archivist.DeltaProposal,
            context={"chapter": chapter},
            at=specs[-1].identity.world_time,
        )
        return archivist.parse(r.raw)

    # ----------------------------------------------------------------- Jurado

    def _rubrics(self) -> RubricSet:
        """RNF-37. La version de las rubricas que guarda el fichero."""
        with connection.reader(self.path) as con:
            row = con.execute(
                "SELECT body FROM document_version WHERE doc_kind = 'rubrics' "
                "ORDER BY version DESC LIMIT 1"
            ).fetchone()
        return rubric_types.loads(row["body"]) if row else rubric_types.DEFAULT_RUBRICS

    def judge_chapter(self, specs: Sequence[SceneSpec], texts: Sequence[str]) -> JuryVerdict:
        """RF-126 a RF-131, RF-160. Tres instancias en paralelo bajo la admision.

        Cada una con su semilla; el paquete es el de §4.9 del Jurado: invariantes
        sin guia de estilo, rubricas, encargo como dato, capitulo, fichas de voz.
        Nada del Escritor. Las dimensiones son las del conjunto de rubricas del
        fichero: nueve en la version 2 (RF-257, RF-258).
        """
        # D-114. Lo que no tiene encargo contra el que juzgarse no se juzga: sin
        # destinatario ni elementos obligatorios no hay personalizacion, y sin tono
        # pedido no hay tono. Puntuarlas daria siempre el nivel minimo y bloquearia.
        rubricas = self._rubrics().without(*self._not_applicable())
        encargo = self._commission()
        with connection.reader(self.path) as con:
            povs = sorted({s.identity.pov for s in specs})
            voz = recipes.cards_text(read.query(con, povs, at=specs[0].identity.world_time))
        textos = {s.identity.scene_id: t for s, t in zip(specs, texts, strict=True)}
        # D-128. El umbral, el minimo de palabras de la cita y la regla de la
        # cita del prompt salen del perfil de extension de la obra.
        perfil = self.brief.profile()
        base = int(hashlib.sha256(specs[0].identity.scene_id.encode()).hexdigest()[:6], 16)

        def una(indice: int, semilla: int) -> tuple[str, tuple[int, InstanceVerdict]]:
            r = self._call(
                "juez",
                prefix=jury_prompts.system(perfil),
                packet="",
                instruction=jury_prompts.instruction(
                    specs,
                    texts,
                    rubrics=rubricas,
                    voice_cards=voz,
                    seed=semilla,
                    commission=encargo,
                ),
                schema=jury_prompts.schema(),
                parse=InstanceVerdict,
                context={"chapter": specs[0].identity.chapter, "instance": indice, "seed": semilla},
                validate=lambda raw: unanchored(jury_prompts.parse(raw), textos, profile=perfil),
            )
            return f"juez-{indice}", (semilla, jury_prompts.parse(r.raw))

        def run(seeds: Sequence[int]) -> dict[str, tuple[int, InstanceVerdict]]:
            with ThreadPoolExecutor(max_workers=len(seeds)) as pool:
                return dict(pool.map(lambda par: una(*par), enumerate(seeds, 1)))

        return adjudicate(
            run,
            textos,
            seeds=[base + i for i in range(INSTANCES)],
            dimensions=rubricas.dimensions,
            profile=perfil,
        )

    def _not_applicable(self) -> tuple[Dimension, ...]:
        """D-114. Las dimensiones del Jurado sin encargo que juzgar en este brief."""
        fuera: list[Dimension] = []
        obligatorios = [e for e in brief_elements(self.brief) if e.mandatory]
        if not self.brief.recipient_name() and not obligatorios:
            fuera.append(Dimension.PERSONALIZATION)
        if not self.brief.tone:
            fuera.append(Dimension.TONE)
        return tuple(fuera)

    def _commission(self) -> str:
        """RF-258. El encargo del Jurado: destinatario, rasgos y recuerdos
        obligatorios, y el tono pedido. Del brief, como dato delimitado."""
        obligatorios = [e for e in brief_elements(self.brief) if e.mandatory]
        return jury_prompts.commission_text(
            recipient=self.brief.recipient_name(),
            traits=[e.text for e in obligatorios if e.kind == "trait"],
            memories=[e.text for e in obligatorios if e.kind == "memory"],
            tone=self.brief.tone,
        )

    def golden_check(self) -> float:
        """RF-134. El Jurado contra los casos sembrados, sin saber que lo son.

        Cuantos casos, lo dice el perfil de la obra (D-131).
        """
        with connection.reader(self.path) as con:
            casos = jury_golden.build(con, limit=self.brief.profile().golden_cases)
            por_id = {
                r["id"]: r
                for r in con.execute(
                    "SELECT id, chapter, scene_number, pov_entity, world_time FROM prose_scene"
                )
            }
        resultados = []
        for caso in casos:
            specs = [self._frozen_spec(por_id[sid]) for sid in caso.scene_ids]
            resultados.append((caso, self.judge_chapter(specs, caso.texts)))
        return jury_golden.detection_rate(resultados)

    def _frozen_spec(self, row: Any) -> SceneSpec:
        """Una especificacion minima para juzgar una escena congelada."""
        return SceneSpec(
            identity=SceneIdentity(
                scene_id=row["id"],
                chapter=row["chapter"],
                ordinal=row["scene_number"],
                pov=row["pov_entity"],
                place="desconocido",
                world_time=WorldTime(stamp=row["world_time"]),
            ),
            function=DramaticFunction(
                function=SceneFunction.ESTABLISH,
                value_change="congelada",
                objective="la de su escena",
                obstacle="la de su escena",
            ),
            content=SceneContent(cast=(row["pov_entity"],), beats=("congelada",)),
            output=ExpectedOutput(target_words=900, ends_with="congelada"),
            constraints=SceneConstraints(),
        )

    # --------------------------------------------------------------- Estilista

    def polish_chapter(
        self, specs: Sequence[SceneSpec], texts: Sequence[str], repetitions: Sequence[Defect]
    ) -> list[str]:
        """RF-139. Guia completa, proscripcion completa, huellas, repeticiones."""
        with connection.reader(self.path) as con:
            proscritos = [
                r["term"]
                for r in con.execute("SELECT term FROM proscribed ORDER BY added_chapter DESC")
            ]
            previas = freeze_rows.read_fingerprints(con)
            povs = sorted({s.identity.pov for s in specs})
            muestras = recipes.model_samples(
                con, povs=povs, exclude_scenes=frozenset(s.identity.scene_id for s in specs)
            )
            voz = recipes.cards_text(read.query(con, povs, at=specs[0].identity.world_time))
        referencia = ", ".join(
            f"{r.chapter}: frase {r.mean_sentence_len:.1f}, adj/sust {r.adj_noun_ratio:.2f}, riqueza {r.lexical_richness:.2f}"
            for r in previas[:3]
        )
        actual = self.fingerprint("\n\n".join(texts))
        packet = recipes.simple_packet(
            "estilista",
            anchor=self.anchor(style_prompts.SYSTEM),
            estimate=self.estimate,
            sections=[],
        )
        r = self._call(
            "estilista",
            prefix=packet.cacheable_prefix,
            packet=packet.body(),
            instruction=style_prompts.instruction(
                specs,
                texts,
                proscribed=proscritos,
                repetitions=[d.evidence.quote for d in repetitions],
                reference=referencia,
                current=f"frase {actual.mean_sentence_len:.1f}, adj/sust {actual.adj_noun_ratio:.2f}, riqueza {actual.lexical_richness:.2f}",
                samples=muestras,
                voice_cards=voz,
            ),
            schema=style_prompts.schema(),
            parse=style_prompts.Polished,
            context={"chapter": specs[0].identity.chapter},
        )
        return style_prompts.parse(r.raw, specs)

    def fingerprint(self, text: str) -> Fingerprint:
        return style_fingerprint.compute(text)

    # ------------------------------------------------------------------ retcon

    def propose_retcon(
        self, rejection: entries.Rejection, passages: Sequence[str]
    ) -> retcon_rules.RetconProposal:
        """RF-151. El Arbitro propone; la regla dura del bucle decide."""
        packet = recipes.simple_packet(
            "arbitro",
            anchor=self.anchor(retcon_rules.SYSTEM),
            estimate=self.estimate,
            sections=[
                (
                    "precedencia",
                    "PRO-10: canon congelado > delta nuevo; brief > derivado; "
                    "invariante > preferencia; cobrado > sin cobrar.",
                    BlockProvenance.PLAN,
                    Priority.UNTOUCHABLE,
                    None,
                ),
            ],
        )
        r = self._call(
            "arbitro",
            prefix=packet.cacheable_prefix,
            packet=packet.body(),
            instruction=retcon_rules.instruction(rejection, passages),
            schema=retcon_rules.schema(),
            parse=retcon_rules.RetconProposal,
            context={"fact": rejection.arbitration.incumbent.fact_key},
        )
        return retcon_rules.parse(r.raw)

    def retcon_rewrite(
        self, scene_id: str, text: str, plan: retcon_rules.RetconPlan
    ) -> tuple[refreeze.RefrozenScene, list[Defect]]:
        """RF-153. El Reparador reescribe el pasaje con el hecho nuevo delante."""
        with connection.reader(self.path) as con:
            row = con.execute(
                "SELECT id, chapter, scene_number, pov_entity, world_time FROM prose_scene WHERE id = ?",
                (scene_id,),
            ).fetchone()
        spec = self._frozen_spec(row)
        pos = text.lower().find(plan.previous_value.lower())
        defecto = Defect(
            kind="retcon",
            severity=Severity.S1,
            evidence=Evidence(
                quote=text[max(0, pos) : max(0, pos) + 80] or plan.previous_value,
                offset=max(0, pos),
            ),
            rule=(
                f"el canon ahora dice {plan.fact_key}={plan.new_value!r}; el pasaje sostiene "
                f"{plan.previous_value!r}. Cambia solo eso"
            ),
        )
        nuevo = self.repair_scene(spec, text, [defecto])
        resumen = self.summarize_scene(spec, nuevo)
        # RF-153: se reverifica desde `check.*` y por el Continuista.
        defectos = [*self.verify_scene(spec, nuevo), *self.review_chapter([spec], [nuevo]).defects]
        return refreeze.RefrozenScene(scene_id=scene_id, text=nuevo, summary=resumen), defectos

    # -------------------------------------------------------------- Supervisor

    def supervise(
        self,
        chapter: int,
        total: int,
        outline: Outline,
        metrics: Sequence[freeze_rows.MetricRow],
    ) -> HealthVerdict:
        """RF-146. El paquete de §4.9 del Supervisor, con sus herramientas."""
        with connection.reader(self.path) as con:
            historia = [r for r in freeze_rows.read_metrics(con) if r.chapter < chapter]
            por_capitulo = {
                int(r["ref_id"]): r["body"]
                for r in con.execute("SELECT ref_id, body FROM summary WHERE level = 'chapter'")
            }
            por_arco = {
                r["ref_id"]: r["body"]
                for r in con.execute("SELECT ref_id, body FROM summary WHERE level = 'arc'")
            }
        resumenes = supervisor_summaries(outline, por_capitulo, por_arco)
        with connection.reader(self.path) as con:
            congeladas = frozenset(r["id"] for r in con.execute("SELECT id FROM prose_scene"))
            usados = freeze_elements.used(con)
            ritmo = {
                int(r["chapter"]): r["lvl"]
                for r in con.execute(
                    "SELECT s.chapter AS chapter, max(v.level) AS lvl FROM scene_verdict v "
                    "JOIN prose_scene s ON s.id = v.scene_id WHERE v.dimension = 'pacing' AND v.valid = 1 "
                    "GROUP BY s.chapter"
                )
            }
        deuda = [
            f"{s.id}: {s.description}"
            for s in debt(outline, congeladas, used_elements=usados).open_setups
        ]
        curva = "\n".join(
            f"  acto {a.number}: planificada {list(a.tension)}; realizada "
            + str(
                [
                    ritmo.get(c)
                    for c in sorted({s.chapter for s in outline.scenes if s.act == a.number})
                ]
            )
            for a in outline.acts
        )
        restante = "\n".join(
            f"  {s.id}: capitulo {s.chapter}, acto {s.act}, {s.function.value}, {s.value_change}"
            for s in outline.scenes
            if s.chapter > chapter
        )
        packet = recipes.simple_packet(
            "supervisor",
            anchor=self.anchor(supervision_prompts.SYSTEM),
            estimate=self.estimate,
            sections=[],
        )
        r = self._call(
            "supervisor",
            prefix=packet.cacheable_prefix,
            packet=packet.body(),
            instruction=supervision_prompts.instruction(
                chapter=chapter,
                total_chapters=total,
                metrics=metrics,
                history=historia,
                debt=deuda,
                curve=curva,
                summaries=resumenes,
                remaining_outline=restante,
            ),
            schema=supervision_prompts.schema(),
            parse=HealthVerdict,
            context={"chapter": chapter},
        )
        return supervision_prompts.parse(r.raw)

    # ------------------------------------------------------------ Lean

    def formal_check(self, path: Path, pending: Pending) -> LeanResult:
        """RF-254, D-88. `run_lean` sobre el canon mas lo que va a entrar."""
        return formal.run_lean(path, pending)

    # ------------------------------------------------------------------ motor

    def engine(self) -> Engine:
        return Engine(
            plan_outline=self.plan_outline,
            replan_act=self.replan_act,
            respec=self.respec,
            write_scene=self.write_scene,
            simulate_match=self.simulate_match,
            narrate_match=self.narrate_match,
            verify_scene=self.verify_scene,
            verify_match=self.verify_match,
            review_chapter=self.review_chapter,
            answer_quiz=self.answer_quiz,
            repair_scene=self.repair_scene,
            summarize_scene=self.summarize_scene,
            summarize_chapter=self.summarize_chapter,
            summarize_arc=self.summarize_arc,
            summarize_work=self.summarize_work,
            extract_delta=self.extract_delta,
            embed=self.embedder,
            judge_chapter=self.judge_chapter,
            polish_chapter=self.polish_chapter,
            fingerprint=self.fingerprint,
            golden_check=self.golden_check,
            supervise=self.supervise,
            propose_retcon=self.propose_retcon,
            retcon_rewrite=self.retcon_rewrite,
            formal_check=self.formal_check,
        )


def specs_provider(composer: Composer) -> Callable[[Outline, int], Sequence[SceneSpec]]:
    """La firma que `run` espera para el Planificador."""

    def specs_for(outline: Outline, chapter: int) -> Sequence[SceneSpec]:
        return composer.specs_for(outline, chapter)

    return specs_for
