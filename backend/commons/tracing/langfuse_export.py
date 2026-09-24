"""Langfuse como espejo de la traza local.

`specs/srs-backend-v4.md` RF-233 a RF-235, RI-60, RI-61, RD-44, RNF-53, RNF-54;
D-85 y D-86. `architecture.md` §11.

**Una sola correspondencia, dos conductores.** `step` convierte un registro de
la traza en los objetos de Langfuse que le tocan, y es pura: recibe el estado de
la correspondencia y devuelve el siguiente. La usan dos conductores:

- **En vivo** (`LiveExporter`): observador de la traza. Encola los objetos en
  una cola acotada y los envia un hilo propio. Nunca bloquea, nunca lanza y
  nunca espera a la red: un fallo deja `export.failed` en la traza local y la
  tirada sigue (RNF-53).
- **Por lote** (`export_novel`, y `python -m commons.tracing.langfuse_export`):
  recorre el JSONL de una novela ya escrito. Sirve para tiradas hechas antes del
  espejo y para recuperar lo que el vivo no pudo enviar (RI-61).

Como los dos pliegan la misma funcion sobre los mismos registros, dan los mismos
objetos. Y como todo identificador es determinista, reexportar actualiza y no
duplica (RF-234).

**Que es una generacion** (RF-234). Cada una es una traza de Langfuse con
`session_id` igual a la novela:

| Generacion | Empieza | Acaba | Identificador |
|---|---|---|---|
| Invocacion del Orquestador | su `calibration`, o el primer registro suelto | `work.cost` | fichero, tipo y primer registro |
| Solicitud de cambio | `amend.request` | `amend.applied` o `amend.rejected` | fichero, tipo y numero de solicitud |
| Entrevista | el primer registro de su fichero | el ultimo | fichero, tipo y primer registro |

El primer registro de una invocacion se identifica por su `seq` **y su
instante**: `seq` vuelve a cero en cada instancia de `Trace`, y dos tiradas
reanudadas de la misma novela empiezan las dos en `seq` 0. La solicitud se
identifica por su numero y no por su primer `seq` porque su apertura y su cierre
los escriben instancias distintas de la traza --la ruta que la recibe y la
tirada que la aplica--, y el numero es lo unico que ven las dos.

**Nada de la novela sale salvo por aqui** (RNF-54). El termino de una
coincidencia del guardarrail viaja como sha256 recortado: puede ser el nombre de
una persona real que el cliente prohibio. El literal queda en la traza local.

**Que hay dentro de cada generacion** (RF-263 a RF-265, D-86):

- un span `chapter` por capitulo y otro `scene` por escena, con el numero en
  los metadatos y la escena colgada de su capitulo (D-106);
- una generation `<rol>.<agente>` por `call`, colgada del span de su escena o de
  su capitulo, con el prompt que uso por nombre y etiqueta (`prompt_version`);
- una observacion `retriever` o `tool` por registro `tool`, hermana de la
  generation que la pidio bajo el mismo span (D-106);
- una observacion `evaluator` por resultado de verificador y otra `guardrail`
  por registro del guardarrail, con el veredicto como salida (D-106);
- los scores de cada verificador, sobre la traza o el span que evaluo.

**Claves.** `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` y `LANGFUSE_BASE_URL`,
del entorno y por nombre. Si falta alguna, o la libreria `langfuse` no esta, no
se envia nada, queda `export.disabled` una vez y la tirada sigue (RI-60). Ningun
valor de clave se escribe en la traza ni sale por la salida de error.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import queue
import re
import sqlite3
import sys
import threading
import uuid
import weakref
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from commons.tracing.trace import (
    Trace,
    TraceRecord,
    add_observer_factory,
    remove_observer_factory,
)

#: RI-60. Las tres variables, por nombre. Sus valores no se imprimen nunca.
ENV_KEYS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")

#: Registros del propio espejo. No se exportan: exportar el aviso de que no se
#: pudo exportar seria un bucle, y no dicen nada de la novela.
_OWN_PREFIX = "export."

#: RNF-54. Registros cuyo contenido de texto viaja como hash.
_GUARDRAIL_PREFIX = "guardrail."
#: RNF-54. Un texto que menciona este verificador puede llevar el termino dentro.
_FORBIDDEN_MARK = "check.forbidden"
#: Longitud del hash de un termino: la misma que `prompt_version` (RF-265).
HASH_CHARS = 12

#: Propuesta: capacidad de la cola del conductor en vivo, en lotes de objetos
#: (uno por registro). Una tirada medida deja del orden de cientos de registros
#: por capitulo; 10.000 aguantan varios capitulos sin red antes de descartar, y
#: lo descartado sigue en el JSONL para el lote (RNF-53).
QUEUE_MAX = 10_000

#: Tope de un envio. La API de ingestion admite lotes de hasta 3,5 MB; se deja
#: margen por el sobre de cada evento.
BATCH_BYTES = 3_000_000

#: Sufijo del fichero de traza de una novela (`commons/settings.py`).
TRACE_SUFFIX = ".trace.jsonl"

GenerationType = Literal["run", "amend", "change_request", "interview"]
Mode = Literal["novel", "interview"]


# ---------------------------------------------------------------- objetos


class LangfuseTrace(BaseModel):
    """Una traza de Langfuse: una generacion. Un mismo `id` enviado dos veces actualiza.

    `timestamp` es `None` en una actualizacion: el inicio lo fija la apertura y
    el cierre no lo mueve.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^[0-9a-f]{32}$")
    name: str
    session_id: str
    timestamp: str | None = None
    metadata: Mapping[str, JsonValue] = Field(default_factory=dict)
    input: Mapping[str, JsonValue] | None = None
    output: Mapping[str, JsonValue] | None = None


ObservationType = Literal[
    "generation", "event", "span", "tool", "retriever", "evaluator", "guardrail"
]


class LangfuseObservation(BaseModel):
    """Una observacion dentro de una traza, con el tipo mas especifico que le toca (D-106).

    Una generation por `call`; un `retriever` por herramienta de solo consulta y
    un `tool` por las demas; un `evaluator` por resultado de verificador, un
    `guardrail` por registro del guardarrail; un span por capitulo y por escena,
    y un evento por lo demas (RF-263, RF-264).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^[0-9a-f]{16}$")
    trace_id: str
    type: ObservationType
    name: str
    start_time: str
    end_time: str | None = None
    parent_observation_id: str | None = None
    metadata: Mapping[str, JsonValue] = Field(default_factory=dict)
    input: JsonValue = None
    output: JsonValue = None
    model: str | None = None
    usage_details: Mapping[str, int] | None = None
    cost_details: Mapping[str, float] | None = None
    level: Literal["DEFAULT", "WARNING", "ERROR"] = "DEFAULT"
    status_message: str | None = None
    #: RF-266. El prompt que uso la generation: nombre igual al agente y
    #: etiqueta igual a su `prompt_version`, la misma que publica `prompts_sync`.
    prompt_name: str | None = None
    prompt_label: str | None = None


ScoreType = Literal["BOOLEAN", "NUMERIC"]


class LangfuseScore(BaseModel):
    """RF-265. El resultado de un verificador, sobre la traza o el span que evaluo."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^[0-9a-f]{32}$")
    trace_id: str
    observation_id: str | None = None
    name: str
    value: float
    data_type: ScoreType
    comment: str | None = None
    metadata: Mapping[str, JsonValue] = Field(default_factory=dict)


LangfuseObject = LangfuseTrace | LangfuseObservation | LangfuseScore


class _Open(BaseModel):
    """La invocacion abierta: lo que hace falta para colgarle registros y cerrarla."""

    model_config = ConfigDict(frozen=True)

    trace_id: str
    name: str
    output: Mapping[str, JsonValue] = Field(default_factory=dict)


