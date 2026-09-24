"""El verificador estructural de la escaleta.

RF-26. Es la puerta de T2: tiene que **rechazar** una escaleta con un arco sin
resolucion y **aceptar** una valida. Las dos mitades importan igual; un
verificador que solo sabe rechazar se satisface no aprobando nada.
"""

from __future__ import annotations

import pytest

from commons.types.primitives import WorldTime
from commons.types.scene import SceneFunction
from planning.outline.check import check
from planning.outline.types import (
    ActPlan,
    Arc,
    ArcKind,
    Outline,
    SceneEntry,
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
            Arc(
                id="competitivo",
                kind=ArcKind.COMPETITIVE,
                subject="equipo",
                start_scene="s1",
                crisis_scene="s3",
                resolution_scene="s5",
            ),
            Arc(
                id="interno",
                kind=ArcKind.INTERNAL,
                subject="marcos",
                start_scene="s1",
                crisis_scene="s4",
                resolution_scene="s6",
            ),
        ),
        acts=(ActPlan(number=1, tension=(3, 5)), ActPlan(number=2, tension=(8,))),
        scenes=scenes,
        setups=(
            Setup(
                id="la-lesion",
                planted_scene="s2",
                payoff_scene="s5",
                description="El tobillo que cruje",
            ),
        ),
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
        Arc(id="x", kind=ArcKind.INTERNAL, subject="marcos", start_scene="s1", crisis_scene="s2")


def test_un_arco_que_resuelve_en_una_escena_inexistente_falla() -> None:
    """Declarar la resolucion no basta: la escena tiene que estar en la escaleta,
    o el arco no se resuelve en ningun sitio y nadie lo nota hasta el final."""
    o = _valida()
    roto = o.model_copy(
        update={"arcs": (o.arcs[0].model_copy(update={"resolution_scene": "fantasma"}), o.arcs[1])}
    )
    assert any(d.kind == "arco-sin-escena" for d in check(roto, word_range=RANGO))


def test_el_doble_arco_no_puede_colapsar() -> None:
    """DEP-20. Si ganan y madura en la misma escena, la victoria explica el
    cambio interior y lo abarata."""
    o = _valida()
    roto = o.model_copy(
        update={"arcs": (o.arcs[0], o.arcs[1].model_copy(update={"resolution_scene": "s5"}))}
    )
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
    roto = o.model_copy(
        update={
            "setups": (
                o.setups[0].model_copy(update={"planted_scene": "s5", "payoff_scene": "s2"}),
            )
        }
    )
    assert any(d.kind == "setup-invertido" for d in check(roto, word_range=RANGO))


def test_un_setup_sin_payoff_planificado_falla() -> None:
    o = _valida()
    roto = o.model_copy(
        update={"setups": (o.setups[0].model_copy(update={"payoff_scene": "nunca"}),)}
    )
    assert any(d.kind == "setup-sin-escena" for d in check(roto, word_range=RANGO))


def test_una_obra_fuera_del_rango_del_brief_falla() -> None:
    assert any(
        d.kind == "longitud-fuera-de-rango" for d in check(_valida(), word_range=(100_000, 200_000))
    )


def test_un_capitulo_fuera_del_rango_de_est07_falla() -> None:
    """EST-07: entre 1.500 y 4.000 palabras."""
    o = _valida()
    # Las dos escenas del capitulo 1 al minimo de escena: 800 palabras en total,
    # por debajo de las 1.500 que EST-07 pide para un capitulo. Cada escena por
    # separado es legal; el capitulo no. Esa es justo la comprobacion.
    corto = o.model_copy(
        update={
            "scenes": tuple(
                sc.model_copy(update={"target_words": 400}) if sc.chapter == 1 else sc
                for sc in o.scenes
            )
        }
    )
    defectos = check(corto, word_range=(4_000, 9_000))
    assert any(d.kind == "capitulo-fuera-de-rango" for d in defectos)


def test_dos_escenas_en_la_misma_posicion_fallan() -> None:
    o = _valida()
    roto = o.model_copy(update={"scenes": (*o.scenes, _escena("s7", 1, 1, words=500))})
    assert any(d.kind == "posicion-ocupada" for d in check(roto, word_range=RANGO))


def test_huecos_en_la_numeracion_de_capitulos_fallan() -> None:
    o = _valida()
    roto = o.model_copy(
        update={
            "scenes": tuple(
                s.model_copy(update={"chapter": 5}) if s.chapter == 3 else s for s in o.scenes
            )
        }
    )
    assert any(d.kind == "capitulos-con-huecos" for d in check(roto, word_range=RANGO))


def test_una_escena_sin_cambio_de_valor_no_se_puede_construir() -> None:
    """EST-13. Una escena sin cambio de valor es relleno, y el relleno no entra
    en la escaleta: se rechaza al construirla."""
    with pytest.raises(ValueError):
        SceneEntry(
            id="x",
            chapter=1,
            ordinal=1,
            act=1,
            function=SceneFunction.COMPLICATE,
            pov="marcos",
            value_change="",
            world_time=WorldTime(stamp="2026-01-01"),
            target_words=800,
        )


