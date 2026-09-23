"""La puerta de cierre de acto y el registro de promesas.

RF-31, RF-105, RF-106. Lo que se comprueba aqui es que la deuda se detecta **un
acto antes** de que sea cara de arreglar, y que el remedio mira hacia delante.
"""

from __future__ import annotations

from planning.act_gate.gate import check_act, closes_an_act, replan_target
from planning.ledger.setups import SetupState, debt, status
from planning.outline.test_check import _valida


def test_el_capitulo_que_cierra_un_acto_se_reconoce() -> None:
    """La escaleta valida tiene el acto 1 en los capitulos 1 y 2, y el 2 en el 3."""
    o = _valida()
    assert closes_an_act(o, 1) is None
    assert closes_an_act(o, 2) == 1
    assert closes_an_act(o, 3) == 2


def test_una_promesa_sin_plantar_no_es_deuda_todavia() -> None:
    """Planificar no es plantar: una promesa que el lector no ha leido aun no
    debe nada."""
    d = debt(_valida(), frozen_scenes=frozenset())
    assert d.open_setups == ()
    assert len(d.planned) == 1
    assert not d.is_clear


def test_plantada_y_sin_cobrar_es_deuda_abierta() -> None:
    d = debt(_valida(), frozen_scenes=frozenset({"s1", "s2"}))
    assert [s.id for s in d.open_setups] == ["la-lesion"]


def test_cobrada_sale_de_la_deuda() -> None:
    d = debt(_valida(), frozen_scenes=frozenset({"s1", "s2", "s3", "s4", "s5"}))
    assert d.open_setups == ()
    assert [s.id for s in d.paid] == ["la-lesion"]
    assert d.is_clear


def test_la_puerta_del_acto_falla_si_queda_algo_sin_cobrar() -> None:
    """El setup se cobra en s5, que es del acto 2. Al cerrar el acto 2 sin s5
    congelada, la puerta tiene que verlo."""
    o = _valida()
    resultado = check_act(o, act=2, frozen_scenes=frozenset({"s1", "s2", "s3", "s4"}))
    assert not resultado.passed
    assert resultado.unpaid == ("la-lesion",)
    assert "sin cobrar" in resultado.reason()


def test_la_puerta_del_acto_pasa_cuando_se_cobro() -> None:
    o = _valida()
    resultado = check_act(o, act=2, frozen_scenes=frozenset({"s1", "s2", "s3", "s4", "s5"}))
    assert resultado.passed
    assert resultado.unpaid == ()


def test_el_acto_uno_no_responde_por_deuda_de_otro_acto() -> None:
    """Solo se le pide lo que la escaleta situaba dentro de el.

    Sin esto, cada acto arrastraria la deuda de los siguientes y la puerta
    fallaria siempre hasta el ultimo, con lo que no serviria de nada.
    """
    o = _valida()
    assert check_act(o, act=1, frozen_scenes=frozenset({"s1", "s2", "s3", "s4"})).passed


def test_el_remedio_mira_hacia_delante() -> None:
    """RF-106. Nunca se toca el acto congelado: el canon congelado gana."""
    o = _valida()
    assert replan_target(o, act=1) == 2
    assert replan_target(o, act=2) is None


def test_el_ultimo_acto_no_tiene_donde_replanificar() -> None:
    """Y ese caso lo recoge la condicion de cierre de obra, no esta puerta."""
    o = _valida()
    fallo = check_act(o, act=2, frozen_scenes=frozenset({"s1"}))
    assert not fallo.passed
    assert replan_target(o, act=2) is None


def test_el_estado_de_un_setup_lleva_sus_capitulos() -> None:
    """Para que el informe diga donde estaba prevista la promesa, no solo que
    falta: el Arquitecto necesita saber que replanificar."""
    [s] = status(_valida(), frozenset({"s1", "s2"}))
    assert s.state is SetupState.PLANTED
    assert s.planted_chapter == 1
    assert s.payoff_chapter == 3


def test_la_curva_realizada_que_baja_dos_veces_donde_la_planificada_sube_no_conforma() -> None:
    """RF-148."""
    from planning.act_gate.gate import tension_conforms

    assert tension_conforms([3, 5, 7], [4, 4, 4])
    assert tension_conforms([3, 5, 7], [4, 3, 4]), "una sola bajada no es sostenida"
    assert not tension_conforms([3, 5, 7], [5, 4, 3])
    assert tension_conforms([3, 5, 7], [5, None, 3]), "sin veredicto no cuenta"
    assert tension_conforms([7, 5, 3], [5, 4, 3]), "si la planificada tambien baja, conforma"
