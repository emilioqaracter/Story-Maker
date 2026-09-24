"""Instruccion del Planificador de capitulo: `scene.spec`.

RF-28 a RF-30. Convierte el tramo de escaleta de un capitulo en
especificaciones de escena con los cinco bloques de `domain-knowledge.md` §4.
Lo que la escaleta ya fijo --capitulo, posicion, POV, funcion, cambio de valor,
instante, longitud, si es encuentro-- **no se decide otra vez**: el modelo
rellena lo que falta y `from_entry` copia lo demas. Si el Planificador pudiera
cambiarlo, la escaleta congelada volveria a ser una sugerencia.

EST-I1 se impone en el parseo (RF-29): una salida sin elenco, sin pasos o con
un POV fuera del elenco no es una especificacion mala, es una salida que no
encaja y consume un reintento.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from canon.skills.read import EntityCard
from commons.types.primitives import Defect
from commons.types.scene import SceneSpec
from planning.ledger.setups import Debt
from planning.outline.types import Outline, SceneEntry
from planning.scene_spec.spec import from_entry

SYSTEM = """Planificas escenas de una novela a partir de su escaleta. Eres un
componente de un sistema automatico: devuelves JSON y nada mas.

La escaleta ya decidio capitulo, posicion, punto de vista, funcion dramatica,
cambio de valor, instante y longitud de cada escena. Eso NO lo cambias. Tu
rellenas lo que falta para que un escritor pueda escribirla sin preguntar nada:

REGLAS QUE NO SE NEGOCIAN

1. El elenco activo son identificadores del estado del mundo, y el POV esta
   siempre dentro del elenco.
2. El lugar es un identificador de entidad de tipo lugar, o el nombre de un
   lugar del estado del mundo.
3. Los pasos (beats) son de tres a siete acciones concretas y observables, en
   orden. Nada de "reflexiona sobre su vida": que HACE.
4. Objetivo y obstaculo son del POV en esta escena, concretos y en conflicto.
5. "ends_with" describe el estado al cerrar: que ha cambiado respecto al
   principio. Tiene que realizar el cambio de valor que la escaleta declara.
6. Las promesas que se plantan o cobran son identificadores de setup de la
   escaleta, solo los que la escaleta situa en esta escena.
7. Un personaje solo puede actuar sobre lo que sabe en ese instante. Si el
   estado dice que desconoce algo, no lo usas.

