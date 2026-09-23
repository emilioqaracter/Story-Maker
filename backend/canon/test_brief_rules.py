"""Contradicciones del brief. RF-200, RF-201, D-75. VER-05, VER-06."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from canon.brief import Brief, BriefEntity, Recipient
from canon.brief_rules import contradictions
from commons.types.primitives import WorldTime


def _brief(**kw: object) -> Brief:
    base: dict[str, object] = {
        "title": "El verano",
        "start": WorldTime(stamp="2026-08-01"),
        "entities": (BriefEntity(id="lucia", kind="person", name="Lucía"),),
        "style_guide": "x",
        "target_words": 1000,
        "recipient": Recipient(entity_id="lucia", age=10, role="protagonista"),
    }
    base.update(kw)
    return Brief(**base)  # type: ignore[arg-type]


def _c(**kw: object) -> list[str]:
    base: dict[str, object] = {
        "age": 10,
        "genre": "aventura",
        "tone": "luminoso",
        "title": "El verano",
        "dedication": "Para Lucía",
        "names": ["Lucía"],
        "forbidden_words": [],
        "forbidden_themes": [],
    }
    base.update(kw)
    return [c.rule for c in contradictions(**base)]  # type: ignore[arg-type]


def test_edad_frente_a_genero_y_tono() -> None:
    assert _c(genre="Terror psicológico") == ["edad-genero"]
    assert _c(tone="Violento") == ["edad-tono"]
    assert _c(age=12, genre="terror") == []
    assert _c(age=None, genre="erótica") == []


def test_prohibida_presente_en_titulo_dedicatoria_o_nombre() -> None:
    assert _c(forbidden_words=["verano"]) == ["prohibida-presente"]
    assert _c(forbidden_words=["lucia"]) == ["prohibida-presente", "prohibida-presente"]
    assert _c(forbidden_words=["perro"]) == []


def test_tema_prohibido_que_es_el_genero_o_el_tono() -> None:
    assert _c(forbidden_themes=["Aventura"]) == ["tema-es-genero"]
    assert _c(forbidden_themes=["luminoso"]) == ["tema-es-tono"]


@given(st.text(max_size=40), st.text(max_size=40), st.text(max_size=40), st.integers(12, 120))
def test_sin_prohibiciones_y_con_12_o_mas_no_hay_contradicciones(
    genre: str, tone: str, title: str, age: int
) -> None:
    """§7.3 de la spec: sin prohibiciones y a partir de 12 años, ningun texto contradice."""
    assert _c(genre=genre, tone=tone, title=title, age=age) == []


def test_ri01_rechaza_un_brief_contradictorio_con_la_regla() -> None:
    """RI-41 del frontend: RI-01 rechaza con la lista de lo que falla."""
    with pytest.raises(ValidationError, match="para mayores de 12"):
        _brief(genre="terror")


def test_el_destinatario_tiene_que_ser_una_entidad_del_brief() -> None:
    with pytest.raises(ValidationError, match="no es una entidad"):
        _brief(recipient=Recipient(entity_id="otro", age=30, role="lector"))


def test_un_brief_sin_campos_nuevos_sigue_valiendo() -> None:
    """RF-200: los briefs anteriores no llevan destinatario."""
    b = _brief(recipient=None)
    assert b.recipient_name() == "" and b.dedication == "" and b.contradictions() == []
