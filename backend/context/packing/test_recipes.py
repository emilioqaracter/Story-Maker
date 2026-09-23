"""La muestra modelica: por puntuacion en cuanto hay veredictos. RF-140, RF-89, RF-139. VER-05."""

from __future__ import annotations

import sqlite3

from context.packing.recipes import STYLIST_SAMPLES, model_samples, voice_sample

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
