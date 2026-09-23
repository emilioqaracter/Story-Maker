"""Huella y deriva. RF-137, RF-138, D-40, D-42. VER-05, VER-06."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from verification.style.drift import deviation, reference, sustained_drift
from verification.style.fingerprint import Fingerprint, compute

TEXTO = (
    "Marcos entró el último. El vestuario olía a linimento viejo y a lluvia fría. "
    "Nadie levantó la vista. El técnico dobló la lista amarilla sin mirarlo. "
    "Marcos se sentó en el banco. La camiseta del nueve seguía colgada."
)


def test_la_huella_mide_las_cinco_metricas() -> None:
    fp = compute(TEXTO)
    assert fp.mean_sentence_len > 0
    assert fp.adj_noun_ratio > 0, "hay adjetivos: viejo, fria, amarilla"
    assert 0 < fp.lexical_richness <= 1
    assert fp.top_ngrams


@settings(max_examples=15, deadline=None)
@given(st.sampled_from([TEXTO, TEXTO * 3, "Una frase. Otra frase más larga que la anterior."]))
def test_la_huella_es_determinista(texto: str) -> None:
    """RF-137."""
    assert compute(texto) == compute(texto)


def _fp(mean: float) -> Fingerprint:
    return Fingerprint(
        mean_sentence_len=mean,
        var_sentence_len=4.0,
        adj_noun_ratio=0.3,
        top_ngrams=(),
        lexical_richness=0.6,
    )


def test_sin_tres_capitulos_no_hay_referencia() -> None:
    assert reference([_fp(10), _fp(11)]) is None


def test_la_deriva_exige_tres_capitulos_seguidos_fuera() -> None:
    """RF-138, D-42. Un capitulo atipico no dispara; tres seguidos si."""
    ref = reference([_fp(10), _fp(11), _fp(12)])
    assert ref is not None
    normal = deviation(_fp(11), ref)
    raro = deviation(_fp(30), ref)
    assert not normal.out_of_tolerance and raro.out_of_tolerance
    assert not sustained_drift([raro, normal, raro])
    assert sustained_drift([normal, raro, raro, raro])


def test_una_referencia_sin_variacion_no_da_infinitas_desviaciones() -> None:
    ref = reference([_fp(10), _fp(10), _fp(10)])
    assert ref is not None
    d = deviation(_fp(10.2), ref)
    assert d.max_abs < 2.0
