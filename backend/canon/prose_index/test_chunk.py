"""Troceado de escenas congeladas.

RF-69, RF-70, RD-16. Metodo VER-06. Las propiedades que importan: determinismo,
que el fragmento no cruce su escena, y que este contenido en ella.
"""

from __future__ import annotations

from itertools import pairwise

from hypothesis import given, settings
from hypothesis import strategies as st

from canon.prose_index.chunk import MAX_CHUNK_TOKENS, chunk_scene, contained_in

_parrafo = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=20, max_size=400
)


def _texto(parrafos: list[str]) -> str:
    return "\n\n".join(parrafos)


@settings(max_examples=40, deadline=None)
@given(parrafos=st.lists(_parrafo, min_size=1, max_size=15))
def test_el_troceado_es_determinista(parrafos: list[str]) -> None:
    """Sin esto, reindexar cambiaria los identificadores y las trazas que los
    citan dejarian de apuntar a nada."""
    texto = _texto(parrafos)
    assert chunk_scene("e1", texto) == chunk_scene("e1", texto)


@settings(max_examples=40, deadline=None)
@given(parrafos=st.lists(_parrafo, min_size=1, max_size=15))
def test_todo_fragmento_esta_contenido_en_su_escena(parrafos: list[str]) -> None:
    """RD-16. Si no lo estuviera, el fragmento recuperado no seria prosa de la
    obra sino algo que el troceado invento."""
    texto = _texto(parrafos)
    assert contained_in(chunk_scene("e1", texto), texto)


@settings(max_examples=40, deadline=None)
@given(parrafos=st.lists(_parrafo, min_size=1, max_size=15))
def test_todo_fragmento_pertenece_a_su_escena(parrafos: list[str]) -> None:
    """Nunca cruza la frontera: es lo que permite heredar los metadatos por
    clave ajena y que el filtro siga siendo exacto sobre fragmentos."""
    assert all(c.scene_id == "e1" for c in chunk_scene("e1", _texto(parrafos)))


def test_hay_solape_entre_fragmentos_consecutivos() -> None:
    """Sin el, una idea que cruza la frontera no se encuentra desde ninguno de
    los dos lados."""
    largo = [f"p{i} {'x' * 600}" for i in range(4)]
    trozos = chunk_scene("e1", _texto(largo))
    assert len(trozos) > 1
    for anterior, siguiente in pairwise(trozos):
        ultimo = anterior.text.split("\n\n")[-1]
        assert siguiente.text.startswith(ultimo)


def test_un_parrafo_solo_no_se_parte() -> None:
    """Por parrafos y no por bloques de N tokens: un corte ciego parte una frase
    y el fragmento llega al paquete sin principio ni final."""
    unico = "x" * (MAX_CHUNK_TOKENS * 8)
    [trozo] = chunk_scene("e1", unico)
    assert trozo.text == unico


def test_una_escena_vacia_no_da_fragmentos() -> None:
    assert chunk_scene("e1", "   \n\n  ") == []
