"""Las tres propiedades que abren la puerta de T1.

RF-04, RF-05, RF-06. Metodo VER-06. Se escriben antes que el resto del tramo
porque son de las que se comprueban generando casos y no ejemplos: un test de
ejemplo sobre "el orden no importa" comprueba un orden, no la propiedad.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from canon.db import connection
from canon.events import log
from canon.events.types import (
    AttributeSet,
    EntityCreated,
    Event,
    KnowledgeGained,
    RelationSet,
)
from canon.projections import rebuild
from commons.types.primitives import Provenance, WorldTime

ENTITIES = ["e1", "e2", "e3"]


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    connection.create(path)
    return path


# ------------------------------------------------------------------ generadores

_days = st.integers(min_value=1, max_value=28).map(lambda d: f"2026-03-{d:02d}")
_seq = st.integers(min_value=0, max_value=3)


@st.composite
def _attribute_event(draw: st.DrawFn) -> Event:
    return Event(
        world_time=WorldTime(stamp=draw(_days), seq=draw(_seq)),
        payload=AttributeSet(
            entity_id=draw(st.sampled_from(ENTITIES)),
            name=draw(st.sampled_from(["estado", "moral", "club"])),
            value=draw(st.sampled_from(["a", "b", "c"])),
        ),
        provenance=Provenance.PROSE,
        chapter_origin=draw(st.integers(min_value=1, max_value=20)),
        entities=frozenset({draw(st.sampled_from(ENTITIES))}),
    )


def _seed_entities() -> list[Event]:
    return [
        Event(
            world_time=WorldTime(stamp="2026-01-01", seq=i),
            payload=EntityCreated(entity_id=e, kind="person", name=e.upper()),
            provenance=Provenance.BRIEF,
            entities=frozenset({e}),
        )
        for i, e in enumerate(ENTITIES)
    ]


def _snapshot(con: sqlite3.Connection) -> list[tuple[object, ...]]:
    """Estado proyectado, en orden estable para poder compararlo."""
    return [
        tuple(r)
        for r in con.execute(
            "SELECT entity_id, name, value, valid_from, valid_to FROM attribute "
            "ORDER BY entity_id, name, valid_from"
        )
    ]


# ----------------------------------------------------------- RF-04 y RF-05

@settings(max_examples=25, deadline=None)
@given(events=st.lists(_attribute_event(), min_size=1, max_size=12), base=st.integers(0, 99))
def test_la_proyeccion_no_depende_del_orden_de_insercion(
    tmp_path_factory: pytest.TempPathFactory, events: list[Event], base: int
) -> None:
    """RF-04. Insertar los mismos eventos en otro orden da el mismo estado.

    Es lo que permite que la congelacion anada un delta sin preocuparse de en
    que orden llegaron sus eventos, y lo que hace que un fichero copiado sea el
    mismo fichero.

    Se les da `seq` distinto a proposito. Con `seq` repetido la propiedad no se
    sostiene, y no por un fallo del codigo sino por la contradiccion que fija
    `test_colision_en_el_mismo_instante_rompe_rf04`. Dejar que el generador la
    produzca haria que esta propiedad fallara una vez de cada tantas y tapara
    con ruido intermitente lo que alli queda dicho con precision.
    """
    events = [
        e.model_copy(update={"world_time": WorldTime(stamp=e.world_time.stamp, seq=base + i)})
        for i, e in enumerate(events)
    ]

    directo = tmp_path_factory.mktemp("d") / "n.sqlite"
    invertido = tmp_path_factory.mktemp("i") / "n.sqlite"
    connection.create(directo)
    connection.create(invertido)

    for path, order in ((directo, events), (invertido, list(reversed(events)))):
        with connection.canon_writer(path) as con:
            log.append(con, _seed_entities())
            log.append(con, order)
            rebuild.rebuild(con)

    with connection.reader(directo) as a, connection.reader(invertido) as b:
        assert _snapshot(a) == _snapshot(b)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CONTRADICCION ABIERTA entre RD-03 y RF-04. RD-03 fija el orden de proyeccion "
        "en (world_time, world_seq, id) y afirma que el orden de insercion no participa; "
        "pero `id` ES el orden de insercion, asi que participa exactamente cuando las dos "
        "primeras claves empatan. Recomendacion: que el Archivero asigne `seq` distinto "
        "dentro de un delta y que el registro rechace la colision, con lo que `id` deja de "
        "decidir nada semantico y RF-04 se sostiene tal como esta escrita. Proceso B."
    ),
)
def test_colision_en_el_mismo_instante_rompe_rf04(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Fija la contradiccion con un caso exacto, no con uno generado.

    La propiedad de arriba la encontraba una vez de cada tantas, que para una
    contradiccion de spec es la peor forma de registrarla: parece un fallo
    intermitente en vez de una decision pendiente.
    """
    colision = [
        Event(
            world_time=WorldTime(stamp="2026-03-01", seq=0),
            payload=AttributeSet(entity_id="e1", name="estado", value=v),
            provenance=Provenance.PROSE,
            chapter_origin=1,
            entities=frozenset({"e1"}),
        )
        for v in ("a", "b")
    ]

    directo = tmp_path_factory.mktemp("cd") / "n.sqlite"
    invertido = tmp_path_factory.mktemp("ci") / "n.sqlite"
    connection.create(directo)
    connection.create(invertido)

    for path, order in ((directo, colision), (invertido, list(reversed(colision)))):
        with connection.canon_writer(path) as con:
            log.append(con, _seed_entities())
            log.append(con, order)
            rebuild.rebuild(con)

    with connection.reader(directo) as a, connection.reader(invertido) as b:
        assert _snapshot(a) == _snapshot(b)


