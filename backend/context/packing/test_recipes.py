"""La muestra modelica y los resumenes del paquete del Escritor.

RF-140, RF-89, RF-139; `architecture.md` §4.3 bloque 5 y §4.5. VER-05.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from canon.brief import create_novel
from canon.db import connection
from canon.freeze.freeze import commit_chapter, prepare
from canon.summaries import levels
from canon.test_manuscript import _brief, _Embedder, _escena
from commons.types.primitives import WorldTime
from commons.types.scene import (
    DramaticFunction,
    ExpectedOutput,
    SceneConstraints,
    SceneContent,
    SceneFunction,
    SceneIdentity,
    SceneSpec,
)
from context.packing.recipes import (
    STYLIST_SAMPLES,
    _summaries,
    model_samples,
    voice_sample,
    writer_packet,
)
from context.retrieval.quotas import Selection

DIALOGO = "—¿Juegas hoy? —pregunto el tecnico, y Marcos no contesto."


def _con(escenas: list[tuple[str, int, str]], votos: list[tuple[str, int]]) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE prose_scene (id TEXT PRIMARY KEY, chapter INTEGER, scene_number INTEGER,
                                  pov_entity TEXT);
        CREATE TABLE prose_chunk (id TEXT PRIMARY KEY, scene_id TEXT, ordinal INTEGER, text TEXT);
        CREATE TABLE scene_verdict (scene_id TEXT, dimension TEXT, level INTEGER, valid INTEGER);
        """
    )
    for sid, cap, pov in escenas:
        con.execute("INSERT INTO prose_scene VALUES (?, ?, 1, ?)", (sid, cap, pov))
        con.execute("INSERT INTO prose_chunk VALUES (?, ?, 0, ?)", (f"{sid}#0", sid, DIALOGO))
    for sid, nivel in votos:
        con.execute("INSERT INTO scene_verdict VALUES (?, 'voice', ?, 1)", (sid, nivel))
    return con


def test_sin_veredictos_rige_la_recencia() -> None:
    con = _con([("c1e1", 1, "marcos"), ("c2e1", 2, "marcos")], [])
    m = voice_sample(con, pov="marcos", exclude_scenes=frozenset(), recent_used=frozenset())
    assert m is not None and m[0] == "c2e1#0"


def test_con_veredictos_la_puntuacion_sustituye_a_la_recencia() -> None:
    """RF-140: una escena reciente sin puntuar ya no es muestra."""
    con = _con([("c1e1", 1, "marcos"), ("c2e1", 2, "marcos")], [("c1e1", 4)])
    m = voice_sample(con, pov="marcos", exclude_scenes=frozenset(), recent_used=frozenset())
    assert m is not None and m[0] == "c1e1#0"


def test_con_veredictos_y_ninguno_sobre_umbral_no_hay_muestra() -> None:
    con = _con([("c1e1", 1, "marcos")], [("c1e1", 2)])
    assert (
        voice_sample(con, pov="marcos", exclude_scenes=frozenset(), recent_used=frozenset()) is None
    )


def test_el_estilista_recibe_hasta_tres_muestras_sin_repetir() -> None:
    """§4.9 Estilista: 3 x 800, rotativas."""
    con = _con([(f"c{n}e1", n, "marcos") for n in range(1, 6)], [])
    muestras = model_samples(con, povs=["marcos"], exclude_scenes=frozenset({"c5e1"}))
    assert len(muestras) == STYLIST_SAMPLES
    ids = [r["id"] for r in con.execute("SELECT id FROM prose_chunk WHERE scene_id != 'c5e1'")]
    assert len(ids) >= STYLIST_SAMPLES


# ---------------------------------------------- resumenes del paquete (§4.3 bloque 5)


def _novela_con_resumenes(tmp_path: Path) -> Path:
    """Dos capitulos congelados con resumenes distinguibles; el 2 trae arco y obra."""
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    for cap in (1, 2):
        altos = (
            [
                levels.SummaryToWrite(level="arc", ref_id="arco-1", body="RESUMEN DEL ARCO"),
                levels.SummaryToWrite(level="work", ref_id="obra", body="RESUMEN DE LA OBRA"),
            ]
            if cap == 2
            else []
        )
        prep = prepare(
            [_escena(cap, 1, f"Lucía y Rex en el capítulo {cap}.", ("lucia", "rex"))],
            chapter=cap,
            chapter_summary=f"RESUMEN DEL CAPITULO {cap}",
            embed=_Embedder(),
            higher_summaries=altos,
        )
        with connection.canon_writer(path) as con:
            commit_chapter(con, prep)
    return path


def _spec(chapter: int) -> SceneSpec:
    return SceneSpec(
        identity=SceneIdentity(
            scene_id=f"c{chapter}e1",
            chapter=chapter,
            ordinal=1,
            pov="lucia",
            place="parque",
            world_time=WorldTime(stamp=f"2026-09-0{chapter}"),
        ),
        function=DramaticFunction(
            function=SceneFunction.ESTABLISH,
            value_change="de la calma a la duda",
            objective="encontrar a Rex",
            obstacle="la lluvia",
        ),
        content=SceneContent(cast=("lucia", "rex"), beats=("busca",)),
        output=ExpectedOutput(target_words=900, ends_with="lo encuentra"),
        constraints=SceneConstraints(),
    )


def _bloque_resumenes(path: Path, chapter: int) -> str:
    with connection.reader(path) as con:
        packet, _hechos = writer_packet(
            con,
            _spec(chapter),
            anchor="ANCLA",
            estimate=len,
            retrieval=Selection(chosen=()),
            previous_prose="",
            previous_chapter=None,
            open_setups=(),
            voice=None,
            knowledge=(),
            related=frozenset(),
        )
    (bloque,) = [b for b in packet.blocks if b.name == "resumenes"]
    return bloque.content


def test_los_resumenes_que_lee_el_escritor_son_obra_arco_y_capitulo_anterior(
    tmp_path: Path,
) -> None:
    """§4.3 bloque 5, §4.5. Para el capitulo 3, el del 2; no el del 1 ni el del 3."""
    path = _novela_con_resumenes(tmp_path)
    with connection.reader(path) as con:
        assert _summaries(con, chapter=3) == (
            "RESUMEN DE LA OBRA",
            "RESUMEN DEL ARCO",
            "RESUMEN DEL CAPITULO 2",
        )
        assert _summaries(con, chapter=2)[2] == "RESUMEN DEL CAPITULO 1"


def test_el_paquete_del_escritor_lleva_el_resumen_del_capitulo_anterior(tmp_path: Path) -> None:
    """ENT-33: lo congelado del capitulo N entra en el paquete del N+1, y el 1 no lleva ninguno."""
    path = _novela_con_resumenes(tmp_path)
    tercero = _bloque_resumenes(path, 3)
    assert "CAPITULO ANTERIOR: RESUMEN DEL CAPITULO 2" in tercero
    assert "OBRA: RESUMEN DE LA OBRA" in tercero and "ARCO: RESUMEN DEL ARCO" in tercero
    assert "RESUMEN DEL CAPITULO 1" not in tercero
    assert "CAPITULO ANTERIOR" not in _bloque_resumenes(path, 1)
