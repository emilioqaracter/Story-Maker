"""Instruccion del Escritor de escena.

RF-40, RF-41. Es la llamada que mas veces se ejecuta de todo el sistema, asi que
lo que se diga aqui se dice cientos de veces por novela.

El prefijo cacheable --guia de estilo, invariantes duros, lexico-- va aparte y
es **identico en todas las llamadas de este agente**: es lo que el cache casa, y
un byte voluble delante lo invalida sin dar error.
"""

from __future__ import annotations

from commons.types.scene import SceneSpec

#: Prefijo cacheable. Todo lo estable del Escritor.
#:
#: Las restricciones van aqui y no en la instruccion por dos motivos: son las
#: mismas en toda la obra, y estar al principio es lo que las hace cacheables.
SYSTEM = """Escribes escenas de una novela. Eres un componente de un sistema
automatico: no conversas, no explicas lo que vas a hacer y no comentas tu propio
trabajo.

REGLAS QUE NO SE NEGOCIAN

1. Un solo punto de vista por escena. Solo ves, oyes y piensas lo que ese
   personaje ve, oye y piensa. Nunca entras en la cabeza de otro.
2. Tercera persona, tiempo pasado.
3. No inventas hechos del mundo. Nombres, fechas, resultados y estados fisicos
   salen del contexto que se te da. Si algo no esta, no ocurrio.
4. El personaje que narra no puede mencionar lo que todavia no sabe. Si el
   contexto dice que desconoce algo, para el no existe.
5. Escribes escena, no resumen. Escenas dramatizadas con dialogo y accion
   concreta, no narracion que cuente por encima lo que paso.
6. No usas los terminos de la lista de proscripcion si se te da una.

La escena tiene que cambiar algo: empieza en un estado y termina en otro. Una
escena donde no cambia nada es relleno, y el relleno se rechaza."""


def instruction(spec: SceneSpec) -> str:
    """La parte que cambia en cada escena."""
    beats = "\n".join(f"  {i}. {b}" for i, b in enumerate(spec.content.beats, 1))
    prohibidos = (
        "\nNO uses estas expresiones: " + ", ".join(spec.constraints.forbidden)
        if spec.constraints.forbidden
        else ""
    )
    ignora = (
        "\nEl POV NO sabe todavia: " + "; ".join(spec.constraints.facts_unknown_to_pov)
        if spec.constraints.facts_unknown_to_pov
        else ""
    )

    return f"""Escribe esta escena.

PUNTO DE VISTA: {spec.identity.pov}
LUGAR: {spec.identity.place}
PERSONAJES PRESENTES: {", ".join(spec.content.cast)}

QUE QUIERE EL POV: {spec.function.objective}
QUE SE LO IMPIDE: {spec.function.obstacle}
CAMBIO DE VALOR: {spec.function.value_change}
COMO TERMINA: {spec.output.ends_with}

PASOS:
{beats}

LONGITUD: en torno a {spec.output.target_words} palabras.{prohibidos}{ignora}

Devuelve SOLO la prosa de la escena. Sin titulo, sin numero, sin notas."""
