"""Contador de tokens. Uno solo para todo el sistema.

`architecture.md` 4.8. Lo consumen las cuatro cosas que cuentan tokens: el
empaquetado, la admision, las herramientas y el guardarrail. Dos contadores
distintos harian que CTX-I1 dejara de ser comprobable.

La API publica es `estimate`, y **siempre** aplica el factor. El recuento
crudo de `tiktoken` no se expone: quien lo necesita es la calibracion, que
vive al lado y usa el privado. Un solo sitio que llame a `tiktoken` directo
rompe el techo sin que salte nada.
"""

from __future__ import annotations

import math
from functools import lru_cache

import tiktoken

from commons.tokens.factors import ModelFactors

#: Codificacion fija. No reproduce el tokenizador de Claude --no existe uno
#: local-- pero es determinista, que es lo que el factor necesita para poder
#: corregir un sesgo estable en vez de un ruido.
ENCODING = "o200k_base"


@lru_cache(maxsize=1)
def _encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding(ENCODING)


def _raw(text: str) -> int:
    """Recuento crudo de `tiktoken`. **Privado a proposito.**

    Solo la calibracion lo usa, para compararlo con el recuento real del
    proveedor. Cualquier otro uso se salta el factor.
    """
    return len(_encoder().encode(text))


class TokenCounter:
    """Estimador con factor por modelo.

    Nunca queda por debajo del recuento real: esa es la unica propiedad que los
    techos de 4.1 necesitan de el, y la vigila RNF-19 en integracion continua.
    """

    def __init__(self, factors: ModelFactors) -> None:
        self._factors = factors

    def estimate(self, text: str, model_id: str) -> int:
        """Tokens estimados, con factor aplicado y redondeo hacia arriba.

        Lanza `UnknownModelError` si el modelo no tiene factor: es fallo
        cerrado, no una estimacion con el factor de otro.
        """
        return math.ceil(_raw(text) * self._factors.get(model_id))

    def estimate_many(self, texts: list[str], model_id: str) -> int:
        """Estimacion de varios textos que viajan en la misma llamada.

        Se redondea una sola vez al final y no por texto: redondear por pieza
        acumularia hasta un token de exceso por bloque, que sobre once bloques
        es ruido que ensucia el contraste con el recuento real.
        """
        raw = sum(_raw(t) for t in texts)
        return math.ceil(raw * self._factors.get(model_id))
