"""Generador de la cronologia en Lean. `specs/srs-backend-v4.md` RF-243, RD-41, RI-63. VER-05, VER-06."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from canon.db import connection
from canon.events.types import AttributeSet, EntityCreated, Event
from canon.freeze.freeze import SceneToFreeze
from commons.types.primitives import Provenance, WorldTime
from verification.formal import fixtures, generate
from verification.formal.generate import (
    FormalExportError,
    Pending,
    age_interval,
    minutes,
    read_chronicle,
    src,
)


@pytest.fixture(scope="module")
def clean(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_clean(tmp_path_factory.mktemp("formal") / "clean.sqlite")


@pytest.fixture(scope="module")
def seeded(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return fixtures.build_seeded(tmp_path_factory.mktemp("formal") / "seeded.sqlite")


def _text(path: Path, pending: Pending | None = None) -> str:
    with connection.reader(path) as con:
        return generate.generate(con, pending)


# ------------------------------------------------------------------- tiempo


def test_el_instante_es_un_natural_en_minutos_desde_el_ano_1() -> None:
    assert minutes("0001-01-01") == 0
    assert minutes("0001-01-02") == 1440
    assert minutes("0001-01-01T01:30") == 90
    assert minutes("0001-01-01T01:30:59") == 90
    assert minutes("2026-08-11") - minutes("2026-08-10") == 1440


@pytest.mark.parametrize("stamp", ["11 de agosto", "2026-02-30", "2026-08-11T25:00", ""])
def test_un_instante_que_no_es_iso_falla_cerrado(stamp: str) -> None:
    with pytest.raises(FormalExportError):
        minutes(stamp)


def test_la_edad_da_el_intervalo_de_un_ano_compatible() -> None:
    lo, hi = age_interval(10, "2026-08-01")
    # Cumplir diez el 2026-08-01 vale; haber cumplido once ese dia, no.
    assert hi == minutes("2016-08-01")
    assert lo == minutes("2015-08-01") + 1


def test_un_29_de_febrero_se_desplaza_al_28_en_un_ano_no_bisiesto() -> None:
    lo, hi = age_interval(1, "2024-02-29")
    assert hi == minutes("2023-02-28")
    assert lo == minutes("2022-02-28") + 1


# -------------------------------------------------------------- lo que se exporta


def test_una_entrada_por_fila_con_su_origen(clean: Path) -> None:
    text = _text(clean)
    with connection.reader(clean) as con:
        presentes = con.execute(
            "SELECT scene_id, entity_id FROM prose_scene_character "
            "UNION SELECT id, pov_entity FROM prose_scene"
        ).fetchall()
        atributos = con.execute("SELECT entity_id, name, valid_from FROM attribute").fetchall()
        entidades = con.execute("SELECT id FROM entity").fetchall()
    assert presentes and atributos and entidades
    for scene_id, entity in presentes:
        assert generate.lean_string(src("chronology", scene_id, entity)) in text
    for entity, name, start in atributos:
        assert generate.lean_string(src("attribute", entity, name, start)) in text
    for (entity,) in entidades:
        assert generate.lean_string(src("entity", entity)) in text
    for theorem in generate.THEOREMS.values():
        assert f"theorem {theorem} :" in text


def test_la_presencia_lleva_instante_desempate_y_lugar_de_su_escena(clean: Path) -> None:
    with connection.reader(clean) as con:
        chron = read_chronicle(con)
    by_src = {p.src: p for p in chron.presences}
    same_day = by_src[src("chronology", "c2e2", "lucia")]
    assert (same_day.time, same_day.seq, same_day.place) == (minutes("2026-08-21"), 1, "parque")
    first = by_src[src("chronology", "c1e1", "lucia")]
    assert (first.time, first.seq, first.place) == (minutes("2026-08-11"), 0, "parque")


def test_el_nacimiento_se_declara_se_deriva_o_falta_nunca_se_inventa(clean: Path) -> None:
    with connection.reader(clean) as con:
        chron = read_chronicle(con)
    births = {b.entity: b for b in chron.births}
    # Declarado: birth_date.
    assert births["lucia"].derived is False
    assert births["lucia"].lo == births["lucia"].hi == minutes("2016-03-04")
    # Derivado: solo edad, con precision de un año y marcado.
    assert births["marco"].derived is True
    assert (births["marco"].lo, births["marco"].hi) == age_interval(12, "2026-08-01")
    # Ausente: ni edad ni fecha.
    assert "tomas" not in births
    assert "rex" not in births


def test_una_birth_date_que_no_es_iso_falla_cerrado(tmp_path: Path) -> None:
    path = fixtures.build_clean(tmp_path / "n.sqlite")
    evento = _set("tomas", "birth_date", "hace mucho", "2026-08-02")
    with connection.reader(path) as con, pytest.raises(FormalExportError):
        read_chronicle(con, Pending(events=(evento,)))


def test_una_edad_que_no_es_entera_falla_cerrado(tmp_path: Path) -> None:
    path = fixtures.build_clean(tmp_path / "n.sqlite")
    evento = _set("tomas", "age", "diez", "2026-08-02")
    with connection.reader(path) as con, pytest.raises(FormalExportError):
        read_chronicle(con, Pending(events=(evento,)))


def test_la_exclusion_sale_del_atributo_reservado(clean: Path) -> None:
    with connection.reader(clean) as con:
        chron = read_chronicle(con)
    assert [(x.entity, x.start) for x in chron.exclusions] == [("tomas", minutes("2026-08-13"))]


# -------------------------------------------------------------- lo pendiente


def _set(entity: str, name: str, value: str, stamp: str) -> Event:
    return Event(
        world_time=WorldTime(stamp=stamp),
        payload=AttributeSet(entity_id=entity, name=name, value=value),
        provenance=Provenance.PROSE,
        chapter_origin=3,
        entities=frozenset({entity}),
    )


def test_lo_pendiente_entra_marcado_y_el_fichero_no_se_toca(clean: Path) -> None:
    antes = clean.read_bytes()
    escena = SceneToFreeze(
        id="c3e1",
        chapter=3,
        scene_number=1,
        pov_entity="lucia",
        place_entity="estadio",
        world_time=WorldTime(stamp="2026-08-30"),
        function="cerrar",
        text="Lucía volvió al estadio.",
        summary="vuelta",
        present=("lucia", "marco"),
    )
    nueva = Event(
        world_time=WorldTime(stamp="2026-08-28"),
        payload=EntityCreated(entity_id="bea", kind="person", name="Bea"),
        provenance=Provenance.PROSE,
        chapter_origin=3,
        entities=frozenset({"bea"}),
    )
    pending = Pending(
        scenes=(escena,), events=(nueva, _set("marco", "excluded", "lesion", "2026-08-29"))
    )
    with connection.reader(clean) as con:
        chron = read_chronicle(con, pending)
    origenes = {p.src for p in chron.presences}
    assert "pending." + src("chronology", "c3e1", "marco") in origenes
    assert src("chronology", "c1e1", "lucia") in origenes
    assert ("pending." + src("attribute", "marco", "excluded", "2026-08-29")) in {
        x.src for x in chron.exclusions
    }
    assert "pending." + src("entity", "bea") in {e.src for e in chron.existences}
    # Lo que ya estaba no se marca.
    assert src("entity", "lucia") in {e.src for e in chron.existences}
    assert clean.read_bytes() == antes


def test_una_escena_pendiente_con_el_id_de_una_congelada_la_sustituye(clean: Path) -> None:
    recongelada = SceneToFreeze(
        id="c1e1",
        chapter=1,
        scene_number=1,
        pov_entity="lucia",
        place_entity="estadio",
        world_time=WorldTime(stamp="2026-08-11"),
        function="establecer",
        text="Lucía, sola.",
        summary="sola",
        present=("lucia",),
    )
    with connection.reader(clean) as con:
        chron = read_chronicle(con, Pending(scenes=(recongelada,)))
    de_c1e1 = [p for p in chron.presences if '"c1e1"' in p.src]
    assert [(p.entity, p.place, p.src.startswith("pending.")) for p in de_c1e1] == [
        ("lucia", "estadio", True)
    ]


# -------------------------------------------------------------- determinismo


def test_dos_generaciones_del_mismo_canon_dan_el_mismo_fichero(clean: Path) -> None:
    assert _text(clean).encode("utf-8") == _text(clean).encode("utf-8")


def test_la_cli_escribe_lo_mismo_que_la_funcion(clean: Path, tmp_path: Path) -> None:
    out = tmp_path / "cronologia.lean"
    assert generate.main([str(clean), "-o", str(out)]) == 0
    assert out.read_bytes() == _text(clean).encode("utf-8")
    assert b"\r\n" not in out.read_bytes()


def test_la_cli_falla_cerrado_con_un_fichero_que_no_es_una_novela(tmp_path: Path) -> None:
    roto = tmp_path / "roto.sqlite"
    roto.write_bytes(b"no soy sqlite")
    assert generate.main([str(roto), "-o", str(tmp_path / "x.lean")]) == 1


def test_las_cronologias_versionadas_son_las_que_genera_hoy_el_canon(
    clean: Path, seeded: Path
) -> None:
    assert fixtures.CLEAN_FILE.read_text(encoding="utf-8") == _text(clean)
    assert fixtures.SEEDED_FILE.read_text(encoding="utf-8") == _text(seeded)


_TABLES = ("entity", "attribute", "prose_scene", "prose_scene_character")


def _rows(path: Path) -> dict[str, list[tuple[object, ...]]]:
    with connection.reader(path) as con:
        return {
            t: [tuple(r) for r in con.execute(f"SELECT * FROM {t}").fetchall()]  # nosec B608
            for t in _TABLES
        }


def _copy_in_order(
    rows: dict[str, list[tuple[object, ...]]], order: dict[str, list[int]], path: Path
) -> None:
    connection.create(path)
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA foreign_keys = OFF")
        for tabla in _TABLES:
            filas = rows[tabla]
            marks = ",".join("?" * len(filas[0]))
            for i in order[tabla]:
                con.execute(f"INSERT INTO {tabla} VALUES ({marks})", filas[i])  # nosec B608
        con.commit()
    finally:
        con.close()


@pytest.fixture(scope="module")
def clean_rows(clean: Path) -> dict[str, list[tuple[object, ...]]]:
    return _rows(clean)


@settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(data=st.data())
def test_el_orden_de_insercion_no_cambia_el_fichero(
    clean_rows: dict[str, list[tuple[object, ...]]], tmp_path: Path, data: st.DataObject
) -> None:
    """RF-243: mismo canon, mismo fichero, sea cual sea el orden en que entraron las filas."""
    identidad = {t: list(range(len(clean_rows[t]))) for t in _TABLES}
    orden = {t: data.draw(st.permutations(identidad[t]), label=t) for t in _TABLES}
    run = uuid.uuid4().hex
    a = tmp_path / f"a{run}.sqlite"
    b = tmp_path / f"b{run}.sqlite"
    _copy_in_order(clean_rows, identidad, a)
    _copy_in_order(clean_rows, orden, b)
    assert _text(a).encode("utf-8") == _text(b).encode("utf-8")


# El cuerpo de la vista `chronology` de la migracion 5 (T42,
# `canon/prose_index/chronology.py:SELECT`), copiado tal cual: es la forma que
# publico S-M. Tras integrar T42, un fichero nuevo ya trae la vista y esta
# prueba sigue diciendo lo mismo: las dos lecturas dan el mismo fichero.
_CHRONOLOGY_VIEW = """
CREATE VIEW chronology AS
SELECT
    s.id            AS scene_id,
    s.chapter       AS chapter,
    s.scene_number  AS scene_number,
    s.world_time    AS world_time,
    s.world_seq     AS world_seq,
    s.place_entity  AS place_entity,
    s.pov_entity    AS pov_entity,
    (
        SELECT json_group_array(p.entity_id) FROM (
            SELECT s.pov_entity AS entity_id
            UNION
            SELECT c.entity_id FROM prose_scene_character c WHERE c.scene_id = s.id
            ORDER BY 1
        ) p
    )               AS present,
    s.summary       AS summary
FROM prose_scene s
ORDER BY s.world_time, s.world_seq, s.chapter, s.scene_number
"""


@pytest.mark.parametrize("build", [fixtures.build_clean, fixtures.build_seeded])
def test_leer_la_vista_chronology_o_las_tablas_da_el_mismo_fichero(
    build: object, tmp_path: Path
) -> None:
    path = build(tmp_path / "n.sqlite")  # type: ignore[operator]
    con = sqlite3.connect(path)
    try:
        con.execute("DROP VIEW IF EXISTS chronology")
        con.commit()
        sin_vista = _text(path)
        con.execute(_CHRONOLOGY_VIEW)
        con.commit()
    finally:
        con.close()
    assert _text(path).encode("utf-8") == sin_vista.encode("utf-8")
    # Y el POV cuenta como presente, igual que en la vista.
    assert generate.lean_string(src("chronology", "c1e2", "lucia")) in sin_vista
