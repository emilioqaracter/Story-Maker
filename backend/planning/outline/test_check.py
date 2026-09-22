"""El verificador estructural de la escaleta.

RF-26. Es la puerta de T2: tiene que **rechazar** una escaleta con un arco sin
resolucion y **aceptar** una valida. Las dos mitades importan igual; un
verificador que solo sabe rechazar se satisface no aprobando nada.
"""

from __future__ import annotations

import pytest

from commons.types.primitives import WorldTime
from planning.outline.check import check
from planning.outline.types import (
    ActPlan,
    Arc,
    ArcKind,
    Outline,
    SceneEntry,
    SceneFunction,
    Setup,
)

RANGO = (5_000, 9_000)


def _escena(
    sid: str, chapter: int, ordinal: int, act: int = 1, words: int = 1_000, **kw: object
) -> SceneEntry:
    return SceneEntry(
        id=sid,
        chapter=chapter,
        ordinal=ordinal,
        act=act,
        function=kw.pop("function", SceneFunction.COMPLICATE),  # type: ignore[arg-type]
        pov=str(kw.pop("pov", "marcos")),
        value_change="de la duda a la decision",
        world_time=WorldTime(stamp=f"2026-01-{chapter:02d}", seq=ordinal),
        target_words=words,
        **kw,  # type: ignore[arg-type]
    )


def _valida() -> Outline:
    """Tres capitulos, dos actos, doble arco resuelto en escenas distintas."""
    scenes = (
        _escena("s1", 1, 1, act=1, words=1_000, function=SceneFunction.ESTABLISH),
        _escena("s2", 1, 2, act=1, words=1_200),
        _escena("s3", 2, 1, act=1, words=1_100),
        _escena("s4", 2, 2, act=1, words=1_000),
        _escena("s5", 3, 1, act=2, words=1_400, function=SceneFunction.CULMINATE),
        _escena("s6", 3, 2, act=2, words=1_300, function=SceneFunction.ASSIMILATE),
    )
    return Outline(
        arcs=(
            Arc(id="competitivo", kind=ArcKind.COMPETITIVE, subject="equipo",
                start_scene="s1", crisis_scene="s3", resolution_scene="s5"),
            Arc(id="interno", kind=ArcKind.INTERNAL, subject="marcos",
                start_scene="s1", crisis_scene="s4", resolution_scene="s6"),
        ),
        acts=(ActPlan(number=1, tension=(3, 5)), ActPlan(number=2, tension=(8,))),
        scenes=scenes,
        setups=(Setup(id="la-lesion", planted_scene="s2", payoff_scene="s5",
                      description="El tobillo que cruje"),),
    )


# ------------------------------------------------------- la mitad que acepta

def test_una_escaleta_valida_pasa() -> None:
    assert check(_valida(), word_range=RANGO) == []


# ------------------------------------------------------ la mitad que rechaza

def test_un_arco_sin_resolucion_no_se_puede_ni_construir() -> None:
    """EST-I2 no admite el silencio: o se cierra o se declara abierto.

    Se rechaza al construir el arco y no en el verificador, porque un arco sin
    resolucion y sin declarar no es una escaleta mala: es un objeto que no
    deberia poder existir.
    """
    with pytest.raises(ValueError, match="no se cierra ni se declara abierto"):
        Arc(id="x", kind=ArcKind.INTERNAL, subject="marcos",
            start_scene="s1", crisis_scene="s2")


def test_un_arco_que_resuelve_en_una_escena_inexistente_falla() -> None:
    """Declarar la resolucion no basta: la escena tiene que estar en la escaleta,
    o el arco no se resuelve en ningun sitio y nadie lo nota hasta el final."""
    o = _valida()
    roto = o.model_copy(update={
        "arcs": (o.arcs[0].model_copy(update={"resolution_scene": "fantasma"}), o.arcs[1])
    })
    assert any(d.kind == "arco-sin-escena" for d in check(roto, word_range=RANGO))


