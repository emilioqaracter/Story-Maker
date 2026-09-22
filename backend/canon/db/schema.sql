-- Esquema de la novela. Un fichero SQLite por obra (RI-14).
--
-- Separacion LOGICA de los cinco almacenes, no fisica: son cinco conjuntos de
-- tablas en la misma base. Unificarlos en un unico indice vectorial es el error
-- estructural mas frecuente en este tipo de sistema (architecture.md 3.1).
--
-- Las tablas `wm_*` son memoria de trabajo: efimeras, purgadas al congelar, y
-- escritas por una conexion distinta que no puede tocar nada mas (D-30).

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================ version (RD-10)

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL PRIMARY KEY,
    applied_at  TEXT    NOT NULL
);

-- ================================================= 1. registro de eventos (RD-01)
--
-- Append-only. La inmutabilidad NO se deja en convencion: la imponen triggers
-- en el propio esquema, porque una regla que vive solo en el codigo de acceso
-- se salta la primera vez que alguien abre el fichero con otra herramienta.

CREATE TABLE IF NOT EXISTS event (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    world_time      TEXT    NOT NULL,           -- ISO 8601 (MUN-05, D-07)
    world_seq       INTEGER NOT NULL DEFAULT 0, -- desempate dentro del instante
    type            TEXT    NOT NULL,
    payload         TEXT    NOT NULL,           -- JSON validado por tipo
    provenance      TEXT    NOT NULL,           -- MET-09, acotada abajo
    chapter_origin  INTEGER,                    -- NULL solo para el brief
    recorded_at     TEXT    NOT NULL,

    CHECK (provenance IN ('brief', 'prose', 'derived', 'arbitration')),
    CHECK (json_valid(payload)),
    -- El brief es el unico sin capitulo de origen (RF-11).
    CHECK ((provenance = 'brief') = (chapter_origin IS NULL)),

    -- RD-19. El par es unico, y eso es lo que hace TOTAL el orden de
    -- proyeccion sin recurrir al `id`. Antes el orden era
    -- (world_time, world_seq, id) y se afirmaba a la vez que el orden de
    -- insercion no participaba: no podian ser las dos cosas, porque `id` ES
    -- el orden de insercion y decidia justo cuando las otras dos empataban.
    -- Con el par unico no hay empates que desempatar.
    UNIQUE (world_time, world_seq)
);

-- RD-03: el orden de proyeccion es (world_time, world_seq), y lo cubre ya el
-- indice unico de la restriccion de arriba. No hace falta otro.

CREATE TRIGGER IF NOT EXISTS event_no_update
BEFORE UPDATE ON event
BEGIN
    SELECT RAISE(ABORT, 'el registro de eventos es append-only: no se modifica');
END;

CREATE TRIGGER IF NOT EXISTS event_no_delete
BEFORE DELETE ON event
BEGIN
    SELECT RAISE(ABORT, 'el registro de eventos es append-only: no se borra');
END;

