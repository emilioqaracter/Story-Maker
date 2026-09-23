"""`revise.targeted`: agrupar defectos y decidir si una reparacion valio.

RF-53, RF-54. `architecture.md` §7.3: los defectos se agrupan por tipo y zona,
se reparan con evidencia, y la reparacion **revalida desde la primera puerta**.
Una que abre defectos nuevos se revierte: mejor la escena anterior con su
defecto conocido que una nueva con uno que nadie ha mirado.

Todo lo de aqui es codigo puro sobre listas de defectos. La llamada al modelo la
despacha el Orquestador con la instruccion de `prompts.py`.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from commons.types.primitives import Defect, Severity


class RepairOutcome(BaseModel):
    """Que paso al revalidar una escena reparada."""

    model_config = ConfigDict(frozen=True)

    accepted: bool
    closed: tuple[str, ...] = Field(default_factory=tuple, description="Reglas que ya no aparecen")
    persisting: tuple[str, ...] = Field(default_factory=tuple)
    regressions: tuple[str, ...] = Field(default_factory=tuple, description="Defectos nuevos")

    def reason(self) -> str:
        if self.regressions:
            return f"revertida: abre {len(self.regressions)} defecto(s) nuevo(s)"
        if self.persisting:
            return f"persisten {len(self.persisting)} defecto(s)"
        return f"cierra {len(self.closed)} defecto(s) sin regresiones"


def _key(d: Defect) -> str:
    return f"{d.kind}|{d.rule}"


def group_by_zone(defects: Sequence[Defect], *, zone_chars: int = 600) -> list[list[Defect]]:
    """Agrupa defectos cercanos en el texto. Una reparacion por grupo.

    Reparar defecto a defecto multiplica llamadas y produce correcciones que se
    pisan; reparar todos a la vez pierde foco. La zona --unos parrafos-- es el
    tamano al que una correccion puede atender varios defectos sin perder el
    hilo. No es un umbral de calidad: es el tamano del fragmento que el
    Reparador recibe con la escena delante.
    """
    ordenados = sorted(defects, key=lambda d: d.evidence.offset)
    grupos: list[list[Defect]] = []
    for d in ordenados:
        if grupos and d.evidence.offset - grupos[-1][0].evidence.offset <= zone_chars:
            grupos[-1].append(d)
        else:
            grupos.append([d])
    return grupos


def evaluate(
    before: Sequence[Defect], after: Sequence[Defect], *, blocking_only: bool = False
) -> RepairOutcome:
    """RF-54. La reparacion se acepta si cierra algo y no abre nada.

    `blocking_only` compara solo S1: una reparacion de continuidad que deja un
    S3 de estilo nuevo no se revierte, porque el Estilista existe para eso; una
    que abre un S1 nuevo si.
    """

    def relevantes(ds: Sequence[Defect]) -> set[str]:
        return {_key(d) for d in ds if not blocking_only or d.severity is Severity.S1}

    antes, despues = relevantes(before), relevantes(after)
    cerrados = antes - despues
    persisten = antes & despues
    nuevos = despues - antes
    aceptada = not nuevos and (bool(cerrados) or not antes)
    return RepairOutcome(
        accepted=aceptada,
        closed=tuple(sorted(cerrados)),
        persisting=tuple(sorted(persisten)),
        regressions=tuple(sorted(nuevos)),
    )
