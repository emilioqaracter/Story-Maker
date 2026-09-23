"""Propiedades del contador de tokens.

RNF-19, metodo VER-06. La propiedad que importa es una sola: **lo estimado
nunca queda por debajo de lo real**. Es lo unico que los techos de 4.1
necesitan del estimador, y su incumplimiento es un fallo de integracion
continua, no un aviso.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from commons.tokens.calibration import (
    MIN_SAMPLE_CHARS,
    CalibrationError,
    calibrate,
)
from commons.tokens.counter import TokenCounter, _raw
from commons.tokens.factors import (
    DEFAULT_FACTOR,
    ModelFactors,
    UnknownModelError,
)

MODEL = "claude-haiku-4-5"


def _counter(factor: float = DEFAULT_FACTOR) -> TokenCounter:
    factors = ModelFactors()
    factors.set(MODEL, factor)
    return TokenCounter(factors)


# ------------------------------------------------------------------ el factor


@given(text=st.text(min_size=1, max_size=2000))
def test_estimacion_nunca_por_debajo_del_crudo(text: str) -> None:
    """Con factor >= 1, la estimacion nunca queda por debajo del recuento crudo.

    Es la mitad comprobable sin red de RNF-19: la otra mitad --que tampoco
    quede por debajo del recuento real del proveedor-- se contrasta en la traza
    contra el `usage` de cada respuesta.
    """
    assert _counter().estimate(text, MODEL) >= _raw(text)


@given(
    text=st.text(min_size=1, max_size=500),
    factor=st.floats(min_value=1.0, max_value=3.0, allow_nan=False),
)
def test_la_estimacion_aplica_el_factor_y_redondea_hacia_arriba(text: str, factor: float) -> None:
    assert _counter(factor).estimate(text, MODEL) == math.ceil(_raw(text) * factor)


@given(a=st.text(max_size=300), b=st.text(max_size=300))
def test_estimar_junto_no_supera_estimar_por_separado(a: str, b: str) -> None:
    """Estimar varios textos de una vez redondea una sola vez.

    Por eso `estimate_many` nunca da mas que sumar estimaciones sueltas: el
    redondeo por pieza acumula hasta un token de exceso por bloque, que sobre
    once bloques ensucia el contraste con el recuento real.
    """
    c = _counter()
    juntos = c.estimate_many([a, b], MODEL)
    sueltos = c.estimate(a, MODEL) + c.estimate(b, MODEL)
    assert juntos <= sueltos


def test_modelo_sin_factor_no_se_admite() -> None:
    """Fallo cerrado: estimar con el factor de otro modelo es el error que los
    factores por modelo existen para evitar."""
    with pytest.raises(UnknownModelError):
        TokenCounter(ModelFactors()).estimate("hola", "modelo-desconocido")


def test_factor_menor_que_uno_se_rechaza() -> None:
    with pytest.raises(ValueError, match="por debajo"):
        ModelFactors().set(MODEL, 0.9)


# ------------------------------------------------------------- la calibracion

_SAMPLE = (
    "El estadio olia a cesped mojado y a gasoil. Marcos se ato las botas dos veces, "
    "porque la primera nunca le convencia, y miro hacia la grada norte donde su padre "
    "habria estado sentado de no ser por el turno de noche. El arbitro reviso el balon "
    "con las dos manos, como si pesara mas de lo que pesaba. "
) * 3


def test_calibracion_fija_un_factor_por_encima_del_ratio() -> None:
    """El factor resultante cubre el ratio observado mas un margen.

    El margen esta para que la muestra del brief, que es un solo registro, no
    deje corto al estimador en los demas registros de la obra.
    """
    ratio_real = 1.4
    factors = ModelFactors()

    result = calibrate(
        sample=_SAMPLE,
        model_id=MODEL,
        real_counter=lambda text, _m: math.ceil(_raw(text) * ratio_real),
        factors=factors,
    )

    assert result.factor > ratio_real
    assert factors.get(MODEL) == result.factor


@given(ratio=st.floats(min_value=0.5, max_value=2.5, allow_nan=False))
def test_el_factor_calibrado_nunca_baja_de_uno(ratio: float) -> None:
    """Aunque el proveedor cuente menos que `tiktoken`, el factor no baja de 1.

    Un factor por debajo de 1 significaria un estimador corto por construccion.
    """
    factors = ModelFactors()
    result = calibrate(
        sample=_SAMPLE,
        model_id=MODEL,
        real_counter=lambda text, _m: max(1, math.ceil(_raw(text) * ratio)),
        factors=factors,
    )
    assert result.factor >= 1.0


def test_muestra_corta_no_calibra() -> None:
    with pytest.raises(CalibrationError, match="ruido"):
        calibrate(
            sample="x" * (MIN_SAMPLE_CHARS - 1),
            model_id=MODEL,
            real_counter=lambda _t, _m: 10,
            factors=ModelFactors(),
        )


def test_proveedor_caido_es_fallo_cerrado() -> None:
    """Sin calibracion no arranca la tirada. No se cae a una estimacion local
    porque un tokenizador offline exacto para Claude no existe."""

    def rompe(_t: str, _m: str) -> int:
        raise ConnectionError("sin red")

    with pytest.raises(CalibrationError, match="recuento real"):
        calibrate(sample=_SAMPLE, model_id=MODEL, real_counter=rompe, factors=ModelFactors())
