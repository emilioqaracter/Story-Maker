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
    """Las entidades base, cada una con su desempate: el par (instante,
    desempate) es unico y las fixtures tampoco se libran (RD-19)."""
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

    Se les da `seq` distinto porque el esquema ya no admite colisiones (RD-19):
    generar una haria fallar la insercion, no la propiedad. Antes esta misma
    linea estaba aqui por otro motivo --tapaba una contradiccion de la spec--
    y ahora esta porque el modelo de datos lo exige, que es donde tenia que
    haber estado desde el principio.
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


def test_una_colision_de_instante_se_rechaza(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """RD-19. Dos eventos en el mismo instante y desempate no entran.

    Esta prueba sustituye a una que fallaba a proposito, y merece la pena contar
    por que. RD-03 fijaba el orden en `(world_time, world_seq, id)` y afirmaba a
    la vez que el orden de insercion no participaba: no podian ser las dos
    cosas, porque `id` ES el orden de insercion y decidia justo cuando las otras
    dos empataban. Una propiedad lo destapo generando la colision.

    La salida no fue relajar RF-04 sino quitarle al `id` el trabajo: con el par
    unico, el orden ya es total y el `id` no decide nada.

    Se rechaza en vez de asignar un hueco libre porque elegir que hecho va
    primero es una decision de causalidad narrativa, y la tiene quien construye
    el delta, no quien escribe filas.
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

    path = tmp_path_factory.mktemp("col") / "n.sqlite"
    connection.create(path)
    with (
        pytest.raises(log.InstantCollisionError, match="next_seq"),
        connection.canon_writer(path) as con,
    ):
        log.append(con, _seed_entities())
        log.append(con, colision)


def test_next_seq_da_el_siguiente_hueco_libre(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Rechazar sin dar una salida facil solo consigue que alguien ponga un
    numero al azar."""
    path = tmp_path_factory.mktemp("seq") / "n.sqlite"
    connection.create(path)
    with connection.canon_writer(path) as con:
        log.append(con, _seed_entities())
        siguiente = log.next_seq(con, "2026-01-01")
        assert siguiente == len(_seed_entities())

        log.append(
            con,
            [
                Event(
                    world_time=WorldTime(stamp="2026-01-01", seq=siguiente),
                    payload=AttributeSet(entity_id="e1", name="estado", value="sano"),
                    provenance=Provenance.PROSE,
                    chapter_origin=1,
                    entities=frozenset({"e1"}),
                )
            ],
        )


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

        filas = [
            tuple(r)
            for r in con.execute(
                "SELECT value, valid_from, valid_to FROM attribute "
                "WHERE entity_id='e1' AND name='estado' ORDER BY valid_from"
            )
        ]
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


def test_reconstruir_con_prosa_congelada_no_rompe_las_claves(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """RF-05 sobre una novela real: el indice de prosa referencia a `entity`."""
    from collections.abc import Sequence

    from canon.brief import Brief, BriefEntity, create_novel
    from canon.db import connection
    from canon.freeze.freeze import SceneToFreeze, commit_chapter, prepare
    from canon.projections import rebuild
    from commons.provider.port import Embedding
    from commons.types.primitives import WorldTime

    class _E:
        def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
            return [Embedding(values=(0.1,), model_id="d", dimension=1) for _ in texts]

    path = tmp_path / "n.sqlite"
    create_novel(
        path,
        Brief(
            title="p",
            start=WorldTime(stamp="2026-01-01"),
            entities=(BriefEntity(id="m", kind="person", name="M"),),
            style_guide="x",
            target_words=1000,
        ),
    )
    esc = SceneToFreeze(
        id="c1e1",
        chapter=1,
        scene_number=1,
        pov_entity="m",
        world_time=WorldTime(stamp="2026-01-02"),
        function="establecer",
        text="M entro.",
        summary="s",
        present=("m",),
    )
    with connection.canon_writer(path) as con:
        commit_chapter(con, prepare([esc], chapter=1, chapter_summary="c", embed=_E()))
    with connection.canon_writer(path) as con:
        rebuild.rebuild(con)
    with connection.reader(path) as con:
        assert con.execute("SELECT count(*) AS n FROM entity").fetchone()["n"] == 1
