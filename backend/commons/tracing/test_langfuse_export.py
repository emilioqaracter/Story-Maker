"""El espejo de Langfuse con un cliente doble. RF-233 a RF-235, RI-60, RI-61, RNF-53, RNF-54.

Metodo VER-05 y, para la identidad de las generaciones, VER-06. Ninguna prueba
habla con Langfuse: el cliente es un doble y las claves son de mentira.
"""

from __future__ import annotations

import json
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


# ------------------------------------------------------------ correspondencia


def test_una_llamada_es_una_generation_con_modelo_uso_coste_e_inicio_y_fin() -> None:
    """RF-235: los cuatro campos de uso, el coste del CLI y la latencia de `dispatch`."""
    objs = to_langfuse([_call(0)], source="n.trace.jsonl", session_id="n")
    (gen,) = _observations(objs)
    assert gen.type == "generation"
    assert gen.name == "escritor"
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
    (gen,) = _observations(to_langfuse([_call(0, cost_usd=None)], source="n", session_id="n"))
    assert gen.cost_details is None


def test_una_traza_anterior_al_desglose_da_la_suma_como_entrada() -> None:
    """Las tiradas ya hechas, como T16, solo traen `real_input`: se exportan igual."""
    viejo = _rec(0, "call", agent="juez", real_input=4_000, output_tokens=300)
    (gen,) = _observations(to_langfuse([viejo], source="n", session_id="n"))
    assert gen.usage_details == {"input": 4_000, "output": 300}
    assert gen.start_time == gen.end_time


def test_una_llamada_fallida_va_como_error_con_su_motivo() -> None:
    (gen,) = _observations(
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
    assert sorted({t.name for t in trazas.values()}) == ["amend", "change_request.1", "run"]
    assert {t.session_id for t in trazas.values()} == {"n"}
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
    cr = [t for t in _traces(objs) if t.name == "change_request.1"]
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
    assert [t.name for t in _traces(cliente.sent)] == ["change_request.4"]
    # Una traza sin fichero no tiene nada que espejar.
    assert Trace.disabled().observers == ()


def test_la_configuracion_no_ensena_sus_valores() -> None:
    config = lf.config_from_env(FAKE_ENV)
    assert config is not None
    assert "TU_CLAVE" not in repr(config)


# ---------------------------------------------------------------- por lote


def _escribe(path: Path, registros: Sequence[TraceRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(r.model_dump_json() + "\n" for r in registros), encoding="utf-8")


def test_el_lote_junta_la_entrevista_y_la_novela_en_una_sesion(tmp_path: Path) -> None:
    """RI-61, RF-234: la entrevista de origen se exporta con el `session_id` de la novela."""
    _escribe(tmp_path / "mi-novela.trace.jsonl", _novela())
    _escribe(
        tmp_path / "_interviews" / "e1.trace.jsonl",
        [_rec(0, "call", agent="brief.extract", real_input=10, output_tokens=5)],
    )
    cliente = FakeClient()
    n = export_novel("mi-novela", tmp_path, cliente, interviews=["e1"])
    assert n == len(cliente.sent)
    nombres = {t.name for t in _traces(cliente.sent)}
    assert nombres == {"interview", "run", "amend", "change_request.1"}
    assert {t.session_id for t in _traces(cliente.sent)} == {"mi-novela"}

    # Reexportar actualiza y no duplica.
    antes = dict(cliente.store)
    export_novel("mi-novela", tmp_path, cliente, interviews=["e1"])
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
    objs = to_langfuse(_novela(), source="n.trace.jsonl", session_id="n")
    eventos = [lf.SdkClient._event(o) for o in objs]
    tipos = {e.type for e in eventos}
    assert tipos == {"trace-create", "generation-create", "event-create"}
    gen = next(e for e in eventos if e.type == "generation-create")
    assert gen.body.usage_details["cache_read_input_tokens"] == 5_000
    assert gen.body.cost_details == {"total": 0.0123}
