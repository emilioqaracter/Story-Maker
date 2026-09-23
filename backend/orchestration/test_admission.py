"""Admision y reintentos.

RF-14, RF-15, RF-18, RF-19, RF-97, RF-107, CTX-I1. Metodos VER-06 y VER-18.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from orchestration.admission import (
    Admission,
    BudgetUnknownError,
    CeilingTooSmallError,
    Reservation,
    reserve,
)
from orchestration.retries import (
    Action,
    Budget,
    Level,
    may_start_chapter,
    on_failure,
)

# ------------------------------------------------------------------ admision


def test_lo_que_cabe_entra() -> None:
    a = Admission(ceiling=100_000)
    assert a.admit(Reservation(agent="escritor", packet_tokens=19_700), call_id="c1")
    assert a.in_flight == 19_700


def test_el_cupo_de_tiron_se_reserva_entero() -> None:
    """RF-97. Admitir por lo que ocupa al empezar y dejar que crezca rompe el
    techo sin que salte nada: cuando la llamada se pasa, ya esta en vuelo."""
    a = Admission(ceiling=100_000)
    a.admit(Reservation(agent="continuista", packet_tokens=47_500, tool_quota=25_000), call_id="c1")
    assert a.in_flight == 72_500


def test_lo_que_no_cabe_se_encola() -> None:
    a = Admission(ceiling=50_000)
    a.admit(Reservation(agent="a", packet_tokens=40_000), call_id="c1")
    assert not a.admit(Reservation(agent="b", packet_tokens=20_000), call_id="c2")
    assert a.queued == 1


def test_fifo_estricta_nadie_adelanta() -> None:
    """Sin esta regla, una llamada grande no entra nunca mientras lleguen
    pequenas, y las grandes son justo las que menos veces corren."""
    a = Admission(ceiling=50_000)
    a.admit(Reservation(agent="grande", packet_tokens=45_000), call_id="c1")
    a.admit(Reservation(agent="mediana", packet_tokens=20_000), call_id="c2")
    # La pequena cabria en los 5.000 que quedan, pero hay alguien esperando.
    assert not a.admit(Reservation(agent="pequena", packet_tokens=1_000), call_id="c3")
    assert a.queued == 2


def test_al_liberar_sale_el_primero_de_la_cola() -> None:
    a = Admission(ceiling=50_000)
    r = Reservation(agent="a", packet_tokens=40_000)
    a.admit(r, call_id="c1")
    a.admit(Reservation(agent="b", packet_tokens=20_000), call_id="c2")
    assert a.release(r) == "c2"


def test_sin_estimacion_no_se_admite() -> None:
    """Fallo cerrado: admitir a ciegas rompe el techo sin que salte nada, que es
    peor que no correr."""
    with pytest.raises(BudgetUnknownError):
        reserve(agent="escritor", packet_tokens=None)


def test_lo_que_no_cabe_ni_vacio_no_se_encola() -> None:
    """Encolarla seria dejarla esperando para siempre: es un problema de diseno
    del paquete, no de concurrencia."""
    a = Admission(ceiling=10_000)
    with pytest.raises(CeilingTooSmallError):
        a.admit(Reservation(agent="gigante", packet_tokens=99_000), call_id="c1")


@settings(max_examples=60, deadline=None)
@given(reservas=st.lists(st.integers(min_value=1_000, max_value=40_000), min_size=1, max_size=8))
def test_lo_en_vuelo_nunca_supera_el_techo(reservas: list[int]) -> None:
    """CTX-I1. La propiedad que sostiene todo el presupuesto de contexto."""
    a = Admission(ceiling=100_000)
    for i, tokens in enumerate(reservas):
        a.admit(Reservation(agent=f"a{i}", packet_tokens=tokens), call_id=f"c{i}")
        assert a.in_flight <= 100_000


def test_el_bloque_libera_aunque_lance() -> None:
    """Una llamada que lanza y no libera va dejando el techo mas bajo cada vez,
    y el sistema acaba bloqueado sin que nada lo explique."""
    a = Admission(ceiling=50_000)
    r = Reservation(agent="a", packet_tokens=10_000)
    with pytest.raises(RuntimeError), a.hold(r):
        raise RuntimeError("algo fallo")
    assert a.in_flight == 0


# ---------------------------------------------------------------- reintentos


def test_la_escena_se_reintenta_tres_veces() -> None:
    b = Budget()
    for _ in range(2):
        d = on_failure(b, level=Level.SCENE)
        assert d.action is Action.RETRY
        b = d.budget
    assert on_failure(b, level=Level.SCENE).action is Action.QUARANTINE_AND_RESPEC


def test_agotada_la_escena_sube_de_nivel_no_insiste() -> None:
    """Cada peldano cambia el diagnostico: 'la prosa esta mal' pasa a 'el
    encargo estaba mal'."""
    b = Budget(scene_attempts=2)
    d = on_failure(b, level=Level.SCENE)
    assert d.budget.chapter_attempts == 1
    assert "encargo" in d.reason


def test_el_contador_de_escena_se_reinicia_al_subir() -> None:
    """La escena que viene es otra, con otra especificacion: arrastrar los
    intentos de la anterior le daria menos oportunidades de las que le tocan."""
    d = on_failure(Budget(scene_attempts=2), level=Level.SCENE)
    assert d.budget.scene_attempts == 0


def test_agotado_el_capitulo_se_replanifica_el_tramo() -> None:
    d = on_failure(Budget(chapter_attempts=1), level=Level.CHAPTER)
    assert d.action is Action.QUARANTINE_AND_REPLAN


def test_no_hay_cuarto_nivel() -> None:
    """Si un arco falla, el problema esta en la escaleta y seguir reparando
    prosa es perder tiempo."""
    d = on_failure(Budget(arc_replans=1), level=Level.ARC)
    assert d.action is Action.RECOMPUTE_ARC
    assert "cuarto nivel" in d.reason


def test_no_se_empieza_un_capitulo_con_el_anterior_sin_congelar() -> None:
    """RF-107. Sin esto, 'la produccion no se detiene' se leeria como 'salta al
    siguiente', que fabrica una contradiccion invisible."""
    assert may_start_chapter(previous_frozen=True)
    assert not may_start_chapter(previous_frozen=False)


def test_tres_llamadas_en_paralelo_respetan_el_techo_y_el_orden() -> None:
    """RF-160, CTX-I1. Tres hilos piden plaza a la vez; nunca hay mas en vuelo
    que el techo, y el que no cabe espera en vez de colarse."""
    import threading
    import time

    from orchestration.admission import Admission, Reservation

    adm = Admission(ceiling=25_000)
    maximo = [0]
    candado = threading.Lock()

    def llamada(agent: str) -> None:
        with adm.hold(Reservation(agent=agent, packet_tokens=11_500)):
            with candado:
                maximo[0] = max(maximo[0], adm.in_flight)
            time.sleep(0.05)

    hilos = [threading.Thread(target=llamada, args=(f"juez-{i}",)) for i in range(3)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=5)
    assert all(not h.is_alive() for h in hilos)
    assert maximo[0] <= 25_000
    assert maximo[0] == 23_000, "dos caben a la vez; el tercero espera"
    assert adm.in_flight == 0
