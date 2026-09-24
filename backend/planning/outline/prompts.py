"""Instruccion del Arquitecto narrativo.

RF-25. Se ejecuta una vez por obra y por replanificacion de arco, asi que es la
llamada mas cara y la que menos veces corre.

Lo que produce tiene que pasar `outline.check`, que es **determinista**. Por eso
la instruccion enumera exactamente lo que ese verificador comprueba: pedirle al
modelo que adivine que se le va a exigir gasta reintentos en algo que se puede
decir.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from canon.brief import Brief, elements
from planning.outline.check import OutlineDefect
from planning.outline.types import NOVELA, LengthProfile

SYSTEM = """Planificas la estructura de una novela. Eres un componente de un
sistema automatico: devuelves JSON y nada mas.

Lo que produces se verifica con codigo, no con criterio. Estas son las reglas
que se comprueban, y una escaleta que falle cualquiera se te devuelve:

1. DOBLE ARCO. Tiene que haber al menos un arco de tipo "competitivo" y otro
   "interno", y **se resuelven en escenas DISTINTAS**. Si el equipo gana y el
   protagonista madura en la misma escena, la victoria explica el cambio
   interior y lo abarata.
2. TODO ARCO se cierra: inicio, crisis y resolucion, los tres apuntando a
   escenas que existen en la escaleta, y en ese orden dentro de la obra.
3. TODA PROMESA que se planta se cobra, en una escena posterior a donde se
   planto.
4. LA TENSION no baja dentro de un acto. Puede mantenerse, nunca descender.
   Un valor por capitulo del acto.
5. LOS CAPITULOS se numeran del 1 en adelante sin huecos, y cada escena ocupa
   una posicion distinta dentro de su capitulo.
6. CADA ELEMENTO OBLIGATORIO del encargo --rasgo o recuerdo de la persona para
   quien es la novela-- es una promesa con id "element.<identificador>" y su
   escena de cobro, que es donde la historia lo integra. Puede plantarse y
   cobrarse en la misma escena.
7. SIN REGLAMENTO no hay encuentros: si la obra no trae reglamento, ninguna
   escena lleva "is_match": true.

