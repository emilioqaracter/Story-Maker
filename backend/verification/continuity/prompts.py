"""Instruccion del Continuista: `continuity.review`.

RF-51, RF-52. El agente caro, y el que justifica la recuperacion selectiva. No
busca material que inspire: busca **todo lo que podria contradecir** al canon
en lo que los verificadores deterministas no alcanzan --una elipsis mal
contada, un personaje que actua sobre algo que no sabe, una competencia que no
tiene, un estado fisico que cambia sin motivo.

No ve el paquete que genero la prosa ni el razonamiento del Escritor (RF-52):
juzga el texto contra el canon, no contra lo que el Escritor creia.

Cada defecto cita el pasaje literal, y **la cita se comprueba** con
`check.evidence` antes de aceptar el defecto (RF-110). Sin cita anclada, el
defecto se descarta y se anota contra el Continuista, no contra el texto.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from canon.skills.read import WorldState
from commons.types.scene import SceneSpec

SYSTEM = """Eres el Continuista de una novela. Eres un componente de un sistema
automatico: devuelves JSON y nada mas. No valoras estilo ni ritmo: buscas
CONTRADICCIONES entre el capitulo y lo que el mundo de la novela ya tiene por
cierto.

Recibes el capitulo entero y el canon que podria contradecirlo: el estado del
mundo al empezar y al acabar, lo que sabe cada punto de vista, los hechos ya
congelados, las promesas abiertas.

REGLAS QUE NO SE NEGOCIAN

1. Solo defectos de continuidad: hechos, tiempo, conocimiento, competencia,
   estado fisico, identidad, lugar, punto de vista, arco, caracterizacion.
   Nada de estilo, ritmo, voz ni "podria estar mejor escrito": un adjetivo que
   la guia prohibe NO es un defecto tuyo. Lo que no sea continuidad se descarta.
2. Cada defecto cita el pasaje LITERAL del capitulo que lo muestra: copiado tal
   cual, ocho palabras seguidas o mas, y que aparezca una sola vez. Sin cita el
   defecto no existe.
3. Severidad: S1 si contradice el canon o el reglamento; S2 si dana el arco o
   la caracterizacion sin contradecir un hecho.
4. "rule" dice que hecho canonico o que regla se viola, con su valor: "el canon
   dice estado=lesionado desde el 10; aqui juega el 12".
5. Si no encuentras nada, devuelves la lista vacia. No inventes defectos para
   parecer util: un capitulo limpio existe.
6. Nunca propones la correccion. Eso es de otro."""


def schema() -> str:
    ejemplo = {
        "defects": [
            {
                "kind": "continuity.state",
                "severity": "S1",
                "quote": "Marcos salto al campo con el nueve a la espalda y el tobillo entero",
                "rule": "el canon dice marcos.estado=lesionado desde 2026-08-10; la escena es del 12",
            }
        ]
    }
    return (
        "Objeto con la clave defects: lista de objetos con kind (continuity.<ambito>, con "
        "ambito uno de fact, time, knowledge, competence, state, identity, place, pov, arc, "
        "character), "
        "severity (S1 o S2), quote (cita literal) y rule.\nEjemplo:\n"
        + json.dumps(ejemplo, ensure_ascii=False, indent=1)
    )


def instruction(
    specs: Sequence[SceneSpec],
    texts: Sequence[str],
    *,
    state_before: WorldState,
    state_after: WorldState,
    knowledge: Mapping[str, Sequence[str]],
    frozen_facts: Sequence[str] = (),
    open_setups: Sequence[str] = (),
) -> str:
    def estado(ws: WorldState) -> str:
        return (
            "\n".join(
                f"  {c.name} ({c.entity_id}): "
                + (", ".join(f"{k}={v}" for k, v in c.attributes) or "sin atributos")
                + (
                    f"; sabe hacer: {', '.join(f'{n}={lvl}' for n, lvl in c.competences)}"
                    if c.competences
                    else ""
                )
                for c in ws.cards
            )
            or "  (vacio)"
        )

    saberes = (
        "\n".join(
            f"  {quien}: {', '.join(sorted(hechos)) or 'nada registrado'}"
            for quien, hechos in sorted(knowledge.items())
        )
        or "  (sin POV registrados)"
    )
    hechos = "\n".join(f"  - {h}" for h in frozen_facts) or "  (ninguno relevante)"
    promesas = "\n".join(f"  - {s}" for s in open_setups) or "  (ninguna)"
    capitulo = "\n\n".join(
        f"### Escena {s.identity.ordinal} · {s.identity.world_time.stamp} · POV {s.identity.pov} · {s.identity.place}\n\n{t}"
        for s, t in zip(specs, texts, strict=True)
    )
    return f"""Verifica la continuidad de este capitulo.

ESTADO DEL MUNDO AL EMPEZAR ({state_before.at.stamp}):
{estado(state_before)}

ESTADO DEL MUNDO AL ACABAR ({state_after.at.stamp}):
{estado(state_after)}

LO QUE SABE CADA PUNTO DE VISTA AL EMPEZAR:
{saberes}

HECHOS CONGELADOS EN LA VENTANA TEMPORAL DEL CAPITULO:
{hechos}

PROMESAS ABIERTAS:
{promesas}

CAPITULO:

{capitulo}

Devuelve SOLO el JSON."""
