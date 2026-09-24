"""Los elementos del brief en la escaleta y en la deuda, y el encuentro sin reglamento.

RF-260, RF-261, RF-273, D-95, D-104. VER-05. `specs/srs-backend-v4.md` T47.

`outline.check` falla si un rasgo o recuerdo obligatorio no tiene su setup con
cobro planificado, y si una escena es un encuentro en un brief sin reglamento.
El registro de setups solo da por cobrado un elemento con un uso anclado: con la
escena de cobro congelada y sin uso, sigue debiendose, y la puerta de acto lo ve.
"""

from __future__ import annotations

from pathlib import Path

from canon.brief import Brief, BriefEntity, Recipient
from commons.types.primitives import WorldTime
from planning.act_gate.gate import check_act
from planning.ledger.setups import SetupState, debt, element_of, status
from planning.outline import prompts
from planning.outline.check import check
from planning.outline.test_check import RANGO, _valida
from planning.outline.types import Outline, Setup

BRIEFS = Path(__file__).resolve().parents[2] / "evals" / "briefs"
RECUERDO = ("memory-1", "el verano en que aprendio a flotar en el rio")


def _con_setups(*extra: Setup) -> Outline:
    base = _valida()
    return base.model_copy(update={"setups": (*base.setups, *extra)})


def _elemento(planted: str = "s2", payoff: str = "s5") -> Setup:
    return Setup(
        id="element.memory-1", planted_scene=planted, payoff_scene=payoff, description=RECUERDO[1]
    )


def _kinds(outline: Outline, **kw: object) -> list[tuple[str, str]]:
    return [(d.kind, d.where) for d in check(outline, word_range=RANGO, **kw)]  # type: ignore[arg-type]


# ------------------------------------------------------------ outline.check


def test_un_recuerdo_obligatorio_sin_setup_hace_fallar_la_escaleta() -> None:
    """RF-260. El defecto nombra el elemento y lo que falta."""
    defectos = check(_valida(), word_range=RANGO, elements=[RECUERDO])
    assert [(d.kind, d.where) for d in defectos] == [("elemento-sin-cobro", "memory-1")]
    assert "element.memory-1" in defectos[0].message and "flotar" in defectos[0].message


def test_con_su_setup_y_cobro_planificado_pasa() -> None:
    assert _kinds(_con_setups(_elemento()), elements=[RECUERDO]) == []


def test_el_setup_de_un_elemento_se_puede_cobrar_donde_se_planta() -> None:
    """El encargo ya lo planto: la escena es donde se integra."""
    assert _kinds(_con_setups(_elemento("s3", "s3")), elements=[RECUERDO]) == []
    trama = Setup(id="la-lista", planted_scene="s3", payoff_scene="s3", description="La lista")
    assert ("setup-invertido", "la-lista") in _kinds(_con_setups(trama))


def test_el_cobro_de_un_elemento_tiene_que_estar_en_la_escaleta() -> None:
    assert ("setup-sin-escena", "element.memory-1") in _kinds(
        _con_setups(_elemento("s2", "s99")), elements=[RECUERDO]
    )


def test_un_encuentro_sin_reglamento_hace_fallar_la_escaleta_con_su_escena() -> None:
    """RF-273, D-104."""
    escenas = tuple(s.model_copy(update={"is_match": s.id == "s5"}) for s in _valida().scenes)
    con_partido = _valida().model_copy(update={"scenes": escenas})
    assert _kinds(con_partido, has_rulebook=False) == [("encuentro-sin-reglamento", "s5")]
    assert _kinds(con_partido, has_rulebook=True) == []
    assert _kinds(_valida(), has_rulebook=False) == []


def test_el_brief_no_deportivo_no_admite_encuentros() -> None:
    """Es lo que `05-no-deportivo` espera (D-104)."""
    brief = Brief.model_validate_json((BRIEFS / "05-no-deportivo.json").read_text(encoding="utf-8"))
    assert not brief.rulebook
    escenas = tuple(s.model_copy(update={"is_match": s.id == "s1"}) for s in _valida().scenes)
    defectos = check(
        _valida().model_copy(update={"scenes": escenas}),
        word_range=RANGO,
        has_rulebook=bool(brief.rulebook),
    )
    assert [(d.kind, d.where) for d in defectos] == [("encuentro-sin-reglamento", "s1")]


# ------------------------------------------------------------------ deuda


def test_la_escena_de_cobro_congelada_sin_uso_no_cobra_el_elemento() -> None:
    """RF-261. Solo un uso anclado cobra un elemento."""
    o = _con_setups(_elemento())
    todas = frozenset(s.id for s in o.scenes)
    [st] = [s for s in status(o, todas) if s.id == "element.memory-1"]
    assert st.state is SetupState.PLANTED and st.element == "memory-1"
    assert not debt(o, todas).is_clear
    [pagado] = [s for s in status(o, todas, used_elements=frozenset({"memory-1"})) if s.element]
    assert pagado.state is SetupState.PAID
    assert debt(o, todas, used_elements=frozenset({"memory-1"})).is_clear


def test_un_elemento_usado_antes_de_su_escena_ya_esta_cobrado() -> None:
    o = _con_setups(_elemento())
    [st] = [s for s in status(o, frozenset(), used_elements=frozenset({"memory-1"})) if s.element]
    assert st.state is SetupState.PAID


def test_la_puerta_de_acto_exige_el_uso_del_elemento_del_acto() -> None:
    """El cobro esta en s5, acto 2: la puerta del acto 2 lo pide."""
    o = _con_setups(_elemento())
    todas = frozenset(s.id for s in o.scenes)
    assert check_act(o, 2, todas).unpaid == ("element.memory-1",)
    assert check_act(o, 2, todas, used_elements=frozenset({"memory-1"})).passed


def test_un_setup_de_la_trama_no_es_un_elemento() -> None:
    assert element_of(_valida().setups[0]) is None
    assert element_of(_elemento()) == "memory-1"


# --------------------------------------------------------------- Arquitecto


def _brief(rulebook: str = "") -> Brief:
    return Brief(
        title="El rio",
        start=WorldTime(stamp="2026-05-01"),
        entities=(BriefEntity(id="ines", kind="person", name="Ines"),),
        style_guide="Tercera persona, pasado.",
        rulebook=rulebook,
        target_words=3_000,
        recipient=Recipient(
            entity_id="ines",
            age=12,
            traits=("paciente",),
            memories=(RECUERDO[1], "la cometa roja"),
            optional=("la cometa roja",),
            role="protagonista",
        ),
    )


def test_el_arquitecto_recibe_los_obligatorios_con_el_id_de_su_promesa() -> None:
    texto = prompts.instruction(_brief(), chapters=3)
    assert '"element.trait-1" (trait): paciente' in texto
    assert '"element.memory-1" (memory)' in texto
    assert "cometa" not in texto, "un opcional no se promete"
    assert "NO TIENE REGLAMENTO" in texto
    assert "NO TIENE REGLAMENTO" not in prompts.instruction(
        _brief(rulebook="Once contra once."), chapters=3
    )