class _Span(BaseModel):
    """Un span de capitulo o de escena abierto dentro de la generacion abierta."""

    model_config = ConfigDict(frozen=True)

    key: str
    id: str
    trace_id: str
    #: `chapter` o `scene`: el numero no va en el nombre, va en `meta` (D-106).
    name: str
    meta: Mapping[str, JsonValue] = Field(default_factory=dict)
    parent: str | None
    start: str
    last: str


class MapState(BaseModel):
    """Estado de la correspondencia. Inmutable: `step` devuelve uno nuevo."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(description="Fichero de la traza, relativo al directorio de tiradas")
    session_id: str
    mode: Mode = "novel"
    open: _Open | None = None
    spans: tuple[_Span, ...] = ()
    #: Spans ya cerrados de la generacion abierta: un registro posterior de ese
    #: capitulo cuelga del mismo span sin volver a abrirlo.
    closed: frozenset[str] = frozenset()


# ---------------------------------------------------------------- roles

#: RF-263, `architecture.md` §11. El rol de cada agente en la traza exportada.
#: No son agentes nuevos: agrupan los de §6 con los nombres de la rubrica.
ROLES: Mapping[str, str] = {
    "brief.extract": "interviewer",
    "amend.interpret": "interviewer",
    "arquitecto": "planner",
    "planificador": "planner",
    "escritor": "writer",
    "especialista": "writer",
    "continuista": "editor",
    "juez": "editor",
    "reparador": "editor",
    "estilista": "editor",
    "lector": "editor",
    "archivero": "canon",
    "arbitro": "canon",
    "supervisor": "supervisor",
}


class UnknownAgentError(KeyError):
    """RF-263. Un agente sin rol en la tabla: la exportacion falla, no inventa un nombre."""


def span_name(agent: str) -> str:
    """`<rol>.<agente>`: el nombre de la generation de una llamada (RF-263)."""
    try:
        return f"{ROLES[agent]}.{agent}"
    except KeyError:
        raise UnknownAgentError(
            f"el agente {agent!r} no tiene rol en la tabla de `architecture.md` §11"
        ) from None


# ---------------------------------------------------------------- correspondencia


def _hex(*parts: object, chars: int) -> str:
    raw = "\x1f".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:chars]


def term_hash(text: str) -> str:
    """RNF-54. Lo que viaja en lugar de un termino prohibido."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:HASH_CHARS]


def generation_id(source: str, gtype: GenerationType, key: object, at: str = "") -> str:
    """RF-234. Identificador determinista de una generacion: 32 hex, el formato de Langfuse."""
    return _hex(source, gtype, key, at, chars=32)


def _observation_id(trace_id: str, record: TraceRecord) -> str:
    return _hex(trace_id, record.kind, record.seq, record.at, chars=16)


def call_observation_id(trace_id: str, call_id: str) -> str:
    """RF-264. La generation de una llamada, por el `call_id` que `dispatch` le da.

    El registro `call` se escribe al acabar la llamada, despues de las
    herramientas que sirvio: sus hijas lo nombran por este identificador, que
    sale del JSONL y es el mismo en los dos conductores.
    """
    return _hex(trace_id, "call", call_id, chars=16)


def _span_id(trace_id: str, key: str) -> str:
    return _hex(trace_id, "span", key, chars=16)


