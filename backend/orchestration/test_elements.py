"""Elementos obligatorios de punta a punta, y el encargo en el Jurado real.

RF-258, RF-260, RF-261, D-95. VER-05, VER-19. `specs/srs-backend-v4.md` T47.

La puerta de T47: un recuerdo obligatorio sin uso anclado impide cerrar la obra
y el motivo lo nombra. Con motores dobles, como `test_loop`: la escaleta
planifica cada rasgo y recuerdo obligatorio como setup `element.<id>`, el
Archivero cita su uso y el bucle lo ancla con `check.evidence` antes de
congelar. Sin cita, o con una cita que no esta en el texto, no hay uso.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from canon.archivist.extract import DeltaProposal, ElementMention
from canon.brief import Brief, Recipient, create_novel
from canon.db import connection
from commons.tokens.counter import TokenCounter
from commons.tokens.factors import ModelFactors
from commons.tracing.trace import Trace
from commons.types.rubrics import DEFAULT_RUBRICS
from commons.types.scene import SceneSpec
from orchestration.admission import Admission
from orchestration.engine import Composer
from orchestration.loop import RunAbortedError, run
from orchestration.test_engine import PROSA, ScriptedPort, _closing, _Embedder
from orchestration.test_engine import _brief as _engine_brief
from orchestration.test_loop import _brief as _loop_brief
from orchestration.test_loop import _delta, _engine, _outline, _specs
from planning.outline.types import Outline, Setup
from verification.jury.prompts import COMMISSION_CLOSE, COMMISSION_OPEN
from verification.jury.test_rubrics_v2 import _spec

RASGO = "paciente"
RECUERDO = "el verano en que su padre le enseno a flotar en el rio"
COMETA = "la tarde de la cometa roja enganchada en el pino"
#: Lo que la prosa narra de cada elemento: el recuerdo no se dice literal.
FRASES = {
    "c1e2": "Marcos espero sin prisa a que todos terminaran, como hacia siempre antes de hablar.",
    "c2e1": "Marcos se acordo del rio y de la mano de su padre sosteniendole la nuca en el agua.",
}
CITAS = {
    "trait-1": ("c1e2", "Marcos espero sin prisa a que todos terminaran, como hacia siempre"),
    "memory-1": ("c2e1", "Marcos se acordo del rio y de la mano de su padre sosteniendole"),
}


def _brief() -> Brief:
    return _loop_brief().model_copy(
        update={
            "recipient": Recipient(
                entity_id="marcos",
                age=30,
                traits=(RASGO,),
                memories=(RECUERDO, COMETA),
                optional=(COMETA,),
                role="protagonista",
            )
        }
    )


def _con_elementos(outline: Outline | None = None) -> Outline:
    base = outline or _outline()
    return base.model_copy(
        update={
            "setups": (
                *base.setups,
                Setup(
                    id="element.trait-1",
                    planted_scene="c1e2",
                    payoff_scene="c1e2",
                    description=RASGO,
                ),
                Setup(
                    id="element.memory-1",
                    planted_scene="c1e1",
                    payoff_scene="c2e1",
                    description=RECUERDO,
                ),
            )
        }
    )


def _escribe(spec: SceneSpec, _p: object) -> str:
    base = " ".join(["palabra"] * spec.output.target_words)
    return f"{base} {FRASES.get(spec.identity.scene_id, '')}".strip()


def _archivero(
    citas: dict[str, tuple[str, str]],
) -> Callable[[Sequence[SceneSpec], Sequence[str], object], DeltaProposal]:
    """El Archivero doble: el delta de `test_loop` mas los elementos que cita."""

    def extrae(specs: Sequence[SceneSpec], textos: Sequence[str], estado: object) -> DeltaProposal:
        propias = {s.identity.scene_id for s in specs}
        menciones = tuple(
            ElementMention(element_id=eid, scene=escena, quote=cita)
            for eid, (escena, cita) in citas.items()
            if escena in propias
        )
        return _delta(specs, textos, estado).model_copy(update={"elements": menciones})

    return extrae


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief(), global_terms=())
    return path


def _run(
    novela: Path, *, citas: dict[str, tuple[str, str]], outline: Outline | None = None
) -> tuple[object, Trace]:
    traza = Trace(novela.with_suffix(".trace.jsonl"))
    escaleta = outline or _con_elementos()
    informe = run(
        novela,
        _brief(),
        _engine(
            plan_outline=lambda _b, _c, _d: escaleta,
            write_scene=_escribe,
            extract_delta=_archivero(citas),
        ),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )
    return informe, traza


# ------------------------------------------------------------- la puerta


def test_con_los_usos_anclados_la_obra_cierra(novela: Path) -> None:
    """RF-261. El opcional no se exige; los dos obligatorios, anclados, cobran."""
    informe, _traza = _run(novela, citas=CITAS)
    assert informe.closed, informe.reason  # type: ignore[attr-defined]
    with connection.reader(novela) as con:
        usos = {
            (r["element_id"], r["scene_id"])
            for r in con.execute("SELECT element_id, scene_id FROM element_use")
        }
        hechos = {
            r["fact_key"]
            for r in con.execute("SELECT fact_key FROM fact_usage WHERE fact_key LIKE 'element.%'")
        }
    assert usos == {("trait-1", "c1e2"), ("memory-1", "c2e1")}
    assert hechos == {"element.trait-1", "element.memory-1"}


def test_un_recuerdo_obligatorio_sin_uso_anclado_impide_cerrar_y_el_motivo_lo_nombra(
    novela: Path,
) -> None:
    """La puerta de T47 (D-95)."""
    informe, traza = _run(novela, citas={"trait-1": CITAS["trait-1"]})
    assert not informe.closed  # type: ignore[attr-defined]
    motivo = informe.reason  # type: ignore[attr-defined]
    assert "recuerdo obligatorio memory-1 sin uso anclado" in motivo
    assert "flotar en el rio" in motivo
    assert "trait-1" not in motivo
    [cierre] = traza.records("work.close")
    assert cierre.fields["closed"] is False and "memory-1" in str(cierre.fields["reason"])
    # La puerta de acto ya lo vio al cerrar el acto 2, donde estaba su cobro.
    assert traza.records("act.gate")[-1].fields["unpaid"] == ["element.memory-1"]


def test_una_cita_que_no_ancla_no_es_un_uso_y_consta_contra_el_archivero(novela: Path) -> None:
    """RF-261. «Aparece» lo decide la cita anclada, no el Archivero."""
    inventada = {**CITAS, "memory-1": ("c2e1", "Marcos recordo aquel verano del rio con su padre")}
    informe, traza = _run(novela, citas=inventada)
    assert not informe.closed  # type: ignore[attr-defined]
    defectos = [r for r in traza.records("process.defect") if r.fields.get("element")]
    assert [(d.fields["agent"], d.fields["element"], d.fields["reason"]) for d in defectos] == [
        ("archivero", "memory-1", "cita sin anclar")
    ]


def test_un_elemento_que_el_brief_no_declara_se_descarta(novela: Path) -> None:
    ajeno = {**CITAS, "memory-9": CITAS["memory-1"]}
    informe, traza = _run(novela, citas=ajeno)
    assert informe.closed, informe.reason  # type: ignore[attr-defined]
    motivos = [
        r.fields["reason"] for r in traza.records("process.defect") if r.fields.get("element")
    ]
    assert motivos == ["elemento no declarado"]


def test_una_escaleta_sin_el_setup_del_recuerdo_no_arranca(novela: Path) -> None:
    """RF-260. `outline.check` falla si un obligatorio no tiene cobro planificado."""
    with pytest.raises(RunAbortedError, match="elemento-sin-cobro"):
        _run(novela, citas=CITAS, outline=_outline())


# ------------------------------------------------------- el Jurado real


class _Grabador(ScriptedPort):
    """El proveedor guionizado que guarda lo que recibe cada juez."""

    def __init__(self) -> None:
        super().__init__()
        self.jueces: list[str] = []

    def _answer(self, prefix: str, instruction: str) -> str:
        if "instancia del Jurado" in prefix:
            self.jueces.append(instruction)
        return super()._answer(prefix, instruction)


def test_cada_juez_recibe_el_encargo_como_dato_y_puntua_nueve(tmp_path: Path) -> None:
    """RF-257, RF-258. Nombre, rasgos y recuerdos obligatorios y tono; nada opcional."""
    brief = _engine_brief().model_copy(
        update={
            "tone": "contenido",
            "recipient": Recipient(
                entity_id="marcos",
                age=30,
                traits=(RASGO,),
                memories=(RECUERDO, COMETA),
                optional=(COMETA,),
                role="protagonista",
            ),
        }
    )
    path = tmp_path / "n.sqlite"
    create_novel(path, brief, global_terms=())
    traza = Trace(tmp_path / "n.trace.jsonl")
    puerto = _Grabador()
    factores = ModelFactors()
    factores.set("haiku", 1.35)
    c = Composer(
        port=puerto,
        path=path,
        brief=brief,
        embedder=_Embedder(),
        counter=TokenCounter(factores),
        model_id="haiku",
        trace=traza,
        admission=Admission(trace=traza),
    )
    veredicto = c.judge_chapter([_spec()], [PROSA * 3 + _closing(1)])

    assert len(puerto.jueces) == 3
    for instruccion in puerto.jueces:
        encargo = instruccion.split(COMMISSION_OPEN, 1)[1].split(COMMISSION_CLOSE, 1)[0]
        assert "Destinatario: Marcos Vela" in encargo
        assert f"Rasgo: {RASGO}" in encargo and f"Recuerdo: {RECUERDO}" in encargo
        assert "Tono pedido: contenido" in encargo
        assert COMETA not in instruccion
    assert {d.dimension for d in veredicto.dimensions} == set(DEFAULT_RUBRICS.dimensions)
    assert veredicto.passed
    assert all(s.justification for d in veredicto.dimensions for s in d.scores)
