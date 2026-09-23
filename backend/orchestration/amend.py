"""Enmiendas al brief: la solicitud de cambio del lector, de la peticion a la version nueva.

RF-221 a RF-227, RNF-50. `specs/srs-backend-v3.md` §4.4, `architecture.md` §8.
La solicitud es un encargo, no una revision: quien encarga dice que pide y el
sistema decide, solo, como se escribe. El Orquestador la aplica (D-53 del
frontend) porque es el unico que puede componer el Reparador con el canon.

Tres momentos:

1. **Crear** (RI-47): se interpreta con `amend.interpret` y el codigo valida la
   interpretacion. Queda `queued` o `rejected` con su motivo, en la misma llamada
   (D-82).
2. **Aplicar**, de una en una y en orden (D-77): se reescriben las escenas que
   nombran el hecho con el Reparador y el hecho nuevo delante, se reverifican, y
   se recongelan junto con el evento de procedencia `brief` en una sola
   transaccion. Un defecto cuya evidencia es el valor nuevo es la enmienda misma
   y no cuenta (D-78); cualquier otro S1 la rechaza y no toca nada.
3. **Leer** (RI-48, RI-49): el estado lo cambia solo el backend (RI-51).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from brief.interpret import NAME, Candidate, Interpreter, TooLongError, validate
from canon import manuscript
from canon.arbiter import refreeze
from canon.arbiter.retcon import RetconPlan
from canon.db import connection
from canon.events import log
from canon.events.types import AttributeSet, EntityRenamed, Event
from canon.prose_index import usage
from canon.prose_index.reindex import scene_texts
from commons.tracing.trace import Trace
from commons.types.primitives import Provenance, Severity, WorldTime
from orchestration.loop import Engine


class FragmentAnchor(BaseModel):
    """Una seleccion del lector: la cita literal, sin recortar ni normalizar (RD-30 del frontend)."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["fragment"] = "fragment"
    version: int = Field(ge=1)
    chapter: int = Field(ge=1)
    scene_id: str = Field(min_length=1, max_length=200)
    quote: str = Field(min_length=1, max_length=20_000)


