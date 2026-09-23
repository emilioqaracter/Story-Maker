"""`outline.check`. Verificador estructural de la escaleta.

RF-26. **No llama a ningun modelo.** Es la sustitucion de "alguien aprueba la
escaleta" por algo comprobable: cobertura de arcos, doble arco resuelto en
momentos distintos, curva de tension monotona por acto, todo setup con payoff
planificado, y el reparto de palabras dentro de rango.

Cada defecto sale con su cita localizable --que escena, que arco-- porque un
veredicto sin evidencia se descarta, y porque el Arquitecto necesita saber que
arreglar, no que algo esta mal.

Si te ves pidiendole a un modelo que valide la escaleta, has cruzado la regla de
"determinista antes que modelo": todo lo de aqui se comprueba contando.
"""

from __future__ import annotations

from planning.outline.types import (
    CHAPTER_WORDS,
    ArcKind,
    Outline,
)

# Cuantos defectos del mismo tipo se detallan antes de resumir. Un informe con
# doscientas lineas identicas no lo lee nadie, y el Arquitecto recibe el informe
# entero dentro de su paquete: cada linea cuesta ventana.
_MAX_DETAIL = 5


class OutlineDefect:
    """Un defecto estructural con su cita."""

    __slots__ = ("kind", "message", "where")

    def __init__(self, kind: str, where: str, message: str) -> None:
        self.kind = kind
        self.where = where
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover - solo para depurar
        return f"{self.kind}[{self.where}]: {self.message}"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, OutlineDefect) and (self.kind, self.where, self.message) == (
            other.kind,
            other.where,
            other.message,
        )

    def __hash__(self) -> int:
        return hash((self.kind, self.where, self.message))


def check(outline: Outline, *, word_range: tuple[int, int]) -> list[OutlineDefect]:
    """Devuelve los defectos estructurales. Lista vacia significa que pasa."""
    defects: list[OutlineDefect] = []
    defects += _check_scene_ids(outline)
    defects += _check_arcs(outline)
    defects += _check_double_arc(outline)
    defects += _check_setups(outline)
    defects += _check_tension(outline)
    defects += _check_words(outline, word_range)
    defects += _check_chapters(outline)
    return defects


# ------------------------------------------------------------------ integridad


def _check_scene_ids(outline: Outline) -> list[OutlineDefect]:
    """Identificadores unicos y posiciones sin repetir dentro del capitulo.

    Va primero porque todo lo demas referencia escenas por identificador: con
    duplicados, los defectos siguientes apuntarian a sitios ambiguos.
    """
    out: list[OutlineDefect] = []
    seen: set[str] = set()
    for scene in outline.scenes:
        if scene.id in seen:
            out.append(OutlineDefect("escena-duplicada", scene.id, "identificador repetido"))
        seen.add(scene.id)

    positions: dict[tuple[int, int], str] = {}
    for scene in outline.scenes:
        key = (scene.chapter, scene.ordinal)
        if key in positions:
            out.append(
                OutlineDefect(
                    "posicion-ocupada",
                    scene.id,
                    f"el capitulo {scene.chapter} ya tiene una escena en la posicion "
                    f"{scene.ordinal}: {positions[key]}",
                )
            )
        positions[key] = scene.id
    return out


# ----------------------------------------------------------------- los arcos


def _check_arcs(outline: Outline) -> list[OutlineDefect]:
    """Todo arco tiene inicio, crisis y resolucion **que existen**.

    Que el arco declare una escena de resolucion no basta: si esa escena no esta
    en la escaleta, el arco no se resuelve en ningun sitio y nadie lo notaria
    hasta escribir el ultimo capitulo.
    """
    out: list[OutlineDefect] = []
    known = outline.scene_ids()

    for arc in outline.arcs:
        momentos = [("inicio", arc.start_scene), ("crisis", arc.crisis_scene)]
        if arc.resolution_scene is not None:
            momentos.append(("resolucion", arc.resolution_scene))

        for nombre, scene_id in momentos:
            if scene_id not in known:
                out.append(
                    OutlineDefect(
                        "arco-sin-escena",
                        arc.id,
                        f"su {nombre} apunta a {scene_id!r}, que no esta en la escaleta",
                    )
                )

        # El orden importa: una crisis antes del inicio no es un arco, es ruido.
        posiciones = {
            nombre: _position(outline, scene_id)
            for nombre, scene_id in momentos
            if scene_id in known
        }
        ordenados = [posiciones[n] for n in ("inicio", "crisis", "resolucion") if n in posiciones]
        if ordenados != sorted(ordenados):
            out.append(
                OutlineDefect(
                    "arco-desordenado",
                    arc.id,
                    "sus momentos no van en orden: inicio, crisis y resolucion "
                    "tienen que avanzar en la obra",
                )
            )
    return out


def _position(outline: Outline, scene_id: str) -> tuple[int, int]:
    scene = outline.scene(scene_id)
    return (scene.chapter, scene.ordinal) if scene else (0, 0)


