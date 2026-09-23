"""Que arcos cierra un capitulo y que capitulos cubre un arco.

RF-116. Son lecturas de la escaleta, asi que viven en `planning/`: `canon/` no
puede conocer la escaleta (regla de los tres pisos), y quien decide cuando se
resume un arco es el Orquestador, que si la conoce.
"""

from __future__ import annotations

from planning.outline.types import Outline


def arcs_closed_by(outline: Outline, chapter: int) -> list[str]:
    """Arcos cuya escena de resolucion esta en este capitulo."""
    escenas = {s.id for s in outline.scenes if s.chapter == chapter}
    return [a.id for a in outline.arcs if a.resolution_scene in escenas]


def chapters_of_arc(outline: Outline, arc_id: str) -> list[int]:
    """Capitulos que el arco cubre, del inicio a la resolucion."""
    arco = next((a for a in outline.arcs if a.id == arc_id), None)
    if arco is None:
        return []
    ids = {arco.start_scene, arco.crisis_scene, arco.resolution_scene}
    caps = [s.chapter for s in outline.scenes if s.id in ids]
    if not caps:
        return []
    return list(range(min(caps), max(caps) + 1))
