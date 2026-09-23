"""Embeddings locales con `fastembed`.

D-22, D-29. `architecture.md` 4.8. No salen a la red: eso quita el unico modo
de fallo intermitente que tenia el ciclo y hace los vectores deterministas.

Dos cosas de aqui son las que se rompen en silencio si se hacen mal:

1. **Los prefijos.** `multilingual-e5-large` exige `query: ` delante del texto
   de consulta y `passage: ` delante de cada fragmento indexado. Sin ellos el
   modelo carga, devuelve vectores de la dimension correcta y recupera peor,
   sin error y sin senal (RF-102).
2. **La dimension.** Cambiar de modelo es sustituir un fichero, asi que mezclar
   vectores incomparables es facil. Se contrasta al arrancar contra la del
   indice y, si no cuadra, la tirada no empieza (RF-101).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, cast, runtime_checkable

from commons.provider.port import Embedding

#: D-29. Se elige por para que fue entrenado --recuperacion-- y no por tamano:
#: aqui la consulta es una especificacion de escena y el resultado son
#: fragmentos de prosa, que es recuperacion asimetrica.
MODEL_ID = "intfloat/multilingual-e5-large"
DIMENSION = 1024

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


class EmbeddingStartupError(RuntimeError):
    """El modelo no carga o su dimension no cuadra con la del indice.

    Es fallo cerrado **en el arranque**, no durante el ciclo. El fallo de un
    modelo local es determinista --si falla una vez, falla siempre-- asi que
    reintentarlo es perder tiempo: o esta bien instalado o la tirada no empieza.
    """


@runtime_checkable
class _EmbeddingBackend(Protocol):
    """Lo minimo que se le pide a `fastembed`, para poder doblarlo en pruebas."""

    def embed(self, documents: Sequence[str]) -> Sequence[Sequence[float]]: ...


def prefixed(text: str, *, is_query: bool) -> str:
    """Aplica el prefijo que el modelo exige.

    Funcion suelta y publica para que la prueba pueda comprobarla sin cargar
    2,24 GB de pesos.
    """
    return (QUERY_PREFIX if is_query else PASSAGE_PREFIX) + text


class LocalEmbedder:
    """Envuelve el modelo local y garantiza prefijo y dimension."""

    def __init__(self, backend: _EmbeddingBackend, *, model_id: str = MODEL_ID) -> None:
        self._backend = backend
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def verify(self, *, index_dimension: int | None) -> int:
        """Comprueba el modelo al arrancar y devuelve su dimension.

        `index_dimension` es la que ya tiene el indice de esta novela, o `None`
        si esta vacio. Que no coincidan no se arregla solo: exige reindexar, y
        seguir con vectores mezclados da resultados sin significado.
        """
        try:
            probe = list(self._backend.embed([prefixed("prueba", is_query=False)]))
        except Exception as exc:
            raise EmbeddingStartupError(f"el modelo de embeddings no carga: {exc}") from exc

        if not probe:
            raise EmbeddingStartupError("el modelo no devolvio ningun vector")

        dimension = len(probe[0])
        if dimension == 0:
            raise EmbeddingStartupError("el modelo devolvio un vector vacio")

        if index_dimension is not None and index_dimension != dimension:
            raise EmbeddingStartupError(
                f"el indice tiene vectores de {index_dimension} dimensiones y el modelo "
                f"produce de {dimension}: hay que reindexar, no mezclar"
            )
        return dimension

    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        """Vectoriza aplicando el prefijo que corresponda."""
        if not texts:
            return []
        prepared = [prefixed(t, is_query=is_query) for t in texts]
        vectors = list(self._backend.embed(prepared))
        if len(vectors) != len(texts):
            raise EmbeddingStartupError(
                f"el modelo devolvio {len(vectors)} vectores para {len(texts)} textos"
            )
        return [
            Embedding(values=tuple(v), model_id=self._model_id, dimension=len(v)) for v in vectors
        ]


def load_backend(model_id: str = MODEL_ID) -> _EmbeddingBackend:
    """Carga el modelo desde la imagen.

    `fastembed` no se importa arriba a proposito: asi el resto del modulo se
    puede probar sin tener los pesos instalados, que es lo que hace posible que
    la puerta de T0 corra en cualquier maquina.
    """
    from fastembed import TextEmbedding

    # `fastembed` no trae stubs, asi que su constructor es `Any` para mypy. El
    # cast es explicito para que la frontera con la libreria sin tipos quede a
    # la vista en vez de disolverse en un `Any` que se propaga.
    backend: _EmbeddingBackend = cast(_EmbeddingBackend, TextEmbedding(model_name=model_id))
    return backend
