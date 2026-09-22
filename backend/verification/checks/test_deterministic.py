"""Los siete verificadores deterministas.

RF-46 a RF-50. Son la red de seguridad del sistema entero, y los unicos a los
que se les exige cobertura de mutacion: un verificador cuyas pruebas no detectan
su ruptura es PEOR que no tener verificador, porque produce confianza falsa.

Por eso aqui se comprueban las dos direcciones de cada uno: que marca lo que
tiene que marcar, y que NO marca lo que no.
"""

from __future__ import annotations

from commons.types.primitives import Severity
from verification.checks.deterministic import (
    check_availability,
    check_format,
    check_knowledge,
    check_ledger,
    check_lexicon,
    check_repetition,
    check_timeline,
)

# --------------------------------------------------------------- toda cita

def test_todo_defecto_trae_cita_localizable() -> None:
    """Un veredicto sin cita se descarta, y el Reparador necesita saber QUE
    arreglar, no que algo esta mal."""
    texto = "El 14 de marzo llovia sobre el estadio."
    [d] = check_timeline(texto, allowed_dates=["10 de marzo"])
    assert d.evidence.quote in texto
    assert texto[d.evidence.offset:].startswith(d.evidence.quote)


# ----------------------------------------------------------- check.timeline

def test_una_fecha_fuera_del_calendario_es_grave() -> None:
    [d] = check_timeline("Fue el 14 de marzo.", allowed_dates=["10 de marzo"])
    assert d.severity is Severity.S1


def test_una_fecha_del_calendario_no_se_marca() -> None:
    assert check_timeline("Fue el 10 de marzo.", allowed_dates=["10 de marzo"]) == []


def test_las_tildes_no_hacen_falsos_positivos() -> None:
    """En espanol hace falta: para un lector es la misma fecha y para un `in`
    son dos cadenas distintas."""
    assert check_timeline("Fue el 10 de márzo.", allowed_dates=["10 de marzo"]) == []


# ------------------------------------------------------------- check.ledger

def test_un_marcador_que_no_cuadra_es_grave() -> None:
    """Contradice el canon y rompe la clasificacion de toda la temporada."""
    [d] = check_ledger("Ganaron 3-1.", expected_score="2-1", team_names=[])
    assert d.severity is Severity.S1
    assert "2-1" in d.rule


def test_el_marcador_correcto_no_se_marca() -> None:
    assert check_ledger("Ganaron 2-1.", expected_score="2-1", team_names=[]) == []


# ------------------------------------------------------- check.availability

def test_alguien_lesionado_actuando_es_grave() -> None:
    [d] = check_availability("Marcos remato de cabeza.",
                             unavailable=[("Marcos", "lesionado")])
    assert d.severity is Severity.S1


def test_quien_no_aparece_no_se_marca() -> None:
    assert check_availability("Elena miro el reloj.",
                              unavailable=[("Marcos", "lesionado")]) == []


# ------------------------------------------------------------- check.format

def test_la_primera_persona_fuera_de_dialogo_es_grave() -> None:
    """Rompe el punto de vista unico, que es una invariante estructural."""
    [d] = check_format("Yo mire el cesped mojado.")
    assert d.severity is Severity.S1


def test_la_primera_persona_dentro_de_dialogo_no_se_marca() -> None:
    """El dialogo va en primera con toda naturalidad: sin esto el verificador
    dispararia en cada conversacion."""
    assert check_format('Marcos dijo: "Yo no fui."') == []


def test_la_raya_de_dialogo_tambien_cuenta() -> None:
    """Es como se escribe dialogo en espanol."""
    assert check_format("El tecnico callo.\n\u2014Yo no lo vi \u2014dijo.") == []


def test_una_escena_fuera_de_rango_es_menos_grave() -> None:
    """Degrada el ritmo pero no contradice nada: marcarla grave pararia el
    capitulo por algo que se arregla en un pase."""
    [d] = check_format("corta", word_range=(400, 1_500))
    assert d.severity is Severity.S2


def test_una_escena_dentro_de_rango_no_se_marca() -> None:
    assert check_format(" ".join(["palabra"] * 500), word_range=(400, 1_500)) == []


# --------------------------------------------------------- check.repetition

def test_un_ngrama_ya_usado_se_marca_como_menos_grave() -> None:
    texto = "El cesped mojado olia a gasoil esa manana."
    [d] = check_repetition(texto, frozen_ngrams=["cesped mojado olia a"], proscribed=[])
    assert d.severity is Severity.S2


def test_un_termino_proscrito_se_marca() -> None:
    [d] = check_repetition("Un silencio sepulcral.", frozen_ngrams=[],
                           proscribed=["silencio sepulcral"])
    assert "proscripcion" in d.rule


def test_texto_limpio_no_se_marca() -> None:
    assert check_repetition("Algo nuevo y distinto aqui.",
                            frozen_ngrams=["otra cosa muy distinta"], proscribed=[]) == []


# ------------------------------------------------------------ check.lexicon

def test_un_nombre_que_no_es_del_canon_es_grave() -> None:
    [d] = check_lexicon("Hablo con Ramirez.", known_names=["Marcos", "Elena"],
                        candidates=["Ramirez"])
    assert d.severity is Severity.S1


def test_un_alias_vigente_no_se_marca() -> None:
    assert check_lexicon("Hablo con el Chino.",
                         known_names=["Marcos Vela", "el Chino"],
                         candidates=["el Chino"]) == []


# ---------------------------------------------------------- check.knowledge

def test_mencionar_lo_que_no_se_sabe_es_grave() -> None:
    """No es un desliz de estilo: es una contradiccion del canon, y de las que
    un lector detecta."""
    [d] = check_knowledge("Sabia que Elena se iba.", pov_knows=["otra.cosa"],
                          mentioned_facts=[("elena.se.va", "Elena se iba")])
    assert d.severity is Severity.S1


def test_mencionar_lo_que_si_se_sabe_no_se_marca() -> None:
    assert check_knowledge("Sabia que Elena se iba.", pov_knows=["elena.se.va"],
                           mentioned_facts=[("elena.se.va", "Elena se iba")]) == []
