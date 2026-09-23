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
    assert texto[d.evidence.offset :].startswith(d.evidence.quote)


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
    [d] = check_availability("Marcos remato de cabeza.", unavailable=[("Marcos", "lesionado")])
    assert d.severity is Severity.S1


def test_quien_no_aparece_no_se_marca() -> None:
    assert check_availability("Elena miro el reloj.", unavailable=[("Marcos", "lesionado")]) == []


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


def test_la_narracion_en_presente_es_grave() -> None:
    """Rompe la guia de estilo en algo que un lector nota en la primera linea, y
    afecta a la escena entera y no a un pasaje.

    Esta comprobacion no estaba, y la PRIMERA escena que el sistema genero de
    verdad salio en presente sin que nada la marcara. De ahi que exista.
    """
    presente = (
        "Marcos abre la puerta. El tecnico esta cerca de los bancos. "
        "Lo ve de reojo y sabe que algo pasa. Nadie dice nada. "
        "Marcos sale y va hacia el pasillo."
    )
    [d] = [x for x in check_format(presente) if "presente" in x.rule]
    assert d.severity is Severity.S1


def test_la_narracion_en_pasado_no_se_marca() -> None:
    pasado = (
        "Marcos entro por la puerta. El tecnico estaba cerca de los bancos. "
        "Lo vio de reojo y supo que algo pasaba. Nadie dijo nada. "
        "Marcos salio y fue hacia el pasillo."
    )
    assert not [x for x in check_format(pasado) if "presente" in x.rule]


def test_el_presente_en_dialogo_no_cuenta() -> None:
    """Los personajes hablan en presente con toda naturalidad; contar sus verbos
    haria que una escena con mucho dialogo se marcara siempre."""
    mixto = "\n".join(
        [
            "Marcos entro en el vestuario. El tecnico estaba de espaldas.",
            "\u2014Esto no es lo que parece. Yo se lo que hay y se que va a pasar",
            "\u2014dijo\u2014. Nadie sale de aqui, nadie dice nada, nadie tiene la culpa.",
            "Marcos lo miro y no contesto. Salio despacio.",
        ]
    )
    assert not [x for x in check_format(mixto) if "presente" in x.rule]


def test_un_presente_suelto_en_pasado_no_marca() -> None:
    """Un pasaje en pasado puede llevar presentes legitimos --una verdad general,
    un pensamiento-- y marcarlos daria falsos positivos en prosa correcta."""
    con_general = (
        "Marcos entro en el vestuario. Estaba vacio. Miro la lista y penso que "
        "el futbol es asi. Salio sin decir nada. Volvio al pasillo."
    )
    assert not [x for x in check_format(con_general) if "presente" in x.rule]


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
    [d] = check_repetition(
        "Un silencio sepulcral.", frozen_ngrams=[], proscribed=["silencio sepulcral"]
    )
    assert "proscripcion" in d.rule


def test_texto_limpio_no_se_marca() -> None:
    assert (
        check_repetition(
            "Algo nuevo y distinto aqui.", frozen_ngrams=["otra cosa muy distinta"], proscribed=[]
        )
        == []
    )


# ------------------------------------------------------------ check.lexicon


def test_un_nombre_que_no_es_del_canon_es_grave() -> None:
    [d] = check_lexicon(
        "Hablo con Ramirez.", known_names=["Marcos", "Elena"], candidates=["Ramirez"]
    )
    assert d.severity is Severity.S1


def test_un_alias_vigente_no_se_marca() -> None:
    assert (
        check_lexicon(
            "Hablo con el Chino.", known_names=["Marcos Vela", "el Chino"], candidates=["el Chino"]
        )
        == []
    )


# ---------------------------------------------------------- check.knowledge


def test_mencionar_lo_que_no_se_sabe_es_grave() -> None:
    """No es un desliz de estilo: es una contradiccion del canon, y de las que
    un lector detecta."""
    [d] = check_knowledge(
        "Sabia que Elena se iba.",
        pov_knows=["otra.cosa"],
        mentioned_facts=[("elena.se.va", "Elena se iba")],
    )
    assert d.severity is Severity.S1


def test_mencionar_lo_que_si_se_sabe_no_se_marca() -> None:
    assert (
        check_knowledge(
            "Sabia que Elena se iba.",
            pov_knows=["elena.se.va"],
            mentioned_facts=[("elena.se.va", "Elena se iba")],
        )
        == []
    )


# ---------------------------------------------------------- check.milestones


def test_un_goleador_que_la_prosa_no_cuenta_es_grave() -> None:
    from verification.checks.deterministic import check_milestones

    defectos = check_milestones(
        "Marcos marco de cabeza y el estadio se vino abajo.", scorers=["Marcos", "Iker Landa"]
    )
    assert len(defectos) == 1
    assert defectos[0].severity is Severity.S1
    assert "Iker Landa" in defectos[0].rule


def test_si_todos_los_goleadores_aparecen_no_hay_defecto() -> None:
    from verification.checks.deterministic import check_milestones

    assert (
        check_milestones("Marcos y luego Íker Landa marcaron.", scorers=["Marcos", "Iker Landa"])
        == []
    )


def test_un_numero_de_algo_que_no_es_mes_no_es_una_fecha() -> None:
    """Falso positivo medido: 'marco 2 de los 3 penaltis' no es una fecha."""
    assert (
        check_timeline("Marco 2 de los 3 penaltis. Era el 1 de esta serie.", allowed_dates=[]) == []
    )
    [d] = check_timeline("Llego el 3 de Abril.", allowed_dates=["10 de marzo"])
    assert d.severity is Severity.S1
