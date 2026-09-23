"""Migraciones hacia delante. RD-10, RI-35. VER-05."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from canon.brief import Brief, BriefEntity, create_novel
from canon.db import connection
from canon.db.migrations import SCHEMA_VERSION, current_version


def _brief() -> Brief:
    return Brief(
        title="p",
        start={"stamp": "2026-01-01"},  # type: ignore[arg-type]
        entities=(BriefEntity(id="m", kind="person", name="M"),),
        style_guide="x",
        target_words=1000,
    )


def _version_one(path: Path) -> None:
    """Un fichero como los dejaba la version 1: sin las tablas nuevas."""
    connection.create(path)
    con = sqlite3.connect(path)
    for tabla in (
        "summary_version",
        "scene_verdict",
        "chapter_fingerprint",
        "chapter_metrics",
        "retcon",
        "retrieval_params",
    ):
        con.execute(f"DROP TABLE IF EXISTS {tabla}")  # nosec B608
    con.execute("DELETE FROM schema_version WHERE version > 1")
    con.commit()
    con.close()


def test_una_novela_nueva_nace_en_la_version_actual(tmp_path: Path) -> None:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    with connection.reader(path) as con:
        assert current_version(con) == SCHEMA_VERSION
        assert con.execute("SELECT count(*) FROM summary_version").fetchone()[0] == 0


def test_leer_un_fichero_antiguo_no_lo_toca_y_escribir_lo_migra(tmp_path: Path) -> None:
    """RI-35: abrir un fichero de la version 1 migra hacia adelante en escritura."""
    path = tmp_path / "v1.sqlite"
    _version_one(path)
    with connection.reader(path) as con:
        assert current_version(con) == 1
    with connection.canon_writer(path):
        pass
    with connection.reader(path) as con:
        assert current_version(con) == SCHEMA_VERSION
        assert con.execute("SELECT count(*) FROM retcon").fetchone()[0] == 0


def test_un_fichero_mas_nuevo_que_el_codigo_no_se_abre(tmp_path: Path) -> None:
    path = tmp_path / "futuro.sqlite"
    create_novel(path, _brief())
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO schema_version (version, applied_at) VALUES (?, 'x')", (SCHEMA_VERSION + 1,)
    )
    con.commit()
    con.close()
    with pytest.raises(connection.SchemaVersionError), connection.reader(path):
        pass


def test_el_registro_de_retcons_es_append_only(tmp_path: Path) -> None:
    """RD-24."""
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    con = sqlite3.connect(path)
    con.execute(
        "INSERT INTO retcon (fact_key, previous_value, new_value, event_ids, refrozen_scenes, rule, chapter_origin, created_at) "
        "VALUES ('k', 'a', 'b', '[1]', '[]', 'r', 2, 'now')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("DELETE FROM retcon")
    con.close()
