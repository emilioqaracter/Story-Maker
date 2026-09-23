"""Instruccion del Reparador: `revise.targeted`.

RF-53, RF-54, CAL-08. Regeneracion **dirigida**: reescribe la escena con el
defecto y su evidencia delante, en lugar de repetir la generacion a ciegas. Es
la reflexion de `verification.md` §5.6 en su forma barata.

Recibe la escena completa que contiene el fragmento --se repara con la escena
delante, no el fragmento suelto--, los defectos agrupados con su cita y su
posicion, y los hechos canonicos que la correccion tiene que respetar. No ve el
paquete que genero el texto ni los veredictos de otros capitulos.

Toda reparacion revalida despues **desde la primera puerta** (RF-54): una
correccion de continuidad que rompe el formato se detecta igual.
"""

from __future__ import annotations

from collections.abc import Sequence

from commons.types.primitives import Defect
from commons.types.scene import SceneSpec

SYSTEM = """Reparas escenas de una novela. Eres un componente de un sistema
automatico: no conversas, no explicas, no comentas.

Recibes una escena, los defectos que tiene --cada uno con el pasaje exacto que
lo muestra-- y los hechos que la version corregida tiene que respetar.

REGLAS QUE NO SE NEGOCIAN

1. Corriges SOLO lo necesario para cerrar los defectos. Lo que no esta marcado
   se conserva palabra por palabra en la medida de lo posible.
2. La correccion respeta los hechos canonicos que se te dan. Si un defecto dice
   que el canon manda X, la escena corregida dice X.
3. No abres defectos nuevos: mismo punto de vista, mismo tiempo verbal, misma
   persona, misma longitud aproximada, mismo cambio de valor.
4. No inventas hechos del mundo para tapar el defecto. Si algo no esta en el
   contexto, no ocurrio.
5. La juntura con la escena anterior se mantiene: si te dan su cola, la escena
   corregida sigue encajando detras.

Devuelves la escena ENTERA corregida, solo la prosa. Sin titulo ni notas."""


def instruction(
    spec: SceneSpec,
    text: str,
    defects: Sequence[Defect],
    *,
    canon_facts: Sequence[str] = (),
    previous_tail: str = "",
) -> str:
    lista = "\n".join(
        f"  {i}. [{d.severity}] {d.kind} — {d.rule}\n     pasaje (pos {d.evidence.offset}): «{d.evidence.quote}»"
        for i, d in enumerate(defects, 1)
    )
    hechos = "\n".join(f"  - {h}" for h in canon_facts) or "  (los que la escena ya respeta)"
    cola = (
        f"\n\nCOLA DE LA ESCENA ANTERIOR, para no romper la juntura:\n{previous_tail}"
        if previous_tail
        else ""
    )
    return f"""Repara esta escena.

PUNTO DE VISTA: {spec.identity.pov} · LUGAR: {spec.identity.place}
CAMBIO DE VALOR QUE DEBE CONSERVAR: {spec.function.value_change}
COMO DEBE TERMINAR: {spec.output.ends_with}
LONGITUD: en torno a {spec.output.target_words} palabras

DEFECTOS A CERRAR:
{lista}

HECHOS CANONICOS QUE LA CORRECCION RESPETA:
{hechos}{cola}

ESCENA:

{text}

Devuelve SOLO la escena corregida."""