class FactAnchor(BaseModel):
    """Un hecho de la ficha: entidad y atributo."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["fact"] = "fact"
    entity_id: str = Field(min_length=1, max_length=200)
    attribute: str = Field(min_length=1, max_length=200)


Anchor = FragmentAnchor | FactAnchor


class RejectedError(Exception):
    """La solicitud no se puede aplicar. El mensaje es el motivo, en palabras."""


# ---------------------------------------------------------------- crear


def _candidates(con: object, ids: Sequence[str]) -> list[Candidate]:
    out = []
    for eid in dict.fromkeys(ids):
        row = con.execute("SELECT id, kind, name FROM entity WHERE id = ?", (eid,)).fetchone()  # type: ignore[attr-defined]
        if row is None:
            continue
        aliases = tuple(
            r["alias"]
            for r in con.execute(  # type: ignore[attr-defined]
                "SELECT alias FROM entity_alias WHERE entity_id = ? AND valid_to IS NULL", (eid,)
            )
        )
        attrs = tuple(
            (r["name"], r["value"])
            for r in con.execute(  # type: ignore[attr-defined]
                "SELECT name, value FROM attribute WHERE entity_id = ? AND valid_to IS NULL ORDER BY name",
                (eid,),
            )
        )
        out.append(
            Candidate(
                entity_id=row["id"],
                kind=row["kind"],
                name=row["name"],
                aliases=aliases,
                attributes=attrs,
            )
        )
    return out


def anchor_context(path: Path, anchor: Anchor) -> tuple[str, list[Candidate]]:
    """Que dice el ancla y que entidades puede estar nombrando. Lanza `RejectedError` si no ancla."""
    with connection.reader(path) as con:
        if isinstance(anchor, FactAnchor):
            candidatas = _candidates(con, [anchor.entity_id])
            if not candidatas:
                raise RejectedError("Ese personaje, lugar u objeto no existe en la novela.")
            valor = dict(candidatas[0].attributes).get(anchor.attribute)
            if anchor.attribute != NAME and valor is None:
                raise RejectedError(f"{candidatas[0].name} no tiene el dato «{anchor.attribute}».")
            actual = candidatas[0].name if anchor.attribute == NAME else valor
            return (
                f"Hecho de la ficha: {candidatas[0].entity_id}.{anchor.attribute} = {actual}",
                candidatas,
            )

        escena = con.execute(
            "SELECT id, chapter, pov_entity, place_entity FROM prose_scene WHERE id = ?",
            (anchor.scene_id,),
        ).fetchone()
        if escena is None or escena["chapter"] != anchor.chapter:
            raise RejectedError("Esa escena no existe en ese capítulo.")
        if anchor.version > manuscript.current_version(con):
            raise RejectedError("Esa versión no existe.")
        texto = manuscript.text_at(
            con, anchor.scene_id, anchor.version, scene_texts(con).get(anchor.scene_id, "")
        )
        # `verification.md` §5.11: la cita tiene que estar literal en la escena que nombra.
        if anchor.quote not in texto:
            raise RejectedError("El fragmento seleccionado no aparece tal cual en esa escena.")
        ids = [escena["pov_entity"], escena["place_entity"]]
        ids += [
            r["entity_id"]
            for r in con.execute(
                "SELECT entity_id FROM prose_scene_character WHERE scene_id = ?", (anchor.scene_id,)
            )
        ]
        # Una entidad nombrada en la cita tambien es candidata aunque no este en el elenco.
        for r in con.execute("SELECT id, name FROM entity"):
            if r["name"] and r["name"].lower() in anchor.quote.lower():
                ids.append(r["id"])
        candidatas = _candidates(con, [i for i in ids if i])
    return (
        f"Fragmento del capítulo {anchor.chapter}, escena {anchor.scene_id}: «{anchor.quote}»",
        candidatas,
    )


def create_request(
    path: Path, text: str, anchor: Anchor, interpreter: Interpreter | None, trace: Trace
) -> manuscript.ChangeRequest:
    """RF-221, RF-222. Interpreta y deja la solicitud `queued` o `rejected`, en la misma llamada."""
    interpretacion: manuscript.Interpretation | None = None
    motivo = ""
    try:
        descripcion, candidatas = anchor_context(path, anchor)
        if interpreter is None:
            raise RejectedError("No hay modelo con el que interpretar la petición en este momento.")
        resultado = validate(interpreter(text, descripcion, candidatas), candidatas)
        if isinstance(resultado, str):
            motivo = resultado
        else:
            interpretacion = resultado
    except RejectedError as exc:
        motivo = str(exc)
    except TooLongError as exc:
        motivo = str(exc)
    except Exception:  # el modelo no respondio: se dice, no se encola a ciegas
        motivo = "No pude interpretar la petición: el modelo no respondió. Vuelve a intentarlo."
    with connection.canon_writer(path) as con:
        rid = manuscript.insert_request(
            con, text=text, anchor=anchor.model_dump(), interpretation=interpretacion, reason=motivo
        )
        solicitud = manuscript.request(con, rid)
    assert solicitud is not None
    trace.emit(
        "amend.request",
        request=rid,
        status=solicitud.status,
        reason=motivo,
        entity=interpretacion.entity_id if interpretacion else None,
        attribute=interpretacion.attribute if interpretacion else None,
    )
    return solicitud


# ---------------------------------------------------------------- aplicar


def old_forms(interp: manuscript.Interpretation) -> list[str]:
    """D-83. Las formas del valor anterior que no pueden quedar en la prosa. Pura.

    Un atributo tiene una sola forma. Un nombre, el completo y cada palabra suya
    de tres letras o mas que no este en el nombre nuevo: la prosa dice «Marcos»
    aunque el canon diga «Marcos Vela», y pasar a «Marcos Ruiz» no quita «Marcos».
    """
    if interp.attribute != NAME:
        return [interp.previous_value]
    nuevas = {w.lower() for w in re.findall(r"\w+", interp.new_value)}
    palabras = [
        w
        for w in re.findall(r"\w+", interp.previous_value)
        if len(w) >= 3 and w.lower() not in nuevas
    ]
    return list(dict.fromkeys([interp.previous_value, *palabras]))


def _names(forms: str | Sequence[str]) -> re.Pattern[str]:
    items = [forms] if isinstance(forms, str) else list(forms)
    alternatives = "|".join(re.escape(f) for f in sorted(items, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


def affected_scenes(
    path: Path, interp: manuscript.Interpretation, trace: Trace | None = None
) -> list[str]:
    """RF-224. Escenas congeladas que nombran el hecho.

    Un cambio de nombre toca toda escena que nombra a la entidad por su nombre
    anterior: el nombre en el texto es la senal, este o no en el elenco. Un
    atributo, las escenas que contienen el valor anterior y en las que la
    entidad es POV, lugar o elenco.

    RF-241, D-89. Para un atributo lee tambien el registro hecho x escena, que
    se escribio al congelar con esta misma regla, y lo contrasta con la busqueda
    en el texto: si discrepan, consta en la traza como `amend.usage_mismatch`.
    Devuelve la busqueda en el texto, que es la que ve el texto de hoy.
    """
    patron = _names(old_forms(interp))
    with connection.reader(path) as con:
        textos = scene_texts(con)
        registro = (
            None
            if interp.attribute == NAME
            else usage.scenes_using(con, interp.entity_id, interp.attribute)
        )
        filas = con.execute(
            "SELECT id, pov_entity, place_entity FROM prose_scene ORDER BY chapter, scene_number"
        ).fetchall()
        elenco = {
            r["scene_id"]
            for r in con.execute(
                "SELECT scene_id FROM prose_scene_character WHERE entity_id = ?",
                (interp.entity_id,),
            )
        }
    out = []
    for r in filas:
        if not patron.search(textos.get(r["id"], "")):
            continue
        presente = interp.entity_id in (r["pov_entity"], r["place_entity"]) or r["id"] in elenco
        if interp.attribute == NAME or presente:
            out.append(r["id"])
    if registro is not None and registro != out and trace is not None:
        trace.emit(
            "amend.usage_mismatch",
            fact=usage.fact_key(interp.entity_id, interp.attribute),
            registry=list(registro),
            text=list(out),
        )
    return out


def _event(path: Path, interp: manuscript.Interpretation) -> tuple[Event, str]:
    """El evento de procedencia `brief` y el instante desde el que rige (PRO-10)."""
    with connection.reader(path) as con:
        if interp.attribute == NAME:
            since = con.execute(
                "SELECT created_at FROM entity WHERE id = ?", (interp.entity_id,)
            ).fetchone()["created_at"]
            payload: EntityRenamed | AttributeSet = EntityRenamed(
                entity_id=interp.entity_id, name=interp.new_value
            )
        else:
            row = con.execute(
                "SELECT valid_from FROM attribute WHERE entity_id = ? AND name = ? AND valid_to IS NULL",
                (interp.entity_id, interp.attribute),
            ).fetchone()
            if row is None:
                raise RejectedError(
                    f"El dato «{interp.attribute}» ya no está vigente: pide el cambio de nuevo."
                )
            since = row["valid_from"]
            payload = AttributeSet(
                entity_id=interp.entity_id, name=interp.attribute, value=interp.new_value
            )
    evento = Event(
        world_time=WorldTime(stamp=since),
        payload=payload,
        provenance=Provenance.BRIEF,
        chapter_origin=None,
        entities=frozenset({interp.entity_id}),
    )
    return evento, since


def counts(defect_quote: str, new_value: str, before: str = "") -> bool:
    """D-78, D-84. Si un defecto de la reescritura cuenta contra la enmienda. Pura.

    No cuenta el que cita el valor nuevo: es la enmienda misma (D-78). Tampoco el
    que cita algo que ya estaba tal cual en la escena antes de reescribirla: es
    previo, y la enmienda no lo abrio (RF-54 de la version 1). Cuenta el resto.
    """
    quote = defect_quote.strip()
    if new_value.lower() in quote.lower():
        return False
    return not (quote and quote in before)


def _apply(path: Path, solicitud: manuscript.ChangeRequest, engine: Engine, trace: Trace) -> int:
    interp = solicitud.interpretation
    if interp is None:
        raise RejectedError("La solicitud no tiene interpretación.")
    escenas = affected_scenes(path, interp, trace)
    evento, since = _event(path, interp)
    plan = RetconPlan(
        fact_key=f"{interp.entity_id}.{interp.attribute}",
        entity_id=interp.entity_id,
        attribute=interp.attribute,
        previous_value=interp.previous_value,
        new_value=interp.new_value,
        frozen_since=since,
        scenes=tuple(escenas),
        paid=False,
    )
    with connection.reader(path) as con:
        textos = scene_texts(con)
        capitulos = {
            r["id"]: r["chapter"] for r in con.execute("SELECT id, chapter FROM prose_scene")
        }
    patron = _names(old_forms(interp))
    nuevas: list[refreeze.RefrozenScene] = []
    for sid in escenas:
        escena, defectos = engine.retcon_rewrite(sid, textos.get(sid, ""), plan)
        if patron.search(escena.text):
            raise RejectedError(
                f"No se consiguió quitar «{interp.previous_value}» de la escena {sid}."
            )
        graves = [
            d
            for d in defectos
            if d.severity == Severity.S1
            and counts(d.evidence.quote, interp.new_value, textos.get(sid, ""))
        ]
        if graves:
            raise RejectedError(
                f"El cambio contradice el canon o un invariante duro: {graves[0].rule}"
            )
        nuevas.append(escena)

    afectados = sorted({capitulos[s] for s in escenas if s in capitulos})
    reescritas = {e.scene_id: e.summary for e in nuevas}
    resumenes: dict[int, str] = {}
    with connection.reader(path) as con:
        for c in afectados:
            partes = [
                reescritas.get(r["id"], r["summary"])
                for r in con.execute(
                    "SELECT id, summary FROM prose_scene WHERE chapter = ? ORDER BY scene_number",
                    (c,),
                )
            ]
            resumenes[c] = engine.summarize_chapter(partes)
    preparado = refreeze.prepare(nuevas, embed=engine.embed)
    with connection.canon_writer(path) as con:
        evento = evento.model_copy(
            update={"world_time": WorldTime(stamp=since, seq=log.next_seq(con, since))}
        )
        version = manuscript.commit_amendment(
            con,
            request_id=solicitud.request_id,
            plan=plan,
            event=evento,
            prepared=preparado,
            old_texts={s: textos.get(s, "") for s in escenas},
            chapter_summaries=resumenes,
        )
    trace.emit(
        "amend.applied",
        request=solicitud.request_id,
        version=version,
        fact=plan.fact_key,
        previous=interp.previous_value,
        new=interp.new_value,
        refrozen=list(escenas),
    )
    return version


def apply_pending(path: Path, engine: Engine, trace: Trace) -> list[int]:
    """RF-223, RF-226. Aplica las pendientes de una en una. Devuelve las versiones creadas.

    Una que falla se rechaza con motivo y no toca nada (RNF-50): la transaccion
    de `commit_amendment` es la unica escritura, y va al final.
    """
    creadas: list[int] = []
    while True:
        with connection.canon_writer(path) as con:
            solicitud = manuscript.next_queued(con)
            if solicitud is None:
                return creadas
            manuscript.set_status(con, solicitud.request_id, "applying")
        try:
            creadas.append(_apply(path, solicitud, engine, trace))
        except RejectedError as exc:
            _reject(path, solicitud.request_id, str(exc), trace)
        except Exception as exc:  # un fallo del proveedor la rechaza con motivo (RF-226)
            _reject(
                path,
                solicitud.request_id,
                f"No se pudo aplicar: {type(exc).__name__}: {exc}"[:300],
                trace,
            )


def _reject(path: Path, request_id: int, reason: str, trace: Trace) -> None:
    with connection.canon_writer(path) as con:
        manuscript.set_status(con, request_id, "rejected", reason=reason)
    trace.emit("amend.rejected", request=request_id, reason=reason)


#: Quien aplica fuera de una tirada: recibe el fichero, el identificador y la traza.
Amender = Callable[[Path, str, Trace], object]


def reject_queued(path: Path, reason: str, trace: Trace) -> None:
    """RF-226. Rechaza con motivo todo lo pendiente: nada queda en cola para siempre."""
    with connection.reader(path) as con:
        pendientes = [
            r.request_id for r in manuscript.requests(con) if r.status in ("queued", "applying")
        ]
    for rid in pendientes:
        _reject(path, rid, reason, trace)


def has_queued(path: Path) -> bool:
    with connection.reader(path) as con:
        return any(r.status in ("queued", "applying") for r in manuscript.requests(con))


def drain(path: Path, apply_once: Callable[[], object]) -> None:
    """El hilo del Orquestador fuera de una tirada: aplica hasta que no quede ninguna (D-77)."""
    while True:
        apply_once()
        if not has_queued(path):
            return
