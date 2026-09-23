"""`check.evidence`. RF-110, RF-111. VER-05 y VER-06."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from verification.checks.evidence import MIN_QUOTE_WORDS, anchor, normalize, occurrences

TEXTO = (
    "Marcos entró el último y nadie levantó la vista. —¿Juego? —preguntó, y el "
    "técnico dobló la lista sin mirarlo. El vestuario olía a linimento y a lluvia "
    "vieja; alguien silbaba una canción que Marcos no reconoció."
)


def test_una_cita_literal_ancla_en_su_posicion() -> None:
    cita = "el técnico dobló la lista sin mirarlo. El vestuario"
    ev = anchor(TEXTO, cita)
    assert ev is not None
    assert TEXTO[ev.offset : ev.offset + len(ev.quote)] == ev.quote
    assert ev.quote.startswith("el técnico dobló")


def test_la_normalizacion_perdona_comillas_guiones_y_mayusculas() -> None:
    """Lo que se perdona es tipografia; el contenido tiene que ser el mismo."""
    cita = '"MARCOS ENTRO EL ULTIMO Y NADIE LEVANTO LA VISTA"'
    ev = anchor(TEXTO, cita)
    assert ev is not None
    assert ev.offset == 0


def test_la_barra_de_salto_de_parrafo_y_los_puntos_tipograficos_no_descartan() -> None:
    texto = (
        "Hoy se sentia bien. Confiaba.\n\nEntonces entro el entrenador sin mirar a nadie… y cerro."
    )
    ev = anchor(texto, "Hoy se sentia bien. Confiaba. / Entonces entro el entrenador sin mirar")
    assert ev is not None and ev.offset == 0
    assert anchor(texto, "entro el entrenador sin mirar a nadie... y cerro") is not None


def test_menos_de_ocho_palabras_no_ancla() -> None:
    assert anchor(TEXTO, "nadie levantó la vista") is None


def test_una_cita_que_aparece_dos_veces_no_es_una_posicion() -> None:
    texto = "el balón rodó hasta la línea de cal y se detuvo. " * 2
    assert occurrences(texto, "el balón rodó hasta la línea de cal y se detuvo") == 2
    assert anchor(texto, "el balón rodó hasta la línea de cal y se detuvo") is None


def test_una_cita_inventada_no_ancla() -> None:
    assert anchor(TEXTO, "el portero se lanzó a la izquierda y detuvo el penalti") is None


def test_normalize_es_idempotente() -> None:
    assert normalize(normalize(TEXTO)) == normalize(TEXTO)


@settings(max_examples=60, deadline=None)
@given(
    palabras=st.lists(
        st.text(alphabet="abcdefghijklmnñopqrstuvwxyzáéíóú", min_size=1, max_size=8),
        min_size=MIN_QUOTE_WORDS,
        max_size=30,
        unique=True,
    ),
)
def test_un_fragmento_del_texto_siempre_ancla_donde_esta(palabras: list[str]) -> None:
    """Propiedad: cualquier tramo de ocho palabras unicas del texto ancla en su offset."""
    texto = " ".join(palabras)
    inicio = 0
    cita = " ".join(palabras[:MIN_QUOTE_WORDS])
    ev = anchor(texto, cita)
    assert ev is not None
    assert ev.offset == inicio
    assert ev.quote == cita
