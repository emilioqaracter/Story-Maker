"""Instruccion del Especialista deportivo: `match.narrate`.

RF-44. **El encuentro ya esta resuelto** cuando llega aqui: `match.simulate`
decidio marcador, hitos y lesiones, y el modelo solo los dramatiza. Invertirlo
reintroduce toda la familia de defectos de verosimilitud deportiva que el motor
de reglas elimina de raiz.

La cronologia entra en el paquete **como dato**, con minutos y nombres, y el
verificador `check.ledger` contrasta despues que la prosa cuente exactamente
eso: mismo marcador, mismos goleadores, mismo orden.

En el perfil de extension `prueba` la instruccion lleva ademas el resultado
obligatorio dicho como lo comprueba `check.ledger` (D-115): el marcador en
cifras, local primero, como unica pareja de cifras de la prosa; cada goleador
con su nombre completo y su minuto; y la ultima frase con el marcador. En
`novela` la instruccion no cambia.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from commons.types.length import NOVELA, LengthProfile, LengthProfileName
from commons.types.primitives import Defect
from commons.types.scene import SceneSpec
from generation.sports.simulate import MatchResult, MilestoneKind
from generation.writer.prompts import previous_defects

SYSTEM = """Narras encuentros deportivos dentro de una novela. Eres un componente
de un sistema automatico: no conversas, no explicas, no comentas.

El encuentro YA ESTA RESUELTO. Recibes su cronologia cerrada: quien marco, en
que minuto, quien se lesiono, como acabo. Tu trabajo es dramatizarla desde el
punto de vista indicado. No decides nada del resultado.

REGLAS QUE NO SE NEGOCIAN

1. El marcador final que narras es EXACTAMENTE el de la cronologia. Si aparece
   una cifra, es esa.
2. Todos los goles de la cronologia ocurren en la prosa, con su autor, en el
   orden de los minutos. Ningun gol de mas.
3. Nadie que no este en las plantillas dadas toca el balon.
4. Una lesion de la cronologia se ve: el jugador se retira y no vuelve a actuar.
5. Un solo punto de vista. Solo ves lo que ese personaje ve desde donde esta.
6. Tercera persona, tiempo pasado. Escena dramatizada, no cronica de prensa: la
   accion se vive, no se enumera.
7. La escena tiene que cambiar algo en el POV: empieza en un estado y termina en
   otro, y no es solo el marcador."""


def chronology(result: MatchResult, names: Mapping[str, str]) -> str:
    """La cronologia como texto, con nombres en vez de identificadores."""
    lineas = []
    for m in result.milestones:
        quien = names.get(m.player_id, m.player_id)
        equipo = names.get(m.team_id, m.team_id)
        match m.kind:
            case MilestoneKind.GOAL:
                lineas.append(f"  min {m.minute}: GOL de {quien} ({equipo})")
            case MilestoneKind.INJURY:
                lineas.append(f"  min {m.minute}: LESION de {quien} ({equipo}), {m.detail}")
            case MilestoneKind.CARD:
                lineas.append(f"  min {m.minute}: tarjeta a {quien} ({equipo})")
            case MilestoneKind.SUBSTITUTION:
                lineas.append(f"  min {m.minute}: cambio, entra {quien} ({equipo})")
    local = names.get(result.home_team, result.home_team)
    visitante = names.get(result.away_team, result.away_team)
    cabecera = (
        f"  {local} {result.home_goals} - {result.away_goals} {visitante} ({result.at.stamp})"
    )
    return "\n".join([cabecera, *lineas]) or cabecera


def ledger_rules(result: MatchResult, names: Mapping[str, str]) -> str:
    """D-115. El resultado obligatorio, dicho como lo comprueba `check.ledger`.

    `check_ledger` marca S1 toda pareja de cifras separadas por guion o por «a»
    que no sea el marcador final, en el orden local-visitante; `check_milestones`,
    todo goleador cuyo nombre completo no aparezca. Asi que un marcador parcial en
    cifras, un «3 a 4 metros» o un goleador nombrado solo por su apellido son un
    S1 aunque la escena cuente bien el partido.
    """
    local = names.get(result.home_team, result.home_team)
    visitante = names.get(result.away_team, result.away_team)
    marcador = expected_score(result)
    goles = [
        f"  - min {m.minute}: {names.get(m.player_id, m.player_id)}"
        for m in result.milestones
        if m.kind is MilestoneKind.GOAL
    ]
    lista = "\n".join(goles) if goles else "  - ninguno: el partido acaba sin goles"
    return f"""RESULTADO OBLIGATORIO (el sistema lo comprueba letra a letra):
- El marcador final es {local} {marcador} {visitante}. Escribelo en cifras
  exactamente asi, «{marcador}», con el local primero. Ni otro marcador ni otro orden.
- Es la UNICA pareja de cifras unidas por guion o por «a» de toda la prosa: los
  marcadores parciales se dicen con palabras («el empate», «se pusieron por
  delante»), nunca en cifras, y ninguna otra cantidad va como «N a N» o «N-N».
- Estos son todos los goles, y en la prosa ocurren todos, en este orden, con el
  nombre completo de su autor escrito tal cual y su minuto. Ni uno mas ni uno menos:
{lista}
- La ultima frase de la escena dice el marcador final en cifras: «{marcador}».

"""


def instruction(
    spec: SceneSpec,
    result: MatchResult,
    names: Mapping[str, str],
    previous: Sequence[Defect] = (),
    *,
    profile: LengthProfile = NOVELA,
) -> str:
    beats = "\n".join(f"  {i}. {b}" for i, b in enumerate(spec.content.beats, 1))
    novela = profile.name is LengthProfileName.NOVELA
    obligatorio = "" if novela else ledger_rules(result, names)
    return f"""Narra este encuentro.

PUNTO DE VISTA: {spec.identity.pov}
LUGAR: {spec.identity.place}
PERSONAJES PRESENTES: {", ".join(spec.content.cast)}

CRONOLOGIA CERRADA DEL ENCUENTRO:
{chronology(result, names)}

{obligatorio}QUE QUIERE EL POV: {spec.function.objective}
QUE SE LO IMPIDE: {spec.function.obstacle}
CAMBIO DE VALOR: {spec.function.value_change}
COMO TERMINA: {spec.output.ends_with}

PASOS:
{beats}

LONGITUD: en torno a {spec.output.target_words} palabras.{previous_defects(previous)}

Devuelve SOLO la prosa. Sin titulo, sin marcador en cabecera, sin notas."""


def expected_score(result: MatchResult) -> str:
    """El marcador tal como `check.ledger` lo espera."""
    return f"{result.home_goals}-{result.away_goals}"


def scorers(result: MatchResult, names: Mapping[str, str]) -> tuple[str, ...]:
    """Autores de los goles, en orden, con nombre: lo que la prosa tiene que contener."""
    return tuple(
        names.get(m.player_id, m.player_id)
        for m in result.milestones
        if m.kind is MilestoneKind.GOAL
    )
