"""El espejo de Langfuse con un cliente doble. RF-233 a RF-235, RI-60, RI-61, RNF-53, RNF-54.

Metodo VER-05 y, para la identidad de las generaciones, VER-06. Ninguna prueba
habla con Langfuse: el cliente es un doble y las claves son de mentira.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import JsonValue

from commons.tracing import langfuse_export as lf
from commons.tracing.langfuse_export import (
    LangfuseObject,
    LangfuseObservation,
    LangfuseTrace,
    attach_live_export,
    export_novel,
    install_live_export,
    to_langfuse,
    uninstall_live_export,
    work_cost,
)
from commons.tracing.trace import Trace, TraceRecord

#: Claves de mentira: el valor no importa, solo que esten las tres.
FAKE_ENV = {
    "LANGFUSE_PUBLIC_KEY": "TU_CLAVE_PUBLICA_AQUI",
    "LANGFUSE_SECRET_KEY": "TU_CLAVE_SECRETA_AQUI",  # nosec B105: de mentira
    "LANGFUSE_BASE_URL": "http://localhost:9",
}


class FakeClient:
    """Guarda lo que recibe y lo aplica como Langfuse: el mismo `id` actualiza."""

    def __init__(self) -> None:
        self.sent: list[LangfuseObject] = []
        self.store: dict[tuple[str, str], LangfuseObject] = {}

    def send(self, objects: Sequence[LangfuseObject]) -> None:
        for o in objects:
            self.sent.append(o)
            self.store[(type(o).__name__, o.id)] = o


class BrokenClient:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, objects: Sequence[LangfuseObject]) -> None:
        self.calls += 1
        raise ConnectionError(f"sin red; clave {FAKE_ENV['LANGFUSE_SECRET_KEY']}")


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    uninstall_live_export()
    yield
    uninstall_live_export()


def _rec(
    seq: int, kind: str, at: str = "2026-09-23T10:00:00+00:00", **fields: JsonValue
) -> TraceRecord:
    return TraceRecord(seq=seq, at=at, kind=kind, fields=fields)


def _call(seq: int, **extra: JsonValue) -> TraceRecord:
    campos: dict[str, JsonValue] = {
        "agent": "escritor",
        "real_input": 5_150,
        "input_tokens": 100,
        "cache_creation_tokens": 50,
        "cache_read_tokens": 5_000,
        "output_tokens": 800,
        "model": "claude-haiku-4-5",
        "cost_usd": 0.0123,
        "duration_ms": 2_500,
        "ok": True,
        "chapter": 1,
    }
    campos.update(extra)
    return _rec(seq, "call", at="2026-09-23T10:00:10+00:00", **campos)


def _traces(objs: Sequence[LangfuseObject]) -> list[LangfuseTrace]:
    return [o for o in objs if isinstance(o, LangfuseTrace)]


def _observations(objs: Sequence[LangfuseObject]) -> list[LangfuseObservation]:
    return [o for o in objs if isinstance(o, LangfuseObservation)]


def _generations(objs: Sequence[LangfuseObject]) -> list[LangfuseObservation]:
    return [o for o in _observations(objs) if o.type == "generation"]


def _spans(
    objs: Sequence[LangfuseObject], chapter: int, scene: int | None = None
) -> list[LangfuseObservation]:
    """Los spans de un capitulo o una escena: el numero va en los metadatos (D-106)."""
    nombre = "chapter" if scene is None else "scene"
    esperado: dict[str, JsonValue] = {"chapter": chapter}
    if scene is not None:
        esperado["scene"] = scene
    return [
        o
        for o in _observations(objs)
        if o.type == "span" and o.name == nombre and dict(o.metadata) == esperado
    ]


# ------------------------------------------------------------ correspondencia


def test_una_llamada_es_una_generation_con_modelo_uso_coste_e_inicio_y_fin() -> None:
    """RF-235: los cuatro campos de uso, el coste del CLI y la latencia de `dispatch`."""
    objs = to_langfuse([_call(0)], source="n.trace.jsonl", session_id="n")
    (gen,) = _generations(objs)
    assert gen.type == "generation"
    assert gen.name == "writer.escritor"
    assert gen.model == "claude-haiku-4-5"
    assert gen.usage_details == {
        "input": 100,
        "cache_creation_input_tokens": 50,
        "cache_read_input_tokens": 5_000,
        "output": 800,
    }
    assert gen.cost_details == {"total": 0.0123}
    assert gen.end_time == "2026-09-23T10:00:10.000+00:00"
    assert gen.start_time == "2026-09-23T10:00:07.500+00:00"


def test_sin_coste_declarado_el_coste_es_nulo_y_no_inventado() -> None:
    (gen,) = _generations(to_langfuse([_call(0, cost_usd=None)], source="n", session_id="n"))
    assert gen.cost_details is None


def test_una_traza_anterior_al_desglose_da_la_suma_como_entrada() -> None:
    """Las tiradas ya hechas, como T16, solo traen `real_input`: se exportan igual."""
    viejo = _rec(0, "call", agent="juez", real_input=4_000, output_tokens=300)
    (gen,) = _generations(to_langfuse([viejo], source="n", session_id="n"))
    assert gen.usage_details == {"input": 4_000, "output": 300}
    assert gen.start_time == gen.end_time


def test_una_llamada_fallida_va_como_error_con_su_motivo() -> None:
    (gen,) = _generations(
        to_langfuse([_call(0, ok=False, error="no encaja")], source="n", session_id="n")
    )
    assert gen.level == "ERROR"
    assert gen.status_message == "no encaja"


def _novela() -> list[TraceRecord]:
    """Una tirada, una solicitud recibida durante ella y su aplicacion fuera."""
    return [
        _rec(0, "calibration", invocation="run", model="haiku"),
        _call(1),
        _rec(0, "amend.request", at="2026-09-23T10:01:00+00:00", request=1, status="queued"),
        _call(2, agent="continuista"),
        _rec(3, "work.close", closed=True, reason="", words=3_000),
        _rec(4, "work.cost", calls=2, cost_usd=0.02),
        _rec(0, "calibration", at="2026-09-23T11:00:00+00:00", invocation="amend"),
        _call(1, agent="reparador"),
        _rec(2, "amend.applied", at="2026-09-23T11:00:30+00:00", request=1, version=2),
        _rec(3, "work.cost", at="2026-09-23T11:00:31+00:00", calls=3),
    ]


def test_una_traza_por_generacion_con_la_novela_como_sesion() -> None:
    """RF-234: la tirada, la solicitud y la aplicacion son tres generaciones de una sesion."""
    objs = to_langfuse(_novela(), source="n.trace.jsonl", session_id="n")
    trazas = {t.id: t for t in _traces(objs)}
    # D-106: el numero de la solicitud va en los metadatos, no en el nombre.
    assert sorted({t.name for t in trazas.values()}) == ["amend", "change_request", "run"]
    assert {t.session_id for t in trazas.values()} == {"n"}
    abierta = next(t for t in _traces(objs) if t.name == "run" and t.timestamp)
    assert abierta.input == {"novel": "n", "invocation": "run", "model": "haiku"}
    # Cada observacion cuelga de una traza que existe.
    assert {o.trace_id for o in _observations(objs)} <= set(trazas)
    # La tirada lleva en su salida el cierre y el coste de la obra.
    run = next(t for t in _traces(objs) if t.name == "run" and t.output)
    finales = [t for t in _traces(objs) if t.id == run.id and t.output]
    assert finales[-1].output == {
        "closed": True,
        "reason": "",
        "words": 3_000,
        "calls": 2,
        "cost_usd": 0.02,
    }
    # La solicitud se abre al recibirse y se cierra al aplicarse.
    cr = [t for t in _traces(objs) if t.name == "change_request"]
    assert cr[0].metadata["request"] == 1
    assert cr[0].input == {"request": 1, "status": "queued"}
    assert cr[0].timestamp == "2026-09-23T10:01:00+00:00"
    assert cr[-1].timestamp is None and cr[-1].output == {"status": "applied", "version": 2}


def test_dos_invocaciones_que_empiezan_en_seq_cero_no_comparten_traza() -> None:
    """`seq` vuelve a cero en cada `Trace`: el instante del primer registro los separa."""
    objs = to_langfuse(_novela(), source="n.trace.jsonl", session_id="n")
    run = {t.id for t in _traces(objs) if t.name == "run"}
    amend = {t.id for t in _traces(objs) if t.name == "amend"}
    assert len(run) == len(amend) == 1 and run != amend


def test_los_registros_del_propio_espejo_no_se_exportan() -> None:
    objs = to_langfuse(
        [_rec(0, "export.failed", error="x"), _rec(1, "export.disabled", missing=[])],
        source="n",
        session_id="n",
    )
    assert objs == []


def test_el_termino_del_guardarrail_viaja_como_hash() -> None:
    """RNF-54: puede ser el nombre de una persona real; el literal no sale de la maquina."""
    registros = [
        _rec(0, "guardrail.match", term="Venancio", level="cliente", quote="dijo Venancio"),
        _rec(
            1,
            "chapter.gate",
            passed=False,
            defects=["S1:check.forbidden: palabra prohibida «Venancio»"],
        ),
    ]
    objs = to_langfuse(registros, source="n", session_id="n")
    volcado = json.dumps([o.model_dump() for o in objs], ensure_ascii=False)
    assert "Venancio" not in volcado
    assert lf.term_hash("Venancio") in volcado
    assert '"cliente"' in volcado  # el nivel sigue siendo legible


# ------------------------------------------------------------- propiedades

_KINDS = (
    "call",
    "calibration",
    "work.close",
    "work.cost",
    "scene.attempt",
    "retry",
    "export.failed",
)


@st.composite
def _registros(draw: st.DrawFn) -> list[TraceRecord]:
    n = draw(st.integers(min_value=0, max_value=30))
    out: list[TraceRecord] = []
    for i in range(n):
        kind = draw(st.sampled_from((*_KINDS, "amend.request", "amend.applied", "amend.rejected")))
        at = f"2026-09-23T10:{draw(st.integers(0, 59)):02d}:00+00:00"
        seq = draw(st.integers(min_value=0, max_value=i))
        campos: dict[str, JsonValue] = {"agent": "escritor", "output_tokens": 1}
        if kind.startswith("amend."):
            campos["request"] = draw(st.integers(min_value=1, max_value=3))
        out.append(TraceRecord(seq=seq, at=at, kind=kind, fields=campos))
    return out


@given(_registros())
def test_la_correspondencia_es_determinista_y_reexportar_no_duplica(
    registros: list[TraceRecord],
) -> None:
    """RF-234, VER-06. Dos exportaciones: los mismos identificadores, ni un objeto mas."""
    a = to_langfuse(registros, source="n.trace.jsonl", session_id="n")
    b = to_langfuse(registros, source="n.trace.jsonl", session_id="n")
    assert a == b
    cliente = FakeClient()
    cliente.send(a)
    antes = dict(cliente.store)
    cliente.send(b)
    assert cliente.store == antes
    # Toda observacion cuelga de una traza de la misma sesion.
    trazas = {t.id for t in _traces(a)}
    assert {o.trace_id for o in _observations(a)} <= trazas
    assert {t.session_id for t in _traces(a)} <= {"n"}


@given(_registros())
def test_el_identificador_depende_del_fichero(registros: list[TraceRecord]) -> None:
    """RF-234: derivado de su fichero; dos novelas nunca comparten traza."""
    a = {t.id for t in _traces(to_langfuse(registros, source="a.trace.jsonl", session_id="a"))}
    b = {t.id for t in _traces(to_langfuse(registros, source="b.trace.jsonl", session_id="b"))}
    assert not (a & b)


# ------------------------------------------------------------ conductor en vivo


def _live(client: object) -> lf.LiveExporter:
    live = install_live_export(FAKE_ENV, client_factory=lambda: client)  # type: ignore[arg-type,return-value]
    assert live is not None
    return live


def test_en_vivo_da_los_mismos_objetos_que_por_lote(tmp_path: Path) -> None:
    """RF-233, D-85: una sola correspondencia, dos conductores, los mismos objetos."""
    cliente = FakeClient()
    live = _live(cliente)
    traza = Trace(tmp_path / "n.trace.jsonl")
    traza.emit("calibration", invocation="run", model="haiku")
    traza.emit(
        "call", agent="escritor", real_input=10, output_tokens=5, cost_usd=0.1, duration_ms=3
    )
    traza.emit("work.close", closed=True, reason="", words=10)
    traza.emit("work.cost", **work_cost(traza.read()))
    assert live.drain(5)

    lote = to_langfuse(traza.records(), source="n.trace.jsonl", session_id="n")
    assert cliente.sent == lote
    assert {t.session_id for t in _traces(cliente.sent)} == {"n"}


def test_un_cliente_que_lanza_deja_export_failed_y_la_traza_sigue(tmp_path: Path) -> None:
    """RNF-53: se cuenta en los fallos de la traza, queda `export.failed` y nada lanza."""
    cliente = BrokenClient()
    live = _live(cliente)
    traza = Trace(tmp_path / "n.trace.jsonl")
    traza.emit("calibration", invocation="run")
    traza.emit("call", agent="escritor", real_input=1, output_tokens=1)
    assert live.drain(5)
    traza.emit("work.cost", calls=1)
    assert live.drain(5)

    fallos = traza.records("export.failed")
    assert fallos and traza.failures >= 1
    assert cliente.calls >= 1
    # El motivo no lleva el valor de ninguna clave.
    texto = (tmp_path / "n.trace.jsonl").read_text(encoding="utf-8")
    assert FAKE_ENV["LANGFUSE_SECRET_KEY"] not in texto
    assert FAKE_ENV["LANGFUSE_PUBLIC_KEY"] not in texto


def test_un_cliente_colgado_no_ralentiza_la_tirada(tmp_path: Path) -> None:
    """RNF-53: la cola no bloquea; si se llena, descarta y lo cuenta."""
    suelta = threading.Event()

    class Colgado:
        def send(self, objects: Sequence[LangfuseObject]) -> None:
            suelta.wait(10)

    live = lf.LiveExporter(lambda: Colgado(), max_queue=2)
    traza = Trace(tmp_path / "n.trace.jsonl")
    live.ensure(traza)
    inicio = time.monotonic()
    for i in range(200):
        traza.emit("call", agent="escritor", n=i)
    assert time.monotonic() - inicio < 2.0
    suelta.set()
    assert live.drain(5)
    assert any(r.fields.get("error") == "cola llena" for r in traza.records("export.failed"))
    assert len(traza.records("call")) == 200


def test_sin_claves_no_envia_y_lo_dice_una_sola_vez(tmp_path: Path) -> None:
    """RI-60: `export.disabled` una vez, con los nombres y nunca los valores."""
    traza = Trace(tmp_path / "n.trace.jsonl")
    assert attach_live_export(traza, env={"LANGFUSE_PUBLIC_KEY": "TU_CLAVE_AQUI"}) is None
    assert attach_live_export(traza, env={"LANGFUSE_PUBLIC_KEY": "TU_CLAVE_AQUI"}) is None
    (aviso,) = traza.records("export.disabled")
    assert aviso.fields["missing"] == ["LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"]
    assert "TU_CLAVE_AQUI" not in (tmp_path / "n.trace.jsonl").read_text(encoding="utf-8")
    assert lf.live_exporter() is None


def test_con_claves_la_traza_de_una_ruta_queda_observada(tmp_path: Path) -> None:
    """D-85: instalado el espejo, toda traza con fichero que se abra queda observada."""
    cliente = FakeClient()
    live = _live(cliente)
    traza = Trace(tmp_path / "n.trace.jsonl")
    traza.emit("amend.request", request=4, status="queued")
    assert live.drain(5)
    assert [(t.name, t.metadata["request"]) for t in _traces(cliente.sent)] == [
        ("change_request", 4)
    ]
    # Una traza sin fichero no tiene nada que espejar.
    assert Trace.disabled().observers == ()


def test_la_configuracion_no_ensena_sus_valores() -> None:
    config = lf.config_from_env(FAKE_ENV)
    assert config is not None
    assert "TU_CLAVE" not in repr(config)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (None, None),
        ("development", "development"),
        ("run-demo_1", "run-demo_1"),
        ("Produccion", None),  # mayusculas: Langfuse rechazaria el lote
        ("langfuse-dev", None),  # prefijo reservado
        ("x" * 41, None),
    ],
)
def test_el_entorno_sale_de_la_variable_estandar_y_solo_si_es_valido(
    valor: str | None, esperado: str | None
) -> None:
    """D-106: `LANGFUSE_TRACING_ENVIRONMENT`, con la regla de nombres de Langfuse."""
    env = dict(FAKE_ENV)
    if valor is not None:
        env[lf.ENV_ENVIRONMENT] = valor
    config = lf.config_from_env(env)
    assert config is not None and config.environment == esperado


# ---------------------------------------------------------------- por lote


def _escribe(path: Path, registros: Sequence[TraceRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(r.model_dump_json() + "\n" for r in registros), encoding="utf-8")


def test_el_lote_junta_la_entrevista_y_la_novela_en_una_sesion(tmp_path: Path) -> None:
    """RI-61, RF-234: la entrevista de origen se exporta con el `session_id` de la novela."""
    _escribe(tmp_path / "mi-novela.trace.jsonl", _novela())
    _escribe(
        tmp_path / "_interviews" / "0123456789ab.trace.jsonl",
        [_rec(0, "call", agent="brief.extract", real_input=10, output_tokens=5)],
    )
    cliente = FakeClient()
    n = export_novel("mi-novela", tmp_path, cliente, interviews=["0123456789ab"])
    assert n == len(cliente.sent)
    nombres = {t.name for t in _traces(cliente.sent)}
    assert nombres == {"interview", "run", "amend", "change_request"}
    assert {t.session_id for t in _traces(cliente.sent)} == {"mi-novela"}

    # Reexportar actualiza y no duplica.
    antes = dict(cliente.store)
    export_novel("mi-novela", tmp_path, cliente, interviews=["0123456789ab"])
    assert cliente.store == antes


def test_el_lote_no_escribe_en_la_traza(tmp_path: Path) -> None:
    ruta = tmp_path / "mi-novela.trace.jsonl"
    _escribe(ruta, _novela())
    antes = ruta.read_bytes()
    with pytest.raises(ConnectionError):
        export_novel("mi-novela", tmp_path, BrokenClient(), interviews=[])
    assert ruta.read_bytes() == antes


def test_la_orden_de_lote_sin_claves_no_envia_nada(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _escribe(tmp_path / "mi-novela.trace.jsonl", _novela())
    assert lf.main(["--novel", "mi-novela", "--runs-dir", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "LANGFUSE_SECRET_KEY" in err


def test_sin_brief_de_origen_no_hay_entrevista() -> None:
    assert lf.origin_interviews(Path("no-existe.sqlite")) == []


# ---------------------------------------------------------------- coste


def test_el_coste_de_la_obra_suma_lo_declarado_y_cuenta_lo_que_no() -> None:
    registros = [
        _call(0, cost_usd=0.5, duration_ms=10),
        _call(1, cost_usd=None, duration_ms=20),
        _rec(2, "retry"),
    ]
    total = work_cost(registros)
    assert total["calls"] == 2
    assert total["input_tokens"] == 2 * 5_150
    assert total["cost_usd"] == 0.5
    assert total["calls_without_cost"] == 1
    assert total["duration_ms"] == 30
    assert work_cost([_call(0, cost_usd=None)])["cost_usd"] is None


# ------------------------------------------------------------ adaptador real


def test_el_adaptador_construye_eventos_validos_del_sdk_sin_red() -> None:
    """El cliente real traduce cada objeto a un evento de ingestion del SDK instalado."""
    pytest.importorskip("langfuse")
    registros = [
        *_novela(),
        _rec(11, "tool", call="c0ffee00c0ffee00", name="canon.lookup", args="x", tokens=4),
    ]
    objs = to_langfuse(registros, source="n.trace.jsonl", session_id="n")
    eventos = [lf.SdkClient._event(o, environment="development") for o in objs]
    tipos = {e.type for e in eventos}
    assert tipos == {
        "trace-create",
        "generation-create",
        "event-create",
        "span-create",
        "score-create",
        "observation-create",
    }
    gen = next(e for e in eventos if e.type == "generation-create")
    assert gen.body.usage_details["cache_read_input_tokens"] == 5_000
    assert gen.body.cost_details == {"total": 0.0123}
    # D-106: el tipo especifico llega al SDK, con su entrada y su salida.
    tipados = {str(e.body.type.value) for e in eventos if e.type == "observation-create"}
    assert tipados == {"RETRIEVER", "EVALUATOR"}
    busqueda = next(
        e for e in eventos if e.type == "observation-create" and e.body.name == "canon.lookup"
    )
    assert busqueda.body.input == "x" and busqueda.body.output == {"tokens": 4}
    assert {e.body.environment for e in eventos} == {"development"}


# ------------------------------------------------------------ T48: roles y spans


def test_cada_llamada_es_una_generation_con_su_rol() -> None:
    """RF-263: `<rol>.<agente>`, con la tabla de roles de `architecture.md` §11."""
    registros = [
        _call(0, agent="arquitecto"),
        _call(1, agent="escritor"),
        _call(2, agent="juez"),
        _call(3, agent="archivero"),
        _call(4, agent="supervisor"),
    ]
    nombres = [g.name for g in _generations(to_langfuse(registros, source="n", session_id="n"))]
    assert nombres == [
        "planner.arquitecto",
        "writer.escritor",
        "editor.juez",
        "canon.archivero",
        "supervisor.supervisor",
    ]


def test_un_agente_sin_rol_hace_fallar_la_exportacion() -> None:
    """RF-263: no inventa un nombre."""
    with pytest.raises(lf.UnknownAgentError):
        to_langfuse([_call(0, agent="agente-nuevo")], source="n", session_id="n")


def test_la_generation_cuelga_de_su_escena_y_la_escena_de_su_capitulo() -> None:
    """RF-263: spans de capitulo y de escena; el capitulo congelado cierra los suyos."""
    registros = [
        _rec(0, "calibration", invocation="run"),
        _call(1, scene=2, prompt_version="abc123abc123", attempt=1),
        _rec(2, "chapter.frozen", at="2026-09-23T10:05:00+00:00", chapter=1),
        _rec(3, "summary", at="2026-09-23T10:06:00+00:00", chapter=1),
    ]
    objs = to_langfuse(registros, source="n.trace.jsonl", session_id="n")
    spans = [o for o in _observations(objs) if o.type == "span"]
    # D-106: nombres fijos, sin el numero, que va en los metadatos.
    assert {s.name for s in spans} == {"chapter", "scene"}
    capitulo = _spans(objs, 1)[0]
    escena = _spans(objs, 1, 2)[0]
    assert escena.parent_observation_id == capitulo.id
    (gen,) = _generations(objs)
    assert gen.parent_observation_id == escena.id
    assert gen.metadata["attempt"] == 1 and gen.metadata["chapter"] == 1
    # RF-266: el prompt que uso, por nombre y etiqueta.
    assert (gen.prompt_name, gen.prompt_label) == ("escritor", "abc123abc123")
    # El capitulo congelado cierra su span y el de sus escenas, y no se reabre.
    cierres = [s for s in spans if s.end_time == "2026-09-23T10:05:00+00:00"]
    assert {s.id for s in cierres} == {capitulo.id, escena.id}
    assert len(_spans(objs, 1)) == 2
    resumen = next(o for o in _observations(objs) if o.name == "summary")
    assert resumen.parent_observation_id == capitulo.id


def test_cada_herramienta_es_hermana_de_su_generation() -> None:
    """RF-264, D-106: el `tool` se escribe antes que su `call` y los dos cuelgan del mismo span.

    La generation que la pidio queda en `metadata.call`; la herramienta de solo
    consulta sale como `retriever`, con sus argumentos de entrada y su resultado
    de salida.
    """
    registros = [
        _rec(0, "calibration", invocation="run"),
        _rec(
            1,
            "tool",
            call="c0ffee00c0ffee00",
            agent="escritor",
            chapter=1,
            name="canon.lookup",
            args="entity=PER-1",
            tokens=40,
            provenance="canon",
            refused=False,
            duration_ms=5,
        ),
        _rec(
            2, "tool", call="c0ffee00c0ffee00", chapter=1, name="context.budget", refused=True
        ),
        _call(3, call_id="c0ffee00c0ffee00"),
    ]
    objs = to_langfuse(registros, source="n.trace.jsonl", session_id="n")
    (gen,) = _generations(objs)
    herramientas = [o for o in _observations(objs) if o.type in ("tool", "retriever")]
    assert [(h.name, h.type) for h in herramientas] == [
        ("canon.lookup", "retriever"),
        ("context.budget", "tool"),
    ]
    (capitulo,) = {s.id for s in _spans(objs, 1)}
    assert {h.parent_observation_id for h in herramientas} == {capitulo}
    assert gen.parent_observation_id == capitulo
    assert {h.metadata["call"] for h in herramientas} == {"c0ffee00c0ffee00"}
    assert {h.trace_id for h in herramientas} == {gen.trace_id}
    busqueda = herramientas[0]
    assert busqueda.input == "entity=PER-1"
    assert busqueda.output == {"tokens": 40, "provenance": "canon", "refused": False}
    assert herramientas[1].level == "WARNING"


def test_los_verificadores_y_el_guardarrail_llevan_su_tipo_y_su_veredicto() -> None:
    """D-106: `evaluator` y `guardrail` con el veredicto como salida; lo demas, `event`."""
    registros = [
        _rec(0, "calibration", invocation="run"),
        _VERIFICADORES["chapter.gate"],
        _VERIFICADORES["guardrail.match"],
        _rec(12, "summary", chapter=1),
    ]
    objs = to_langfuse(registros, source="n", session_id="n")
    por_nombre = {o.name: o for o in _observations(objs)}
    puerta = por_nombre["chapter.gate"]
    assert puerta.type == "evaluator"
    assert puerta.output == {"chapter": 1, "passed": True, "s1": 0, "s2": 1, "defects": []}
    assert puerta.end_time == puerta.start_time
    guarda = por_nombre["guardrail.match"]
    assert guarda.type == "guardrail"
    # RNF-54: el termino sale como hash tambien en la salida.
    assert isinstance(guarda.output, dict)
    assert "Venancio" not in json.dumps(guarda.output)
    assert por_nombre["summary"].type == "event" and por_nombre["summary"].output is None


def test_la_llamada_de_amend_interpret_cuelga_de_su_solicitud() -> None:
    """RF-262: el `call` lleva el numero de solicitud y va a la traza de esa solicitud."""
    registros = [
        _rec(0, "amend.request", request=3, status="queued"),
        _call(1, agent="amend.interpret", request=3),
    ]
    objs = to_langfuse(registros, source="n.trace.jsonl", session_id="n")
    (traza,) = _traces(objs)
    (gen,) = _generations(objs)
    assert traza.name == "change_request" and traza.metadata["request"] == 3
    assert gen.trace_id == traza.id and gen.name == "interviewer.amend.interpret"


def test_la_entrevista_es_una_sola_traza_aunque_la_escriban_varias_rutas(tmp_path: Path) -> None:
    """RF-262, D-85: cada turno abre su `Trace`; en vivo y por lote dan la misma traza."""
    cliente = FakeClient()
    live = _live(cliente)
    ruta = tmp_path / "_interviews" / "0123456789ab.trace.jsonl"
    Trace(ruta).emit("interview.created")
    turno = Trace(ruta)
    turno.emit("call", agent="brief.extract", real_input=10, output_tokens=5)
    turno.emit("interview.turn", free_text=True)
    assert live.drain(5)
    en_vivo = {t.id for t in _traces(cliente.sent)}
    lote = {t.id for t in _traces(lf.interview_objects("mi-novela", tmp_path, ["0123456789ab"]))}
    assert len(en_vivo) == 1 and en_vivo == lote
    assert [g.name for g in _generations(cliente.sent)] == ["interviewer.brief.extract"]


def test_un_identificador_de_entrevista_que_no_lo_es_no_se_convierte_en_ruta(
    tmp_path: Path,
) -> None:
    """RD-46: `origin_interview` llega del cliente en el brief."""
    from commons.settings import InvalidNovelIdError, Settings

    with pytest.raises(InvalidNovelIdError):
        Settings(runs_dir=tmp_path).interview_trace_path("../mi-novela")


# ---------------------------------------------------------------- T48: scores

#: Un registro de cada verificador, como los escribe el motor.
_VERIFICADORES: dict[str, TraceRecord] = {
    "scene.checks": _rec(
        1,
        "scene.checks",
        chapter=1,
        scene=1,
        ran=["check.format", "check.timeline"],
        failed=["check.timeline"],
    ),
    "scene.attempt": _rec(
        2,
        "scene.attempt",
        chapter=1,
        scene=1,
        attempt=1,
        passed=False,
        defects=["check.timeline:S1", "check.format:S2"],
    ),
    "chapter.gate": _rec(3, "chapter.gate", chapter=1, passed=True, s1=0, s2=1, defects=[]),
    "jury": _rec(
        4,
        "jury",
        chapter=1,
        passed=True,
        levels={"voz": 4, "ritmo": 3},
        spreads={"voz": 0.5, "ritmo": 1.0},
    ),
    "quiz": _rec(5, "quiz", chapter=1, questions=4, wrong=1),
    "outline.check": _rec(6, "outline.check", passed=True, defects=[]),
    "act.gate": _rec(7, "act.gate", act=1, passed=False),
    "work.close": _rec(8, "work.close", closed=True, reason="", words=10),
    "formal.lean": _rec(
        9, "formal.lean", chapter=1, passed=False, theorem="pov_en_elenco", rule="EST-I1"
    ),
    "guardrail.match": _rec(
        10,
        "guardrail.match",
        chapter=1,
        scene=1,
        attempt=1,
        term="Venancio",
        level="cliente",
        decision="reintentar",
        stage="escena",
    ),
}

#: Los scores que da cada uno: los nombres de la tabla de `architecture.md` §11.
_ESPERADOS: dict[str, set[str]] = {
    "scene.checks": {"check.format", "check.timeline"},
    "scene.attempt": {"gate.scene", "gate.scene.s1", "gate.scene.s2", "guardrail.forbidden"},
    "chapter.gate": {"gate.chapter", "gate.chapter.s1", "gate.chapter.s2", "guardrail.forbidden"},
    "jury": {"jury.voz", "jury.ritmo"},
    "quiz": {"quiz.wrong"},
    "outline.check": {"outline.check"},
    "act.gate": {"act.gate"},
    "work.close": {"work.close"},
    "formal.lean": {"formal.lean"},
    "guardrail.match": {"guardrail.forbidden"},
}


def _scores(objs: Sequence[LangfuseObject]) -> list[lf.LangfuseScore]:
    return [o for o in objs if isinstance(o, lf.LangfuseScore)]


def test_cada_verificador_tiene_su_score() -> None:
    """RF-265: con los nombres y tipos de la tabla de scores de `architecture.md` §11."""
    assert set(_VERIFICADORES) == set(lf.SCORERS) == set(_ESPERADOS)
    for kind, registro in _VERIFICADORES.items():
        objs = to_langfuse(
            [_rec(0, "calibration", invocation="run"), registro], source="n", session_id="n"
        )
        assert {s.name for s in _scores(objs)} == _ESPERADOS[kind], kind


def test_los_scores_van_al_span_que_evaluaron_con_su_tipo() -> None:
    registros = [_rec(0, "calibration", invocation="run"), *_VERIFICADORES.values()]
    objs = to_langfuse(registros, source="n", session_id="n")
    escena = _spans(objs, 1, 1)[0].id
    capitulo = _spans(objs, 1)[0].id
    por_nombre = {s.name: s for s in _scores(objs)}
    assert por_nombre["check.timeline"].value == 0.0
    assert por_nombre["check.format"].value == 1.0
    assert por_nombre["check.format"].observation_id == escena
    assert por_nombre["gate.scene"].data_type == "BOOLEAN"
    assert por_nombre["gate.scene.s1"].data_type == "NUMERIC"
    assert por_nombre["gate.scene.s1"].value == 1.0
    assert por_nombre["gate.chapter"].observation_id == capitulo
    assert por_nombre["jury.voz"].value == 4.0
    assert por_nombre["jury.voz"].comment == "dispersion=0.5"
    assert por_nombre["quiz.wrong"].value == 1.0
    assert por_nombre["formal.lean"].comment == "pov_en_elenco"
    # La tirada y el acto no tienen span: el score va a la traza.
    for nombre in ("outline.check", "act.gate", "work.close"):
        assert por_nombre[nombre].observation_id is None
    assert por_nombre["act.gate"].comment == "acto 1"
    # Reexportar no duplica: los identificadores de los scores son deterministas.
    assert _scores(objs) == _scores(to_langfuse(registros, source="n", session_id="n"))


_EMIT = re.compile(r"\.emit\(\s*\"([a-z_.]+)\"", re.S)


def _emitted_kinds() -> set[str]:
    raiz = Path(__file__).resolve().parents[2]
    kinds: set[str] = set()
    for fichero in raiz.rglob("*.py"):
        if fichero.name.startswith("test_") or ".venv" in fichero.parts:
            continue
        kinds |= set(_EMIT.findall(fichero.read_text(encoding="utf-8")))
    return kinds


def test_todo_registro_de_la_traza_esta_clasificado() -> None:
    """RF-265: un registro de verificador sin score definido hace fallar la prueba.

    Cada tipo que el codigo escribe tiene que estar en `SCORERS`, con su score, o
    en `UNSCORED`, dicho a proposito. Un verificador nuevo que no se clasifica no
    llega a Langfuse sin que nadie se entere.
    """
    kinds = _emitted_kinds()
    assert {"call", "tool", "scene.attempt", "guardrail.match", "scene.checks"} <= kinds
    sin_clasificar = kinds - set(lf.SCORERS) - lf.UNSCORED
    assert not sin_clasificar, f"tipos de registro sin clasificar: {sorted(sin_clasificar)}"
    assert not (set(lf.SCORERS) & lf.UNSCORED)
