"""El examen de comprension. RF-112 a RF-115. VER-05 y VER-20 con doble."""

from __future__ import annotations

import json

from commons.types.primitives import Severity, WorldTime
from commons.types.scene import (
    DramaticFunction,
    ExpectedOutput,
    SceneConstraints,
    SceneContent,
    SceneFunction,
    SceneIdentity,
    SceneSpec,
)
from verification.quiz import build, grade, prompts

NOMBRES = {"marcos": "Marcos Vela", "tecnico": "Aurelio Peña", "vestuario": "el vestuario"}


def _spec() -> SceneSpec:
    return SceneSpec(
        identity=SceneIdentity(
            scene_id="c1e1",
            chapter=1,
            ordinal=1,
            pov="marcos",
            place="vestuario",
            world_time=WorldTime(stamp="2026-08-10"),
        ),
        function=DramaticFunction(
            function=SceneFunction.ESTABLISH,
            value_change="x",
            objective="saber",
            obstacle="silencio",
        ),
        content=SceneContent(cast=("marcos", "tecnico"), beats=("entra",)),
        output=ExpectedOutput(target_words=500, ends_with="sale"),
        constraints=SceneConstraints(),
    )


def test_las_preguntas_salen_del_encargo_y_tienen_solucionario() -> None:
    """RF-113: nunca del capitulo, nunca sin clave."""
    preguntas = build.build([_spec()], NOMBRES)
    assert {q.id for q in preguntas} == {"c1e1-pov", "c1e1-lugar", "c1e1-elenco"}
    assert all(q.keys for q in preguntas)
    elenco = next(q for q in preguntas if q.id == "c1e1-elenco")
    assert set(elenco.keys) == {"Marcos Vela", "Aurelio Peña"}


def test_una_respuesta_con_todas_las_claves_es_correcta_sin_importar_tildes() -> None:
    preguntas = build.build([_spec()], NOMBRES)
    elenco = next(q for q in preguntas if q.id == "c1e1-elenco")
    assert grade.is_correct(elenco, "Estaban MARCOS VELA y aurelio pena en el vestuario")
    assert not grade.is_correct(elenco, "Estaba Marcos Vela solo")


def test_cada_respuesta_erronea_es_un_s2_que_cita_su_escena() -> None:
    """RF-115. Sin puerta nueva ni umbral propio."""
    preguntas = build.build([_spec()], NOMBRES)
    respuestas = ["no se sabe"] * len(preguntas)
    defectos = grade.grade(preguntas, respuestas, scene_texts={"c1e1": "Marcos entró el último..."})
    assert len(defectos) == len(preguntas)
    assert all(d.severity is Severity.S2 and d.kind == "quiz" for d in defectos)
    assert defectos[0].evidence.quote.startswith("Marcos entró")


def test_el_lector_no_recibe_prefijo_ni_canon() -> None:
    """RF-114. Solo capitulo, preguntas e instruccion."""
    texto = prompts.instruction("CAPITULO DE PRUEBA", build.build([_spec()], NOMBRES))
    assert "CAPITULO DE PRUEBA" in texto
    assert "canon" not in prompts.SYSTEM.lower()
    assert "estilo" not in prompts.SYSTEM.lower()


def test_las_respuestas_vuelven_en_el_orden_de_las_preguntas() -> None:
    preguntas = build.build([_spec()], NOMBRES)
    raw = json.dumps({"answers": {"c1e1-lugar": "el vestuario", "c1e1-pov": "Marcos Vela"}})
    respuestas = prompts.parse(raw, preguntas)
    assert respuestas[0] == "Marcos Vela"
    assert respuestas[1] == "el vestuario"
    assert respuestas[2] == ""


def test_una_palabra_distintiva_del_nombre_basta_y_un_articulo_no() -> None:
    """Medido en la tirada real: "Marcos" y "en el vestuario" son respuestas correctas."""
    preguntas = build.build([_spec()], NOMBRES)
    pov = next(q for q in preguntas if q.id == "c1e1-pov")
    lugar = next(q for q in preguntas if q.id == "c1e1-lugar")
    assert grade.is_correct(pov, "Marcos")
    assert grade.is_correct(lugar, "en el vestuario")
    assert not grade.is_correct(lugar, "en el campo")
    assert not grade.is_correct(pov, "el")


def test_una_preposicion_no_cuenta_como_palabra_distintiva() -> None:
    """D-64: fuera de articulos y preposiciones, tambien las de tres letras o mas."""
    from verification.quiz.build import Question

    q = Question(
        id="q", scene_id="c1e1", text="¿Con quien?", expected="Pol con Iker", keys=("Pol con Iker",)
    )
    assert not grade.is_correct(q, "fue con su padre")
    assert grade.is_correct(q, "con Iker")
