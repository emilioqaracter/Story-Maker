"""`replan.arc`. Recalcula el tramo de escaleta que viene.

RF-19, RF-106, PRO-12. Es la salida de dos puertas: la de cierre de acto, cuando
deja promesas sin cobrar, y la cuarentena de capitulo, cuando el problema no
esta en la prosa ni en el encargo sino en el plan del tramo.

Dos reglas que no se negocian, y las dos son la misma:

- **Nunca toca lo congelado.** El canon congelado gana (PRO-10), asi que el
  remedio solo mira hacia delante: se reemplazan las escenas del tramo que aun
  no se ha escrito, y ninguna otra.
- **Lo que reemplaza tiene que pasar `outline.check` otra vez.** Una
  replanificacion que rompe la estructura no es un remedio: la escaleta nueva
  vuelve al verificador determinista como la primera.

El modelo propone las escenas nuevas; el codigo las coloca y **recoloca las
promesas** cuyo cobro caia en el tramo reemplazado, para que ninguna se pierda
por el camino.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from planning.outline.types import NOVELA, LengthProfile, Outline, SceneEntry, Setup

SYSTEM = """Replanificas un tramo de la escaleta de una novela. Eres un componente
de un sistema automatico: devuelves JSON y nada mas.

Lo ya escrito y congelado NO se toca. Recibes el tramo que viene --un acto o
los capitulos que quedan de el-- y lo que ese tramo tiene que conseguir que el
plan anterior no consiguio: cobrar promesas, resolver arcos, corregir lo que
fallo. Devuelves las escenas nuevas de ese tramo, con la misma forma que la
escaleta original.

REGLAS QUE NO SE NEGOCIAN

1. Solo escenas del tramo indicado: mismos capitulos, mismo acto. Ni una escena
   en un capitulo ya congelado.
2. Toda promesa que te pidan cobrar tiene una escena de cobro en el tramo nuevo,
   posterior a donde se planto, y la declaras en payoffs.
3. Todo arco que te pidan resolver tiene su escena de resolucion en el tramo, y
   la declaras en resolutions.
4. La tension no baja dentro del acto. Un valor por capitulo.
5. Cada escena declara un cambio de valor concreto. Sin el es relleno.
6. Identificadores "c<capitulo>e<posicion>", POV como identificador de entidad,
   fechas de mundo que avanzan."""


class ReplannedTract(BaseModel):
    """Lo que el modelo devuelve para el tramo."""

    model_config = ConfigDict(frozen=True)

    scenes: tuple[SceneEntry, ...] = Field(min_length=1)
    payoffs: dict[str, str] = Field(
        default_factory=dict, description="setup_id -> escena nueva donde se cobra"
    )
    resolutions: dict[str, str] = Field(
        default_factory=dict, description="arc_id -> escena nueva donde se resuelve"
    )
    tension: tuple[int, ...] = Field(default_factory=tuple)


def schema(profile: LengthProfile = NOVELA) -> str:
    """El rango de escena y el ejemplo salen del perfil de extension (T53)."""
    low, high = profile.scene_words
    palabras = 900 if low <= 900 <= high else (low + high) // 2
    ejemplo = {
        "scenes": [
            {
                "id": "c3e1",
                "chapter": 3,
                "ordinal": 1,
                "act": 2,
                "function": "decidir",
                "pov": "marcos",
                "value_change": "de la evasion a la confesion",
                "world_time": {"stamp": "2026-09-02", "seq": 0},
                "target_words": palabras,
                "is_match": False,
                "arcs": ["interno"],
            }
        ],
        "payoffs": {"la-lista": "c3e1"},
        "resolutions": {},
        "tension": [7, 9],
    }
    return (
        "Objeto con scenes (lista de escenas con la forma de la escaleta), payoffs "
        "(setup_id -> id de escena), resolutions (arc_id -> id de escena) y tension "
        f"(un valor por capitulo del tramo). target_words entre {low} y "
        f"{high}.\nEjemplo:\n" + json.dumps(ejemplo, ensure_ascii=False, indent=1)
    )


def instruction(
    outline: Outline,
    *,
    act: int,
    from_chapter: int,
    unpaid_setups: Sequence[str],
    reasons: Sequence[str],
    profile: LengthProfile = NOVELA,
) -> str:
    """El tramo a reemplazar y lo que tiene que conseguir.

    D-116. Si el perfil fija la forma de la obra (`prueba`), la instruccion la
    dice: cuantas escenas por capitulo, su rango de palabras y cuanto puede sumar
    el tramo para que la obra entera quepa en su rango. Sin esto el Arquitecto
    devolvia tramos fuera del perfil y `outline.check` los rechazaba hasta abortar.
    """
    tramo = [s for s in outline.scenes if s.act == act and s.chapter >= from_chapter]
    actual = (
        "\n".join(
            f"  {s.id}: capitulo {s.chapter}, {s.function.value}, POV {s.pov}, "
            f"{s.world_time.stamp}, {s.target_words} palabras, {s.value_change}"
            for s in tramo
        )
        or "  (el tramo estaba vacio)"
    )
    promesas = (
        "\n".join(
            f"  {st.id}: {st.description} (plantada en {st.planted_scene})"
            for st in outline.setups
            if st.id in set(unpaid_setups)
        )
        or "  (ninguna)"
    )
    arcos = (
        "\n".join(
            f"  {a.id} ({a.kind.value}, {a.subject}): resolucion planificada en {a.resolution_scene}"
            for a in outline.arcs
            if a.resolution_scene and any(s.id == a.resolution_scene for s in tramo)
        )
        or "  (ninguno se resuelve en este tramo)"
    )
    motivos = "\n".join(f"  - {r}" for r in reasons) or "  - la puerta de cierre de acto fallo"
    capitulos = sorted({s.chapter for s in tramo})
    forma = _shape(outline, tramo, capitulos, profile)

    return f"""Replanifica el acto {act} desde el capitulo {from_chapter}.