def test_el_ejemplo_del_esquema_del_arquitecto_pasa_su_propia_verificacion() -> None:
    """Un ejemplo es lo que el modelo imita: si no cuadra, la escaleta tampoco.

    Medido en la primera tirada real: con un ejemplo que declaraba dos valores
    de tension para un acto de un capitulo, el Arquitecto ponia uno por escena.
    """
    import json

    from planning.outline import prompts
    from planning.outline.types import Outline

    texto = prompts.schema()
    ejemplo = Outline.model_validate(json.loads(texto[texto.index("{") :]))
    assert check(ejemplo, word_range=(1_000, 20_000)) == []


# ------------------------------------------------- perfiles de extension, T53


def _minima() -> Outline:
    """La forma del perfil `prueba`: tres capitulos de una escena de un parrafo."""
    return Outline(
        arcs=(
            Arc(
                id="competitivo",
                kind=ArcKind.COMPETITIVE,
                subject="equipo",
                start_scene="p1",
                crisis_scene="p1",
                resolution_scene="p2",
            ),
            Arc(
                id="interno",
                kind=ArcKind.INTERNAL,
                subject="marcos",
                start_scene="p1",
                crisis_scene="p2",
                resolution_scene="p3",
            ),
        ),
        acts=(
            ActPlan(number=1, tension=(3,)),
            ActPlan(number=2, tension=(6,)),
            ActPlan(number=3, tension=(9,)),
        ),
        scenes=(
            _escena("p1", 1, 1, act=1, words=130, function=SceneFunction.ESTABLISH),
            _escena("p2", 2, 1, act=2, words=140, function=SceneFunction.CULMINATE),
            _escena("p3", 3, 1, act=3, words=120, function=SceneFunction.ASSIMILATE),
        ),
    )


def test_una_escaleta_minima_pasa_con_el_perfil_prueba() -> None:
    from planning.outline.types import PRUEBA

    assert check(_minima(), word_range=(300, 500), profile=PRUEBA) == []


def test_la_escaleta_minima_no_vale_como_novela() -> None:
    """El perfil por defecto sigue siendo EST-07 y EST-08: nada cambia sin pedirlo."""
    tipos = {d.kind for d in check(_minima(), word_range=(300, 500))}
    assert {"escena-fuera-de-rango", "capitulo-fuera-de-rango"} <= tipos


def test_una_escaleta_de_novela_no_vale_como_prueba() -> None:
    from planning.outline.types import PRUEBA

    tipos = {d.kind for d in check(_valida(), word_range=(300, 500), profile=PRUEBA)}
    assert {
        "escena-fuera-de-rango",
        "capitulo-fuera-de-rango",
        "escenas-descuadradas",
        "longitud-fuera-de-rango",
    } <= tipos


@pytest.mark.parametrize("capitulos", [2, 4])
def test_el_perfil_prueba_exige_exactamente_tres_capitulos(capitulos: int) -> None:
    from planning.outline.types import PRUEBA

    base = _minima()
    escenas = tuple(_escena(f"q{c}", c, 1, act=c, words=120) for c in range(1, capitulos + 1))
    arcos = tuple(
        a.model_copy(
            update={
                "start_scene": "q1",
                "crisis_scene": "q1",
                "resolution_scene": f"q{capitulos}" if a.kind is ArcKind.INTERNAL else "q1",
            }
        )
        for a in base.arcs
    )
    tension = tuple(ActPlan(number=c, tension=(3 * c,)) for c in range(1, capitulos + 1))
    otra = Outline(arcs=arcos, acts=tension, scenes=escenas)
    defectos = check(otra, word_range=(200, 500), profile=PRUEBA)
    # Un acto por capitulo sigue valiendo; lo que falla es cuantos hay.
    assert {d.kind for d in defectos} == {"capitulos-descuadrados", "actos-descuadrados"}
    [capitulos_mal] = [d for d in defectos if d.kind == "capitulos-descuadrados"]
    assert f"planifica {capitulos} capitulos" in capitulos_mal.message


def test_el_perfil_prueba_exige_tres_actos_de_un_capitulo() -> None:
    """T53. Con un capitulo por acto, la puerta de acto corre tras cada capitulo."""
    from planning.outline.types import PRUEBA

    base = _minima()
    dos_actos = base.model_copy(
        update={
            "acts": (ActPlan(number=1, tension=(3, 6)), ActPlan(number=2, tension=(9,))),
            "scenes": tuple(
                s.model_copy(update={"act": 1 if s.chapter < 3 else 2}) for s in base.scenes
            ),
        }
    )
    defectos = check(dos_actos, word_range=(300, 500), profile=PRUEBA)
    assert {d.where for d in defectos if d.kind == "actos-descuadrados"} == {"obra", "acto 1"}
    # La misma escaleta, como novela, no tiene forma de actos que cumplir.
    assert not [
        d for d in check(dos_actos, word_range=(300, 500)) if d.kind == "actos-descuadrados"
    ]


def test_el_ejemplo_del_esquema_de_prueba_pasa_su_propia_verificacion() -> None:
    import json

    from planning.outline import prompts
    from planning.outline.types import PRUEBA

    texto = prompts.schema(PRUEBA)
    assert "EXACTAMENTE 3 capitulos, con 1 escena" in texto
    ejemplo = Outline.model_validate(json.loads(texto[texto.index("{") :]))
    assert check(ejemplo, word_range=(300, 500), profile=PRUEBA) == []
