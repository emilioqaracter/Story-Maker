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

from collections.abc import Sequence

from canon.brief import ELEMENT_PREFIX
from planning.outline.types import (
    NOVELA,
    ArcKind,
    LengthProfile,
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


def check(
    outline: Outline,
    *,
    word_range: tuple[int, int],
    profile: LengthProfile = NOVELA,
    elements: Sequence[tuple[str, str]] = (),
    has_rulebook: bool = True,
) -> list[OutlineDefect]:
    """Devuelve los defectos estructurales. Lista vacia significa que pasa.

    `profile` es el perfil de extension del brief (T53): de el salen los rangos
    de escena y de capitulo, y la forma de la obra si el perfil la fija.

    `elements` son los rasgos y recuerdos **obligatorios** del destinatario,
    como (identificador, texto): cada uno necesita su setup `element.<id>` con
    cobro planificado (RF-260). `has_rulebook` dice si el brief trae
    reglamento: sin el, ninguna escena puede ser un encuentro (RF-273).
    """
    defects: list[OutlineDefect] = []
    defects += _check_scene_ids(outline)
    defects += _check_arcs(outline)
    defects += _check_double_arc(outline)
    defects += _check_setups(outline)
    defects += _check_tension(outline)
    defects += _check_words(outline, word_range)
    defects += _check_scenes(outline, profile)
    defects += _check_chapters(outline, profile)
    defects += _check_shape(outline, profile)
    defects += _check_elements(outline, elements)
    defects += _check_matches(outline, has_rulebook=has_rulebook)
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
        # Un elemento del brief ya lo planto el encargo: su setup puede plantarse
        # y cobrarse en la misma escena, que es donde se integra (RF-260).
        mismo_sitio = setup.id.startswith(ELEMENT_PREFIX) and (
            setup.planted_scene == setup.payoff_scene
        )
        if (
            not mismo_sitio
            and {setup.planted_scene, setup.payoff_scene} <= known
            and _position(outline, setup.payoff_scene) <= _position(outline, setup.planted_scene)
        ):
            out.append(
                OutlineDefect(
                    "setup-invertido",
                    setup.id,
                    "se cobra antes o a la vez que se planta",
                )
            )
    return out


def _check_elements(outline: Outline, elements: Sequence[tuple[str, str]]) -> list[OutlineDefect]:
    """RF-260, D-95. Todo elemento obligatorio tiene su setup con cobro planificado.

    Un recuerdo que la escaleta no situa en ninguna escena no aparece nunca: el
    Escritor no lo sabe y el Archivero no tiene nada que citar. Que el cobro
    exista en la escaleta lo mira `_check_setups`; aqui, que el setup exista.
    """
    planificados = {s.id for s in outline.setups}
    out: list[OutlineDefect] = []
    for element_id, texto in elements:
        setup = f"{ELEMENT_PREFIX}{element_id}"
        if setup not in planificados:
            out.append(
                OutlineDefect(
                    "elemento-sin-cobro",
                    element_id,
                    f"el elemento obligatorio {element_id} «{texto[:80]}» no tiene setup "
                    f"{setup!r} con escena de cobro en la escaleta",
                )
            )
    return out


def _check_matches(outline: Outline, *, has_rulebook: bool) -> list[OutlineDefect]:
    """RF-273, D-104. Sin reglamento (DEP-02) no hay encuentros.

    `verify_match` comprueba el encuentro contra el reglamento del brief; con
    `is_match` y sin reglamento correria contra nada. Es una regla sobre los
    datos de la escaleta, sin juicio: va aqui, con la escena que lo trae.
    """
    if has_rulebook:
        return []
    return [
        OutlineDefect(
            "encuentro-sin-reglamento",
            s.id,
            "la escena es un encuentro (is_match) y el brief no tiene reglamento: "
            "sin el, el encuentro no se puede verificar",
        )
        for s in outline.scenes
        if s.is_match
    ]


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


def _check_scenes(outline: Outline, profile: LengthProfile) -> list[OutlineDefect]:
    """Cada escena cae en el rango de EST-08 del perfil."""
    low, high = profile.scene_words
    fuera = [s for s in outline.scenes if not low <= s.target_words <= high]
    return [
        OutlineDefect(
            "escena-fuera-de-rango",
            s.id,
            f"planifica {s.target_words} palabras y el rango de escena es {low} a {high}",
        )
        for s in fuera[:_MAX_DETAIL]
    ]


def _check_chapters(outline: Outline, profile: LengthProfile) -> list[OutlineDefect]:
    """Cada capitulo cae en el rango de EST-07, y no hay huecos en la numeracion."""
    out: list[OutlineDefect] = []
    low, high = profile.chapter_words
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


def _check_shape(outline: Outline, profile: LengthProfile) -> list[OutlineDefect]:
    """T53. Cuantos capitulos, escenas por capitulo y actos, si el perfil lo fija."""
    out: list[OutlineDefect] = []
    chapters = outline.chapters()
    if profile.chapters is not None and len(chapters) != profile.chapters:
        out.append(
            OutlineDefect(
                "capitulos-descuadrados",
                "obra",
                f"planifica {len(chapters)} capitulos y el perfil {profile.name!s} "
                f"pide exactamente {profile.chapters}",
            )
        )
    if profile.scenes_per_chapter is not None:
        out.extend(
            OutlineDefect(
                "escenas-descuadradas",
                f"capitulo {number}",
                f"tiene {len(scenes)} escenas y el perfil {profile.name!s} pide "
                f"exactamente {profile.scenes_per_chapter} por capitulo",
            )
            for number, scenes in sorted(chapters.items())
            if len(scenes) != profile.scenes_per_chapter
        )
    capitulos_por_acto: dict[int, set[int]] = {}
    for scene in outline.scenes:
        capitulos_por_acto.setdefault(scene.act, set()).add(scene.chapter)
    if profile.acts is not None and len(capitulos_por_acto) != profile.acts:
        out.append(
            OutlineDefect(
                "actos-descuadrados",
                "obra",
                f"planifica {len(capitulos_por_acto)} actos y el perfil {profile.name!s} "
                f"pide exactamente {profile.acts}",
            )
        )
    if profile.chapters_per_act is not None:
        out.extend(
            OutlineDefect(
                "actos-descuadrados",
                f"acto {act}",
                f"tiene {len(caps)} capitulos y el perfil {profile.name!s} pide "
                f"exactamente {profile.chapters_per_act} por acto",
            )
            for act, caps in sorted(capitulos_por_acto.items())
            if len(caps) != profile.chapters_per_act
        )
    return out