def _scrub(value: JsonValue, *, hide_text: bool) -> JsonValue:
    """RNF-54. Quita del valor todo texto que pueda llevar un termino prohibido."""
    if isinstance(value, dict):
        return {
            k: (
                f"sha256:{term_hash(v)}"
                if k == "term" and isinstance(v, str)
                else _scrub(v, hide_text=hide_text)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub(v, hide_text=hide_text) for v in value]
    if isinstance(value, str) and (hide_text or _FORBIDDEN_MARK in value):
        return f"sha256:{term_hash(value)}"
    return value


def _metadata(record: TraceRecord) -> dict[str, JsonValue]:
    campos: dict[str, JsonValue] = dict(record.fields)
    guardrail = record.kind.startswith(_GUARDRAIL_PREFIX)
    limpio = _scrub(campos, hide_text=guardrail)
    assert isinstance(limpio, dict)
    if guardrail:
        # El nivel no es texto de la novela: se conserva para poder filtrar.
        for k in ("level", "kind"):
            if isinstance(record.fields.get(k), str):
                limpio[k] = record.fields[k]
    limpio["seq"] = record.seq
    limpio["record"] = record.kind
    return limpio


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _minus_ms(at: str, ms: int) -> str:
    """`at` menos `ms` milisegundos, con precision de milisegundo en los dos extremos."""
    try:
        instante = datetime.fromisoformat(at)
    except ValueError:
        return at
    return (instante - timedelta(milliseconds=ms)).isoformat(timespec="milliseconds")


def _usage(fields: Mapping[str, JsonValue]) -> dict[str, int]:
    """Los cuatro campos de uso (RF-235). Una traza anterior a RD-44 solo trae la suma."""
    salida = _int(fields.get("output_tokens")) or 0
    entrada = _int(fields.get("input_tokens"))
    if entrada is None:
        return {"input": _int(fields.get("real_input")) or 0, "output": salida}
    return {
        "input": entrada,
        "cache_creation_input_tokens": _int(fields.get("cache_creation_tokens")) or 0,
        "cache_read_input_tokens": _int(fields.get("cache_read_tokens")) or 0,
        "output": salida,
    }


def _generation(trace_id: str, record: TraceRecord, parent: str | None) -> LangfuseObservation:
    """Un registro `call` como generation `<rol>.<agente>` (RF-235, RF-263, RF-266)."""
    f = record.fields
    agente = str(f.get("agent") or "")
    duracion = _int(f.get("duration_ms"))
    coste = f.get("cost_usd")
    ok = f.get("ok") is not False
    error = f.get("error")
    call_id = _str(f.get("call_id"))
    version = _str(f.get("prompt_version"))
    return LangfuseObservation(
        id=call_observation_id(trace_id, call_id) if call_id else _observation_id(trace_id, record),
        trace_id=trace_id,
        type="generation",
        name=span_name(agente),
        start_time=_minus_ms(record.at, duracion or 0),
        end_time=_minus_ms(record.at, 0),
        parent_observation_id=parent,
        metadata=_metadata(record),
        model=_str(f.get("model")),
        usage_details=_usage(f),
        cost_details=(
            {"total": float(coste)}
            if isinstance(coste, int | float) and not isinstance(coste, bool)
            else None
        ),
        level="DEFAULT" if ok else "ERROR",
        status_message=None if ok or not isinstance(error, str) else error,
        prompt_name=agente if version else None,
        prompt_label=version,
    )


#: D-106. Herramientas de `orchestration/tools/server.py` que solo consultan y
#: no cambian estado: en Langfuse son `retriever`. Una que no este aqui sale
#: como `tool`, que es el tipo generico y nunca un tipo falso.
RETRIEVER_TOOLS: frozenset[str] = frozenset({"canon.lookup"})

#: Campos del registro `tool` que forman la salida de la observacion (RF-264).
_TOOL_OUTPUT = ("tokens", "provenance", "refused", "error")


def _tool(trace_id: str, record: TraceRecord, parent: str | None) -> LangfuseObservation:
    """RF-264, D-106. Una llamada a herramienta, hermana de la generation que la pidio.

    Cuelga del span de su escena o su capitulo, como la generation: en Langfuse
    una herramienta es un paso del agente, no algo que ocurra dentro de la
    llamada al modelo. La generation que la pidio queda en `metadata.call`.
    """
    f = record.fields
    duracion = _int(f.get("duration_ms")) or 0
    error = _str(f.get("error"))
    nombre = str(f.get("name") or "tool")
    meta = _metadata(record)
    salida = {k: meta[k] for k in _TOOL_OUTPUT if k in meta}
    return LangfuseObservation(
        id=_observation_id(trace_id, record),
        trace_id=trace_id,
        type="retriever" if nombre in RETRIEVER_TOOLS else "tool",
        name=nombre,
        start_time=_minus_ms(record.at, duracion),
        end_time=_minus_ms(record.at, 0),
        parent_observation_id=parent,
        metadata=meta,
        input=meta.get("args"),
        output=salida or None,
        level="ERROR" if error else ("WARNING" if f.get("refused") is True else "DEFAULT"),
        status_message=error,
    )


#: Claves de `_metadata` que no son el veredicto, sino donde y cuando se dio.
_BOOKKEEPING = frozenset({"seq", "record"})


def _event(trace_id: str, record: TraceRecord, parent: str | None = None) -> LangfuseObservation:
    """Un registro sin duracion. Si es de verificador o del guardarrail, lleva su tipo (D-106).

    El veredicto va tambien como salida, que es lo que Langfuse ensena en la
    tabla y lo que lee un evaluador; los metadatos conservan el registro entero.
    """
    meta = _metadata(record)
    tipo: ObservationType = "event"
    if record.kind.startswith(_GUARDRAIL_PREFIX):
        tipo = "guardrail"
    elif record.kind in SCORERS:
        tipo = "evaluator"
    return LangfuseObservation(
        id=_observation_id(trace_id, record),
        trace_id=trace_id,
        type=tipo,
        name=record.kind,
        start_time=record.at,
        end_time=record.at if tipo != "event" else None,
        parent_observation_id=parent,
        metadata=meta,
        output={k: v for k, v in meta.items() if k not in _BOOKKEEPING} if tipo != "event" else None,
    )


def _observation(trace_id: str, record: TraceRecord, parent: str | None) -> LangfuseObservation:
    if record.kind == "call":
        return _generation(trace_id, record, parent)
    if record.kind == "tool":
        return _tool(trace_id, record, parent)
    return _event(trace_id, record, parent)


# ---------------------------------------------------------------- spans


def _scope(fields: Mapping[str, JsonValue]) -> tuple[int | None, int | None]:
    """Capitulo y escena de un registro. Una escena sin capitulo no abre span."""
    capitulo = _int(fields.get("chapter"))
    escena = _int(fields.get("scene")) if capitulo is not None else None
    return capitulo, escena


def _chapter_key(chapter: int) -> str:
    return f"chapter.{chapter}"


def _scene_key(chapter: int, scene: int) -> str:
    return f"scene.{chapter}.{scene}"


def _span_object(span: _Span, end: str | None = None) -> LangfuseObservation:
    return LangfuseObservation(
        id=span.id,
        trace_id=span.trace_id,
        type="span",
        name=span.name,
        start_time=span.start,
        end_time=end,
        parent_observation_id=span.parent,
        metadata=span.meta,
    )


def _touch(
    state: MapState,
    trace_id: str,
    key: str,
    parent: str | None,
    start: str,
    at: str,
    meta: Mapping[str, JsonValue],
) -> tuple[MapState, list[LangfuseObject], str]:
    """Que el span `key` exista: lo abre la primera vez, y si esta abierto lo alarga.

    El identificador sale de `key`, que lleva el numero; el nombre es la parte
    fija (D-106). Reexportar una tirada antigua renombra el span, no lo duplica.
    """
    sid = _span_id(trace_id, key)
    if key in state.closed:
        return state, [], sid
    for i, span in enumerate(state.spans):
        if span.key == key:
            spans = list(state.spans)
            spans[i] = span.model_copy(update={"last": at})
            return state.model_copy(update={"spans": tuple(spans)}), [], sid
    span = _Span(
        key=key,
        id=sid,
        trace_id=trace_id,
        name=key.split(".", 1)[0],
        meta=meta,
        parent=parent,
        start=start,
        last=at,
    )
    return state.model_copy(update={"spans": (*state.spans, span)}), [_span_object(span)], sid


def _enter(
    state: MapState, trace_id: str, record: TraceRecord, start: str
) -> tuple[MapState, list[LangfuseObject], str | None]:
    """Abre o alarga el span de capitulo y el de escena del registro; devuelve el padre."""
    capitulo, escena = _scope(record.fields)
    if capitulo is None:
        return state, [], None
    state, objetos, padre = _touch(
        state, trace_id, _chapter_key(capitulo), None, start, record.at, {"chapter": capitulo}
    )
    if escena is not None:
        state, mas, padre = _touch(
            state,
            trace_id,
            _scene_key(capitulo, escena),
            padre,
            start,
            record.at,
            {"chapter": capitulo, "scene": escena},
        )
        objetos += mas
    return state, objetos, padre


def _close(
    state: MapState, keys: Callable[[_Span], bool], end: str | None = None
) -> tuple[MapState, list[LangfuseObject]]:
    """Cierra los spans que cumplen `keys`, con su ultimo instante o con `end`."""
    quedan: list[_Span] = []
    objetos: list[LangfuseObject] = []
    cerrados = set(state.closed)
    for span in state.spans:
        if keys(span):
            objetos.append(_span_object(span, end or span.last))
            cerrados.add(span.key)
        else:
            quedan.append(span)
    return state.model_copy(update={"spans": tuple(quedan), "closed": frozenset(cerrados)}), objetos


# ---------------------------------------------------------------- scores

#: RF-265. Lo que marca una coincidencia del guardarrail en los defectos.
_FORBIDDEN_KIND = _FORBIDDEN_MARK


def _create_score(
    trace_id: str,
    record: TraceRecord,
    name: str,
    value: float | bool,
    *,
    target: str | None,
    comment: str | None = None,
    key: object = "",
    meta: Mapping[str, JsonValue] | None = None,
) -> LangfuseScore:
    """Un score con identificador determinista: reexportar lo actualiza, no lo duplica."""
    tipo: ScoreType = "BOOLEAN" if isinstance(value, bool) else "NUMERIC"
    return LangfuseScore(
        id=_hex(trace_id, "score", record.kind, record.seq, record.at, name, key, chars=32),
        trace_id=trace_id,
        observation_id=target,
        name=name,
        value=float(value),
        data_type=tipo,
        comment=comment,
        metadata={"record": record.kind, "seq": record.seq, **dict(meta or {})},
    )


def _targets(trace_id: str, fields: Mapping[str, JsonValue]) -> tuple[str | None, str | None]:
    """El span de la escena y el del capitulo del registro, si los tiene."""
    capitulo, escena = _scope(fields)
    if capitulo is None:
        return None, None
    cap = _span_id(trace_id, _chapter_key(capitulo))
    esc = _span_id(trace_id, _scene_key(capitulo, escena)) if escena is not None else None
    return esc, cap


def _strings(value: object) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else []


def _severities(defects: Sequence[str]) -> tuple[int, int]:
    """S1 y S2 de una lista `kind:severidad` de `scene.attempt`."""
    return (
        sum(1 for d in defects if d.endswith(":S1")),
        sum(1 for d in defects if d.endswith(":S2")),
    )


def _attempt(fields: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    intento = _int(fields.get("attempt"))
    return {"attempt": intento} if intento is not None else {}


Scorer = Callable[[str, TraceRecord], list[LangfuseScore]]


def _score_checks(tid: str, r: TraceRecord) -> list[LangfuseScore]:
    """`check.<kind>` de un intento de escena: cada verificador que corrio, paso o no."""
    esc, cap = _targets(tid, r.fields)
    fallidos = set(_strings(r.fields.get("failed")))
    return [
        _create_score(
            tid, r, kind, kind not in fallidos, target=esc or cap, meta=_attempt(r.fields)
        )
        for kind in _strings(r.fields.get("ran"))
    ]


def _score_scene(tid: str, r: TraceRecord) -> list[LangfuseScore]:
    """`gate.scene` con S1 y S2, y `guardrail.forbidden` cuando no hubo coincidencia."""
    esc, cap = _targets(tid, r.fields)
    objetivo = esc or cap
    defectos = _strings(r.fields.get("defects"))
    s1, s2 = _severities(defectos)
    extra = _attempt(r.fields)
    out = [
        _create_score(
            tid, r, "gate.scene", r.fields.get("passed") is True, target=objetivo, meta=extra
        ),
        _create_score(tid, r, "gate.scene.s1", s1, target=objetivo, meta=extra),
        _create_score(tid, r, "gate.scene.s2", s2, target=objetivo, meta=extra),
    ]
    if not any(d.startswith(_FORBIDDEN_KIND) for d in defectos):
        # La coincidencia tiene su propio score, con nivel y termino (`guardrail.match`).
        out.append(_create_score(tid, r, "guardrail.forbidden", True, target=objetivo, meta=extra))
    return out


def _score_chapter(tid: str, r: TraceRecord) -> list[LangfuseScore]:
    _esc, cap = _targets(tid, r.fields)
    defectos = _strings(r.fields.get("defects"))
    return [
        _create_score(
            tid,
            r,
            "gate.chapter",
            r.fields.get("passed") is True,
            target=cap,
            comment=_str(r.fields.get("reason")),
        ),
        _create_score(tid, r, "gate.chapter.s1", _int(r.fields.get("s1")) or 0, target=cap),
        _create_score(tid, r, "gate.chapter.s2", _int(r.fields.get("s2")) or 0, target=cap),
        _create_score(
            tid,
            r,
            "guardrail.forbidden",
            not any(_FORBIDDEN_KIND in d for d in defectos),
            target=cap,
        ),
    ]


def _score_jury(tid: str, r: TraceRecord) -> list[LangfuseScore]:
    """`jury.<dimension>`, de 1 a 5, con la dispersion y la justificacion como comentario."""
    _esc, cap = _targets(tid, r.fields)
    niveles = r.fields.get("levels")
    dispersiones = r.fields.get("spreads")
    justificaciones = r.fields.get("justifications")
    out: list[LangfuseScore] = []
    if not isinstance(niveles, dict):
        return out
    for dim, nivel in niveles.items():
        if not isinstance(nivel, int | float) or isinstance(nivel, bool):
            continue
        partes = []
        if isinstance(dispersiones, dict) and dispersiones.get(dim) is not None:
            partes.append(f"dispersion={dispersiones[dim]}")
        if isinstance(justificaciones, dict) and isinstance(justificaciones.get(dim), str):
            limpio = _scrub(justificaciones[dim], hide_text=False)
            partes.append(str(limpio))
        out.append(
            _create_score(
                tid, r, f"jury.{dim}", float(nivel), target=cap, comment="; ".join(partes) or None
            )
        )
    return out


def _score_quiz(tid: str, r: TraceRecord) -> list[LangfuseScore]:
    _esc, cap = _targets(tid, r.fields)
    return [_create_score(tid, r, "quiz.wrong", _int(r.fields.get("wrong")) or 0, target=cap)]


def _flag(name: str, field: str) -> Scorer:
    """Un booleano sobre la traza: la tirada o el acto no tienen span propio."""

    def score(tid: str, r: TraceRecord) -> list[LangfuseScore]:
        act = _int(r.fields.get("act"))
        comentario = f"acto {act}" if act is not None else _str(r.fields.get("reason"))
        return [
            _create_score(
                tid, r, name, r.fields.get(field) is True, target=None, comment=comentario
            )
        ]

    return score


def _score_formal(tid: str, r: TraceRecord) -> list[LangfuseScore]:
    """`formal.lean`, con el teorema que fallo como comentario (RF-254, RF-265)."""
    esc, cap = _targets(tid, r.fields)
    paso = r.fields.get("passed", r.fields.get("ok"))
    comentario = None
    if paso is not True:
        comentario = _str(r.fields.get("theorem")) or _str(r.fields.get("rule"))
    return [
        _create_score(tid, r, "formal.lean", paso is True, target=esc or cap, comment=comentario)
    ]


def _score_match(tid: str, r: TraceRecord) -> list[LangfuseScore]:
    """RF-265, RNF-54. Una coincidencia: el nivel y el termino como sha256 recortado."""
    esc, cap = _targets(tid, r.fields)
    termino = r.fields.get("term")
    huella = term_hash(termino) if isinstance(termino, str) else None
    nivel = _str(r.fields.get("level"))
    return [
        _create_score(
            tid,
            r,
            "guardrail.forbidden",
            False,
            target=esc or cap,
            comment=f"nivel={nivel}; termino=sha256:{huella}",
            key=huella,
            meta={
                "level": nivel,
                "term_hash": huella,
                "decision": _str(r.fields.get("decision")),
                "stage": _str(r.fields.get("stage")),
                **_attempt(r.fields),
            },
        )
    ]


#: RF-265, `architecture.md` §11. Cada registro de verificador y el score que da.
#: Un registro nuevo tiene que estar aqui o en `UNSCORED`: la prueba lo exige.
SCORERS: Mapping[str, Scorer] = {
    "scene.checks": _score_checks,
    "scene.attempt": _score_scene,
    "chapter.gate": _score_chapter,
    "jury": _score_jury,
    "quiz": _score_quiz,
    "outline.check": _flag("outline.check", "passed"),
    "act.gate": _flag("act.gate", "passed"),
    "work.close": _flag("work.close", "closed"),
    "formal.lean": _score_formal,
    "guardrail.match": _score_match,
}

#: Registros que no son el resultado de un verificador: no llevan score.
UNSCORED: frozenset[str] = frozenset(
    {
        "admission",
        "amend.applied",
        "amend.rejected",
        "amend.request",
        "amend.usage_mismatch",
        "arbitration",
        "audit",
        "calibration",
        "call",
        "chapter.frozen",
        "chapter.resumed",
        "export.disabled",
        "export.failed",
        "golden",
        "guardrail.levels",
        "health",
        "interview.created",
        "interview.turn",
        "outline.resumed",
        "packet",
        "process.defect",
        "proscription",
        "repair",
        "replan",
        "respec",
        "retcon.aborted",
        "retcon.applied",
        "retcon.proposal",
        "retry",
        "scene.resumed",
        "style.fingerprint",
        "style.polish",
        "summary",
        "tool",
        "work.cost",
    }
)


def scores_of(trace_id: str, record: TraceRecord) -> list[LangfuseScore]:
    """RF-265. Los scores de un registro; ninguno si no es de verificador."""
    scorer = SCORERS.get(record.kind)
    return scorer(trace_id, record) if scorer else []


# ---------------------------------------------------------------- generaciones


def _request_id(record: TraceRecord) -> int | None:
    """La solicitud de cambio a la que pertenece un registro, si la nombra (RF-234, RF-262)."""
    return _int(record.fields.get("request"))


def _change_request(
    state: MapState, record: TraceRecord, rid: int
) -> tuple[MapState, tuple[LangfuseObject, ...]]:
    """RF-234. La solicitud de cambio, de `amend.request` a su aplicacion o rechazo.

    Cuelga de ella todo registro que nombre su numero: la llamada de
    `amend.interpret` que la interpreto (RF-262) y lo que la aplico.
    """
    tid = generation_id(state.source, "change_request", rid)
    meta: dict[str, JsonValue] = {"source": state.source, "type": "change_request", "request": rid}
    objetos: list[LangfuseObject] = []
    if record.kind == "amend.request":
        pedido = {k: v for k, v in _metadata(record).items() if k not in _BOOKKEEPING}
        objetos.append(
            LangfuseTrace(
                id=tid,
                name="change_request",
                session_id=state.session_id,
                timestamp=record.at,
                metadata=meta,
                input=pedido,
            )
        )
    elif record.kind in ("amend.applied", "amend.rejected"):
        final = "applied" if record.kind == "amend.applied" else "rejected"
        salida: dict[str, JsonValue] = {"status": final}
        for k in ("version", "reason"):
            if k in record.fields:
                salida[k] = record.fields[k]
        objetos.append(
            LangfuseTrace(
                id=tid,
                name="change_request",
                session_id=state.session_id,
                metadata=meta,
                output=salida,
            )
        )
    objetos.append(_observation(tid, record, None))
    objetos += scores_of(tid, record)
    return state, tuple(objetos)


def _opening(state: MapState, record: TraceRecord) -> tuple[_Open, LangfuseTrace]:
    """Abre la generacion que empieza en este registro."""
    if state.mode == "interview":
        # Una sola traza por fichero de entrevista: cada ruta abre su propia
        # instancia de `Trace`, y el primer registro de cada una no la separa.
        tid = generation_id(state.source, "interview", 0)
        abierta = _Open(trace_id=tid, name="interview")
        return abierta, LangfuseTrace(
            id=tid,
            name="interview",
            session_id=state.session_id,
            timestamp=record.at if record.kind == "interview.created" else None,
            metadata={"source": state.source, "type": "interview"},
            input={"interview": state.source},
        )
    invocacion = record.fields.get("invocation") if record.kind == "calibration" else None
    gtype: GenerationType = "amend" if invocacion == "amend" else "run"
    tid = generation_id(state.source, gtype, record.seq, record.at)
    abierta = _Open(trace_id=tid, name=gtype)
    traza = LangfuseTrace(
        id=tid,
        name=gtype,
        session_id=state.session_id,
        timestamp=record.at,
        metadata={
            "source": state.source,
            "type": gtype,
            "first_seq": record.seq,
            "first_at": record.at,
        },
        # D-106. Lo que identifica la invocacion de un vistazo; la salida la
        # ponen `work.close` y `work.cost` al cerrarla.
        input={
            "novel": state.session_id,
            "invocation": gtype,
            **(
                {"model": record.fields["model"]}
                if record.kind == "calibration" and isinstance(record.fields.get("model"), str)
                else {}
            ),
        },
    )
    return abierta, traza


#: Registros que cierran o describen el final de una invocacion. Lo que llevan
#: pasa a la salida de su traza.
_CLOSING_FIELDS: Mapping[str, tuple[str, ...]] = {
    "work.close": ("closed", "reason", "words"),
    "work.cost": (
        "calls",
        "input_tokens",
        "output_tokens",
        "cache_creation_tokens",
        "cache_read_tokens",
        "cost_usd",
        "calls_without_cost",
        "duration_ms",
    ),
}


def _start_of(record: TraceRecord) -> str:
    """Cuando empezo lo que el registro describe: una llamada, su duracion antes."""
    if record.kind in ("call", "tool"):
        return _minus_ms(record.at, _int(record.fields.get("duration_ms")) or 0)
    return record.at


def step(state: MapState, record: TraceRecord) -> tuple[MapState, tuple[LangfuseObject, ...]]:
    """Un registro de la traza y lo que le toca en Langfuse. **Pura** (RF-233).

    Devuelve el estado siguiente y los objetos, en orden: una traza que se abre
    va antes que sus spans, un span antes que lo que cuelga de el, y una traza
    que se actualiza al cerrar va despues de la observacion que la cierra.
    """
    if record.kind.startswith(_OWN_PREFIX):
        return state, ()

    rid = _request_id(record) if state.mode == "novel" else None
    if rid is not None:
        return _change_request(state, record, rid)

    objetos: list[LangfuseObject] = []
    abierta = state.open
    # Una `calibration` es el arranque de una invocacion nueva: si la anterior
    # no llego a su `work.cost` --una caida--, se da por terminada sin mas.
    if abierta is None or (record.kind == "calibration" and state.mode == "novel"):
        state, cierres = _close(state, lambda _s: True)
        objetos += cierres
        abierta, traza = _opening(state, record)
        state = state.model_copy(update={"spans": (), "closed": frozenset()})
        objetos.append(traza)

    tid = abierta.trace_id
    # La herramienta llega antes que su generation y abre el span si hace falta:
    # las dos cuelgan de el como hermanas (D-106).
    state, spans, padre = _enter(state, tid, record, _start_of(record))
    objetos += spans
    objetos.append(_observation(tid, record, padre))
    objetos += scores_of(tid, record)

    if record.kind == "chapter.frozen":
        capitulo = _int(record.fields.get("chapter"))
        if capitulo is not None:
            prefijos = (_chapter_key(capitulo), f"scene.{capitulo}.")
            state, cierres = _close(
                state,
                lambda s: s.key == prefijos[0] or s.key.startswith(prefijos[1]),
                record.at,
            )
            objetos += cierres

    campos = _CLOSING_FIELDS.get(record.kind)
    if campos is not None:
        salida = dict(abierta.output)
        salida.update({k: record.fields[k] for k in campos if k in record.fields})
        abierta = abierta.model_copy(update={"output": salida})
        objetos.append(
            LangfuseTrace(
                id=abierta.trace_id,
                name=abierta.name,
                session_id=state.session_id,
                output=salida,
            )
        )
    if record.kind == "work.cost":
        state, cierres = _close(state, lambda _s: True)
        objetos += cierres
        abierta = None
    return state.model_copy(update={"open": abierta}), tuple(objetos)


def to_langfuse(
    records: Iterable[TraceRecord], *, source: str, session_id: str, mode: Mode = "novel"
) -> list[LangfuseObject]:
    """RF-233. Todos los objetos de una traza: `step` plegado sobre sus registros."""
    state = MapState(source=source, session_id=session_id, mode=mode)
    out: list[LangfuseObject] = []
    for record in records:
        state, objetos = step(state, record)
        out.extend(objetos)
    return out


def mode_of(source: str) -> Mode:
    """La traza de una entrevista vive en `_interviews/` (RD-46)."""
    return "interview" if source.startswith("_interviews/") else "novel"


def session_of(trace_path: Path) -> str:
    """La novela de una traza, por su nombre de fichero (`commons/settings.py`)."""
    nombre = trace_path.name
    return nombre[: -len(TRACE_SUFFIX)] if nombre.endswith(TRACE_SUFFIX) else trace_path.stem


# ---------------------------------------------------------------- coste de la obra


def work_cost(records: Iterable[TraceRecord]) -> dict[str, JsonValue]:
    """RF-235. Tokens y coste totales de la novela, sumados de sus registros `call`.

    El coste suma solo lo declarado: si ninguna llamada lo declaro es nulo, y
    las que no lo declararon se cuentan aparte para que el total no parezca
    completo cuando no lo es.
    """
    llamadas = 0
    entrada = salida = creados = leidos = sin_coste = duracion = 0
    coste = 0.0
    alguno = False
    for r in records:
        if r.kind != "call":
            continue
        f = r.fields
        llamadas += 1
        entrada += _int(f.get("real_input")) or 0
        salida += _int(f.get("output_tokens")) or 0
        creados += _int(f.get("cache_creation_tokens")) or 0
        leidos += _int(f.get("cache_read_tokens")) or 0
        duracion += _int(f.get("duration_ms")) or 0
        c = f.get("cost_usd")
        if isinstance(c, int | float) and not isinstance(c, bool):
            coste += float(c)
            alguno = True
        else:
            sin_coste += 1
    return {
        "calls": llamadas,
        "input_tokens": entrada,
        "output_tokens": salida,
        "cache_creation_tokens": creados,
        "cache_read_tokens": leidos,
        "cost_usd": round(coste, 6) if alguno else None,
        "calls_without_cost": sin_coste,
        "duration_ms": duracion,
    }


# ---------------------------------------------------------------- cliente


class LangfuseClient(Protocol):
    """Lo unico que el espejo necesita de Langfuse: enviar objetos."""

    def send(self, objects: Sequence[LangfuseObject]) -> None: ...


#: D-106. Variable estandar del SDK de Langfuse para el entorno. Opcional: sin
#: ella, Langfuse usa `default`. No es una clave y no condiciona el espejo.
ENV_ENVIRONMENT = "LANGFUSE_TRACING_ENVIRONMENT"

#: La regla de Langfuse para un nombre de entorno: minusculas, cifras, `-` y
#: `_`, hasta 40 caracteres y sin empezar por `langfuse`. Uno que no la cumple
#: haria rechazar el lote entero, asi que se ignora.
_ENVIRONMENT = re.compile(r"^(?!langfuse)[a-z0-9_-]{1,40}$")


@dataclass(frozen=True)
class LangfuseConfig:
    """Las tres variables de RI-60 y el entorno opcional. `repr` no ensena ningun valor."""

    public_key: str
    secret_key: str
    base_url: str
    environment: str | None = None

    def __repr__(self) -> str:
        return (
            "LangfuseConfig(public_key=***, secret_key=***, base_url=***, "
            f"environment={self.environment!r})"
        )

    @property
    def secrets(self) -> tuple[str, ...]:
        return tuple(v for v in (self.public_key, self.secret_key) if v)


def missing_keys(env: Mapping[str, str] | None = None) -> list[str]:
    """Los nombres de las variables de RI-60 que faltan. Solo nombres."""
    fuente = os.environ if env is None else env
    return [k for k in ENV_KEYS if not fuente.get(k)]


def config_from_env(env: Mapping[str, str] | None = None) -> LangfuseConfig | None:
    fuente = os.environ if env is None else env
    if missing_keys(fuente):
        return None
    entorno = fuente.get(ENV_ENVIRONMENT) or None
    return LangfuseConfig(
        public_key=fuente["LANGFUSE_PUBLIC_KEY"],
        secret_key=fuente["LANGFUSE_SECRET_KEY"],
        base_url=fuente["LANGFUSE_BASE_URL"],
        environment=entorno if entorno and _ENVIRONMENT.match(entorno) else None,
    )


def library_available() -> bool:
    """Si `langfuse` esta instalada, sin importarla: el import es perezoso."""
    return importlib.util.find_spec("langfuse") is not None


def _iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


class SdkClient:
    """`LangfuseClient` sobre el SDK de Langfuse, por la API de ingestion.

    Se usa la ingestion y no el trazado OpenTelemetry del SDK porque es la via
    que acepta identificadores y marcas de tiempo propias: el lote exporta
    tiradas pasadas con sus horas reales, y el mismo `id` actualiza en vez de
    duplicar (RF-234). El SDK se importa aqui, al primer envio: sin la libreria
    el sistema funciona igual (RI-60).

    **El enlace al prompt** (RF-266). Langfuse enlaza una generation con la
    version numerada de un prompt. El numero lo asigna Langfuse al publicar, asi
    que el cliente lo resuelve una vez por agente y etiqueta, en el hilo del
    espejo, y lo recuerda. Nunca usa el texto: la tirada ya se hizo con el del
    repositorio (D-86). Si la etiqueta no esta publicada, la generation sale sin
    enlace y con nombre y etiqueta en sus metadatos.
    """

    def __init__(self, config: LangfuseConfig) -> None:
        from langfuse import Langfuse

        self._client = Langfuse(
            public_key=config.public_key,
            secret_key=config.secret_key,
            base_url=config.base_url,
            tracing_enabled=False,
        )
        self._environment = config.environment
        self._versions: dict[tuple[str, str], int | None] = {}

    def send(self, objects: Sequence[LangfuseObject]) -> None:
        eventos = [self._event(o, self._prompt_version(o), self._environment) for o in objects]
        lote: list[Any] = []
        tam = 0
        for evento in eventos:
            peso = len(evento.json().encode("utf-8"))
            if lote and tam + peso > BATCH_BYTES:
                self._client.api.ingestion.batch(batch=lote)
                lote, tam = [], 0
            lote.append(evento)
            tam += peso
        if lote:
            self._client.api.ingestion.batch(batch=lote)

    def _prompt_version(self, obj: LangfuseObject) -> int | None:
        if not isinstance(obj, LangfuseObservation) or not (obj.prompt_name and obj.prompt_label):
            return None
        clave = (obj.prompt_name, obj.prompt_label)
        if clave not in self._versions:
            try:
                prompt = self._client.api.prompts.get(obj.prompt_name, label=obj.prompt_label)
                self._versions[clave] = int(prompt.version)
            except Exception:  # sin publicar o sin red: sin enlace, nunca sin exportar
                self._versions[clave] = None
        return self._versions[clave]

    @staticmethod
    def _event(
        obj: LangfuseObject, prompt_version: int | None = None, environment: str | None = None
    ) -> Any:
        from langfuse import api

        ahora = datetime.now(UTC).isoformat(timespec="milliseconds")
        sobre = str(uuid.uuid4())  # el sobre es unico por envio; el cuerpo, estable
        if isinstance(obj, LangfuseTrace):
            return api.IngestionEvent_TraceCreate(
                id=sobre,
                timestamp=ahora,
                body=api.TraceBody(
                    id=obj.id,
                    timestamp=_iso(obj.timestamp) if obj.timestamp else None,
                    name=obj.name,
                    session_id=obj.session_id,
                    metadata=dict(obj.metadata),
                    input=dict(obj.input) if obj.input is not None else None,
                    output=dict(obj.output) if obj.output is not None else None,
                    environment=environment,
                ),
            )
        if isinstance(obj, LangfuseScore):
            return api.IngestionEvent_ScoreCreate(
                id=sobre,
                timestamp=ahora,
                body=api.ScoreBody(
                    id=obj.id,
                    trace_id=obj.trace_id,
                    observation_id=obj.observation_id,
                    name=obj.name,
                    value=obj.value,
                    data_type=cast(Any, obj.data_type),
                    comment=obj.comment,
                    metadata=dict(obj.metadata),
                    environment=environment,
                ),
            )
        if obj.type == "generation":
            return api.IngestionEvent_GenerationCreate(
                id=sobre,
                timestamp=ahora,
                body=api.CreateGenerationBody(
                    id=obj.id,
                    trace_id=obj.trace_id,
                    name=obj.name,
                    start_time=_iso(obj.start_time),
                    end_time=_iso(obj.end_time) if obj.end_time else None,
                    parent_observation_id=obj.parent_observation_id,
                    metadata={
                        **dict(obj.metadata),
                        "prompt_name": obj.prompt_name,
                        "prompt_label": obj.prompt_label,
                    },
                    model=obj.model,
                    usage_details=dict(obj.usage_details) if obj.usage_details else None,
                    cost_details=dict(obj.cost_details) if obj.cost_details else None,
                    level=cast(Any, obj.level),
                    status_message=obj.status_message,
                    prompt_name=obj.prompt_name if prompt_version is not None else None,
                    prompt_version=prompt_version,
                    environment=environment,
                ),
            )
        if obj.type == "span":
            return api.IngestionEvent_SpanCreate(
                id=sobre,
                timestamp=ahora,
                body=api.CreateSpanBody(
                    id=obj.id,
                    trace_id=obj.trace_id,
                    name=obj.name,
                    start_time=_iso(obj.start_time),
                    end_time=_iso(obj.end_time) if obj.end_time else None,
                    parent_observation_id=obj.parent_observation_id,
                    metadata=dict(obj.metadata),
                    environment=environment,
                ),
            )
        if obj.type == "event":
            return api.IngestionEvent_EventCreate(
                id=sobre,
                timestamp=ahora,
                body=api.CreateEventBody(
                    id=obj.id,
                    trace_id=obj.trace_id,
                    name=obj.name,
                    start_time=_iso(obj.start_time),
                    parent_observation_id=obj.parent_observation_id,
                    metadata=dict(obj.metadata),
                    level=cast(Any, obj.level),
                    environment=environment,
                ),
            )
        # tool, retriever, evaluator y guardrail: la observacion generica con su tipo.
        return api.IngestionEvent_ObservationCreate(
            id=sobre,
            timestamp=ahora,
            body=api.ObservationBody(
                id=obj.id,
                trace_id=obj.trace_id,
                type=cast(Any, api.ObservationType(obj.type.upper())),
                name=obj.name,
                start_time=_iso(obj.start_time),
                end_time=_iso(obj.end_time) if obj.end_time else None,
                parent_observation_id=obj.parent_observation_id,
                metadata=dict(obj.metadata),
                input=obj.input,
                output=obj.output,
                level=cast(Any, obj.level),
                status_message=obj.status_message,
                environment=environment,
            ),
        )


def _redact(text: str, secrets: Sequence[str]) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "[CLAVE_OCULTA]")
    return text


# ---------------------------------------------------------------- conductor en vivo


class _LiveObserver:
    """El observador de una traza: su estado de correspondencia y su cola."""

    def __init__(self, exporter: LiveExporter, trace: Trace, source: str) -> None:
        self.exporter = exporter
        self._trace = weakref.ref(trace)
        self._state = MapState(
            source=source, session_id=session_of(Path(source)), mode=mode_of(source)
        )

    def __call__(self, record: TraceRecord) -> None:
        self._state, objetos = step(self._state, record)
        traza = self._trace()
        if objetos and traza is not None:
            self.exporter.enqueue(traza, objetos)


class LiveExporter:
    """RF-233, RNF-53. Un hilo y una cola acotada por proceso, para todas las trazas.

    `enqueue` nunca bloquea: si la cola esta llena, descarta y lo cuenta, y lo
    descartado sigue en el JSONL. El hilo arranca con el primer envio y el
    cliente se construye dentro de el, asi que ni el import del SDK ni la red
    tocan el hilo de la tirada.
    """

    def __init__(
        self,
        client_factory: Callable[[], LangfuseClient],
        *,
        max_queue: int = QUEUE_MAX,
        secrets: Sequence[str] = (),
    ) -> None:
        self._factory = client_factory
        self._queue: queue.Queue[tuple[Trace, tuple[LangfuseObject, ...]] | None] = queue.Queue(
            maxsize=max_queue
        )
        self._secrets = tuple(secrets)
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._dropped: dict[int, tuple[weakref.ref[Trace], int]] = {}
        self._traces: weakref.WeakSet[Trace] = weakref.WeakSet()
        self._client: LangfuseClient | None = None
        self.sent = 0

    # ------------------------------------------------------------ observadores

    def observer_for(self, trace: Trace) -> _LiveObserver | None:
        """Fabrica de observadores de `Trace`: uno por traza con fichero."""
        if trace.path is None or trace in self._traces:
            return None
        self._traces.add(trace)
        return _LiveObserver(self, trace, _source_of(trace.path))

    def ensure(self, trace: Trace) -> None:
        """Que esta traza este observada, aunque se abriera antes de instalar el espejo."""
        observador = self.observer_for(trace)
        if observador is not None:
            trace.subscribe(observador)

    def enqueue(self, trace: Trace, objects: tuple[LangfuseObject, ...]) -> None:
        """Encola sin bloquear nunca. Corre dentro del cerrojo de la traza."""
        self._start()
        try:
            self._queue.put_nowait((trace, objects))
        except queue.Full:
            with self._lock:
                _, n = self._dropped.get(id(trace), (weakref.ref(trace), 0))
                self._dropped[id(trace)] = (weakref.ref(trace), n + len(objects))

    # ------------------------------------------------------------------ hilo

    def _start(self) -> None:
        if self._thread is not None:
            return
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._work, name="langfuse-export", daemon=True
                )
                self._thread.start()

    def _work(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                self._queue.task_done()
                return
            lote = [item]
            while True:
                try:
                    siguiente = self._queue.get_nowait()
                except queue.Empty:
                    break
                if siguiente is None:
                    self._queue.put_nowait(None)  # que el cierre llegue tras este lote
                    self._queue.task_done()
                    break
                lote.append(siguiente)
            try:
                self._send(lote)
            finally:
                for _ in lote:
                    self._queue.task_done()

    def _send(self, lote: list[tuple[Trace, tuple[LangfuseObject, ...]]]) -> None:
        objetos = [o for _, objs in lote for o in objs]
        try:
            if self._client is None:
                self._client = self._factory()
            self._client.send(objetos)
            self.sent += len(objetos)
        except Exception as exc:  # RNF-53: el espejo observa y no gobierna
            motivo = _redact(f"{type(exc).__name__}: {exc}", self._secrets)[:300]
            por_traza: dict[int, tuple[Trace, int]] = {}
            for traza, objs in lote:
                _, n = por_traza.get(id(traza), (traza, 0))
                por_traza[id(traza)] = (traza, n + len(objs))
            for traza, n in por_traza.values():
                traza.failures += 1
                traza.emit("export.failed", error=motivo, objects=n)
        self._report_drops()

    def _report_drops(self) -> None:
        with self._lock:
            caidos = list(self._dropped.values())
            self._dropped.clear()
        for ref, n in caidos:
            traza = ref()
            if traza is not None and n:
                traza.failures += 1
                traza.emit("export.failed", error="cola llena", objects=n)

    # --------------------------------------------------------------- control

    def drain(self, timeout: float) -> bool:
        """Espera a que la cola se vacie, con plazo. Solo para pruebas y el lote.

        Una tirada nunca llama a esto: cerrar no espera a la red (RNF-53).
        """
        fin = threading.Event()

        def esperar() -> None:
            self._queue.join()
            fin.set()

        threading.Thread(target=esperar, daemon=True).start()
        return fin.wait(timeout)

    def close(self) -> None:
        """Pide al hilo que termine tras lo encolado. No espera."""
        if self._thread is None:
            return
        with contextlib.suppress(queue.Full):
            self._queue.put_nowait(None)


def _source_of(trace_path: Path) -> str:
    """El fichero de la traza relativo al directorio de tiradas: estable entre maquinas."""
    if trace_path.parent.name == "_interviews":
        return f"_interviews/{trace_path.name}"
    return trace_path.name


# ---------------------------------------------------------------- instalacion

_LIVE: LiveExporter | None = None
_DISABLED_NOTED: set[str] = set()
_INSTALL_LOCK = threading.Lock()


def live_exporter() -> LiveExporter | None:
    return _LIVE


def install_live_export(
    env: Mapping[str, str] | None = None,
    *,
    client_factory: Callable[[], LangfuseClient] | None = None,
) -> LiveExporter | None:
    """Engancha el conductor en vivo a toda traza con fichero que se abra desde ahora.

    Idempotente. Sin las tres variables, o sin la libreria cuando no se da otro
    cliente, no engancha nada y devuelve `None`: la tirada es la misma (RI-60).
    """
    global _LIVE
    with _INSTALL_LOCK:
        if _LIVE is not None:
            return _LIVE
        config = config_from_env(env)
        if config is None:
            return None
        if client_factory is None:
            if not library_available():
                return None
            factory: Callable[[], LangfuseClient] = lambda: SdkClient(config)  # noqa: E731
        else:
            factory = client_factory
        _LIVE = LiveExporter(factory, secrets=config.secrets)
        add_observer_factory(_LIVE.observer_for)
        return _LIVE


def uninstall_live_export() -> None:
    """Desengancha el conductor en vivo. Lo encolado se sigue enviando."""
    global _LIVE
    with _INSTALL_LOCK:
        if _LIVE is not None:
            remove_observer_factory(_LIVE.observer_for)
            _LIVE.close()
            _LIVE = None
        _DISABLED_NOTED.clear()


def attach_live_export(trace: Trace, env: Mapping[str, str] | None = None) -> LiveExporter | None:
    """Lo que hace una invocacion del Orquestador al arrancar (RI-60).

    Con espejo, se asegura de que su traza esta observada. Sin el, deja
    `export.disabled` en la traza una sola vez por fichero y proceso, con los
    nombres de lo que falta y nunca sus valores, y sigue.
    """
    live = install_live_export(env)
    if live is not None:
        live.ensure(trace)
        return live
    if trace.path is None:
        return None
    clave = str(trace.path.resolve())
    with _INSTALL_LOCK:
        if clave in _DISABLED_NOTED:
            return None
        _DISABLED_NOTED.add(clave)
    faltan = missing_keys(env)
    trace.emit(
        "export.disabled",
        missing=list(faltan),
        reason="faltan variables" if faltan else "falta la libreria langfuse",
    )
    return None


# ---------------------------------------------------------------- conductor por lote


def interview_trace_path(runs_dir: Path, interview_id: str) -> Path:
    """La traza de una entrevista (`specs/srs-backend-v4.md` RD-46), por `commons/settings.py`."""
    from commons.settings import Settings

    return Settings(runs_dir=runs_dir).interview_trace_path(interview_id)


def origin_interviews(novel_path: Path) -> list[str]:
    """Las entrevistas de las que salio una novela, segun su brief (`origin_interview`).

    Se lee el SQLite en solo lectura y sin importar `canon/`, que esta encima de
    `commons/`. Un brief sin el campo --los anteriores a RD-42-- no tiene ninguna.
    """
    if not novel_path.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{novel_path.as_posix()}?mode=ro", uri=True)
        try:
            fila = con.execute(
                "SELECT body FROM document_version WHERE doc_kind = 'brief' "
                "ORDER BY version DESC LIMIT 1"
            ).fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return []
    if fila is None:
        return []
    try:
        origen = json.loads(fila[0]).get("origin_interview")
    except (ValueError, AttributeError):
        return []
    from commons.settings import INTERVIEW_ID

    # El brief llega por RI-01 y el campo es texto: solo un identificador de
    # entrevista valido se convierte en ruta.
    return [origen] if isinstance(origen, str) and INTERVIEW_ID.match(origen) else []


def novel_objects(
    novel_id: str, runs_dir: Path, *, interviews: Sequence[str] | None = None
) -> list[LangfuseObject]:
    """RI-61. Los objetos de una novela: su traza y la de sus entrevistas, sesion `novel_id`."""
    iids = (
        list(interviews)
        if interviews is not None
        else origin_interviews(runs_dir / f"{novel_id}.sqlite")
    )
    objetos = interview_objects(novel_id, runs_dir, iids)
    ruta = runs_dir / f"{novel_id}{TRACE_SUFFIX}"
    objetos += to_langfuse(_read(ruta), source=_source_of(ruta), session_id=novel_id)
    return objetos


def interview_objects(
    novel_id: str, runs_dir: Path, interviews: Sequence[str]
) -> list[LangfuseObject]:
    """RF-262. Las trazas de las entrevistas de una novela, con la novela como sesion."""
    objetos: list[LangfuseObject] = []
    for iid in interviews:
        ruta = interview_trace_path(runs_dir, iid)
        objetos += to_langfuse(
            _read(ruta), source=_source_of(ruta), session_id=novel_id, mode="interview"
        )
    return objetos


def link_interviews(novel_id: str, runs_dir: Path) -> int:
    """RF-262. Al crear la novela, su entrevista pasa a la sesion de la novela.

    Mientras dura, la entrevista va al espejo con su propio identificador como
    sesion: todavia no hay novela. Al crearla con `origin_interview`, se reenvia
    con el de la novela, y como los identificadores de sus objetos no cambian,
    se actualizan y no se duplican. Sin espejo no hace nada. Nunca lanza: un
    fallo queda como `export.failed` en la traza de la novela.
    """
    live = live_exporter()
    if live is None:
        return 0
    from commons.settings import Settings

    settings = Settings(runs_dir=runs_dir)
    try:
        iids = origin_interviews(settings.novel_path(novel_id))
        objetos = interview_objects(novel_id, runs_dir, iids)
    except Exception as exc:  # RNF-53: el espejo observa y no gobierna
        with contextlib.suppress(Exception):
            Trace(settings.trace_path(novel_id)).emit(
                "export.failed", error=f"{type(exc).__name__}: {exc}"[:300], objects=0
            )
        return 0
    if objetos:
        live.enqueue(Trace(settings.trace_path(novel_id)), tuple(objetos))
    return len(objetos)


def _read(path: Path) -> list[TraceRecord]:
    """Los registros del fichero, sin abrir una `Trace`: el lote no escribe en el JSONL."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        return [TraceRecord.model_validate(json.loads(line)) for line in fh if line.strip()]


def export_novel(
    novel_id: str,
    runs_dir: Path,
    client: LangfuseClient,
    *,
    interviews: Sequence[str] | None = None,
) -> int:
    """RI-61. Reexporta una novela entera. Devuelve cuantos objetos envio.

    No escribe en la traza: una novela terminada, o una tirada en marcha, no
    gana lineas por exportarla. Un fallo sube a quien lo llama.
    """
    objetos = novel_objects(novel_id, runs_dir, interviews=interviews)
    if objetos:
        client.send(objetos)
    return len(objetos)


def main(argv: list[str] | None = None) -> int:
    """`python -m commons.tracing.langfuse_export --novel <id> [--runs-dir <dir>]`."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--novel", required=True)
    parser.add_argument("--runs-dir", type=Path, default=None)
    parser.add_argument(
        "--interview",
        action="append",
        default=None,
        help="Entrevista de origen; sin esta opcion se lee `origin_interview` del brief",
    )
    args = parser.parse_args(argv)

    from commons.settings import Settings

    runs = args.runs_dir if args.runs_dir else Settings.from_env().runs_dir
    Settings(runs_dir=runs).novel_path(args.novel)  # valida el identificador
    config = config_from_env()
    if config is None:
        sys.stderr.write(f"export.disabled: faltan {', '.join(missing_keys())}\n")
        return 2
    if not library_available():
        sys.stderr.write("export.disabled: falta la libreria langfuse\n")
        return 2
    try:
        n = export_novel(args.novel, runs, SdkClient(config), interviews=args.interview)
    except Exception as exc:
        motivo = _redact(f"{type(exc).__name__}: {exc}", config.secrets)[:300]
        sys.stderr.write(f"export.failed: {motivo}\n")
        return 1
    print(json.dumps({"novel": args.novel, "objects": n}, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