def _check_double_arc(outline: Outline) -> list[OutlineDefect]:
    """DEP-20. El competitivo y el interno se resuelven en escenas distintas.

    Es el fallo estructural clasico del genero: si ganan y madura en la misma
    escena, la victoria explica el cambio interior y lo abarata. Que sean
    escenas distintas es lo minimo comprobable sin juicio.
    """
    out: list[OutlineDefect] = []
    comp = [a for a in outline.arcs if a.kind is ArcKind.COMPETITIVE]
    intern = [a for a in outline.arcs if a.kind is ArcKind.INTERNAL]

    if not comp or not intern:
        faltan = "competitivo" if not comp else "interno"
        out.append(
            OutlineDefect(
                "doble-arco-incompleto",
                "obra",
                f"no hay ningun arco {faltan}: el doble arco es el principio "
                "estructural del genero, no un adorno",
            )
        )
        return out

    for a in comp:
        for b in intern:
            if a.resolution_scene is not None and a.resolution_scene == b.resolution_scene:
                out.append(
                    OutlineDefect(
                        "doble-arco-colapsado",
                        a.resolution_scene,
                        f"los arcos {a.id!r} y {b.id!r} se resuelven en la misma escena; "
                        "la victoria explicaria el cambio interior y lo abarataria",
                    )
                )
    return out


# ------------------------------------------------------------------ promesas


def _check_setups(outline: Outline) -> list[OutlineDefect]:
    """Todo setup se planta y se cobra, y se cobra **despues** de plantarse."""
    out: list[OutlineDefect] = []
    known = outline.scene_ids()

    for setup in outline.setups:
        for nombre, scene_id in (
            ("plantado", setup.planted_scene),
            ("cobrado", setup.payoff_scene),
        ):
            if scene_id not in known:
                out.append(
                    OutlineDefect(
                        "setup-sin-escena",
                        setup.id,
                        f"se {nombre} en {scene_id!r}, que no esta en la escaleta",
                    )
                )
        if {setup.planted_scene, setup.payoff_scene} <= known and _position(
            outline, setup.payoff_scene
        ) <= _position(outline, setup.planted_scene):
            out.append(
                OutlineDefect(
                    "setup-invertido",
                    setup.id,
                    "se cobra antes o a la vez que se planta",
                )
            )
    return out


# ----------------------------------------------------------- curva de tension


def _check_tension(outline: Outline) -> list[OutlineDefect]:
    """La tension sube dentro de cada acto.

    Monotona **no decreciente**, no estrictamente creciente: un capitulo de
    respiro al mismo nivel es una decision legitima de ritmo. Lo que no lo es
    es bajar dentro de un acto, que deshace lo que el acto venia construyendo.
    """
    out: list[OutlineDefect] = []
    capitulos_por_acto: dict[int, set[int]] = {}
    for scene in outline.scenes:
        capitulos_por_acto.setdefault(scene.act, set()).add(scene.chapter)

    for act in outline.acts:
        esperados = len(capitulos_por_acto.get(act.number, set()))
        if len(act.tension) != esperados:
            out.append(
                OutlineDefect(
                    "tension-descuadrada",
                    f"acto {act.number}",
                    f"declara {len(act.tension)} valores de tension y el acto tiene "
                    f"{esperados} capitulos",
                )
            )
        for i in range(1, len(act.tension)):
            if act.tension[i] < act.tension[i - 1]:
                out.append(
                    OutlineDefect(
                        "tension-decreciente",
                        f"acto {act.number}",
                        f"baja de {act.tension[i - 1]} a {act.tension[i]} entre el "
                        f"capitulo {i} y el {i + 1} del acto",
                    )
                )
    return out


# ------------------------------------------------------------------ longitud


def _check_words(outline: Outline, word_range: tuple[int, int]) -> list[OutlineDefect]:
    """La suma de palabras cae en el rango del brief."""
    total = sum(s.target_words for s in outline.scenes)
    low, high = word_range
    if not low <= total <= high:
        return [
            OutlineDefect(
                "longitud-fuera-de-rango",
                "obra",
                f"la escaleta suma {total} palabras y el brief pide entre {low} y {high}",
            )
        ]
    return []


def _check_chapters(outline: Outline) -> list[OutlineDefect]:
    """Cada capitulo cae en el rango de EST-07, y no hay huecos en la numeracion."""
    out: list[OutlineDefect] = []
    low, high = CHAPTER_WORDS
    chapters = outline.chapters()

    for number, scenes in sorted(chapters.items()):
        words = sum(s.target_words for s in scenes)
        if not low <= words <= high:
            out.append(
                OutlineDefect(
                    "capitulo-fuera-de-rango",
                    f"capitulo {number}",
                    f"suma {words} palabras y el rango es {low} a {high}",
                )
            )

    numeros = sorted(chapters)
    if numeros and numeros != list(range(1, len(numeros) + 1)):
        faltan = sorted(set(range(1, max(numeros) + 1)) - set(numeros))
        out.append(
            OutlineDefect(
                "capitulos-con-huecos",
                "obra",
                f"faltan los capitulos {faltan[:_MAX_DETAIL]}",
            )
        )
    return out
