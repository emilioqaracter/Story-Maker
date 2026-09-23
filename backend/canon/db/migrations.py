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

Un paso es una sentencia o, cuando SQLite no tiene forma idempotente de
decirlo --`ALTER TABLE ... ADD COLUMN` no admite `IF NOT EXISTS`--, una funcion
que mira el esquema antes de tocarlo. Asi reintentar una migracion a medias
sigue siendo seguro.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

#: Version que este codigo escribe.
SCHEMA_VERSION = 4

Step = str | Callable[[sqlite3.Connection], None]


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {str(r[1]) for r in con.execute(f"PRAGMA table_info({table})")}  # nosec B608


def _add_proscribed_level(con: sqlite3.Connection) -> None:
    """RD-37. `proscribed` gana `level`, sin tocar lo que ya tiene."""
    if "level" in _columns(con, "proscribed"):
        return
    con.execute(
        "ALTER TABLE proscribed ADD COLUMN level TEXT NOT NULL DEFAULT 'estilo' "
        "CHECK (level IN ('global', 'cliente', 'novela', 'estilo'))"
    )


MIGRATIONS: dict[int, tuple[Step, ...]] = {
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
    # `specs/srs-backend-v4.md` RD-37, D-91: los niveles de la proscripcion.
    4: (
        _add_proscribed_level,
        # Un fichero anterior: lo que prohibio el brief es nivel `cliente`, y
        # `kind` deja de mezclar el origen con el tipo. Los n-gramas ya quedan
        # en `estilo` por el valor por defecto.
        "UPDATE proscribed SET level = 'cliente', kind = 'term' WHERE kind = 'brief'",
        "CREATE INDEX IF NOT EXISTS idx_proscribed_level ON proscribed (level)",
        # D-91: un termino se queda en su nivel mas fuerte. Bajarlo no es un
        # colapso, es perder una prohibicion, y se impide en el esquema.
        """
        CREATE TRIGGER IF NOT EXISTS proscribed_level_no_downgrade
        BEFORE UPDATE OF level ON proscribed
        WHEN (CASE NEW.level WHEN 'global' THEN 0 WHEN 'cliente' THEN 1
                   WHEN 'novela' THEN 2 ELSE 3 END)
           > (CASE OLD.level WHEN 'global' THEN 0 WHEN 'cliente' THEN 1
                   WHEN 'novela' THEN 2 ELSE 3 END)
        BEGIN
            SELECT RAISE(ABORT, 'un termino proscrito se queda en su nivel mas fuerte');
        END
        """,
        # RD-37: un termino del guardarrail es `term`; lo de `estilo`, `ngram` o
        # `image`. Separar nivel y tipo no sirve si se pueden volver a mezclar.
        """
        CREATE TRIGGER IF NOT EXISTS proscribed_kind_insert
        BEFORE INSERT ON proscribed
        WHEN NEW.kind NOT IN ('ngram', 'image', 'term')
           OR (NEW.level <> 'estilo' AND NEW.kind <> 'term')
           OR (NEW.level = 'estilo' AND NEW.kind = 'term')
        BEGIN
            SELECT RAISE(ABORT, 'kind y level de proscribed no casan');
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS proscribed_kind_update
        BEFORE UPDATE OF kind, level ON proscribed
        WHEN NEW.kind NOT IN ('ngram', 'image', 'term')
           OR (NEW.level <> 'estilo' AND NEW.kind <> 'term')
           OR (NEW.level = 'estilo' AND NEW.kind = 'term')
        BEGIN
            SELECT RAISE(ABORT, 'kind y level de proscribed no casan');
        END
        """,
    ),
}


def current_version(con: sqlite3.Connection) -> int:
    row = con.execute("SELECT max(version) AS v FROM schema_version").fetchone()
    return int(row["v"]) if row is not None and row["v"] is not None else 0


def migrate(con: sqlite3.Connection) -> int:
    """Aplica las versiones pendientes. Devuelve la version final.

    Idempotente: una version ya aplicada no se repite, y cada paso es
    `IF NOT EXISTS`, un `UPDATE` que da lo mismo aplicado dos veces o una
    funcion que mira el esquema antes, asi que reintentar una migracion a medias
    es seguro.
    """
    actual = current_version(con)
    for version in sorted(MIGRATIONS):
        if version <= actual:
            continue
        for paso in MIGRATIONS[version]:
            if callable(paso):
                paso(con)
            else:
                con.execute(paso)
        con.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
            (version,),
        )
        actual = version
    return actual
