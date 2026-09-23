"""Fusion por rangos y seleccion por cupos.

RF-76, RF-77, RF-79 a RF-85. Metodo VER-06. La propiedad que importa es el
determinismo: el mismo canon y la misma peticion dan el mismo paquete, y eso es
lo que hace reproducible el camino de empuje.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from commons.types.primitives import Quota
from context.retrieval.fusion import RRF_K, reciprocal_rank_fusion
from context.retrieval.quotas import Candidate, select

# ------------------------------------------------------------------- la fusion


def test_aparecer_en_las_dos_piernas_puntua_mas() -> None:
    """Es el efecto util de la fusion: lo que encuentran las dos formas de
    buscar es lo mas probable que sea relevante."""
    fusion = dict(reciprocal_rank_fusion([["a", "b"], ["b", "c"]]))
    assert fusion["b"] > fusion["a"]
    assert fusion["b"] > fusion["c"]


def test_solo_usa_posiciones_no_puntuaciones() -> None:
    """Por eso no hay que calibrar nada: la formula no ve las puntuaciones de
    origen, que estan en escalas incomparables."""
    esperado = 1 / (RRF_K + 1)
    assert reciprocal_rank_fusion([["x"]])[0][1] == esperado


@given(
    a=st.lists(st.sampled_from("abcdef"), max_size=6, unique=True),
    b=st.lists(st.sampled_from("abcdef"), max_size=6, unique=True),
)
def test_la_fusion_es_determinista(a: list[str], b: list[str]) -> None:
    """Dos ejecuciones con la misma entrada dan el mismo orden.

    Sin esto, una tirada deja de ser reproducible y el conjunto dorado no puede
    comparar nada con nada.
    """
    assert reciprocal_rank_fusion([a, b]) == reciprocal_rank_fusion([a, b])


def test_una_pierna_vacia_no_rompe_la_fusion() -> None:
    """Se degrada sola: sin caso especial que programar."""
    assert reciprocal_rank_fusion([["a", "b"], []]) == reciprocal_rank_fusion([["a", "b"]])


def test_el_desempate_no_depende_del_orden_de_las_piernas() -> None:
    """Con igual puntuacion, ordenar por como llegaron haria que el resultado
    dependiera de en que orden corrieron unas piernas que son independientes."""
    assert reciprocal_rank_fusion([["a"], ["b"]]) == reciprocal_rank_fusion([["b"], ["a"]])


# ------------------------------------------------------------------ los cupos


def _c(cid: str, **kw: object) -> Candidate:
    base: dict[str, object] = {
        "chunk_id": cid,
        "scene_id": f"esc-{cid}",
        "chapter": 1,
        "text": f"texto {cid}",
        "tokens": 100,
        "summary": f"resumen de {cid}" * 3,
    }
    base.update(kw)
    return Candidate(**base)  # type: ignore[arg-type]


def _sel(ranked: list[Candidate], **kw: object):  # type: ignore[no-untyped-def]
    args: dict[str, object] = {
        # El escaner ve "token" en el nombre y lo toma por una contrasena.
        "token_budget": 1_000,
        "place": "estadio",
        "pov": "marcos",  # nosec B105
        "function": "revelar",
        "entities": frozenset({"marcos"}),
    }
    args.update(kw)
    return select(ranked, **args)  # type: ignore[arg-type]


def test_cada_cupo_trae_su_tipo_de_evidencia() -> None:
    seleccion = _sel(
        [
            _c("lugar", place="estadio"),
            _c("voz", has_dialogue=True, pov="marcos"),
            _c("promesa", plants_setup=("la-lesion",)),
            _c("espejo", function="revelar", entities=frozenset({"marcos"})),
            _c("libre"),
        ],
        setups_to_pay=frozenset({"la-lesion"}),
    )

    por_cupo = {s.quota: s.candidate.chunk_id for s in seleccion.chosen}
    assert por_cupo[Quota.PLACE] == "lugar"
    assert por_cupo[Quota.VOICE] == "voz"
    assert por_cupo[Quota.PROMISE] == "promesa"
    assert por_cupo[Quota.MIRROR] == "espejo"


def test_un_cupo_vacio_no_es_un_error() -> None:
    """En los primeros capitulos casi todos lo estan."""
    seleccion = _sel([_c("solo-libre")])
    assert Quota.PLACE in seleccion.empty_quotas
    assert len(seleccion.chosen) == 1


def test_el_cupo_de_voz_excluye_lo_ya_usado() -> None:
    """Contramedida directa contra que el sistema se copie a si mismo."""
    cand = _c("voz", has_dialogue=True, pov="marcos")
    seleccion = _sel([cand], recent_voice_scenes=frozenset({cand.scene_id}))
    assert Quota.VOICE in seleccion.empty_quotas


def test_no_entra_nada_de_una_escena_que_ya_viaja_literal() -> None:
    """Duplicar texto gasta presupuesto sin anadir informacion."""
    cand = _c("lugar", place="estadio")
    seleccion = _sel([cand], literal_scenes=frozenset({cand.scene_id}))
    assert all(s.candidate.chunk_id != "lugar" for s in seleccion.chosen)


def test_un_fragmento_que_no_cabe_entra_como_resumen() -> None:
    """RF-84. Nunca se trunca: medio parrafo deja al Escritor sin saber que le
    falta."""
    seleccion = _sel([_c("grande", place="estadio", tokens=5_000)], token_budget=60)
    [elegido] = [s for s in seleccion.chosen if s.quota is Quota.PLACE]
    assert elegido.as_summary
    assert elegido.content.startswith("resumen")


def test_no_se_repite_escena_salvo_que_no_haya_alternativa() -> None:
    """RF-83. Dos cupos sin otra opcion valen mas que un cupo vacio.

    La regla es sobre ESCENAS, no sobre fragmentos: dos fragmentos distintos de
    la misma escena pueden llenar dos cupos si no hay alternativa. El mismo
    fragmento dos veces seria texto duplicado literal, que no lo arregla ninguna
    regla de diversidad.
    """
    a = _c("a", scene_id="unica", place="estadio")
    b = _c("b", scene_id="unica", has_dialogue=True, pov="marcos")
    seleccion = _sel([a, b])
    cupos = {s.quota for s in seleccion.chosen}
    assert Quota.PLACE in cupos and Quota.VOICE in cupos


def test_el_mismo_fragmento_no_llena_dos_cupos() -> None:
    """Meterlo dos veces seria texto duplicado literal en el paquete."""
    unico = _c("mismo", place="estadio", has_dialogue=True, pov="marcos")
    seleccion = _sel([unico])
    assert len([s for s in seleccion.chosen if s.candidate.chunk_id == "mismo"]) == 1
