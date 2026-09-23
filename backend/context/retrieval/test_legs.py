"""Las dos piernas contra el indice real.

RF-75, RF-76, RF-78, D-12. Lo que se comprueba es que filtran por metadatos
antes de puntuar, que no mezclan vectores incomparables, y que la semantica se
degrada sin romper nada.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from canon.db import connection
from commons.types.primitives import WorldTime
from commons.types.vectors import cosine, pack_vector, unpack_vector
from context.query.build import RetrievalRequest
from context.retrieval.legs import lexical, semantic

DIM = 4


def _req(**kw: object) -> RetrievalRequest:
    base: dict[str, object] = {
        "entities": frozenset({"marcos"}),
        "lexical_terms": ("Marcos Vela", "el Chino"),
        "semantic_text": "descubre que le han vendido",
        # El escaner ve "token" en el nombre y lo toma por una contrasena.
        "token_budget": 3_000,  # nosec B105
    }
    base.update(kw)
    return RetrievalRequest(**base)  # type: ignore[arg-type]


@pytest.fixture
def indexada(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    connection.create(path)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        INSERT INTO entity (id, kind, name, created_at) VALUES
            ('marcos','person','Marcos Vela','2026-01-01');
        INSERT INTO prose_scene (id, chapter, scene_number, pov_entity, world_time,
                                 world_seq, function, summary) VALUES
            ('e1', 1, 1, 'marcos', '2026-01-10', 0, 'revelar', 'resumen uno'),
            ('e2', 2, 1, 'marcos', '2026-02-10', 0, 'complicar', 'resumen dos');
        """
    )
    con.execute(
        "INSERT INTO prose_chunk (id, scene_id, ordinal, text, vector, vector_model, vector_dim)"
        " VALUES (?,?,?,?,?,?,?)",
        ("c1", "e1", 1, "Marcos Vela miro el cesped mojado.", pack_vector([1, 0, 0, 0]), "m", DIM),
    )
    con.execute(
        "INSERT INTO prose_chunk (id, scene_id, ordinal, text, vector, vector_model, vector_dim)"
        " VALUES (?,?,?,?,?,?,?)",
        (
            "c2",
            "e2",
            1,
            "El Chino se ato las botas dos veces.",
            pack_vector([0, 1, 0, 0]),
            "m",
            DIM,
        ),
    )
    # Vector de otra dimension: simula un fragmento indexado con otro modelo.
    con.execute(
        "INSERT INTO prose_chunk (id, scene_id, ordinal, text, vector, vector_model, vector_dim)"
        " VALUES (?,?,?,?,?,?,?)",
        ("c3", "e2", 2, "Otro parrafo.", pack_vector([1, 1]), "viejo", 2),
    )
    con.execute("INSERT INTO prose_chunk_fts (rowid, text) SELECT rowid, text FROM prose_chunk")
    con.commit()
    con.close()
    return path


# ------------------------------------------------------------------ serializar


def test_el_vector_sobrevive_al_viaje() -> None:
    v = [0.5, -0.25, 1.0, 0.0]
    assert list(unpack_vector(pack_vector(v))) == v


def test_el_coseno_es_uno_consigo_mismo() -> None:
    assert cosine([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


def test_el_coseno_de_un_vector_nulo_no_revienta() -> None:
    assert cosine([0, 0], [1, 1]) == 0.0


# -------------------------------------------------------------------- lexica


def test_la_lexica_encuentra_nombres_propios(indexada: Path) -> None:
    """Es la unica que acierta con ellos, y por eso sus terminos salen de la
    tabla de alias y no de un modelo."""
    with connection.reader(indexada) as con:
        assert set(lexical(con, _req())) == {"c1", "c2"}


def test_la_lexica_filtra_por_instante(indexada: Path) -> None:
    """Antes de puntuar, no despues: es lo que hace barata la consulta."""
    with connection.reader(indexada) as con:
        ids = lexical(con, _req(before=WorldTime(stamp="2026-01-20")))
    assert ids == ["c1"]


def test_la_lexica_respeta_las_escenas_excluidas(indexada: Path) -> None:
    with connection.reader(indexada) as con:
        ids = lexical(con, _req(excluded_scenes=frozenset({"e1"})))
    assert "c1" not in ids


def test_sin_terminos_no_hay_busqueda_lexica(indexada: Path) -> None:
    with connection.reader(indexada) as con:
        assert lexical(con, _req(lexical_terms=())) == []


# ------------------------------------------------------------------ semantica


def test_la_semantica_ordena_por_parecido(indexada: Path) -> None:
    with connection.reader(indexada) as con:
        ids = semantic(con, _req(), [1, 0, 0, 0])
    assert ids[0] == "c1"


def test_no_se_comparan_vectores_de_otra_dimension(indexada: Path) -> None:
    """Mezclarlos daria numeros sin significado, y con un modelo local cambiarlo
    es sustituir un fichero: el error es facil de cometer."""
    with connection.reader(indexada) as con:
        assert "c3" not in semantic(con, _req(), [1, 0, 0, 0])


def test_sin_vector_de_consulta_la_semantica_devuelve_vacio(indexada: Path) -> None:
    """No aplica el fallo cerrado: la recuperacion no es una comprobacion, asi
    que se degrada a una sola pierna y se marca."""
    with connection.reader(indexada) as con:
        assert semantic(con, _req(), None) == []
