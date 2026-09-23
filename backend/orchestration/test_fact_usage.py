"""El registro `fact_usage` y `affected_scenes` dan las mismas escenas. RF-241, D-89. VER-05, VER-06.

Vive en `orchestration/` porque `affected_scenes` es del Orquestador y `canon/` no
puede importarlo. Las enmiendas pasan por el camino real, `create_request` y
`apply_pending`, con un Reparador de reemplazo literal.
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from brief.interpret import Candidate, RawInterpretation
from canon import manuscript
from canon.brief import create_novel
from canon.db import connection
from canon.prose_index import usage
from canon.test_manuscript import _brief, _congelar, _escena
from commons.tracing.trace import Trace
from orchestration import amend
from orchestration.amend import FactAnchor
from orchestration.test_loop import _engine


def _vigentes(path: Path) -> list[manuscript.Interpretation]:
    with connection.reader(path) as con:
        return [
            manuscript.Interpretation(
                entity_id=r["entity_id"],
                attribute=r["name"],
                previous_value=r["value"],
                new_value="x",
            )
            for r in con.execute(
                "SELECT entity_id, name, value FROM attribute WHERE valid_to IS NULL ORDER BY entity_id, name"
            )
        ]


def _registro(path: Path, interp: manuscript.Interpretation) -> list[str] | None:
    with connection.reader(path) as con:
        return usage.scenes_using(con, interp.entity_id, interp.attribute)


def _coinciden(path: Path) -> None:
    hechos = _vigentes(path)
    assert hechos, "sin hechos vigentes no se comprueba nada"
    for interp in hechos:
        assert _registro(path, interp) == amend.affected_scenes(path, interp), interp


def test_tras_congelar_dos_capitulos_registro_y_affected_scenes_coinciden(tmp_path: Path) -> None:
    """La puerta de T42."""
    path = tmp_path / "dos.sqlite"
    create_novel(path, _brief())
    _congelar(
        path,
        1,
        [
            _escena(1, 1, "Rex, negro como el carbón, corrió.", ("lucia", "rex")),
            _escena(1, 2, "Lucía, de 10 años, miró el cielo negro.", ("lucia",)),
        ],
    )
    _congelar(
        path,
        2,
        [
            _escena(2, 1, "Rex ladró; Lucía cumplía 10.", ("lucia", "rex")),
            _escena(2, 2, "El perro negro durmió.", ("rex",)),
        ],
    )
    color = manuscript.Interpretation(
        entity_id="rex", attribute="color", previous_value="negro", new_value="blanco"
    )
    assert _registro(path, color) == amend.affected_scenes(path, color) == ["c1e1", "c2e2"]
    edad = manuscript.Interpretation(
        entity_id="lucia", attribute="edad", previous_value="10", new_value="11"
    )
    # Lucia es POV de todas: su edad se usa donde sale el valor.
    assert _registro(path, edad) == amend.affected_scenes(path, edad) == ["c1e2", "c2e1"]
    _coinciden(path)


def test_una_discrepancia_consta_en_la_traza_y_no_cambia_el_resultado(tmp_path: Path) -> None:
    """RF-241: la busqueda en el texto se conserva como comprobacion."""
    path = tmp_path / "roto.sqlite"
    create_novel(path, _brief())
    _congelar(path, 1, [_escena(1, 1, "Rex, negro, corrió.", ("rex",))])
    with connection.canon_writer(path) as con:
        con.execute("DELETE FROM fact_usage")
    traza = Trace(tmp_path / "n.trace.jsonl")
    color = manuscript.Interpretation(
        entity_id="rex", attribute="color", previous_value="negro", new_value="blanco"
    )
    assert amend.affected_scenes(path, color, traza) == ["c1e1"]
    [aviso] = traza.records("amend.usage_mismatch")
    assert aviso.fields["registry"] == [] and aviso.fields["text"] == ["c1e1"]
    assert aviso.fields["fact"] == "rex.color"

    # Con el registro al dia no hay aviso.
    with connection.canon_writer(path) as con:
        usage.rebuild(con)
    amend.affected_scenes(path, color, traza)
    assert len(traza.records("amend.usage_mismatch")) == 1


def _pedir_color(path: Path, nuevo: str) -> None:
    def interpreta(_t: str, _a: str, _c: Sequence[Candidate]) -> RawInterpretation:
        return RawInterpretation(entity_id="rex", attribute="color", new_value=nuevo)

    amend.create_request(
        path,
        f"Rex es {nuevo}",
        FactAnchor(entity_id="rex", attribute="color"),
        interpreta,
        Trace.disabled(),
    )


# ------------------------------------------------------------------ propiedad

_PALABRAS = ("Rex", "negro", "Negro", "negros", "blanco", "gris", "10", "corrió", "el", "Lucía")
_ESCENA = st.tuples(
    st.lists(st.sampled_from(_PALABRAS), min_size=1, max_size=8),
    st.sets(st.sampled_from(("lucia", "rex")), max_size=2),
)
_PASO: st.SearchStrategy[tuple[str, list[tuple[list[str], set[str]]], str]] = st.one_of(
    st.tuples(st.just("capitulo"), st.lists(_ESCENA, min_size=1, max_size=3), st.just("")),
    st.tuples(st.just("enmienda"), st.just([]), st.sampled_from(("negro", "gris", "blanco"))),
)


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(pasos=st.lists(_PASO, min_size=1, max_size=5))
def test_propiedad_registro_y_affected_scenes_coinciden_tras_cualquier_secuencia(
    pasos: list[tuple[str, list[tuple[list[str], set[str]]], str]],
) -> None:
    """RF-241, `srs-backend-v4.md` §7.3 «Registro de usos»: para cualquier secuencia
    de congelaciones y enmiendas, el registro da las escenas que da la busqueda."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "p.sqlite"
        create_novel(path, _brief())
        cap = 0
        motor = _engine()
        for kind, datos, valor in pasos:
            if kind == "enmienda":
                _pedir_color(path, valor)
                amend.apply_pending(path, motor, Trace.disabled())
            else:
                cap += 1
                _congelar(
                    path,
                    cap,
                    [
                        _escena(cap, n, " ".join(palabras) + ".", tuple(sorted(elenco)))
                        for n, (palabras, elenco) in enumerate(datos, start=1)
                    ],
                )
            _coinciden(path)
