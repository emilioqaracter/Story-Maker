"""Los siete verificadores deterministas.

RF-46 a RF-50. Son la red de seguridad del sistema entero, y los unicos a los
que se les exige cobertura de mutacion: un verificador cuyas pruebas no detectan
su ruptura es PEOR que no tener verificador, porque produce confianza falsa.

Por eso aqui se comprueban las dos direcciones de cada uno: que marca lo que
tiene que marcar, y que NO marca lo que no.
"""

from __future__ import annotations

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from commons.types.primitives import Severity
from verification.checks.deterministic import (
    check_availability,
    check_chapter_length,
    check_format,
    check_knowledge,
    check_ledger,
    check_lexicon,
    check_repetition,
    check_timeline,
    edit_distance,
    misspelling_of,
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


def test_una_tilde_cambiada_ya_no_da_el_nombre_por_bueno() -> None:
    """La rubrica pide el nombre *exactamente* como en el canon. Antes se
    comparaba sin tildes y "Nála" pasaba por "Nala"."""
    [d] = check_lexicon("Llamo a Nála.", known_names=["Nala"], candidates=["Nála"])
    assert d.severity is Severity.S1
    assert d.evidence.quote == "Nála"
    assert "'Nala'" in d.rule


def test_una_letra_de_mas_es_una_variante_del_canon() -> None:
    [d] = check_lexicon("Llamo a Nalah.", known_names=["Nala"], candidates=["Nalah"])
    assert d.severity is Severity.S1
    assert d.evidence.quote == "Nalah"
    assert "variante" in d.rule
    assert "'Nala'" in d.rule


def test_un_nombre_lejano_sigue_siendo_ajeno_al_canon() -> None:
    [d] = check_lexicon("Hablo con Ramirez.", known_names=["Nala"], candidates=["Ramirez"])
    assert "no es una entidad del canon" in d.rule
    assert "variante" not in d.rule


def test_el_nombre_exacto_con_su_tilde_no_se_marca() -> None:
    assert (
        check_lexicon(
            "Peña y Nala.",
            known_names=["Aurelio Peña", "Peña", "Nala"],
            candidates=["Peña", "Nala"],
        )
        == []
    )


@pytest.mark.parametrize(
    ("a", "b", "distancia"),
    [
        ("nala", "nala", 0),
        ("nala", "nalah", 1),  # insercion
        ("nala", "nla", 1),  # borrado
        ("nala", "nata", 1),  # sustitucion
        ("nala", "nála", 1),  # tilde
        ("nala", "nlaa", 1),  # trasposicion: Levenshtein daria 2
        ("nala", "anla", 1),
        ("nala", "lana", 2),
        ("", "abc", 3),
        ("abc", "", 3),
        ("kitten", "sitting", 3),
        ("ca", "abc", 3),  # restringida: no edita dos veces la misma subcadena
    ],
)
def test_la_distancia_de_edicion(a: str, b: str, distancia: int) -> None:
    assert edit_distance(a, b) == distancia
    assert edit_distance(b, a) == distancia


def test_solo_los_nombres_con_mayuscula_admiten_variantes() -> None:
    """Los articulos de un alias --el "el" de "el Chino"-- no son nombres: sin
    este filtro "Del" al principio de frase seria una variante de "el"."""
    assert misspelling_of("Del", ["el Chino", "el", "Chino"]) is None
    assert misspelling_of("Chinos", ["el Chino", "el", "Chino"]) == "Chino"


def test_un_nombre_del_canon_no_es_variante_de_si_mismo() -> None:
    assert misspelling_of("Nala", ["Nala"]) is None
    assert misspelling_of("NALA", ["Nala"]) is None
    assert misspelling_of("Ramirez", ["Nala"]) is None


def test_dos_tildes_cambiadas_tambien_son_variante() -> None:
    """A distancia 2 pero igual sin tildes: sigue siendo el mismo nombre mal
    escrito, no un personaje nuevo."""
    assert misspelling_of("Rámirez", ["Ramírez"]) == "Ramírez"


_LETRAS = "abcdefghijlmnoprstuvz"
_TILDES = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú", "n": "ñ"}


@st.composite
def _nombre_y_variante(draw: st.DrawFn) -> tuple[str, str]:
    """Un nombre propio y una variante a una sola edicion: letra de mas, de
    menos, cambiada, trasladada o con la tilde cambiada."""
    cuerpo = draw(st.text(alphabet=_LETRAS, min_size=4, max_size=9))
    nombre = cuerpo.capitalize()
    i = draw(st.integers(min_value=0, max_value=len(cuerpo) - 1))
    letra = draw(st.sampled_from(_LETRAS))
    edicion = draw(
        st.sampled_from(["insercion", "borrado", "sustitucion", "trasposicion", "tilde"])
    )
    if edicion == "insercion":
        v = cuerpo[:i] + letra + cuerpo[i:]
    elif edicion == "borrado":
        v = cuerpo[:i] + cuerpo[i + 1 :]
    elif edicion == "sustitucion":
        v = cuerpo[:i] + letra + cuerpo[i + 1 :]
    elif edicion == "trasposicion":
        j = min(i + 1, len(cuerpo) - 1)
        v = cuerpo[:i] + cuerpo[j] + cuerpo[i] + cuerpo[j + 1 :] if j > i else cuerpo
    else:
        v = cuerpo[:i] + _TILDES.get(cuerpo[i], "á") + cuerpo[i + 1 :]
    variante = v.capitalize()
    assume(variante.casefold() != nombre.casefold())
    return nombre, variante


@given(_nombre_y_variante())
def test_toda_variante_a_una_edicion_de_un_nombre_del_canon_salta(par: tuple[str, str]) -> None:
    """VER-06. Letra de mas, de menos, cambiada, trasladada o tilde cambiada:
    toda variante a una edicion de un nombre del canon es un S1 con su cita."""
    nombre, variante = par
    assert misspelling_of(variante, [nombre]) == nombre
    texto = f"Marcos llamo a {variante} y se fue."
    [d] = check_lexicon(texto, known_names=[nombre], candidates=[variante])
    assert d.severity is Severity.S1
    assert d.evidence.quote == variante
    assert texto[d.evidence.offset :].startswith(variante)


@given(st.text(alphabet=_LETRAS, min_size=3, max_size=9))
def test_un_nombre_bien_escrito_nunca_salta(cuerpo: str) -> None:
    nombre = cuerpo.capitalize()
    assert misspelling_of(nombre, [nombre, "Marcos"]) is None
    assert check_lexicon(nombre, known_names=[nombre], candidates=[nombre]) == []


# ------------------------------------------------------ longitud de capitulo


def _palabras(n: int) -> str:
    return " ".join(["palabra"] * n)


@pytest.mark.parametrize(
    ("palabras", "salta"),
    [(1_499, True), (1_500, False), (2_750, False), (4_000, False), (4_001, True), (0, True)],
)
def test_la_longitud_del_capitulo_contra_su_rango(palabras: int, salta: bool) -> None:
    """EST-07. Lo que se mide es lo **escrito**, no lo planificado en la
    escaleta."""
    defectos = check_chapter_length(_palabras(palabras), word_range=(1_500, 4_000))
    assert bool(defectos) is salta
    for d in defectos:
        assert d.kind == "check.format"
        assert f"{palabras} palabras" in d.rule
        assert "1500-4000" in d.rule
        assert d.evidence.quote


def test_la_longitud_del_capitulo_tiene_la_severidad_de_la_de_escena() -> None:
    """La misma que `check.format` da a una escena fuera de rango: degrada el
    ritmo, no contradice el canon."""
    [capitulo] = check_chapter_length(_palabras(10), word_range=(1_500, 4_000))
    [escena] = check_format(_palabras(10), word_range=(400, 1_500))
    assert capitulo.severity is escena.severity is Severity.S2


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