POR QUE:
{motivos}

TRAMO ACTUAL, que se reemplaza entero (capitulos {capitulos}):
{actual}

PROMESAS QUE ESTE TRAMO TIENE QUE COBRAR:
{promesas}

ARCOS QUE SE RESUELVEN EN ESTE TRAMO Y SIGUEN TENIENDO QUE RESOLVERSE:
{arcos}
{forma}
Devuelve SOLO el JSON."""


def _shape(
    outline: Outline, tramo: Sequence[SceneEntry], capitulos: Sequence[int], profile: LengthProfile
) -> str:
    """D-116. La forma que el perfil impone al tramo, o nada si no la fija."""
    if profile.chapters is None or profile.scenes_per_chapter is None:
        return ""
    low, high = profile.scene_words
    ids = {s.id for s in tramo}
    fuera = sum(s.target_words for s in outline.scenes if s.id not in ids)
    lineas = [
        "",
        "FORMA OBLIGATORIA DEL PERFIL (si no se cumple, el tramo se rechaza):",
        f"  - exactamente los capitulos {list(capitulos)}, ni uno mas ni uno menos",
        f"  - {profile.scenes_per_chapter} escena por capitulo",
        f"  - cada escena con target_words entre {low} y {high}",
    ]
    if profile.work_words is not None:
        w_low, w_high = profile.work_words
        lineas.append(
            f"  - el tramo suma entre {max(0, w_low - fuera)} y {max(0, w_high - fuera)} "
            f"palabras en total (el resto de la obra ya suma {fuera})"
        )
    return "\n".join(lineas) + "\n"


def parse(raw: str) -> ReplannedTract:
    return ReplannedTract.model_validate_json(raw)


def apply(
    outline: Outline,
    tract: ReplannedTract,
    *,
    act: int,
    from_chapter: int,
) -> Outline:
    """Coloca el tramo nuevo en la escaleta. **Nunca toca lo anterior.**

    Reemplaza solo las escenas del acto desde `from_chapter`; recoloca los cobros
    y las resoluciones que el modelo declara; conserva todo lo demas. La escaleta
    resultante vuelve a `outline.check`, que es quien dice si vale.
    """
    fuera = [s for s in tract.scenes if s.act != act or s.chapter < from_chapter]
    if fuera:
        raise ValueError(
            f"la replanificacion toca escenas fuera del tramo: {[s.id for s in fuera]}. "
            "Lo congelado no se toca"
        )

    conservadas = tuple(
        s for s in outline.scenes if not (s.act == act and s.chapter >= from_chapter)
    )
    escenas = tuple(sorted((*conservadas, *tract.scenes), key=lambda s: (s.chapter, s.ordinal)))

    setups = tuple(_move_payoffs(outline.setups, tract.payoffs))
    arcos = tuple(
        a.model_copy(update={"resolution_scene": tract.resolutions[a.id]})
        if a.id in tract.resolutions
        else a
        for a in outline.arcs
    )
    actos = tuple(
        a.model_copy(update={"tension": tract.tension}) if a.number == act and tract.tension else a
        for a in outline.acts
    )
    return outline.model_copy(
        update={"scenes": escenas, "setups": setups, "arcs": arcos, "acts": actos}
    )


def _move_payoffs(setups: Sequence[Setup], moves: Mapping[str, str]) -> list[Setup]:
    return [
        s.model_copy(update={"payoff_scene": moves[s.id]}) if s.id in moves else s for s in setups
    ]