@settings(max_examples=25, deadline=None)
@given(events=st.lists(_attribute_event(), min_size=1, max_size=12))
def test_reconstruir_desde_cero_es_igual_a_mantener_incremental(
    tmp_path_factory: pytest.TempPathFactory, events: list[Event]
) -> None:
    """RF-05. El canon estructurado es proyeccion reconstruible.

    Si esto falla, alguna tabla guarda algo que no deriva de un evento, y el
    registro deja de ser la fuente de verdad sin que nada lo senale.
    """
    path = tmp_path_factory.mktemp("r") / "n.sqlite"
    connection.create(path)

    # Se aplica por lotes cronologicos, que es lo que hace la congelacion: un
    # capitulo entero de una vez, y los capitulos en orden. Aplicar de uno en
    # uno en orden de llegada violaria la precondicion de `apply_all` y la
    # igualdad no se sostendria: es una propiedad del sistema, no del modulo.
    ordenados = sorted(events, key=lambda e: (e.world_time.stamp, e.world_time.seq))
    lotes = [ordenados[i : i + 3] for i in range(0, len(ordenados), 3)]

    with connection.canon_writer(path) as con:
        log.append(con, _seed_entities())
        rebuild.rebuild(con)
        for lote in lotes:
            ids = set(log.append(con, lote))
            rebuild.apply_all(con, [s for s in log.read_all(con) if s.id in ids])
        incremental = _snapshot(con)

        rebuild.rebuild(con)  # desde cero
        assert _snapshot(con) == incremental


# ---------------------------------------------------------------- RF-06

def test_un_atributo_nuevo_cierra_al_anterior(novela: Path) -> None:
    """RF-06. Nunca hay dos valores vigentes del mismo atributo.

    Dejar los dos abiertos fabrica en origen el conflicto de contexto CTX-15:
    el paquete llevaria las dos versiones y el Arbitro tendria que resolver
    algo que nunca debio existir.
    """
    with connection.canon_writer(novela) as con:
        log.append(con, _seed_entities())
        log.append(
            con,
            [
                Event(
                    world_time=WorldTime(stamp=f"2026-04-{d:02d}"),
                    payload=AttributeSet(entity_id="e1", name="estado", value=v),
                    provenance=Provenance.PROSE,
                    chapter_origin=d,
                    entities=frozenset({"e1"}),
                )
                for d, v in ((1, "sano"), (10, "lesionado"), (20, "sano"))
            ],
        )
        rebuild.rebuild(con)

        abiertos = con.execute(
            "SELECT count(*) AS n FROM attribute "
            "WHERE entity_id='e1' AND name='estado' AND valid_to IS NULL"
        ).fetchone()["n"]
        assert abiertos == 1

        filas = [tuple(r) for r in con.execute(
            "SELECT value, valid_from, valid_to FROM attribute "
            "WHERE entity_id='e1' AND name='estado' ORDER BY valid_from"
        )]
        assert filas == [
            ("sano", "2026-04-01", "2026-04-10"),
            ("lesionado", "2026-04-10", "2026-04-20"),
            ("sano", "2026-04-20", None),
        ]


def test_proyectar_hasta_un_instante_ignora_lo_posterior(novela: Path) -> None:
    """RF-03. Se proyecta menos, no se filtra despues de proyectar."""
    with connection.canon_writer(novela) as con:
        log.append(con, _seed_entities())
        log.append(
            con,
            [
                Event(
                    world_time=WorldTime(stamp="2026-05-01"),
                    payload=AttributeSet(entity_id="e1", name="estado", value="sano"),
                    provenance=Provenance.PROSE,
                    chapter_origin=1,
                    entities=frozenset({"e1"}),
                ),
                Event(
                    world_time=WorldTime(stamp="2026-06-01"),
                    payload=AttributeSet(entity_id="e1", name="estado", value="lesionado"),
                    provenance=Provenance.PROSE,
                    chapter_origin=2,
                    entities=frozenset({"e1"}),
                ),
            ],
        )
        rebuild.rebuild(con, until=WorldTime(stamp="2026-05-15"))
        vigente = con.execute(
            "SELECT value FROM attribute WHERE entity_id='e1' AND name='estado'"
        ).fetchall()
        assert [r["value"] for r in vigente] == ["sano"]


# --------------------------------------------------- el registro es append-only

def test_el_registro_no_admite_update_ni_delete(novela: Path) -> None:
    """RF-01. Lo impiden triggers del esquema, no el codigo de acceso.

    Una regla que vive solo en el modulo de escritura se salta la primera vez
    que alguien abre el fichero con otra herramienta.
    """
    with connection.canon_writer(novela) as con:
        log.append(con, _seed_entities())

    with connection.canon_writer(novela) as con:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            con.execute("UPDATE event SET type = 'otro'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            con.execute("DELETE FROM event")


def test_el_brief_es_el_unico_sin_capitulo_de_origen() -> None:
    """RF-11 y RD-01: la restriccion vive tambien en el esquema."""
    with pytest.raises(ValueError, match="capitulo de origen"):
        Event(
            world_time=WorldTime(stamp="2026-01-01"),
            payload=KnowledgeGained(entity_id="e1", fact_key="k"),
            provenance=Provenance.PROSE,
            chapter_origin=None,
            entities=frozenset({"e1"}),
        )


def test_un_evento_sin_entidad_se_rechaza() -> None:
    """RD-02: sin entidad no se puede proyectar sobre nada."""
    with pytest.raises(ValueError, match="sin entidad"):
        Event(
            world_time=WorldTime(stamp="2026-01-01"),
            payload=RelationSet(source_id="e1", target_id="e2", kind="rival"),
            provenance=Provenance.BRIEF,
            entities=frozenset(),
        )
