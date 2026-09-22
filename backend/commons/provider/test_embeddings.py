"""Prefijos y dimension del modelo de embeddings.

RF-101, RF-102. Metodo VER-05. Las dos cosas que se rompen en silencio.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from commons.provider.embeddings import (
    DIMENSION,
    PASSAGE_PREFIX,
    QUERY_PREFIX,
    EmbeddingStartupError,
    LocalEmbedder,
    prefixed,
)


class _Backend:
    """Doble que recuerda que se le paso y devuelve vectores de tamano fijo."""

    def __init__(self, dimension: int = DIMENSION) -> None:
        self.dimension = dimension
        self.seen: list[str] = []

    def embed(self, documents: Sequence[str]) -> Sequence[Sequence[float]]:
        self.seen.extend(documents)
        return [[0.1] * self.dimension for _ in documents]


class _Roto:
    def embed(self, documents: Sequence[str]) -> Sequence[Sequence[float]]:
        raise OSError("pesos ausentes")


# --------------------------------------------------------------- los prefijos

def test_consulta_y_pasaje_llevan_prefijos_distintos() -> None:
    assert prefixed("hola", is_query=True) == QUERY_PREFIX + "hola"
    assert prefixed("hola", is_query=False) == PASSAGE_PREFIX + "hola"


def test_indexar_usa_passage_y_consultar_usa_query() -> None:
    """Sin esto el modelo recupera peor sin dar error ni senal."""
    backend = _Backend()
    embedder = LocalEmbedder(backend)

    embedder.embed(["el estadio"], is_query=False)
    embedder.embed(["como describi el estadio"], is_query=True)

    assert backend.seen[0].startswith(PASSAGE_PREFIX)
    assert backend.seen[1].startswith(QUERY_PREFIX)


def test_el_vector_lleva_modelo_y_dimension() -> None:
    """RD-13: con un modelo local, cambiarlo es sustituir un fichero, asi que
    mezclar vectores incomparables es facil y la deteccion es lo unico que lo
    impide."""
    [emb] = LocalEmbedder(_Backend()).embed(["texto"], is_query=False)
    assert emb.model_id == "intfloat/multilingual-e5-large"
    assert emb.dimension == DIMENSION
    assert len(emb.values) == DIMENSION


# ------------------------------------------------------- arranque, no ejecucion

def test_verifica_contra_un_indice_vacio() -> None:
    assert LocalEmbedder(_Backend()).verify(index_dimension=None) == DIMENSION


def test_dimension_que_no_cuadra_impide_arrancar() -> None:
    """Seguir con vectores mezclados da resultados sin significado."""
    with pytest.raises(EmbeddingStartupError, match="reindexar"):
        LocalEmbedder(_Backend(dimension=768)).verify(index_dimension=DIMENSION)


def test_modelo_que_no_carga_impide_arrancar() -> None:
    """El fallo de un modelo local es determinista: si falla una vez, falla
    siempre. Por eso se comprueba al arrancar y no se reintenta."""
    with pytest.raises(EmbeddingStartupError, match="no carga"):
        LocalEmbedder(_Roto()).verify(index_dimension=None)


def test_lista_vacia_no_llama_al_modelo() -> None:
    backend = _Backend()
    assert LocalEmbedder(backend).embed([], is_query=False) == []
    assert backend.seen == []
