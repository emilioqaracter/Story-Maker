"""Calibracion del factor del contador, al arrancar.

`architecture.md` 4.8, D-28. Con una ventana de 1.000.000 el error del
estimador era irrelevante: sobraban 900.000 tokens. Con Haiku 4.5 la ventana
es de 200.000 y el peor caso --100.000 de entrada mas 50.000 de salida-- deja
50.000 de margen. El factor deja de ser una formalidad, asi que se mide antes
de empezar en vez de corregirse despues.

Se mide con prosa del propio brief y no con un texto de laboratorio: el sesgo
de `tiktoken` depende del idioma y del registro, y lo que va a contar durante
la tirada es exactamente eso.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from commons.tokens.counter import _raw
from commons.tokens.factors import CALIBRATION_MARGIN, ModelFactors

#: Por debajo de esto la muestra no dice nada: el ratio lo domina el ruido de
#: unas pocas palabras. Son unos dos parrafos de prosa.
MIN_SAMPLE_CHARS = 500


class CalibrationError(RuntimeError):
    """No se pudo calibrar. Fallo cerrado: la tirada no arranca."""


@dataclass(frozen=True)
class CalibrationResult:
    model_id: str
    raw_tokens: int
    real_tokens: int
    ratio: float
    factor: float


def calibrate(
    *,
    sample: str,
    model_id: str,
    real_counter: Callable[[str, str], int],
    factors: ModelFactors,
) -> CalibrationResult:
    """Fija el factor de `model_id` midiendo `sample`.

    `real_counter` recibe texto y modelo y devuelve el recuento real del
    proveedor. Se inyecta en vez de importarse para que la calibracion sea
    comprobable sin red.

    El factor resultante es el ratio observado mas un margen, nunca menos de 1:
    un factor por debajo de 1 significaria que el estimador queda corto por
    construccion, que es justo lo que no puede pasar.
    """
    if len(sample) < MIN_SAMPLE_CHARS:
        raise CalibrationError(
            f"muestra de {len(sample)} caracteres, minimo {MIN_SAMPLE_CHARS}: "
            "el ratio lo dominaria el ruido"
        )

    raw = _raw(sample)
    if raw == 0:
        raise CalibrationError("la muestra no produce tokens")

    try:
        real = real_counter(sample, model_id)
    except Exception as exc:
        raise CalibrationError(f"el proveedor no devolvio recuento real: {exc}") from exc

    if real <= 0:
        raise CalibrationError(f"recuento real invalido: {real}")

    ratio = real / raw
    factor = max(1.0, ratio + CALIBRATION_MARGIN)
    factors.set(model_id, factor)

    return CalibrationResult(
        model_id=model_id,
        raw_tokens=raw,
        real_tokens=real,
        ratio=ratio,
        factor=factor,
    )
