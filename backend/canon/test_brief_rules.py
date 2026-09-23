"""Contradicciones y esquema del brief. RF-200, RF-201, RF-247, RF-248, RD-42, D-75, D-93.

VER-05, VER-06 y VER-08.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from canon.brief import Brief, BriefEntity, Recipient
from canon.brief_rules import ADULT_TERMS, contradictions
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


def test_seis_anos_y_tono_thriller_erotico_es_contradiccion() -> None:
    """RF-247, ENT-04: el caso literal de la rubrica, y el plural en el genero."""
    assert _c(age=6, tone="thriller erótico") == ["edad-tono"]
    assert _c(age=6, genre="eróticas") == ["edad-genero"]
    assert _c(age=6, tone="EROTICO") == ["edad-tono"]
    # La lista es una para los dos campos (D-75).
    assert _c(age=6, genre="violento") == ["edad-genero"]
    assert _c(age=6, tone="terror") == ["edad-tono"]
    assert _c(age=6, genre="novela gore", tone="Macabros") == ["edad-genero", "edad-tono"]


def test_la_regla_de_edad_compara_por_palabra_y_no_por_subcadena() -> None:
    """RF-237: «aterrorizado» no es «terror» ni «gorense» es «gore»."""
    assert _c(age=6, tone="aterrorizado") == []
    assert _c(age=6, genre="aventura gorense") == []


_MARCAS = {"e": "é", "o": "ó", "a": "á", "i": "í"}


@st.composite
def _escrita_de_otra_forma(draw: st.DrawFn) -> str:
    """Un termino adulto con otra caja, tildes de mas o de menos y quiza en plural."""
    termino = draw(st.sampled_from(ADULT_TERMS))
    letras = []
    for c in termino:
        c = draw(st.sampled_from([c, _MARCAS.get(c, c)]))
        letras.append(c.upper() if draw(st.booleans()) else c)
    return "".join(letras) + draw(st.sampled_from(["", "s"]))


@given(
    _escrita_de_otra_forma(),
    st.integers(0, 11),
    st.sampled_from(["", "thriller ", "novela de "]),
    st.sampled_from(["", " psicológico", ", con humor"]),
)
def test_menor_de_12_con_un_termino_adulto_siempre_choca(
    termino: str, age: int, antes: str, despues: str
) -> None:
    """RF-247, VER-06. Cualquier caja, tilde o plural, entre otras palabras, en tono o genero."""
    texto = f"{antes}{termino}{despues}"
    assert _c(age=age, tone=texto) == ["edad-tono"]
    assert _c(age=age, genre=texto) == ["edad-genero"]


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


def test_ri01_rechaza_seis_anos_con_tono_thriller_erotico() -> None:
    """RF-247 en la carga del brief."""
    seis = Recipient(entity_id="lucia", age=6, role="protagonista")
    with pytest.raises(ValidationError, match="tono «thriller erótico»"):
        _brief(recipient=seis, tone="thriller erótico")


@pytest.mark.parametrize(
    "cambio",
    [
        {"pov": "primera"},
        {"recipient": {"entity_id": "lucia", "age": 10, "role": "protagonista", "apodo": "Lu"}},
        {"entities": [{"id": "lucia", "kind": "person", "name": "Lucía", "color": "rojo"}]},
        {"start": {"stamp": "2026-08-01", "hora": "10:00"}},
        {"relations": [{"source": "lucia", "target": "lucia", "kind": "x", "peso": 1}]},
    ],
)
def test_un_campo_de_mas_en_el_brief_o_en_sus_partes_se_rechaza(cambio: dict[str, object]) -> None:
    """RF-248, D-93: un campo que el sistema no lee es un campo que la persona cree haber pedido."""
    base = _brief().model_dump(mode="json")
    base.update(cambio)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Brief.model_validate(base)


def test_nacimiento_opcionales_y_origen_son_opcionales() -> None:
    """RD-42: los briefs anteriores siguen valiendo y los nuevos campos se validan."""
    b = _brief(
        recipient=Recipient(
            entity_id="lucia",
            age=10,
            birth_date="2016-05-10",  # type: ignore[arg-type]
            traits=("valiente",),
            memories=("el río",),
            optional=("el río",),
            role="protagonista",
        ),
        origin_interview="abcdef012345",
    )
    assert b.recipient is not None and b.recipient.optional == ("el río",)
    assert Brief.model_validate_json(b.model_dump_json()) == b
    with pytest.raises(ValidationError, match="optional solo admite"):
        Recipient(entity_id="lucia", age=10, optional=("inventado",), role="x")
    with pytest.raises(ValidationError):
        Recipient(entity_id="lucia", age=10, birth_date="2016-02-30", role="x")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        _brief(origin_interview="no-es-un-id")


def test_el_destinatario_no_repite_sus_atributos_reservados() -> None:
    """RF-249: la edad va en `recipient`; en la entidad serian dos valores del mismo hecho."""
    lucia = BriefEntity(id="lucia", kind="person", name="Lucía", attributes=(("age", "9"),))
    with pytest.raises(ValidationError, match="reservados"):
        _brief(entities=(lucia,))


def test_un_brief_sin_campos_nuevos_sigue_valiendo() -> None:
    """RF-200: los briefs anteriores no llevan destinatario."""
    b = _brief(recipient=None)
    assert b.recipient_name() == "" and b.dedication == "" and b.contradictions() == []