def test_el_doble_arco_no_puede_colapsar() -> None:
    """DEP-20. Si ganan y madura en la misma escena, la victoria explica el
    cambio interior y lo abarata."""
    o = _valida()
    roto = o.model_copy(update={
        "arcs": (o.arcs[0], o.arcs[1].model_copy(update={"resolution_scene": "s5"}))
    })
    defectos = check(roto, word_range=RANGO)
    assert any(d.kind == "doble-arco-colapsado" for d in defectos)


def test_sin_arco_interno_no_hay_doble_arco() -> None:
    o = _valida()
    roto = o.model_copy(update={"arcs": (o.arcs[0],)})
    assert any(d.kind == "doble-arco-incompleto" for d in check(roto, word_range=RANGO))


def test_la_tension_no_puede_bajar_dentro_de_un_acto() -> None:
    """Monotona no decreciente: un capitulo de respiro al mismo nivel vale, pero
    bajar deshace lo que el acto venia construyendo."""
    o = _valida()
    roto = o.model_copy(update={"acts": (ActPlan(number=1, tension=(5, 3)), o.acts[1])})
    assert any(d.kind == "tension-decreciente" for d in check(roto, word_range=RANGO))


def test_la_tension_plana_dentro_de_un_acto_es_legitima() -> None:
    o = _valida()
    igual = o.model_copy(update={"acts": (ActPlan(number=1, tension=(5, 5)), o.acts[1])})
    assert not any(d.kind == "tension-decreciente" for d in check(igual, word_range=RANGO))


def test_un_setup_que_se_cobra_antes_de_plantarse_falla() -> None:
    o = _valida()
    roto = o.model_copy(update={
        "setups": (o.setups[0].model_copy(update={"planted_scene": "s5", "payoff_scene": "s2"}),)
    })
    assert any(d.kind == "setup-invertido" for d in check(roto, word_range=RANGO))


def test_un_setup_sin_payoff_planificado_falla() -> None:
    o = _valida()
    roto = o.model_copy(update={
        "setups": (o.setups[0].model_copy(update={"payoff_scene": "nunca"}),)
    })
    assert any(d.kind == "setup-sin-escena" for d in check(roto, word_range=RANGO))


def test_una_obra_fuera_del_rango_del_brief_falla() -> None:
    assert any(
        d.kind == "longitud-fuera-de-rango"
        for d in check(_valida(), word_range=(100_000, 200_000))
    )


def test_un_capitulo_fuera_del_rango_de_est07_falla() -> None:
    """EST-07: entre 1.500 y 4.000 palabras."""
    o = _valida()
    # Las dos escenas del capitulo 1 al minimo de escena: 800 palabras en total,
    # por debajo de las 1.500 que EST-07 pide para un capitulo. Cada escena por
    # separado es legal; el capitulo no. Esa es justo la comprobacion.
    corto = o.model_copy(update={
        "scenes": tuple(
            sc.model_copy(update={"target_words": 400}) if sc.chapter == 1 else sc
            for sc in o.scenes
        )
    })
    defectos = check(corto, word_range=(4_000, 9_000))
    assert any(d.kind == "capitulo-fuera-de-rango" for d in defectos)


def test_dos_escenas_en_la_misma_posicion_fallan() -> None:
    o = _valida()
    roto = o.model_copy(update={
        "scenes": (*o.scenes, _escena("s7", 1, 1, words=500))
    })
    assert any(d.kind == "posicion-ocupada" for d in check(roto, word_range=RANGO))


def test_huecos_en_la_numeracion_de_capitulos_fallan() -> None:
    o = _valida()
    roto = o.model_copy(update={
        "scenes": tuple(s.model_copy(update={"chapter": 5}) if s.chapter == 3 else s
                        for s in o.scenes)
    })
    assert any(d.kind == "capitulos-con-huecos" for d in check(roto, word_range=RANGO))


def test_una_escena_sin_cambio_de_valor_no_se_puede_construir() -> None:
    """EST-13. Una escena sin cambio de valor es relleno, y el relleno no entra
    en la escaleta: se rechaza al construirla."""
    with pytest.raises(ValueError):
        SceneEntry(
            id="x", chapter=1, ordinal=1, act=1,
            function=SceneFunction.COMPLICATE, pov="marcos", value_change="",
            world_time=WorldTime(stamp="2026-01-01"), target_words=800,
        )