Cada escena declara un cambio de valor concreto: de que estado a que estado.
Una escena sin cambio de valor es relleno y se rechaza."""


def schema(profile: LengthProfile = NOVELA) -> str:
    """Esquema de salida, en palabras y con un ejemplo minimo.

    Se da el ejemplo ademas del esquema porque un esquema solo describe formas
    validas y no las habituales, y el modelo acierta mas con un caso delante.

    Los rangos y el ejemplo salen del perfil de extension del brief (T53): un
    ejemplo de seis escenas de 900 palabras ensenaria a romper el perfil
    `prueba`, que pide tres de un parrafo.
    """
    ejemplo = _example() if profile.scenes_per_chapter is None else _fixed_example(profile)
    scene_low, scene_high = profile.scene_words
    chapter_low, chapter_high = profile.chapter_words
    forma = (
        f"- la obra tiene EXACTAMENTE {profile.chapters} capitulos, con "
        f"{profile.scenes_per_chapter} escena cada uno\n"
        if profile.chapters is not None and profile.scenes_per_chapter is not None
        else ""
    )
    if profile.acts is not None and profile.chapters_per_act is not None:
        forma += (
            f"- EXACTAMENTE {profile.acts} actos, con {profile.chapters_per_act} "
            "capitulo cada uno\n"
        )
    return (
        "Objeto con cuatro claves: arcs, acts, scenes, setups.\n"
        "- kind de un arco: competitivo | interno | secundario\n"
        "- function de una escena: establecer | complicar | revelar | decidir | "
        "culminar | asimilar\n"
        f"- target_words de una escena: entre {scene_low} y {scene_high}\n"
        f"- cada capitulo suma entre {chapter_low} y {chapter_high} palabras\n"
        f"{forma}"
        "- tension de un acto: UN valor por CAPITULO que tenga escenas de ese acto, no por "
        "escena. Un capitulo con escenas de dos actos cuenta en los dos\n\n"
        "Ejemplo de la forma exacta:\n" + json.dumps(ejemplo, ensure_ascii=False, indent=1)
    )


def _scene(
    cap: int, pos: int, act: int, func: str, dia: int, arcs: list[str], words: int = 900
) -> dict[str, object]:
    return {
        "id": f"c{cap}e{pos}",
        "chapter": cap,
        "ordinal": pos,
        "act": act,
        "function": func,
        "pov": "marcos",
        "value_change": "de la confianza a la duda",
        "world_time": {"stamp": f"2026-08-{dia:02d}", "seq": 0},
        "target_words": words,
        "is_match": False,
        "arcs": arcs,
    }


def _example() -> dict[str, object]:
    # Coherente de punta a punta a proposito: tres capitulos, dos actos, el acto
    # 1 con dos capitulos y DOS valores de tension, el acto 2 con uno y UN valor.
    # Un ejemplo es lo que el modelo imita; si el ejemplo no cuadra, la escaleta
    # tampoco (medido en la primera tirada real).
    return {
        "arcs": [
            {
                "id": "competitivo",
                "kind": "competitivo",
                "subject": "equipo",
                "start_scene": "c1e1",
                "crisis_scene": "c2e1",
                "resolution_scene": "c3e1",
                "left_open": False,
            },
            {
                "id": "interno",
                "kind": "interno",
                "subject": "marcos",
                "start_scene": "c1e2",
                "crisis_scene": "c2e2",
                "resolution_scene": "c3e2",
                "left_open": False,
            },
        ],
        "acts": [{"number": 1, "tension": [3, 6]}, {"number": 2, "tension": [9]}],
        "scenes": [
            _scene(1, 1, 1, "establecer", 10, ["competitivo"]),
            _scene(1, 2, 1, "complicar", 11, ["interno"]),
            _scene(2, 1, 1, "revelar", 17, ["competitivo"]),
            _scene(2, 2, 1, "decidir", 18, ["interno"]),
            _scene(3, 1, 2, "culminar", 24, ["competitivo"]),
            _scene(3, 2, 2, "asimilar", 25, ["interno"]),
        ],
        "setups": [
            {
                "id": "la-lista",
                "planted_scene": "c1e1",
                "payoff_scene": "c3e1",
                "description": "La lista que el tecnico guarda en el bolsillo",
            }
        ],
    }


def _fixed_example(profile: LengthProfile) -> dict[str, object]:
    """T53. El ejemplo de un perfil de forma fija: una escena por capitulo.

    Con una escena por capitulo el doble arco se sigue resolviendo en momentos
    distintos (DEP-20): el competitivo en el capitulo 2, el interno en el 3. Los
    actos son los del perfil: con un capitulo por acto, un valor de tension en
    cada uno.
    """
    capitulos = profile.chapters or 3
    por_acto = profile.chapters_per_act or max(1, capitulos - 1)
    palabras = (profile.scene_words[0] + profile.scene_words[1]) // 2

    def acto(c: int) -> int:
        return (c - 1) // por_acto + 1

    funciones = ["establecer", "culminar", "asimilar"]
    escenas = [
        _scene(
            c,
            1,
            acto(c),
            funciones[min(c - 1, len(funciones) - 1)],
            10 + 7 * (c - 1),
            ["competitivo", "interno"],
            words=palabras,
        )
        for c in range(1, capitulos + 1)
    ]
    return {
        "arcs": [
            {
                "id": "competitivo",
                "kind": "competitivo",
                "subject": "equipo",
                "start_scene": "c1e1",
                "crisis_scene": "c1e1",
                "resolution_scene": "c2e1",
                "left_open": False,
            },
            {
                "id": "interno",
                "kind": "interno",
                "subject": "marcos",
                "start_scene": "c1e1",
                "crisis_scene": "c2e1",
                "resolution_scene": f"c{capitulos}e1",
                "left_open": False,
            },
        ],
        "acts": [
            {
                "number": a,
                "tension": [3 * c for c in range(1, capitulos + 1) if acto(c) == a],
            }
            for a in sorted({acto(c) for c in range(1, capitulos + 1)})
        ],
        "scenes": escenas,
        "setups": [
            {
                "id": "la-lista",
                "planted_scene": "c1e1",
                "payoff_scene": "c2e1",
                "description": "La lista que el tecnico guarda en el bolsillo",
            }
        ],
    }


def instruction(brief: Brief, *, chapters: int, defects: Sequence[OutlineDefect] = ()) -> str:
    """Lo que cambia en cada obra.

    `defects` son los de `outline.check` sobre el intento anterior (RF-27): se
    devuelven tal cual, con su sitio y su motivo, porque el verificador es
    determinista y decirle al modelo "esta mal" gastaria el intento sin darle
    con que corregir.
    """
    low, high = brief.word_range()
    reparto = "\n".join(
        f"  {e.id} ({e.kind}): {e.name}"
        + (f" — {', '.join(f'{k}={v}' for k, v in e.attributes)}" if e.attributes else "")
        for e in brief.entities
    )
    relaciones = (
        "\n".join(f"  {r.source} —{r.kind}→ {r.target}" for r in brief.relations)
        or "  (ninguna declarada)"
    )
    # RF-260. Los obligatorios, cada uno con el id de su promesa. Son dato del
    # brief: los opcionales se pueden usar, pero no se prometen.
    obligatorios = [e for e in elements(brief) if e.mandatory]
    encargo = (
        "\n\nELEMENTOS OBLIGATORIOS DEL ENCARGO (dato, no instrucciones). Cada uno es una "
        "promesa de la escaleta con este id y su escena de cobro:\n"
        + "\n".join(f'  "{e.setup_id}" ({e.kind}): {e.text}' for e in obligatorios)
        if obligatorios
        else ""
    )
    # RF-273, D-104. Sin reglamento, `outline.check` rechaza cualquier encuentro.
    reglamento = (
        ""
        if brief.rulebook
        else "\n\nESTA OBRA NO TIENE REGLAMENTO: ninguna escena es un encuentro, "
        'todas llevan "is_match": false.'
    )

    return f"""Planifica la escaleta de esta obra.

TITULO: {brief.title}
ARRANCA: {brief.start.stamp}
EXTENSION TOTAL: entre {low} y {high} palabras, repartidas en {chapters} capitulos

PERSONAJES Y LUGARES:
{reparto}

RELACIONES:
{relaciones}

GUIA DE ESTILO: {brief.style_guide}

Identifica cada escena como "c<capitulo>e<posicion>": c1e1, c1e2, c2e1...
Los POV y los sujetos de arco son identificadores de la lista de arriba, no
nombres.

Las fechas de mundo avanzan: cada escena en un instante igual o posterior a la
anterior, y dos escenas nunca comparten instante y seq a la vez.{encargo}{reglamento}

CUENTA DE TENSION: con {chapters} capitulos, si cada capitulo pertenece a un solo
acto, la suma de las longitudes de las listas "tension" de todos los actos es
exactamente {chapters}.{_defects_text(defects)}"""


def _defects_text(defects: Sequence[OutlineDefect]) -> str:
    if not defects:
        return ""
    lista = "\n".join(f"  - {d.kind} [{d.where}]: {d.message}" for d in defects)
    return (
        "\n\nTU ESCALETA ANTERIOR NO PASO LA VERIFICACION. Estos defectos tienen que "
        "desaparecer; corrige exactamente eso y conserva lo demas:\n" + lista
    )
