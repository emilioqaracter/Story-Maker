"""El motor real con un proveedor guionizado, de punta a punta.

RF-13, RF-14, RF-16, RF-86, RF-98, RF-99, RI-24. Metodo VER-05 con doble del
proveedor (RNF-17): lo que se comprueba es la **composicion** --recetas,
auditoria, admision, dispatch, traza, parseo por funcionalidad-- sin gastar una
llamada de modelo. Las llamadas reales son evals.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

import pytest

from canon.brief import Brief, BriefEntity, create_novel
from canon.db import connection
from commons.provider.port import (
    Completion,
    Embedding,
    ProviderError,
    ToolCall,
    ToolServer,
    Usage,
)
from commons.tokens.counter import TokenCounter
from commons.tokens.factors import ModelFactors
from commons.tracing.trace import Trace
from commons.types.primitives import Defect
from context.packing.recipes import BUDGETS
from orchestration.admission import Admission
from orchestration.engine import Composer, specs_provider
from orchestration.loop import run
from verification.checks.deterministic import check_lexicon

PROSA = (
    "Marcos Vela entró el último y nadie levantó la vista. El vestuario olía a "
    "linimento y a lluvia vieja. —¿Juego? —preguntó. Aurelio Peña no contestó: "
    "estaba doblando la lista sin mirarlo, y la lista era lo único que importaba. "
    "Marcos se sentó; el banco estaba frío y la camiseta era la del nueve. "
)

_CLOSING = re.compile(r"Cierre numero \d+ de esta escena y de ninguna otra del libro\.")


def _closing(n: int) -> str:
    return f"\n\nCierre numero {n} de esta escena y de ninguna otra del libro."


_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_QIDS = re.compile(r"^\s+(c\d+e\d+-\w+):", re.M)


def _outline_json() -> str:
    def esc(cap: int, pos: int, act: int, func: str, dia: int) -> dict[str, object]:
        return {
            "id": f"c{cap}e{pos}",
            "chapter": cap,
            "ordinal": pos,
            "act": act,
            "function": func,
            "pov": "marcos",
            "value_change": "de la duda a la decision",
            "world_time": {"stamp": f"2026-08-{dia:02d}", "seq": 0},
            "target_words": 900,
        }

    return json.dumps(
        {
            "arcs": [
                {
                    "id": "comp",
                    "kind": "competitivo",
                    "subject": "marcos",
                    "start_scene": "c1e1",
                    "crisis_scene": "c1e2",
                    "resolution_scene": "c2e1",
                    "left_open": False,
                },
                {
                    "id": "int",
                    "kind": "interno",
                    "subject": "marcos",
                    "start_scene": "c1e1",
                    "crisis_scene": "c1e2",
                    "resolution_scene": "c2e2",
                    "left_open": False,
                },
            ],
            "acts": [{"number": 1, "tension": [3]}, {"number": 2, "tension": [8]}],
            "scenes": [
                esc(1, 1, 1, "establecer", 10),
                esc(1, 2, 1, "complicar", 11),
                esc(2, 1, 2, "culminar", 20),
                esc(2, 2, 2, "asimilar", 21),
            ],
            "setups": [
                {
                    "id": "la-lista",
                    "planted_scene": "c1e1",
                    "payoff_scene": "c2e1",
                    "description": "La lista",
                }
            ],
        }
    )


def _plan_json() -> str:
    cuerpo = {
        "place": "vestuario",
        "cast": ["marcos", "tecnico"],
        "beats": ["entra", "pregunta", "sale"],
        "objective": "saber si juega",
        "obstacle": "nadie habla",
        "ends_with": "sale sin saberlo",
        "setups_to_plant": [],
        "setups_to_pay": [],
    }
    return json.dumps({"scenes": {f"c{c}e{e}": cuerpo for c in (1, 2) for e in (1, 2)}})


class ScriptedPort:
    """Responde segun el agente que reconoce en el prefijo cacheable."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.written = 0

    def _answer(self, prefix: str, instruction: str) -> str:
        if "Planificas la estructura" in prefix:
            self.calls.append("arquitecto")
            return _outline_json()
        if "Planificas escenas" in prefix:
            self.calls.append("planificador")
            return _plan_json()
        if "Escribes escenas" in prefix:
            self.calls.append("escritor")
            self.written += 1
            return PROSA * 12 + _closing(self.written)
        if "Continuista" in prefix:
            self.calls.append("continuista")
            return json.dumps({"defects": []})
        if "Lees un capitulo" in prefix:
            self.calls.append("lector")
            ids = _QIDS.findall(instruction)
            return json.dumps(
                {"answers": dict.fromkeys(ids, "Marcos Vela, Aurelio Peña, en el vestuario")}
            )
        if "Archivero" in prefix:
            self.calls.append("archivero")
            fecha = _DATE.search(instruction)
            stamp = fecha.group(1) if fecha else "2026-08-10"
            return json.dumps(
                {
                    "events": [
                        {
                            "world_time": {"stamp": stamp, "seq": 0},
                            "payload": {
                                "type": "attribute.set",
                                "entity_id": "marcos",
                                "name": "estado",
                                "value": f"tras-{stamp}",
                            },
                            "quote": "Marcos Vela entró el último y nadie levantó la vista",
                        }
                    ]
                }
            )
        if "Resumes partes" in prefix:
            self.calls.append("resumen")
            return "Marcos Vela entró en el vestuario y no supo si jugaba."
        if "instancia del Jurado" in prefix:
            self.calls.append("juez")
            escenas = re.findall(r"^### (c\d+e\d+)", instruction, re.M)
            cierre = _CLOSING.search(instruction)
            return json.dumps(
                {
                    "scores": [
                        {
                            "dimension": d,
                            "level": 4,
                            "scene": escenas[0],
                            "quote": cierre.group(0) if cierre else "sin cierre",
                        }
                        for d in ("voice", "style_guide", "pacing", "subtext", "theme")
                    ]
                }
            )
        if "Estilista" in prefix:
            self.calls.append("estilista")
            partes = re.split(r"^### (c\d+e\d+)[^\n]*\n\n", instruction, flags=re.M)
            escenas = [
                {"scene": partes[i], "text": partes[i + 1].split("\n\nDevuelve SOLO")[0].strip()}
                for i in range(1, len(partes) - 1, 2)
            ]
            return json.dumps({"scenes": escenas})
        if "Supervisor de una novela" in prefix:
            self.calls.append("supervisor")
            return json.dumps({"healthy": True, "signal": "", "reason": "sin tendencias"})
        if "Replanificas" in prefix:
            raise AssertionError("no deberia replanificarse en la tirada guionizada")
        if "Reparas escenas" in prefix:
            self.calls.append("reparador")
            self.written += 1
            return PROSA * 12 + _closing(self.written)
        raise AssertionError(f"agente desconocido en el prefijo: {prefix[:60]!r}")

    def _completion(self, text: str, prefix: str, packet: str, instruction: str) -> Completion:
        real = len(prefix + packet + instruction) // 3
        return Completion(
            text=text,
            usage=Usage(input_tokens=real, output_tokens=len(text) // 4),
            stop_reason="end_turn",
            harness_tokens=100,
        )

    def complete_once(
        self,
        *,
        cacheable_prefix: str,
        packet: str,
        instruction: str,
        output_schema: str,
        max_output_tokens: int,
        json_schema: str | None = None,
    ) -> Completion:
        return self._completion(
            self._answer(cacheable_prefix, instruction), cacheable_prefix, packet, instruction
        )

    def complete_with_tools(
        self,
        *,
        cacheable_prefix: str,
        packet: str,
        instruction: str,
        output_schema: str,
        max_output_tokens: int,
        tools: Sequence[str],
        server: ToolServer,
        json_schema: str | None = None,
    ) -> Completion:
        # Una consulta legitima antes de concluir, para ejercitar el servidor.
        server.serve(
            ToolCall(
                name=tools[0],
                arguments='{"kind": "entity", "entity_ids": ["marcos"]}',
            )
        )
        return self._completion(
            self._answer(cacheable_prefix, instruction), cacheable_prefix, packet, instruction
        )

    def embed(self, texts: Sequence[str], *, is_query: bool) -> Sequence[Embedding]:
        return [Embedding(values=(0.2, 0.1, 0.7), model_id="doble", dimension=3) for _ in texts]

    def count_tokens(self, text: str, model_id: str) -> int:
        return len(text) // 3


class _Embedder:
    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        return [Embedding(values=(0.2, 0.1, 0.7), model_id="doble", dimension=3) for _ in texts]


def _brief() -> Brief:
    return Brief(
        title="Prueba de motor",
        start={"stamp": "2026-08-01"},  # type: ignore[arg-type]
        entities=(
            BriefEntity(
                id="marcos",
                kind="person",
                name="Marcos Vela",
                aliases=("el Chino",),
                attributes=(("estado", "sano"), ("dorsal", "9")),
            ),
            BriefEntity(id="tecnico", kind="person", name="Aurelio Peña"),
            BriefEntity(id="vestuario", kind="place", name="el vestuario"),
        ),
        style_guide="Tercera persona, pasado. Frases cortas. " * 20,
        target_words=3_600,
        word_tolerance=0.5,
    )


@pytest.fixture
def composer(tmp_path: Path) -> tuple[Composer, ScriptedPort, Trace, Path]:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    traza = Trace(tmp_path / "n.trace.jsonl")
    puerto = ScriptedPort()
    factores = ModelFactors()
    factores.set("haiku", 1.35)
    c = Composer(
        port=puerto,
        path=path,
        brief=_brief(),
        embedder=_Embedder(),
        counter=TokenCounter(factores),
        model_id="haiku",
        trace=traza,
        admission=Admission(trace=traza),
    )
    return c, puerto, traza, path


def test_una_tirada_entera_pasa_por_el_motor_real(
    composer: tuple[Composer, ScriptedPort, Trace, Path],
) -> None:
    """La composicion completa: recetas, auditoria, admision, dispatch, parseo."""
    c, puerto, traza, path = composer
    informe = run(
        path,
        _brief(),
        c.engine(),
        novel_id="p",
        chapters=2,
        specs_for=specs_provider(c),
        trace=traza,
    )

    assert informe.closed, informe.reason
    assert {
        "arquitecto",
        "planificador",
        "escritor",
        "continuista",
        "lector",
        "archivero",
        "resumen",
    } <= set(puerto.calls)
    assert all(ch.events_applied >= 1 for ch in informe.chapters)


class _FlakyPort:
    """El proveedor falla en las llamadas elegidas y responde en las demas."""

    def __init__(self, inner: ScriptedPort, fail_on: set[int]) -> None:
        self.inner = inner
        self.fail_on = fail_on
        self.n = 0

    def complete_once(self, **kw: object) -> object:
        self.n += 1
        if self.n in self.fail_on:
            raise ProviderError("el CLI salio con codigo 1")
        return self.inner.complete_once(**kw)  # type: ignore[arg-type]

    def __getattr__(self, name: str) -> object:
        return getattr(self.inner, name)


def test_un_fallo_del_proveedor_consume_un_reintento_y_la_tirada_sigue(
    composer: tuple[Composer, ScriptedPort, Trace, Path],
) -> None:
    """architecture.md §4.8: el fallo de red es intermitente y se reintenta."""
    c, puerto, traza, path = composer
    c.port = _FlakyPort(puerto, fail_on={1, 5})  # type: ignore[assignment]
    informe = run(
        path,
        _brief(),
        c.engine(),
        novel_id="p",
        chapters=2,
        specs_for=specs_provider(c),
        trace=traza,
    )
    assert informe.closed, informe.reason
    reintentos = [r for r in traza.records("retry") if "proveedor" in str(r.fields.get("reason"))]
    assert len(reintentos) == 2


def test_un_proveedor_caido_agota_el_presupuesto_y_sube(
    composer: tuple[Composer, ScriptedPort, Trace, Path],
) -> None:
    c, puerto, traza, path = composer
    c.port = _FlakyPort(puerto, fail_on=set(range(1, 100)))  # type: ignore[assignment]
    with pytest.raises(ProviderError):
        run(
            path,
            _brief(),
            c.engine(),
            novel_id="p",
            chapters=2,
            specs_for=specs_provider(c),
            trace=traza,
        )


def test_ningun_paquete_supera_el_presupuesto_de_su_agente(
    composer: tuple[Composer, ScriptedPort, Trace, Path],
) -> None:
    """RF-86, RF-16. Lo estimado de cada llamada cabe en la fila de §4.2."""
    c, _puerto, traza, path = composer
    run(
        path,
        _brief(),
        c.engine(),
        novel_id="p",
        chapters=2,
        specs_for=specs_provider(c),
        trace=traza,
    )

    llamadas = traza.records("call")
    assert llamadas
    for r in llamadas:
        agente = str(r.fields["agent"])
        estimado = r.fields["estimated_input"]
        assert isinstance(estimado, int)
        assert estimado <= BUDGETS[agente].input_tokens, f"{agente}: {estimado}"
        assert r.fields["ok"] is True


def test_el_paquete_del_escritor_lleva_ancla_y_especificacion_y_se_traza(
    composer: tuple[Composer, ScriptedPort, Trace, Path],
) -> None:
    """RF-32, RF-34, RF-39. Once bloques como maximo, ancla primero, especificacion al final."""
    c, _puerto, traza, path = composer
    run(
        path,
        _brief(),
        c.engine(),
        novel_id="p",
        chapters=2,
        specs_for=specs_provider(c),
        trace=traza,
    )

    paquetes = traza.records("packet")
    assert len(paquetes) == 4
    for p in paquetes:
        bloques = [str(b).split(":")[0] for b in p.fields["blocks"]]  # type: ignore[union-attr]
        assert bloques[0] == "ancla" and bloques[-1] == "especificacion"
        assert p.fields["tokens"] <= BUDGETS["escritor"].input_tokens  # type: ignore[operator]
    # A partir del capitulo 2 hay prosa congelada que recuperar.
    assert any(p.fields["quotas"] for p in paquetes[2:])
    # El Supervisor lee de aqui la senal de resumenes sustituidos (RF-145).
    assert [p.fields["chapter"] for p in paquetes] == [1, 1, 2, 2]
    assert all(isinstance(p.fields["summaries"], int) for p in paquetes)
    # §4.4: un indice vacio no es degradacion. El capitulo 1 no tiene prosa que
    # recuperar y la pierna semantica vuelve vacia sin haber fallado.
    assert not any(p.fields["degraded"] for p in paquetes), [p.fields["degraded"] for p in paquetes]


def test_la_admision_reserva_el_cupo_de_tiron_de_los_agentes_que_lo_tienen(
    composer: tuple[Composer, ScriptedPort, Trace, Path],
) -> None:
    """RF-97. El Archivero reserva sus 15.000 aunque solo consulte una vez."""
    c, _puerto, traza, path = composer
    run(
        path,
        _brief(),
        c.engine(),
        novel_id="p",
        chapters=2,
        specs_for=specs_provider(c),
        trace=traza,
    )

    admitidos = [r for r in traza.records("admission") if r.fields["state"] == "admitted"]
    archivero = [r for r in admitidos if r.fields["agent"] == "archivero"]
    assert archivero
    assert all(int(str(r.fields["reserved"])) >= BUDGETS["archivero"].tool_quota for r in archivero)


def test_tras_congelar_no_queda_borrador_y_el_canon_evoluciono(
    composer: tuple[Composer, ScriptedPort, Trace, Path],
) -> None:
    c, _puerto, traza, path = composer
    run(
        path,
        _brief(),
        c.engine(),
        novel_id="p",
        chapters=2,
        specs_for=specs_provider(c),
        trace=traza,
    )
    with connection.reader(path) as con:
        assert con.execute("SELECT count(*) AS n FROM wm_draft").fetchone()["n"] == 0
        valores = [
            r["value"]
            for r in con.execute(
                "SELECT value FROM attribute WHERE name='estado' ORDER BY valid_from"
            )
        ]
    assert valores[-1].startswith("tras-2026-08-2")


# ------------------------------------------------ paquetes de la version 2


def test_la_version_del_prompt_no_cambia_con_el_lexico_y_si_con_el_agente() -> None:
    """RI-34: hash de la instruccion de sistema y de la plantilla, no del lexico."""
    from context.packing.recipes import BUDGETS
    from orchestration.engine import PROMPT_MODULES, prompt_version

    llamados = {a for a in BUDGETS if a != "documentalista"}
    assert llamados <= set(PROMPT_MODULES), llamados - set(PROMPT_MODULES)
    assert prompt_version("escritor") == prompt_version("escritor")
    assert len({prompt_version(a) for a in PROMPT_MODULES}) == len(PROMPT_MODULES)


def test_el_supervisor_compacta_por_arco_lo_que_ya_tiene_resumen_de_arco() -> None:
    """RF-118, §4.9 Supervisor."""
    from orchestration.engine import supervisor_summaries
    from orchestration.test_loop import _outline

    esc = _outline()
    arco = esc.arcs[0].id
    caps = {1: "uno", 2: "dos"}
    sin = supervisor_summaries(esc, caps, {})
    con = supervisor_summaries(esc, caps, {arco: "resumen del arco"})
    assert sin == ["Capitulo 1: uno", "Capitulo 2: dos"]
    assert any(s.startswith(f"Arco {arco}") for s in con)
    assert len(con) < len(sin) + 1


def test_la_instruccion_del_estilista_lleva_muestras_y_fichas() -> None:
    """RF-139, §4.9 Estilista."""
    from orchestration.test_loop import _outline, _specs
    from verification.style.prompts import instruction

    specs = list(_specs(_outline(), 1))
    texto = instruction(
        specs,
        ["x"] * len(specs),
        proscribed=[],
        repetitions=[],
        reference="",
        current="",
        samples=["MUESTRA UNO"],
        voice_cards="FICHA DE MARCOS",
    )
    assert "MUESTRA UNO" in texto and "FICHA DE MARCOS" in texto


class _SloppyJudgePort(ScriptedPort):
    """El juez recorta sus citas la primera vez; corregido, cita bien (D-71)."""

    def _answer(self, prefix: str, instruction: str) -> str:
        raw = super()._answer(prefix, instruction)
        if "instancia del Jurado" in prefix and "NO SON LITERALES" not in instruction:
            return re.sub(r'"quote": "[^"]*"', '"quote": "Cierre... del libro"', raw)
        return raw


def test_una_cita_del_jurado_que_no_ancla_vuelve_al_juez_con_el_motivo(tmp_path: Path) -> None:
    """D-71: la cita recortada no se descarta sin mas; el juez la corrige."""
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    traza = Trace(tmp_path / "n.trace.jsonl")
    factores = ModelFactors()
    factores.set("haiku", 1.35)
    c = Composer(
        port=_SloppyJudgePort(),
        path=path,
        brief=_brief(),
        embedder=_Embedder(),
        counter=TokenCounter(factores),
        model_id="haiku",
        trace=traza,
        admission=Admission(trace=traza),
    )
    informe = run(
        path,
        _brief(),
        c.engine(),
        novel_id="p",
        chapters=2,
        specs_for=specs_provider(c),
        trace=traza,
    )
    assert informe.closed, informe.reason
    reintentos = [r for r in traza.records("retry") if "sin anclar" in str(r.fields.get("reason"))]
    assert reintentos, "la cita recortada volvio al juez"
    assert all(ch.jury is not None and ch.jury.passed for ch in informe.chapters)


# ----------------------------------------------------- candidatos a nombre


def _composer_nala(tmp_path: Path) -> Composer:
    """Un canon con nombres cortos, que son los que mas erratas admiten."""
    brief = Brief(
        title="Nombres",
        start={"stamp": "2026-08-01"},  # type: ignore[arg-type]
        entities=(
            BriefEntity(id="nala", kind="person", name="Nala"),
            BriefEntity(id="carla", kind="person", name="Carla"),
            BriefEntity(id="marcos", kind="person", name="Marcos Vela", aliases=("el Chino",)),
            BriefEntity(id="tecnico", kind="person", name="Aurelio Peña"),
        ),
        style_guide="Tercera persona, pasado. " * 20,
        target_words=3_600,
    )
    path = tmp_path / "nala.sqlite"
    create_novel(path, brief)
    traza = Trace(tmp_path / "nala.trace.jsonl")
    factores = ModelFactors()
    factores.set("haiku", 1.35)
    return Composer(
        port=ScriptedPort(),
        path=path,
        brief=brief,
        embedder=_Embedder(),
        counter=TokenCounter(factores),
        model_id="haiku",
        trace=traza,
        admission=Admission(trace=traza),
    )


def _lexico(c: Composer, texto: str) -> list[Defect]:
    """Lo mismo que `verify_scene` pasa a `check.lexicon`, sin montar una escena."""
    return check_lexicon(texto, known_names=c._known_names(), candidates=c._name_candidates(texto))


@pytest.mark.parametrize(
    ("texto", "errata"),
    [
        pytest.param("Marcos llamo a Nalah y se fue.", "Nalah", id="una-sola-vez"),
        pytest.param("Nalah ladro. Marcos rio.", "Nalah", id="principio-de-frase"),
        pytest.param("Marcos llamo a Nála, y se fue.", "Nála", id="tilde-cambiada"),
        pytest.param("—Nla, ven —dijo Marcos.", "Nla", id="tras-raya"),
        pytest.param("Marcos miro a Anla sin decir nada.", "Anla", id="trasposicion"),
        pytest.param("Hablo con Pena en el pasillo.", "Pena", id="tilde-quitada"),
    ],
)
def test_una_errata_de_un_nombre_del_canon_salta(tmp_path: Path, texto: str, errata: str) -> None:
    """ENT-37. Con Nala en el canon, un "Nalah" suelto, al principio de frase o
    con la tilde cambiada es un S1 que cita la errata. Antes no llegaba ni a
    candidato: tenia que repetirse y no podia ir tras un punto."""
    c = _composer_nala(tmp_path)
    assert errata in c._name_candidates(texto)
    lexico = _lexico(c, texto)
    assert [d.evidence.quote for d in lexico] == [errata]
    assert "variante mal escrita" in lexico[0].rule


@pytest.mark.parametrize(
    "texto",
    [
        pytest.param("Nala ladro. Marcos Vela rio con Nala.", id="nombres-exactos"),
        pytest.param("Aurelio Peña miro al Chino. El Chino no contesto.", id="alias-y-tilde"),
        pytest.param("Nada. Nadie dijo nada. Luego se fue.", id="comunes-cerca-de-nala"),
        pytest.param("Cara a cara, nadie aparto la cara.", id="comun-en-minuscula"),
        pytest.param("Pena le daba verlo asi, y la pena no se iba.", id="pena-comun"),
        pytest.param("Del banco salio Marcos.", id="articulo-del-alias"),
    ],
)
def test_los_nombres_exactos_y_las_palabras_comunes_no_saltan(tmp_path: Path, texto: str) -> None:
    """Sin falsos positivos: un nombre bien escrito no es candidato a errata, y
    una palabra comun al principio de frase tampoco, aunque se quede a una
    letra de un nombre del canon ("Nada" y "Nala", "Cara" y "Carla")."""
    c = _composer_nala(tmp_path)
    assert _lexico(c, texto) == []


def test_un_nombre_nuevo_repetido_sigue_siendo_candidato(tmp_path: Path) -> None:
    """La regla de antes no cambia: lo que se repite en mitad de frase y no esta
    en el canon es un personaje que sobra."""
    c = _composer_nala(tmp_path)
    texto = "Marcos hablo con Ramirez. Luego, Ramirez se fue."
    assert c._name_candidates(texto) == ["Ramirez"]
    assert c._name_candidates("Marcos hablo con Ramirez y se fue.") == []
