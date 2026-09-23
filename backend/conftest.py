"""Configuracion comun de las pruebas.

Las propiedades de `hypothesis` miden tiempo por caso, y la primera llamada al
codificador de `tiktoken` carga tablas y tarda segundos. Sin calentarlo antes,
ese coste de arranque se le imputa al primer caso generado y lo tumba por
plazo: un falso negativo que no dice nada sobre el codigo.
"""

from __future__ import annotations

import pytest
from hypothesis import settings

# Perfil de integracion continua: sin plazo por caso. Lo que se mide aqui son
# invariantes, no rendimiento; el rendimiento tiene sus propias comprobaciones.
settings.register_profile("ci", deadline=None)
settings.load_profile("ci")


def pytest_configure(config: pytest.Config) -> None:
    """Ninguna prueba habla con Langfuse de verdad (RNF-53, RI-60).

    Se quitan las variables antes de recoger las pruebas, porque importar
    `orchestration.app` ya instala el espejo si las encuentra. Sin ellas no se
    engancha nada: las pruebas que lo ejercitan instalan un cliente doble a
    proposito. Sin esto, una maquina con las claves en el entorno mandaria las
    tiradas de prueba a un servicio real.
    """
    import os

    for k in list(os.environ):
        if k.upper().startswith(("LANGFUSE_", "OTEL_")):
            del os.environ[k]


@pytest.fixture(scope="session", autouse=True)
def _warm_token_encoder() -> None:
    """Paga una sola vez la carga del codificador, fuera de lo medido."""
    from commons.tokens.counter import _encoder

    _encoder()