-- RD-02: todo evento afecta al menos a una entidad. Sin esto, un evento no se
-- puede proyectar sobre nada y queda como ruido en el registro.
CREATE TABLE IF NOT EXISTS event_entity (
    event_id    INTEGER NOT NULL REFERENCES event(id),
    entity_id   TEXT    NOT NULL,
    PRIMARY KEY (event_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_event_entity_entity ON event_entity (entity_id);

-- ============================ 2. canon estructurado, proyectado (RD-04)
--
-- Todo lo de aqui es PROYECCION: se puede tirar y regenerar desde `event`, y el
-- resultado tiene que ser identico (RF-05). Por eso ninguna tabla de esta
-- seccion guarda nada que no derive de un evento.

CREATE TABLE IF NOT EXISTS entity (
    id          TEXT    NOT NULL PRIMARY KEY,
    kind        TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL   -- instante de mundo en que aparece
);

CREATE TABLE IF NOT EXISTS entity_alias (
    entity_id   TEXT NOT NULL REFERENCES entity(id),
    alias       TEXT NOT NULL,
    valid_from  TEXT NOT NULL,
    valid_to    TEXT,              -- NULL = vigencia abierta
    PRIMARY KEY (entity_id, alias, valid_from)
);

-- MET-07: todo atributo tiene vigencia. Una consulta en t devuelve solo lo
-- vigente en t, que es lo que permite responder "que era cierto en el 12".
CREATE TABLE IF NOT EXISTS attribute (
    entity_id   TEXT NOT NULL REFERENCES entity(id),
    name        TEXT NOT NULL,
    value       TEXT NOT NULL,
    valid_from  TEXT NOT NULL,
    valid_to    TEXT,
    source_event INTEGER NOT NULL REFERENCES event(id),
    PRIMARY KEY (entity_id, name, valid_from)
);

CREATE INDEX IF NOT EXISTS idx_attribute_validity ON attribute (entity_id, valid_from, valid_to);

-- 3. grafo de entidades: aristas tipadas con vigencia, recorridas con CTE
CREATE TABLE IF NOT EXISTS relation (
    source_id   TEXT NOT NULL REFERENCES entity(id),
    target_id   TEXT NOT NULL REFERENCES entity(id),
    kind        TEXT NOT NULL,
    valid_from  TEXT NOT NULL,
    valid_to    TEXT,
    source_event INTEGER NOT NULL REFERENCES event(id),
    PRIMARY KEY (source_id, target_id, kind, valid_from)
);

CREATE INDEX IF NOT EXISTS idx_relation_source ON relation (source_id, valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_relation_target ON relation (target_id, valid_from, valid_to);

-- PER-10: que sabe un personaje y desde cuando. Es lo que permite que
-- check.knowledge marque una mencion imposible.
CREATE TABLE IF NOT EXISTS knowledge (
    entity_id   TEXT NOT NULL REFERENCES entity(id),
    fact_key    TEXT NOT NULL,
    known_from  TEXT NOT NULL,
    source_event INTEGER NOT NULL REFERENCES event(id),
    PRIMARY KEY (entity_id, fact_key)
);

-- PER-09: competencias vigentes
CREATE TABLE IF NOT EXISTS competence (
    entity_id   TEXT NOT NULL REFERENCES entity(id),
    name        TEXT NOT NULL,
    level       TEXT NOT NULL,
    valid_from  TEXT NOT NULL,
    valid_to    TEXT,
    source_event INTEGER NOT NULL REFERENCES event(id),
    PRIMARY KEY (entity_id, name, valid_from)
);

-- RF-10, D-08: guia de estilo, escaleta y reglamento entran por el registro y
-- se proyectan a versiones. Ninguna version se sobrescribe.
CREATE TABLE IF NOT EXISTS document_version (
    doc_kind    TEXT    NOT NULL,   -- style_guide | outline | rulebook
    version     INTEGER NOT NULL,
    body        TEXT    NOT NULL,
    source_event INTEGER NOT NULL REFERENCES event(id),
    PRIMARY KEY (doc_kind, version)
);

-- ==================================== 4. indice de prosa, dos niveles (RD-06, RD-15)

CREATE TABLE IF NOT EXISTS prose_scene (
    id              TEXT    NOT NULL PRIMARY KEY,
    chapter         INTEGER NOT NULL,
    scene_number    INTEGER NOT NULL,
    pov_entity      TEXT    NOT NULL REFERENCES entity(id),
    place_entity    TEXT    REFERENCES entity(id),
    world_time      TEXT    NOT NULL,
    world_seq       INTEGER NOT NULL DEFAULT 0,
    function        TEXT    NOT NULL,   -- EST-14
    summary         TEXT    NOT NULL,
    vector          BLOB,
    vector_model    TEXT,               -- RD-13
    vector_dim      INTEGER,
    UNIQUE (chapter, scene_number),
    -- Un vector sin modelo es un vector incomparable esperando a mezclarse.
    CHECK ((vector IS NULL) = (vector_model IS NULL)),
    CHECK ((vector IS NULL) = (vector_dim IS NULL))
);

CREATE TABLE IF NOT EXISTS prose_scene_character (
    scene_id    TEXT NOT NULL REFERENCES prose_scene(id),
    entity_id   TEXT NOT NULL REFERENCES entity(id),
    PRIMARY KEY (scene_id, entity_id)
);

-- RD-16: todo fragmento pertenece a exactamente una escena y hereda sus
-- metadatos por clave ajena, no duplicandolos. Eso es lo que hace que el filtro
-- por metadatos siga aplicandose exacto sobre fragmentos.
CREATE TABLE IF NOT EXISTS prose_chunk (
    id              TEXT    NOT NULL PRIMARY KEY,
    scene_id        TEXT    NOT NULL REFERENCES prose_scene(id),
    ordinal         INTEGER NOT NULL,
    text            TEXT    NOT NULL,
    vector          BLOB,
    vector_model    TEXT,
    vector_dim      INTEGER,
    UNIQUE (scene_id, ordinal),
    CHECK ((vector IS NULL) = (vector_model IS NULL))
);

CREATE INDEX IF NOT EXISTS idx_chunk_scene ON prose_chunk (scene_id, ordinal);

-- Pierna lexica: FTS5 trae BM25 de serie. Tabla externa para no duplicar texto.
CREATE VIRTUAL TABLE IF NOT EXISTS prose_chunk_fts USING fts5(
    text,
    content='prose_chunk',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);

-- ============================== 5. resumenes jerarquicos (CTX-06)

CREATE TABLE IF NOT EXISTS summary (
    level       TEXT    NOT NULL,   -- scene | chapter | arc | work
    ref_id      TEXT    NOT NULL,
    parent_ref  TEXT,
    body        TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    PRIMARY KEY (level, ref_id),
    CHECK (level IN ('scene', 'chapter', 'arc', 'work'))
);

-- ================================== proscripcion (POE-12, RF-108)
--
-- La inserta la CONGELACION, no el verificador que detecta: check.repetition
-- opera sobre borradores, y un borrador puede acabar en cuarentena. Proscribir
-- desde ahi condicionaria la obra por un texto que nunca existio.

CREATE TABLE IF NOT EXISTS proscribed (
    term        TEXT    NOT NULL PRIMARY KEY,
    kind        TEXT    NOT NULL,   -- ngram | image
    added_chapter INTEGER NOT NULL,
    added_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_proscribed_recent ON proscribed (added_chapter DESC);

-- ============================ memoria de trabajo (RD-07, PRO-13)
--
-- Efimera. Se purga al congelar (PRO-I1). La escribe `commons/db`, no `canon/`.

CREATE TABLE IF NOT EXISTS wm_run_state (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    chapter         INTEGER NOT NULL,
    last_closed_scene INTEGER,
    step            TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS wm_draft (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter     INTEGER NOT NULL,
    scene_number INTEGER NOT NULL,
    attempt     INTEGER NOT NULL DEFAULT 0,
    text        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS wm_defect (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter     INTEGER NOT NULL,
    scene_number INTEGER,
    kind        TEXT    NOT NULL,
    severity    TEXT    NOT NULL CHECK (severity IN ('S1', 'S2', 'S3')),
    quote       TEXT    NOT NULL,
    offset      INTEGER NOT NULL,
    rule        TEXT    NOT NULL,
    state       TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

-- Se crea aunque la v1 no tenga Jurado, para que el fichero sea completo (RD-07).
CREATE TABLE IF NOT EXISTS wm_verdict (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter     INTEGER NOT NULL,
    dimension   TEXT    NOT NULL,
    score       REAL    NOT NULL,
    dispersion  REAL,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS wm_admission (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT    NOT NULL,
    reserved    INTEGER NOT NULL,
    state       TEXT    NOT NULL,   -- queued | in_flight | done
    queued_at   TEXT    NOT NULL
);
