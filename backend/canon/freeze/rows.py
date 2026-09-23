"""Las filas de proyeccion que la version 2 escribe al congelar.

RD-20, RD-21, RD-22, RD-26. Las **prepara** quien produce el estado
--`verification/` los veredictos y la huella, `supervision/` las metricas-- y
las **escribe** la congelacion, dentro de su transaccion. Los tipos viven aqui,
en `canon/`, porque `canon/` no puede importar de ninguna funcionalidad y todas
pueden importar de `canon/`.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


class SceneVerdictRow(BaseModel):
    """RD-20. Una puntuacion anclada del Jurado, en la escena que cita."""

    model_config = ConfigDict(frozen=True)

    scene_id: str
    dimension: str
    level: int | None = Field(description="Nivel resultante de la dimension en el capitulo")
    dispersion: int = Field(ge=0)
    valid: bool
    instance: str
    seed: int
    score: int = Field(ge=1, le=5, description="Lo que puntuo esta instancia")
    quote: str
    offset: int = Field(ge=0)


class FingerprintRow(BaseModel):
    """RD-21. La huella de un capitulo congelado."""

    model_config = ConfigDict(frozen=True)

    chapter: int
    mean_sentence_len: float
    var_sentence_len: float
    adj_noun_ratio: float
    top_ngrams: tuple[str, ...]
    lexical_richness: float
    deviation: float | None = None
    is_reference: bool = False


class MetricRow(BaseModel):
    """RD-22. Una senal de `architecture.md` §11 para un capitulo."""

    model_config = ConfigDict(frozen=True)

    chapter: int
    signal: str
    value: float | None
    threshold: str
    state: str = Field(pattern="^(ok|alarm|unknown)$")


def write_verdicts(con: sqlite3.Connection, rows: Sequence[SceneVerdictRow]) -> None:
    con.executemany(
        "INSERT OR REPLACE INTO scene_verdict (scene_id, dimension, level, dispersion, valid, "
        "instance, seed, score, quote, offset, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'))",
        [
            (
                r.scene_id,
                r.dimension,
                r.level,
                r.dispersion,
                int(r.valid),
                r.instance,
                r.seed,
                r.score,
                r.quote,
                r.offset,
            )
            for r in rows
        ],
    )


def write_fingerprint(con: sqlite3.Connection, row: FingerprintRow | None) -> None:
    if row is None:
        return
    con.execute(
        "INSERT OR REPLACE INTO chapter_fingerprint (chapter, mean_sentence_len, var_sentence_len, "
        "adj_noun_ratio, top_ngrams, lexical_richness, deviation, is_reference, created_at) "
        "VALUES (?,?,?,?,?,?,?,?, datetime('now'))",
        (
            row.chapter,
            row.mean_sentence_len,
            row.var_sentence_len,
            row.adj_noun_ratio,
            json.dumps(list(row.top_ngrams), ensure_ascii=False),
            row.lexical_richness,
            row.deviation,
            int(row.is_reference),
        ),
    )


def write_metrics(con: sqlite3.Connection, rows: Sequence[MetricRow]) -> None:
    con.executemany(
        "INSERT OR REPLACE INTO chapter_metrics (chapter, signal, value, threshold, state, created_at) "
        "VALUES (?,?,?,?,?, datetime('now'))",
        [(r.chapter, r.signal, r.value, r.threshold, r.state) for r in rows],
    )


def read_fingerprints(con: sqlite3.Connection) -> list[FingerprintRow]:
    rows = con.execute("SELECT * FROM chapter_fingerprint ORDER BY chapter").fetchall()
    return [
        FingerprintRow(
            chapter=r["chapter"],
            mean_sentence_len=r["mean_sentence_len"],
            var_sentence_len=r["var_sentence_len"],
            adj_noun_ratio=r["adj_noun_ratio"],
            top_ngrams=tuple(json.loads(r["top_ngrams"])),
            lexical_richness=r["lexical_richness"],
            deviation=r["deviation"],
            is_reference=bool(r["is_reference"]),
        )
        for r in rows
    ]


def read_metrics(con: sqlite3.Connection) -> list[MetricRow]:
    rows = con.execute("SELECT * FROM chapter_metrics ORDER BY chapter, signal").fetchall()
    return [
        MetricRow(
            chapter=r["chapter"],
            signal=r["signal"],
            value=r["value"],
            threshold=r["threshold"],
            state=r["state"],
        )
        for r in rows
    ]
