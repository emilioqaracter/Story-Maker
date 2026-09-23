"""El Continuista: de la salida a defectos anclados. RF-51, RF-110, RF-111. VER-05."""

from __future__ import annotations

import json

from commons.types.primitives import Severity
from verification.continuity.review import anchor_all, parse, scene_of, scene_offsets

ESCENAS = [
    "Marcos saltó al campo con el nueve a la espalda y el tobillo entero, como si nada.",
    "El técnico lo vio desde el banquillo y apretó los dientes hasta que le dolieron.",
]


def _raw(*defectos: dict[str, str]) -> str:
    return json.dumps({"defects": list(defectos)})


def test_una_cita_real_produce_un_defecto_con_posicion() -> None:
    texto = "\n\n".join(ESCENAS)
    anclado = anchor_all(
        parse(
            _raw(
                {
                    "kind": "continuity.state",
                    "severity": "S1",
                    "quote": "Marcos saltó al campo con el nueve a la espalda y el tobillo entero",
                    "rule": "el canon dice estado=lesionado",
                }
            )
        ),
        texto,
    )
    assert len(anclado.defects) == 1
    assert anclado.defects[0].severity is Severity.S1
    assert anclado.defects[0].evidence.offset == 0
    assert anclado.discarded == ()


def test_una_cita_inventada_se_descarta_y_consta() -> None:
    """RF-111: defecto de proceso del emisor, no del texto."""
    anclado = anchor_all(
        parse(
            _raw(
                {
                    "kind": "continuity.state",
                    "severity": "S1",
                    "quote": "el portero detuvo el penalti en el último minuto del partido",
                    "rule": "x",
                }
            )
        ),
        "\n\n".join(ESCENAS),
    )
    assert anclado.defects == ()
    assert len(anclado.discarded) == 1


def test_una_cita_corta_tampoco_vale() -> None:
    anclado = anchor_all(
        parse(_raw({"kind": "k", "severity": "S2", "quote": "el técnico lo vio", "rule": "x"})),
        "\n\n".join(ESCENAS),
    )
    assert anclado.defects == ()


def test_el_defecto_vuelve_a_su_escena() -> None:
    offsets = scene_offsets(ESCENAS)
    texto = "\n\n".join(ESCENAS)
    pos = texto.find("El técnico lo vio")
    assert scene_of(pos, offsets) == 1
    assert scene_of(0, offsets) == 0


def test_un_defecto_de_estilo_no_es_del_continuista() -> None:
    """RF-51, RF-111: fuera de ambito se descarta como defecto de proceso, no tumba la puerta."""
    from verification.continuity.review import ProposedDefect, Review, anchor_all

    texto = "Marcos sintio un cosquilleo en el estomago antes de salir al campo aquella tarde."
    cita = "Marcos sintio un cosquilleo en el estomago antes de salir"
    rev = Review(
        defects=(
            ProposedDefect(
                kind="continuity.style", severity=Severity.S1, quote=cita, rule="adjetivo"
            ),
            ProposedDefect(
                kind="continuity.state", severity=Severity.S1, quote=cita, rule="lesionado"
            ),
        )
    )
    anclado = anchor_all(rev, texto)
    assert [d.kind for d in anclado.defects] == ["continuity.state"]
    assert anclado.discarded and "fuera de ambito" in anclado.discarded[0]
