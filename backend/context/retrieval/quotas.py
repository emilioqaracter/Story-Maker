"""Seleccion por cupos, no por peso.

RF-79 a RF-85. Con la lista fusionada hay que elegir de 4 a 6 fragmentos. Lo
habitual seria coger los mejores. Aqui no: el espacio se reparte en **cupos por
tipo de evidencia**, y cada cupo se llena con el mejor candidato que lo cumpla.

Por que es mejor que un ranking:

- **Cada fragmento lleva su motivo**, asi que el paquete se puede auditar y se
  puede responder por que entro cada cosa.
- **La diversidad esta garantizada por construccion.** Un ranking por puntuacion
  devuelve los seis fragmentos mas parecidos a la consulta, que es justo lo que
  menos ayuda a escribir algo nuevo.
- **Un cupo vacio no rompe nada.** En los primeros capitulos casi todos lo
  estan, y su presupuesto pasa al cupo libre.
- **El cupo de voz penaliza lo ya usado**, que es la contramedida directa contra
  que el sistema se copie a si mismo.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from commons.types.primitives import BlockProvenance, Quota


class Candidate(BaseModel):
    """Un fragmento candidato, con lo que hace falta para decidir su cupo."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    scene_id: str
    chapter: int
    text: str
    tokens: int = Field(gt=0)
    place: str | None = None
    pov: str | None = None
    function: str | None = None
    has_dialogue: bool = False
    plants_setup: tuple[str, ...] = Field(default_factory=tuple)
    entities: frozenset[str] = Field(default_factory=frozenset)
    summary: str = Field(default="", description="Resumen de su escena, por si no cabe")


class Selected(BaseModel):
    """Un fragmento elegido, con su cupo y su procedencia.

    Sin estos dos campos el fragmento es texto suelto en el paquete, y un
    fragmento sin motivo se descarta en la auditoria (RF-80).
    """

    model_config = ConfigDict(frozen=True)

    candidate: Candidate
    quota: Quota
    provenance: BlockProvenance = BlockProvenance.FROZEN_PROSE
    as_summary: bool = Field(
        default=False, description="True si no cabia y entro su resumen"
    )

    @property
    def tokens(self) -> int:
        return len(self.candidate.summary) // 4 if self.as_summary else self.candidate.tokens

    @property
    def content(self) -> str:
        return self.candidate.summary if self.as_summary else self.candidate.text


class Selection(BaseModel):
    model_config = ConfigDict(frozen=True)

    chosen: tuple[Selected, ...]
    empty_quotas: tuple[Quota, ...] = Field(
        default_factory=tuple,
        description="Cupos sin candidato. No es un error: su presupuesto pasa al libre",
    )

    @property
    def tokens(self) -> int:
        return sum(s.tokens for s in self.chosen)


def _fits(cand: Candidate, quota: Quota, ctx: _Context) -> bool:
    """Si un candidato cumple un cupo."""
    match quota:
        case Quota.PLACE:
            return cand.place is not None and cand.place == ctx.place
        case Quota.VOICE:
            # Con dialogo, del mismo POV, y **no usado en las ultimas llamadas**:
            # esa exclusion es la contramedida contra la autosimilitud.
            return (
                cand.has_dialogue
                and cand.pov == ctx.pov
                and cand.scene_id not in ctx.recent_voice_scenes
            )
        case Quota.PROMISE:
            return bool(set(cand.plants_setup) & ctx.setups_to_pay)
        case Quota.MIRROR:
            return (
                cand.function == ctx.function
                and bool(cand.entities & ctx.entities)
                and cand.scene_id != ctx.current_scene
            )
        case Quota.FREE:
            return True


class _Context:
    """Lo que hace falta para decidir si un candidato cumple un cupo."""

    __slots__ = (
        "current_scene",
        "entities",
        "function",
        "place",
        "pov",
        "recent_voice_scenes",
        "setups_to_pay",
    )

    def __init__(
        self,
        *,
        place: str | None,
        pov: str,
        function: str,
        entities: frozenset[str],
        setups_to_pay: frozenset[str],
        recent_voice_scenes: frozenset[str],
        current_scene: str,
    ) -> None:
        self.place = place
        self.pov = pov
        self.function = function
        self.entities = entities
        self.setups_to_pay = setups_to_pay
        self.recent_voice_scenes = recent_voice_scenes
        self.current_scene = current_scene


def select(
    ranked: Sequence[Candidate],
    *,
    token_budget: int,
    place: str | None,
    pov: str,
    function: str,
    entities: frozenset[str],
    setups_to_pay: frozenset[str] = frozenset(),
    recent_voice_scenes: frozenset[str] = frozenset(),
    current_scene: str = "",
    literal_scenes: frozenset[str] = frozenset(),
    quotas: Sequence[Quota] = tuple(Quota),
) -> Selection:
    """Llena los cupos por orden, con el mejor candidato de cada uno.

    `ranked` viene ya ordenado por la fusion. `literal_scenes` son las escenas
    que ya viajan enteras en el paquete: nada de ellas entra aqui, porque
    duplicar texto gasta presupuesto sin anadir informacion (RF-83).
    """
    ctx = _Context(
        place=place,
        pov=pov,
        function=function,
        entities=entities,
        setups_to_pay=setups_to_pay,
        recent_voice_scenes=recent_voice_scenes,
        current_scene=current_scene,
    )

    disponibles = [c for c in ranked if c.scene_id not in literal_scenes]
    chosen: list[Selected] = []
    empty: list[Quota] = []
    usados: set[str] = set()
    escenas_usadas: set[str] = set()
    restante = token_budget

    for quota in quotas:
        elegido = _take(disponibles, quota, ctx, usados, escenas_usadas, restante)
        if elegido is None:
            empty.append(quota)
            continue
        chosen.append(elegido)
        usados.add(elegido.candidate.chunk_id)
        escenas_usadas.add(elegido.candidate.scene_id)
        restante -= elegido.tokens

    return Selection(chosen=tuple(chosen), empty_quotas=tuple(empty))


def _take(
    disponibles: Sequence[Candidate],
    quota: Quota,
    ctx: _Context,
    usados: set[str],
    escenas_usadas: set[str],
    restante: int,
) -> Selected | None:
    """El mejor candidato del cupo que quepa.

    **Un fragmento no se trunca nunca** (RF-84): si no cabe en lo que queda, se
    prueba el siguiente del mismo cupo, y si ninguno cabe entra el resumen de su
    escena, que ya existe y ocupa poco. Cortarlo por la mitad daria al Escritor
    medio parrafo sin saber que le falta.
    """
    sin_repetir_escena = [
        c
        for c in disponibles
        if c.chunk_id not in usados and c.scene_id not in escenas_usadas and _fits(c, quota, ctx)
    ]
    # Si ningun candidato queda tras excluir escenas repetidas, se permite
    # repetir: dos cupos sin otra opcion valen mas que un cupo vacio (RF-83).
    candidatos = sin_repetir_escena or [
        c for c in disponibles if c.chunk_id not in usados and _fits(c, quota, ctx)
    ]

    for cand in candidatos:
        if cand.tokens <= restante:
            return Selected(candidate=cand, quota=quota)

    for cand in candidatos:
        resumen = len(cand.summary) // 4
        if cand.summary and resumen <= restante:
            return Selected(candidate=cand, quota=quota, as_summary=True)

    return None