Si recibes DEFECTOS de un intento anterior, la especificacion nueva tiene que
hacerlos imposibles: mas restricciones, pasos mas concretos, elenco mas corto."""


class SpecBody(BaseModel):
    """Lo que el Planificador aporta. Lo demas viene de la escaleta."""

    model_config = ConfigDict(frozen=True)

    place: str = Field(min_length=1)
    cast: tuple[str, ...] = Field(min_length=1)
    beats: tuple[str, ...] = Field(min_length=1)
    objective: str = Field(min_length=1)
    obstacle: str = Field(min_length=1)
    ends_with: str = Field(min_length=1)
    setups_to_plant: tuple[str, ...] = Field(default_factory=tuple)
    setups_to_pay: tuple[str, ...] = Field(default_factory=tuple)


class ChapterPlan(BaseModel):
    """Una entrada por escena del capitulo, por identificador de escaleta."""

    model_config = ConfigDict(frozen=True)

    scenes: dict[str, SpecBody]


def schema() -> str:
    ejemplo = {
        "scenes": {
            "c1e1": {
                "place": "vestuario",
                "cast": ["marcos", "tecnico"],
                "beats": [
                    "Marcos entra el ultimo y nadie levanta la vista",
                    "El tecnico lee la alineacion sin nombrarlo",
                    "Marcos descubre la lista doblada en el bolsillo del tecnico",
                ],
                "objective": "saber si juega",
                "obstacle": "nadie le habla",
                "ends_with": "sale sin saberlo y con la lista en la cabeza",
                "setups_to_plant": ["la-lista"],
                "setups_to_pay": [],
            }
        }
    }
    return (
        "Objeto con la clave scenes: un objeto cuyas claves son los identificadores "
        "de escena del capitulo y cuyos valores tienen place, cast, beats, objective, "
        "obstacle, ends_with, setups_to_plant y setups_to_pay.\n"
        "Ejemplo:\n" + json.dumps(ejemplo, ensure_ascii=False, indent=1)
    )


def instruction(
    entries: Sequence[SceneEntry],
    outline: Outline,
    *,
    cards: Sequence[EntityCard],
    debt: Debt,
    previous_summaries: Sequence[str] = (),
    defects: Sequence[Defect] = (),
) -> str:
    """La parte que cambia: el tramo de escaleta y el estado del mundo."""
    tramo = "\n".join(
        f"  {e.id}: capitulo {e.chapter}, posicion {e.ordinal}, acto {e.act}, "
        f"funcion {e.function.value}, POV {e.pov}, instante {e.world_time.stamp}, "
        f"{e.target_words} palabras, cambio de valor: {e.value_change}"
        + (" — ES UN ENCUENTRO" if e.is_match else "")
        for e in entries
    )
    ids = {e.id for e in entries}
    promesas = (
        "\n".join(
            f"  {s.id}: {s.description} (se planta en {s.planted_scene}, se cobra en {s.payoff_scene})"
            for s in outline.setups
            if s.planted_scene in ids or s.payoff_scene in ids
        )
        or "  (ninguna en este capitulo)"
    )
    mundo = "\n".join(
        f"  {c.entity_id} ({c.kind}): {c.name}"
        + (f" — {', '.join(f'{k}={v}' for k, v in c.attributes)}" if c.attributes else "")
        for c in cards
    )
    deuda = "\n".join(f"  {s.id}: {s.description}" for s in debt.open_setups) or "  (ninguna)"
    resumenes = "\n\n".join(previous_summaries) or "(es el primer capitulo)"
    fallos = ""
    if defects:
        lista = "\n".join(f"  - [{d.severity}] {d.kind}: {d.rule}" for d in defects)
        fallos = f"\n\nDEFECTOS DEL INTENTO ANTERIOR, que esta especificacion tiene que hacer imposibles:\n{lista}"

    claves = ", ".join(e.id for e in entries)
    return f"""Especifica las escenas de este capitulo.

TRAMO DE ESCALETA:
{tramo}

El objeto scenes lleva exactamente estas claves: {claves}. Ni una mas, ni una menos,
escritas tal cual.

PROMESAS DE ESTE CAPITULO:
{promesas}

ESTADO DEL MUNDO:
{mundo}

DEUDA NARRATIVA ABIERTA:
{deuda}

LO QUE PASO ANTES:
{resumenes}{fallos}

Devuelve SOLO el JSON."""


def plan_model(
    entries: Sequence[SceneEntry], *, forbidden: Sequence[str] = ()
) -> type[ChapterPlan]:
    """D-134. El modelo que `dispatch` exige a la salida de esta llamada.

    Compone las especificaciones igual que `parse`, asi que una escena sin
    especificar o un POV fuera del elenco (EST-I1) son una salida que no encaja
    --un reintento con su motivo, RI-18-- y no un error que para la tirada.
    """

    class ChapterPlanFor(ChapterPlan):
        @model_validator(mode="after")
        def _compone(self) -> ChapterPlanFor:
            _compose(self, entries, forbidden)
            return self

    return ChapterPlanFor


def parse(
    raw: str, entries: Sequence[SceneEntry], *, forbidden: Sequence[str] = ()
) -> list[SceneSpec]:
    """Valida la salida y la compone con la escaleta. EST-I1 se impone aqui (RF-29)."""
    return _compose(ChapterPlan.model_validate_json(raw), entries, forbidden)


def _compose(
    plan: ChapterPlan, entries: Sequence[SceneEntry], forbidden: Sequence[str]
) -> list[SceneSpec]:
    faltan = [e.id for e in entries if e.id not in plan.scenes]
    if faltan:
        raise ValueError(f"el Planificador no especifico las escenas {faltan}")

    out: list[SceneSpec] = []
    for entry in entries:
        body = plan.scenes[entry.id]
        out.append(
            from_entry(
                entry,
                place=body.place,
                cast=body.cast,
                beats=body.beats,
                objective=body.objective,
                obstacle=body.obstacle,
                ends_with=body.ends_with,
                setups_to_plant=body.setups_to_plant,
                setups_to_pay=body.setups_to_pay,
                forbidden=tuple(forbidden),
            )
        )
    return out
