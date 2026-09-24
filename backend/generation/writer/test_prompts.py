"""La instruccion del Escritor: la longitud con su minimo (D-135)."""

from __future__ import annotations

from generation.sports.test_narrate import _spec
from generation.writer.prompts import instruction


def test_la_longitud_lleva_el_minimo_del_perfil() -> None:
    """D-135. Con «en torno a» solo, el Escritor entregaba un 25 % menos."""
    texto = instruction(_spec(), min_words=1_000)
    assert "en torno a 500 palabras" in texto
    assert "NUNCA menos de 1000" in texto


def test_sin_minimo_la_longitud_es_la_de_siempre() -> None:
    texto = instruction(_spec())
    assert "LONGITUD: en torno a 500 palabras." in texto
    assert "NUNCA" not in texto
