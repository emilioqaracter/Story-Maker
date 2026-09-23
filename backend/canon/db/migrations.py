"""Migraciones del esquema. Hacia delante, en escritura.

RD-10, RI-35. Abrir un fichero de una version anterior lo migra al escribir;
leerlo no lo toca. Una version desconocida --mas nueva que este codigo-- falla,
porque abrir a ciegas un fichero mas nuevo es como se corrompe una novela.

Cada version es una lista de sentencias que **solo anaden**: tablas, columnas,
indices. Nunca se borra ni se renombra, porque las proyecciones se reconstruyen
desde el registro de eventos y todo lo demas es estado que no se puede
recuperar de otro sitio.

La version 2 trae las tablas de `specs/srs-backend-v2.md` §5 en un solo paso,
para que un fichero de la version 1 suba de una vez y no tramo a tramo.

Una version puede llevar ademas un **relleno** (`BACKFILL`): codigo que, tras sus
sentencias y en la misma transaccion, llena lo nuevo a partir de lo que el
fichero ya tenia. Tambien solo anade. La 5 lo usa para registrar hecho x escena
sobre la prosa congelada antes de que existiera el registro (RD-39).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from canon.prose_index import chronology

#: Version que este codigo escribe.
SCHEMA_VERSION = 5

MIGRATIONS: dict[int, tuple[str, ...]] = {
    2: (
        # RD-23. Ninguna version de resumen se sobrescribe: `summary` guarda la
        # vigente y esta tabla, todas.
        """
        CREATE TABLE IF NOT EXISTS summary_version (
            level       TEXT    NOT NULL,
            ref_id      TEXT    NOT NULL,
            version     INTEGER NOT NULL,
            covers_to   INTEGER,
            body        TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            PRIMARY KEY (level, ref_id, version),
            CHECK (level IN ('scene', 'chapter', 'arc', 'work'))
        )
        """,
        # RD-20. Veredictos del Jurado por escena congelada: proyeccion, no traza.
        """
        CREATE TABLE IF NOT EXISTS scene_verdict (
            scene_id    TEXT    NOT NULL REFERENCES prose_scene(id),
            dimension   TEXT    NOT NULL,
            level       INTEGER,
            dispersion  INTEGER NOT NULL,
            valid       INTEGER NOT NULL,
            instance    TEXT    NOT NULL,
            seed        INTEGER NOT NULL,
            score       INTEGER NOT NULL,
            quote       TEXT    NOT NULL,
            offset      INTEGER NOT NULL,
            created_at  TEXT    NOT NULL,
            PRIMARY KEY (scene_id, dimension, instance)
        )
        """,
        # RD-21. Huella estilistica por capitulo congelado.
        """
        CREATE TABLE IF NOT EXISTS chapter_fingerprint (
            chapter             INTEGER NOT NULL PRIMARY KEY,
            mean_sentence_len   REAL    NOT NULL,
            var_sentence_len    REAL    NOT NULL,
            adj_noun_ratio      REAL    NOT NULL,
            top_ngrams          TEXT    NOT NULL,
            lexical_richness    REAL    NOT NULL,
            deviation           REAL,
            is_reference        INTEGER NOT NULL DEFAULT 0,
            created_at          TEXT    NOT NULL
        )
        """,
        # RD-22. Las trece senales de architecture.md 11 por capitulo.
        """
        CREATE TABLE IF NOT EXISTS chapter_metrics (
            chapter     INTEGER NOT NULL,
            signal      TEXT    NOT NULL,
            value       REAL,
            threshold   TEXT    NOT NULL,
            state       TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            PRIMARY KEY (chapter, signal),
            CHECK (state IN ('ok', 'alarm', 'unknown'))
        )
        """,
        # RD-24. Retcons aplicados. Append-only como el registro.
        """
        CREATE TABLE IF NOT EXISTS retcon (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fact_key        TEXT    NOT NULL,
            previous_value  TEXT    NOT NULL,
            new_value       TEXT    NOT NULL,
            event_ids       TEXT    NOT NULL,
            refrozen_scenes TEXT    NOT NULL,
            rule            TEXT    NOT NULL,
            chapter_origin  INTEGER NOT NULL,
            created_at      TEXT    NOT NULL
        )
        """,
        """
        CREATE TRIGGER IF NOT EXISTS retcon_no_update
        BEFORE UPDATE ON retcon
        BEGIN
            SELECT RAISE(ABORT, 'el registro de retcons es append-only');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS retcon_no_delete
        BEFORE DELETE ON retcon
        BEGIN
            SELECT RAISE(ABORT, 'el registro de retcons es append-only');
        END
        """,
        # RD-27. Con que parametros se corto e indexo la prosa. Cambiarlos es
        # reindexar, igual que cambiar el modelo de los vectores (RD-13).
        """
        CREATE TABLE IF NOT EXISTS retrieval_params (
            id              INTEGER PRIMARY KEY CHECK (id = 1),
            chunk_tokens    INTEGER NOT NULL,
            fusion_k        INTEGER NOT NULL,
            quotas          TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL
        )
        """,
    ),
    # `specs/srs-backend-v3.md` §5: versiones del manuscrito y solicitudes de cambio.
    3: (
        # RD-33. Una solicitud de cambio del lector y lo que el sistema hizo con ella.
        # No es canon ni traza: es el encargo, y su estado lo cambia solo el backend.
        """
        CREATE TABLE IF NOT EXISTS change_request (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            text            TEXT    NOT NULL,
            anchor          TEXT    NOT NULL,
            status          TEXT    NOT NULL,
            entity_id       TEXT,
            attribute       TEXT,
            previous_value  TEXT,
            new_value       TEXT,
            reason          TEXT    NOT NULL DEFAULT '',
            version         INTEGER,
            changed_chapters TEXT   NOT NULL DEFAULT '[]',
            created_at      TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL,
            CHECK (status IN ('queued', 'applying', 'applied', 'rejected')),
            CHECK (json_valid(anchor)),
            CHECK (json_valid(changed_chapters))
        )
        """,
        # RD-34. La version 1 es la tirada y no tiene fila. Cada enmienda aplicada
        # anade una, con el ultimo capitulo congelado cuando se creo.
        """
        CREATE TABLE IF NOT EXISTS manuscript_version (
            version         INTEGER PRIMARY KEY,
            cause           INTEGER REFERENCES change_request(id),
            changed_chapters TEXT   NOT NULL,
            max_chapter     INTEGER NOT NULL,
            created_at      TEXT    NOT NULL,
            CHECK (version >= 2),
            CHECK (json_valid(changed_chapters))
        )
        """,
        # RD-34. El texto que tenia una escena hasta la version `until_version`,
        # guardado antes de recongelarla. Sin esto, recongelar borraria el pasado.
        """
        CREATE TABLE IF NOT EXISTS scene_text_history (
            scene_id        TEXT    NOT NULL REFERENCES prose_scene(id),
            until_version   INTEGER NOT NULL,
            text            TEXT    NOT NULL,
            PRIMARY KEY (scene_id, until_version)
        )
        """,
        """
        CREATE TRIGGER IF NOT EXISTS scene_text_history_no_update
        BEFORE UPDATE ON scene_text_history
        BEGIN
            SELECT RAISE(ABORT, 'la historia del manuscrito es append-only');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS scene_text_history_no_delete
        BEFORE DELETE ON scene_text_history
        BEGIN
            SELECT RAISE(ABORT, 'la historia del manuscrito es append-only');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS manuscript_version_no_update
        BEFORE UPDATE ON manuscript_version
        BEGIN
            SELECT RAISE(ABORT, 'una version publicada no cambia');
        END
        """,
    ),
    # `specs/srs-backend-v4.md` T42: hecho x escena, cronologia y la historia que no
    # se borra. Se escribe tras la 4 de T41 (orden de integracion, `backend/PLAN.md` §8).
    5: (
        # RD-39, D-89. Indice, no verdad: vive con el indice de prosa. Lo escribe la
        # congelacion y la recongelacion (`canon/prose_index/usage.py`).
        """
        CREATE TABLE IF NOT EXISTS fact_usage (
            fact_key        TEXT    NOT NULL,
            source_event    INTEGER NOT NULL REFERENCES event(id),
            scene_id        TEXT    NOT NULL REFERENCES prose_scene(id),
            chapter         INTEGER NOT NULL,
            PRIMARY KEY (fact_key, source_event, scene_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_fact_usage_scene ON fact_usage (scene_id)",
        "CREATE INDEX IF NOT EXISTS idx_fact_usage_chapter ON fact_usage (fact_key, chapter)",
        # RD-40, RF-242. Una vista no puede desincronizarse de lo que proyecta.
        "CREATE VIEW IF NOT EXISTS chronology AS " + chronology.SELECT,
        # RD-34. Una version publicada tampoco se borra.
        """
        CREATE TRIGGER IF NOT EXISTS manuscript_version_no_delete
        BEFORE DELETE ON manuscript_version
        BEGIN
            SELECT RAISE(ABORT, 'una version publicada no se borra');
        END
        """,
    ),
}


def _backfill_fact_usage(con: sqlite3.Connection) -> None:
    # Import tardio: `usage` lee el indice de prosa y `connection` importa este
    # modulo; arriba seria un ciclo.
    from canon.prose_index import usage

    usage.rebuild(con)


#: Rellenos por version, tras sus sentencias y en la misma transaccion.
BACKFILL: dict[int, Callable[[sqlite3.Connection], None]] = {
    5: _backfill_fact_usage,
}


def current_version(con: sqlite3.Connection) -> int:
    row = con.execute("SELECT max(version) AS v FROM schema_version").fetchone()
    return int(row["v"]) if row is not None and row["v"] is not None else 0


def migrate(con: sqlite3.Connection) -> int:
    """Aplica las versiones pendientes. Devuelve la version final.

    Idempotente: una version ya aplicada no se repite, y todas las sentencias
    son `IF NOT EXISTS`, asi que reintentar una migracion a medias es seguro.
    """
    actual = current_version(con)
    for version in sorted(MIGRATIONS):
        if version <= actual:
            continue
        for sentencia in MIGRATIONS[version]:
            con.execute(sentencia)
        if version in BACKFILL:
            BACKFILL[version](con)
        con.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
            (version,),
        )
        actual = version
    return actual
