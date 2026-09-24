"""El perfil de extension `prueba` (T53), de punta a punta con dobles. VER-05.

Los cinco briefs de evaluacion piden una obra minima: de 1.200 a 1.800 palabras,
tres capitulos de una escena, cada escena de 400 a 600 palabras. Aqui se corre la
tirada entera de cada uno con el motor real y un proveedor guionizado que
responde con el reparto de ese brief: lo que se comprueba es que el perfil llega
a todos los consumidores de rangos --escaleta, puerta de escena, puerta de
capitulo y cierre de obra-- y que la obra cierra con la forma que el perfil fija.

Con escenas de unas 500 palabras tambien tienen que funcionar el Jurado de nueve
dimensiones y los elementos obligatorios del brief (T47): el proveedor integra
cada rasgo y recuerdo obligatorio en la prosa, el Arquitecto los planifica como
setups `element.<id>` y el Archivero cita su uso.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from canon.brief import Brief, create_novel, elements
from canon.db import connection
from commons.tokens.counter import TokenCounter
from commons.tokens.factors import ModelFactors
from commons.tracing.trace import Trace
from commons.types.length import PRUEBA
from commons.types.rubrics import DEFAULT_RUBRICS
from orchestration.admission import Admission
from orchestration.compose import chapters_for
from orchestration.engine import Composer, specs_provider
from orchestration.loop import run
from orchestration.test_engine import _QIDS, ScriptedPort, _closing, _Embedder
from planning.outline.check import check
from planning.outline.types import Outline

BRIEFS = Path(__file__).parent / "briefs"
NOMBRES = sorted(p.name for p in BRIEFS.glob("[0-9][0-9]-*.json"))


def _load(name: str) -> Brief:
    return Brief.model_validate_json((BRIEFS / name).read_text(encoding="utf-8"))


class _PruebaPort(ScriptedPort):
    """El proveedor guionizado de `test_engine`, con el reparto de un brief y
    las escenas de unas 500 palabras que pide el perfil `prueba`."""

    def __init__(self, brief: Brief) -> None:
        super().__init__()
        self.brief = brief
        personas = [e for e in brief.entities if e.kind == "person"]
        lugares = [e for e in brief.entities if e.kind == "place"]
        self.pov = brief.recipient.entity_id if brief.recipient else personas[0].id
        self.nombre = next(e.name for e in brief.entities if e.id == self.pov)
        self.lugar_id = lugares[0].id
        self.lugar = lugares[0].name
        self.inicio = date.fromisoformat(brief.start.stamp)
        #: Las instrucciones de resumen, para comprobar su tope (T53).
        self.resumenes: list[str] = []
        #: RF-260. Los elementos obligatorios, cada uno con su frase en la prosa.
        self.elementos = [e for e in elements(brief) if e.mandatory]

    def _frase(self, i: int) -> str:
        """La frase que integra el elemento i: unica en la escena y de mas de ocho palabras."""
        ordinal = ("primero", "segundo", "tercero", "cuarto")[i]
        return f"Por dentro volvió a pensar en su recuerdo {ordinal} y sonrió."

    def _stamp(self, capitulo: int) -> str:
        return (self.inicio + timedelta(days=2 + 7 * (capitulo - 1))).isoformat()

    def _prosa(self) -> str:
        """Unas 500 palabras en tercera persona y pasado, con el cierre unico.

        Seis parrafos sin fechas, sin primera persona fuera de dialogo y sin
        formas de presente, para que ni `check.format` ni `check.timeline` tengan
        nada que decir de la forma: lo que se prueba es el perfil.
        """
        return (
            f"{self.nombre} entró en {self.lugar} cuando todavía era temprano y el aire "
            "estaba quieto. Nadie más había llegado. Caminó despacio, contó los pasos y "
            "se detuvo junto a la pared. Pensó en lo que había prometido la tarde anterior "
            "y en lo poco que faltaba. Sacó la libreta del bolsillo, leyó la lista dos "
            "veces y la guardó sin decir nada. Afuera sonaba el viento contra las "
            "ventanas.\n\n"
            "Durante un rato no hizo otra cosa que escuchar. El suelo crujía bajo sus "
            "zapatos y una gota caía, lenta, desde algún rincón del techo. Recordó la voz "
            "de su abuela cuando le explicaba que las cosas importantes se hacían sin "
            "prisa, con las manos frías y la cabeza clara. Entonces le había parecido un "
            "consejo para otros. Ahora lo entendía mejor. Apoyó la espalda en la pared, "
            "cerró los ojos un momento y dejó que el silencio le ordenara las ideas, una "
            "detrás de otra, como piedras en un camino.\n\n"
            "Luego abrió otra vez la libreta. En la primera hoja estaban los nombres, "
            "escritos con letra apretada, y en la segunda una lista de tareas que había "
            "ido tachando durante la semana. Quedaban tres. La primera era sencilla y la "
            "resolvió enseguida. La segunda le costó más, porque exigía hablar con alguien "
            "a quien no había vuelto a ver desde el verano. La tercera la dejó para el "
            "final, como siempre hacía con lo que más temía.\n\n"
            "Se sentó en el banco del fondo y repasó en voz baja lo que diría. Probó "
            "varias maneras de empezar y ninguna le pareció buena del todo. Una sonaba "
            "demasiado seria; otra, demasiado ligera. Al final eligió la más corta, la que "
            "cabía en una sola frase, porque sabía que con los nervios se le olvidarían las "
            "largas. La repitió tres veces, despacio, hasta que dejó de sonarle extraña y "
            "empezó a parecerle suya.\n\n"
            "Oyó pasos en el pasillo y se quedó inmóvil. Los pasos se acercaron, dudaron "
            "junto a la puerta y siguieron de largo. Soltó el aire que había retenido sin "
            "darse cuenta. Miró sus manos, que temblaban un poco, y las frotó para "
            "calentarlas. Pensó que el miedo tenía algo de útil: le obligaba a prestar "
            "atención, a no dar nada por sabido, a mirar dos veces antes de moverse. Con "
            "esa idea se levantó, sacudió el polvo de las rodillas y buscó con la vista la "
            "salida más cercana.\n\n"
            f"{self.nombre} respiró hondo, levantó la vista y decidió que ese día no iba a "
            "esperar a nadie. Recogió sus cosas, cerró la puerta con cuidado y salió con "
            "paso firme hacia la luz de la mañana. En la calle, el frío le mordió la cara "
            "y el ruido de los primeros coches llenó el aire. Caminó sin mirar atrás, con "
            "la libreta apretada contra el pecho y la tercera tarea todavía pendiente, "
            "pero ya sin la duda que la había retenido toda la semana."
            + "".join(" " + self._frase(i) for i in range(len(self.elementos)))
        )

    def _outline(self) -> str:
        palabras = (PRUEBA.scene_words[0] + PRUEBA.scene_words[1]) // 2

        def esc(cap: int, act: int, func: str) -> dict[str, object]:
            return {
                "id": f"c{cap}e1",
                "chapter": cap,
                "ordinal": 1,
                "act": act,
                "function": func,
                "pov": self.pov,
                "value_change": "de la duda a la decision",
                "world_time": {"stamp": self._stamp(cap), "seq": 0},
                "target_words": palabras,
            }

        return json.dumps(
            {
                "arcs": [
                    {
                        "id": "comp",
                        "kind": "competitivo",
                        "subject": self.pov,
                        "start_scene": "c1e1",
                        "crisis_scene": "c1e1",
                        "resolution_scene": "c2e1",
                    },
                    {
                        "id": "int",
                        "kind": "interno",
                        "subject": self.pov,
                        "start_scene": "c1e1",
                        "crisis_scene": "c2e1",
                        "resolution_scene": "c3e1",
                    },
                ],
                "acts": [{"number": a, "tension": [3 * a]} for a in (1, 2, 3)],
                "scenes": [
                    esc(1, 1, "establecer"),
                    esc(2, 2, "culminar"),
                    esc(3, 3, "asimilar"),
                ],
                "setups": [
                    {
                        "id": "la-lista",
                        "planted_scene": "c1e1",
                        "payoff_scene": "c2e1",
                        "description": "La lista",
                    },
                    # RF-260: un setup por elemento obligatorio, que el brief ya planto.
                    *(
                        {
                            "id": e.setup_id,
                            "planted_scene": f"c{min(i + 1, 3)}e1",
                            "payoff_scene": f"c{min(i + 1, 3)}e1",
                            "description": e.text,
                        }
                        for i, e in enumerate(self.elementos)
                    ),
                ],
            }
        )

    def _answer(self, prefix: str, instruction: str) -> str:
        if "Planificas la estructura" in prefix:
            self.calls.append("arquitecto")
            return self._outline()
        if "Planificas escenas" in prefix:
            self.calls.append("planificador")
            cuerpo = {
                "place": self.lugar_id,
                "cast": [self.pov],
                "beats": ["entra", "duda", "sale"],
                "objective": "decidir",
                "obstacle": "nadie llega",
                "ends_with": "sale decidido",
                "setups_to_plant": [],
                "setups_to_pay": [],
            }
            return json.dumps({"scenes": {f"c{c}e1": cuerpo for c in (1, 2, 3)}})
        if "Escribes escenas" in prefix or "Reparas escenas" in prefix:
            self.calls.append("escritor" if "Escribes" in prefix else "reparador")
            self.written += 1
            return self._prosa() + _closing(self.written)
        if "Lees un capitulo" in prefix:
            self.calls.append("lector")
            ids = _QIDS.findall(instruction)
            respuesta = f"{self.nombre}, en {self.lugar}"
            return json.dumps({"answers": dict.fromkeys(ids, respuesta)})
        if "Resumes partes" in prefix:
            self.resumenes.append(instruction)
            return super()._answer(prefix, instruction)
        if "Archivero" in prefix:
            self.calls.append("archivero")
            respuesta = json.loads(super()._answer(prefix, instruction))
            for evento in respuesta["events"]:
                evento["payload"]["entity_id"] = self.pov
                evento["quote"] = f"{self.nombre} entró en {self.lugar} cuando todavía era temprano"
            # RF-261: cada elemento que el capitulo integra, con su cita literal.
            respuesta["elements"] = [
                {"element_id": e.id, "scene": "", "quote": self._frase(i)}
                for i, e in enumerate(self.elementos)
                if f"- {e.id} (" in instruction and self._frase(i) in instruction
            ]
            return json.dumps(respuesta)
        return super()._answer(prefix, instruction)


def _composer(brief: Brief, tmp_path: Path) -> tuple[Composer, _PruebaPort, Trace, Path]:
    path = tmp_path / "n.sqlite"
    create_novel(path, brief, global_terms=())
    traza = Trace(tmp_path / "n.trace.jsonl")
    puerto = _PruebaPort(brief)
    factores = ModelFactors()
    factores.set("haiku", 1.35)
    c = Composer(
        port=puerto,
        path=path,
        brief=brief,
        embedder=_Embedder(),
        counter=TokenCounter(factores),
        model_id="haiku",
        trace=traza,
        admission=Admission(trace=traza),
    )
    return c, puerto, traza, path


def test_los_cinco_briefs_de_evaluacion_son_del_perfil_prueba() -> None:
    for name in NOMBRES:
        brief = _load(name)
        assert brief.length_profile == "prueba", name
        low, high = PRUEBA.work_words or (0, 0)
        assert low <= brief.target_words <= high, name
        assert chapters_for(brief) == 3


@pytest.mark.parametrize("name", NOMBRES)
def test_la_tirada_de_prueba_cierra_con_tres_capitulos_de_una_escena(
    name: str, tmp_path: Path
) -> None:
    brief = _load(name)
    c, puerto, traza, path = _composer(brief, tmp_path)
    informe = run(
        path,
        brief,
        c.engine(),
        novel_id="p",
        chapters=chapters_for(brief),
        specs_for=specs_provider(c),
        trace=traza,
    )

    assert informe.closed, informe.reason
    assert [ch.number for ch in informe.chapters] == [1, 2, 3]
    assert all(len(ch.scenes) == 1 for ch in informe.chapters)
    assert all(ch.frozen for ch in informe.chapters)
    low, high = PRUEBA.work_words or (0, 0)
    assert low <= informe.words <= high, informe.words
    for ch in informe.chapters:
        assert PRUEBA.scene_words[0] <= ch.words <= PRUEBA.scene_words[1]
    # Las puertas de escena y de capitulo miden contra el rango del perfil: con
    # el de novela, cada escena y cada capitulo darian su S2 de longitud.
    formato = [
        d
        for ch in informe.chapters
        for s in ch.scenes
        for d in s.defects
        if d.kind == "check.format"
    ]
    assert formato == []
    longitud = [
        d
        for r in traza.records("chapter.gate")
        for d in r.fields["defects"]  # type: ignore[union-attr]
        if "palabras y el rango" in str(d)
    ]
    assert longitud == []
    # La escaleta que paso es la del perfil, y lo dice su verificacion.
    [paso] = [r for r in traza.records("outline.check") if r.fields["passed"]]
    escaleta = Outline.model_validate_json(str(paso.fields["outline"]))
    assert check(escaleta, word_range=brief.word_range(), profile=brief.profile()) == []
    assert "arquitecto" in puerto.calls and "juez" in puerto.calls

    # T47 con escenas de unas 500 palabras. El Jurado puntua las nueve dimensiones, cada
    # puntuacion con su justificacion en la traza (RF-257, RF-259).
    # Sin destinatario ni elementos obligatorios, `personalization` no aplica, y
    # sin tono pedido tampoco `tone` (D-114): no hay encargo contra el que juzgar.
    nueve = {d.value for d in DEFAULT_RUBRICS.dimensions}
    esperadas = set(nueve)
    if not brief.recipient_name() and not puerto.elementos:
        esperadas.discard("personalization")
    if not brief.tone:
        esperadas.discard("tone")
    for r in traza.records("jury"):
        assert set(r.fields["levels"]) == esperadas  # type: ignore[arg-type]
        assert all(s["justification"] for s in r.fields["scores"])  # type: ignore[index, union-attr, call-overload]
    # Cada elemento obligatorio tiene uso anclado en SQLite, y por eso cierra (RF-261).
    with connection.reader(path) as con:
        usados = {row["element_id"] for row in con.execute("SELECT element_id FROM element_use")}
    assert usados == {e.id for e in puerto.elementos}

    # Tres actos de un capitulo: la puerta de acto corre tras cada capitulo.
    assert [r.fields["act"] for r in traza.records("act.gate")] == [1, 2, 3]
    # Lo de cada cinco capitulos corre una vez, al cierre.
    assert [r.fields["chapter"] for r in traza.records("golden")] == [3]
    obra = [r for r in traza.records("summary") if r.fields["level"] == "work"]
    assert [r.fields["chapter"] for r in obra] == [3]
    # Los resumenes de escena y de capitulo, como mucho la mitad de lo que resumen.
    escena = [i for i in puerto.resumenes if i.startswith("Resume esta escena")]
    capitulo = [i for i in puerto.resumenes if i.startswith("Resume este capitulo")]
    assert len(escena) == len(capitulo) == 3
    for ch, (ie, ic) in zip(informe.chapters, zip(escena, capitulo, strict=True), strict=True):
        assert _tope(ie) <= ch.words // 2
        assert _tope(ic) <= ch.words // 2


def _tope(instruccion: str) -> int:
    """El maximo de palabras que pide una instruccion de resumen."""
    m = re.match(r"Resume [^\n]*? en (?:entre \d+ y (\d+)|exactamente (\d+)) palabras", instruccion)
    assert m, instruccion[:120]
    return int(m.group(1) or m.group(2))


def test_un_brief_prueba_con_extension_de_novela_se_rechaza_con_el_motivo() -> None:
    crudo = json.loads((BRIEFS / "01-semilla.json").read_text(encoding="utf-8"))
    with pytest.raises(
        ValidationError,
        match="el perfil de extension «prueba» admite una obra de 1200 a 1800 palabras "
        "y el brief pide 9000",
    ):
        Brief.model_validate(crudo | {"target_words": 9000})


def test_un_perfil_desconocido_se_rechaza() -> None:
    crudo = json.loads((BRIEFS / "01-semilla.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError, match="length_profile"):
        Brief.model_validate(crudo | {"length_profile": "cuento"})


def test_la_tolerancia_no_desborda_el_rango_de_obra_del_perfil() -> None:
    crudo = json.loads((BRIEFS / "01-semilla.json").read_text(encoding="utf-8"))
    brief = Brief.model_validate(crudo | {"target_words": 1800, "word_tolerance": 0.35})
    assert brief.word_range() == (1200, 1800)


def test_una_cita_minima_del_jurado_cabe_en_una_escena_de_prueba() -> None:
    """Las citas del Jurado (8 a 25 palabras) no se escalan: una de 8 ancla en 400."""
    from verification.checks.evidence import MIN_QUOTE_WORDS, anchor

    port = _PruebaPort(_load("01-semilla.json"))
    parrafo = port._prosa()
    palabras = parrafo.split()
    assert PRUEBA.scene_words[0] <= len(palabras) <= PRUEBA.scene_words[1]
    cita = " ".join(palabras[20 : 20 + MIN_QUOTE_WORDS])
    evidencia = anchor(parrafo, cita)
    assert evidencia is not None and parrafo[evidencia.offset :].startswith(palabras[20])


def test_con_perfil_novela_los_resumenes_y_lo_periodico_no_cambian() -> None:
    from canon.summaries.prompts import Level, instruction
    from commons.types.length import NOVELA

    assert NOVELA.summary_cap(130) is None
    assert instruction(Level.SCENE, ["x"]) == instruction(Level.SCENE, ["x"], max_words=None)
    assert "entre 60 y 100 palabras" in instruction(Level.SCENE, ["x"])
    assert "entre 60 y 65 palabras" in instruction(Level.SCENE, ["x"], max_words=65)
    assert [c for c in range(1, 11) if NOVELA.periodic_due(c, last_chapter=10, every=5)] == [5, 10]
    assert [c for c in range(1, 4) if PRUEBA.periodic_due(c, last_chapter=3, every=5)] == [3]


def test_sin_destinatario_el_jurado_no_juzga_la_personalizacion(tmp_path: Path) -> None:
    """D-114. La tirada real eval-01 (brief sin destinatario) suspendia siempre por
    `personalization` 1 con todo lo demas en 3 o 4: no habia encargo que juzgar."""
    brief = _load(NOMBRES[0])
    assert not brief.recipient_name()
    c, _, traza, path = _composer(brief, tmp_path)
    run(
        path,
        brief,
        c.engine(),
        novel_id="p",
        chapters=chapters_for(brief),
        specs_for=specs_provider(c),
        trace=traza,
    )
    jurados = traza.records("jury")
    assert jurados
    for r in jurados:
        assert "personalization" not in r.fields["levels"]  # type: ignore[operator]
