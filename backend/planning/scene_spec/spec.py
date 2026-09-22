"""Fabrica de especificaciones de escena desde la escaleta.

El artefacto vive en `commons/types/scene.py` porque lo consumen varias
funcionalidades; aqui queda solo quien lo produce, que es `planning/`.
"""

from __future__ import annotations

from commons.types.scene import (
    DramaticFunction,
    ExpectedOutput,
    SceneConstraints,
    SceneContent,
    SceneIdentity,
    SceneSpec,
)
from planning.outline.types import SceneEntry


def from_entry(
    entry: SceneEntry,
    *,
    place: str,
    cast: tuple[str, ...],
    beats: tuple[str, ...],
    objective: str,
    obstacle: str,
    ends_with: str,
    setups_to_plant: tuple[str, ...] = (),
    setups_to_pay: tuple[str, ...] = (),
    forbidden: tuple[str, ...] = (),
    facts_unknown_to_pov: tuple[str, ...] = (),
) -> SceneSpec:
    """Compone la especificacion a partir de la entrada de escaleta.

    Lo que viene de la escaleta --capitulo, posicion, POV, funcion, cambio de
    valor, instante, longitud, si es encuentro-- se copia y no se decide otra
    vez. Si el Planificador pudiera cambiarlo, la escaleta congelada dejaria de
    gobernar y volveria a ser una sugerencia.
    """
    return SceneSpec(
        identity=SceneIdentity(
            scene_id=entry.id,
            chapter=entry.chapter,
            ordinal=entry.ordinal,
            pov=entry.pov,
            place=place,
            world_time=entry.world_time,
        ),
        function=DramaticFunction(
            function=entry.function,
            value_change=entry.value_change,
            arcs=entry.arcs,
            objective=objective,
            obstacle=obstacle,
        ),
        content=SceneContent(
            cast=cast,
            beats=beats,
            setups_to_plant=setups_to_plant,
            setups_to_pay=setups_to_pay,
        ),
        output=ExpectedOutput(target_words=entry.target_words, ends_with=ends_with),
        constraints=SceneConstraints(
            forbidden=forbidden, facts_unknown_to_pov=facts_unknown_to_pov
        ),
        is_match=entry.is_match,
    )
