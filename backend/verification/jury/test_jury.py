"""El Jurado: anclaje, dispersion, mediana, segunda ronda y conjunto dorado.

RF-126 a RF-136, D-37, D-39, D-41. VER-05, VER-06, VER-19.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from commons.types.primitives import Severity
from commons.types.rubrics import DEFAULT_RUBRICS, Dimension, dumps, loads
from verification.jury import golden, prompts
from verification.jury.prompts import InstanceVerdict, Score
from verification.jury.verdict import (
    THRESHOLD,
    AnchoredScore,
    adjudicate,
    anchor,
    judge,
)

ESCENA = (
    "Marcos entró el último y nadie levantó la vista del suelo del vestuario. "
    "—¿Juego? —preguntó, y el técnico dobló la lista sin mirarlo a la cara. "
    "El banco estaba frío y la camiseta del nueve seguía colgada en su gancho."
)
CITA = "Marcos entró el último y nadie levantó la vista del suelo"


def _instancia(niveles: Mapping[Dimension, int], *, cita: str = CITA) -> InstanceVerdict:
    return InstanceVerdict(
        scores=tuple(
            Score(dimension=d, level=n, scene="c1e1", quote=cita) for d, n in niveles.items()
        )
    )


def _todas(n: int) -> dict[Dimension, int]:
    return dict.fromkeys(Dimension, n)


def test_las_rubricas_son_datos_con_cinco_niveles_por_dimension() -> None:
    """RF-128, RNF-37."""
    assert {r.dimension for r in DEFAULT_RUBRICS.rubrics} == set(Dimension)
    assert all(len(r.levels) == 5 for r in DEFAULT_RUBRICS.rubrics)
    assert loads(dumps(DEFAULT_RUBRICS)) == DEFAULT_RUBRICS


def test_una_cita_que_no_ancla_descarta_la_puntuacion() -> None:
    """RF-129, RF-111."""
    validas, descartes = anchor(
        {
            "j1": (
                1,
                _instancia(
                    {Dimension.VOICE: 4}, cita="una cita que el juez se invento de principio a fin"
                ),
            )
        },
        {"c1e1": ESCENA},
    )
    assert validas == []
    assert descartes == [("j1", "una cita que el juez se invento de principio a fin")]


def test_una_cita_que_nombra_mal_la_escena_ancla_donde_esta() -> None:
    """RF-129. La prueba es la cita; la escena nombrada es una pista."""
    otra = "El silbato sono y el estadio entero se puso en pie a la vez para verlo."
    ver = InstanceVerdict(
        scores=(
            Score(dimension=Dimension.PACING, level=4, scene="capitulo", quote=CITA),
            Score(dimension=Dimension.VOICE, level=4, scene="c1e2", quote=CITA),
        )
    )
    validas, descartes = anchor({"j1": (1, ver)}, {"c1e1": ESCENA, "c1e2": otra})
    assert descartes == []
    assert {v.scene for v in validas} == {"c1e1"}


def test_una_cita_que_esta_en_dos_escenas_no_es_una_posicion() -> None:
    ver = InstanceVerdict(
        scores=(Score(dimension=Dimension.PACING, level=4, scene="capitulo", quote=CITA),)
    )
    validas, _ = anchor({"j1": (1, ver)}, {"c1e1": ESCENA, "c1e2": ESCENA})
    assert validas == []


def test_tres_instancias_de_acuerdo_dan_la_mediana() -> None:
    """RF-131. Mediana de 3, 4, 4 es 4, y pasa."""
    runs = {
        "j1": (1, _instancia(_todas(3))),
        "j2": (2, _instancia(_todas(4))),
        "j3": (3, _instancia(_todas(4))),
    }
    validas, _ = anchor(runs, {"c1e1": ESCENA})
    dims = judge(validas)
    assert all(d.valid and d.level == 4 and d.passed for d in dims)


def test_dispersion_de_dos_niveles_invalida_y_no_promedia() -> None:
    """RF-130. 2, 3, 4: rango 2, invalida aunque la media sea 3."""
    runs = {
        "j1": (1, _instancia(_todas(2))),
        "j2": (2, _instancia(_todas(3))),
        "j3": (3, _instancia(_todas(4))),
    }
    validas, _ = anchor(runs, {"c1e1": ESCENA})
    dims = judge(validas)
    assert all(not d.valid and d.level is None and not d.passed for d in dims)


def test_la_segunda_ronda_repite_solo_lo_invalido_con_otras_semillas() -> None:
    """RF-130. Si la segunda ronda acuerda, vale; nunca hay tercera."""
    llamadas: list[list[int]] = []

    def run(seeds: Sequence[int]) -> Mapping[str, tuple[int, InstanceVerdict]]:
        llamadas.append(list(seeds))
        if len(llamadas) == 1:
            voz = [2, 3, 4]
            return {
                f"j{i}": (s, _instancia({**_todas(4), Dimension.VOICE: voz[i]}))
                for i, s in enumerate(seeds)
            }
        return {f"j{i}": (s, _instancia(_todas(3))) for i, s in enumerate(seeds)}

    v = adjudicate(run, {"c1e1": ESCENA}, seeds=[1, 2, 3])
    assert v.rounds == 2
    assert llamadas[1] != llamadas[0]
    assert v.get(Dimension.VOICE).level == 3  # type: ignore[union-attr]
    assert v.get(Dimension.PACING).level == 4  # type: ignore[union-attr]
    assert v.passed


def test_bajo_umbral_da_defectos_con_evidencia_y_severidad() -> None:
    """RF-132, CAL-06."""
    runs = {
        "j1": (1, _instancia(_todas(2))),
        "j2": (2, _instancia(_todas(2))),
        "j3": (3, _instancia(_todas(2))),
    }
    v = adjudicate(lambda _s: runs, {"c1e1": ESCENA}, seeds=[1, 2, 3])
    assert not v.passed
    defectos = {d.kind: d for d in v.defects()}
    assert defectos["jury.voice"].severity is Severity.S2
    assert defectos["jury.pacing"].severity is Severity.S3
    assert defectos["jury.voice"].evidence.offset == 0


def test_una_dimension_sin_tres_citas_ancladas_es_invalida() -> None:
    """Fallo cerrado: no se mide dispersion de lo que no hay."""
    runs = {"j1": (1, _instancia(_todas(4))), "j2": (2, _instancia(_todas(4)))}
    validas, _ = anchor(runs, {"c1e1": ESCENA})
    assert all(not d.valid for d in judge(validas))


@settings(max_examples=60, deadline=None)
@given(st.lists(st.integers(min_value=1, max_value=5), min_size=3, max_size=3))
def test_nunca_hay_nivel_resultante_con_dispersion_invalida(niveles: list[int]) -> None:
    """Propiedad de la SRS v2 §7.3."""
    scores = [
        AnchoredScore(
            instance=f"j{i}",
            seed=i,
            dimension=Dimension.THEME,
            level=n,
            scene="c1e1",
            evidence=__import__("commons.types.primitives", fromlist=["Evidence"]).Evidence(
                quote=CITA, offset=0
            ),
        )
        for i, n in enumerate(niveles)
    ]
    [d] = judge(scores, dimensions=[Dimension.THEME])
    if max(niveles) - min(niveles) >= 2:
        assert d.level is None and not d.passed
    else:
        assert d.level is not None and d.passed == (d.level >= THRESHOLD)


def test_el_prompt_no_lleva_guia_de_estilo_y_la_semilla_cambia_el_orden() -> None:
    """RF-127, RNF-32: invariantes sin guia; tres semillas, tres ordenes."""
    assert "GUIA DE ESTILO" not in prompts.SYSTEM
    ordenes = {tuple(prompts.order_for(s)) for s in (11, 12, 13)}
    assert len(ordenes) > 1


# --------------------------------------------------------------- conjunto dorado


def test_las_transformaciones_siembran_lo_que_dicen() -> None:
    texto = (
        "Primero.\n\nSegundo parrafo aqui.\n\nTercero y final. Otra frase. Y el cierre del valor."
    )
    assert golden.duplicate_paragraph(texto).count("Segundo parrafo aqui.") == 2  # type: ignore[union-attr]
    assert not golden.drop_last_sentence(texto).endswith("cierre del valor.")  # type: ignore[union-attr]
    assert "Aurelio" in golden.swap_name("Marcos llego.", "Marcos", "Aurelio")  # type: ignore[operator]
    a, b = golden.swap_dialogue("x\n—Hola, dijo.\ny", "z\n—Adios, dijo.\nw")  # type: ignore[misc]
    assert "Adios" in a and "Hola" in b
    assert "el gol de la esperanza" in golden.insert_cliches(texto, [])


def test_el_conjunto_se_construye_desde_prosa_congelada(tmp_path: Path) -> None:
    """RF-133. Sin nadie que marque nada; cada caso dice su dimension."""
    from canon.brief import Brief, BriefEntity, create_novel
    from canon.db import connection
    from canon.freeze.freeze import SceneToFreeze, commit_chapter, prepare
    from commons.provider.port import Embedding
    from commons.types.primitives import WorldTime

    class _Embedder:
        def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
            return [Embedding(values=(0.1, 0.2), model_id="doble", dimension=2) for _ in texts]

    path = tmp_path / "n.sqlite"
    create_novel(
        path,
        Brief(
            title="p",
            start=WorldTime(stamp="2026-08-01"),
            entities=(
                BriefEntity(id="marcos", kind="person", name="Marcos"),
                BriefEntity(id="aurelio", kind="person", name="Aurelio"),
            ),
            style_guide="x",
            target_words=1000,
        ),
    )
    prosa = (
        "Marcos miró el campo. Aurelio no dijo nada.\n\n—Juego —dijo Marcos.\n\n"
        "El banco estaba frío. Nadie se movió. Al final salió."
    )
    escenas = [
        SceneToFreeze(
            id=f"c1e{n}",
            chapter=1,
            scene_number=n,
            pov_entity=pov,
            world_time=WorldTime(stamp=f"2026-08-1{n}"),
            function="establecer",
            text=prosa,
            summary="resumen",
            present=("marcos", "aurelio"),
        )
        for n, pov in ((1, "marcos"), (2, "aurelio"))
    ]
    preparado = prepare(escenas, chapter=1, chapter_summary="capitulo", embed=_Embedder())
    with connection.canon_writer(path) as con:
        commit_chapter(con, preparado)
    with connection.reader(path) as con:
        casos = golden.build(con, limit=8)
    assert casos
    assert {c.transformation for c in casos} >= {"duplicar-parrafo", "insertar-proscritos"}
    assert all(c.dimension in Dimension for c in casos)
    sqlite3.connect(":memory:").close()


def test_la_tasa_de_deteccion_cuenta_lo_que_no_pasa() -> None:
    """RF-134, D-41."""
    caso = golden.GoldenCase(
        id="x",
        transformation="duplicar-parrafo",
        dimension=Dimension.PACING,
        scene_ids=("c1e1",),
        povs=("m",),
        texts=(ESCENA,),
    )
    malo = adjudicate(
        lambda _s: {f"j{i}": (i, _instancia(_todas(2))) for i in range(3)},
        {"c1e1": ESCENA},
        seeds=[0, 1, 2],
    )
    bueno = adjudicate(
        lambda _s: {f"j{i}": (i, _instancia(_todas(4))) for i in range(3)},
        {"c1e1": ESCENA},
        seeds=[0, 1, 2],
    )
    assert golden.detection_rate([(caso, malo), (caso, bueno)]) == 0.5
    assert golden.DETECTION_FLOOR == 0.90


def test_el_motivo_de_una_cita_que_no_ancla_se_le_dice_al_juez() -> None:
    """D-71."""
    from verification.jury.verdict import unanchored

    ver = InstanceVerdict(
        scores=(
            Score(dimension=Dimension.VOICE, level=4, scene="c1e1", quote="Marcos entró el último"),
            Score(
                dimension=Dimension.PACING,
                level=4,
                scene="c1e1",
                quote="Marcos entró el último... la camiseta del nueve seguía colgada en su gancho",
            ),
            Score(dimension=Dimension.THEME, level=4, scene="c1e1", quote=CITA),
        )
    )
    motivos = unanchored(ver, {"c1e1": ESCENA})
    assert len(motivos) == 2
    assert "minimo" in motivos[0] and "puntos suspensivos" in motivos[1]
