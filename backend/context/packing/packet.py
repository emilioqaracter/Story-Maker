"""El paquete de contexto: bloques, presupuesto y compactacion.

RF-32 a RF-35, RF-88, RF-103, RF-109. CTX-03.

Tres reglas gobiernan todo lo de aqui, y las tres tienen consecuencias visibles
en el codigo:

1. **Cada bloque declara su procedencia.** Sin la etiqueta, un fragmento de
   prosa que describia una intencion se lee igual que un hecho canonico, y a los
   tres capitulos esa intencion se ha convertido en verdad sin que nadie la haya
   aprobado.
2. **Al desbordar se compacta por prioridad inversa, nunca se trunca.** Primero
   los fragmentos recuperados, despues la prosa previa, despues los resumenes,
   despues las fichas secundarias. Las anclas, el conocimiento del POV y la
   especificacion **no se tocan jamas**.
3. **El ensamblador es una funcion pura.** Construye cada paquete desde cero y
   no lo muta ni lo reutiliza. Eso es el aislamiento en forma comprobable: si
   dos llamadas comparten un objeto de paquete, el aislamiento ya esta roto
   aunque nadie lo note.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import IntEnum

from pydantic import BaseModel, ConfigDict, Field

from commons.types.primitives import BlockProvenance, Quota

#: RF-103. Tamano del prefijo cacheable. El modelo no cachea prefijos por debajo
#: de 4.096 y no avisa, asi que por debajo de esa cifra comprimir el ancla es
#: una economia falsa: se cobra entera en todas las llamadas.
CACHEABLE_PREFIX_TOKENS = 4_500

#: Tope de ensamblaje. Los 15.000 que faltan hasta el techo quedan para lo que
#: anada un reintento --el defecto y su evidencia-- sin rehacer el paquete.
MAX_PACKET_TOKENS = 85_000


class Priority(IntEnum):
    """Orden de sacrificio al desbordar. Menor numero, se sacrifica antes.

    `UNTOUCHABLE` no es una prioridad alta: es la ausencia de prioridad. Una
    llamada sin anclas es deriva garantizada, y una sin especificacion de escena
    no sabe que escribir.
    """

    RETRIEVED = 0
    PREVIOUS_PROSE = 1
    SUMMARIES = 2
    SECONDARY_CARDS = 3
    UNTOUCHABLE = 99


class Block(BaseModel):
    """Un bloque del paquete."""

    model_config = ConfigDict(frozen=True)

    name: str
    content: str
    tokens: int = Field(ge=0)
    provenance: BlockProvenance
    priority: Priority
    quota: Quota | None = Field(
        default=None, description="Solo los fragmentos recuperados lo llevan"
    )
    source_chapter: int | None = Field(
        default=None, description="Obligatorio si la procedencia es prosa congelada"
    )
    compacted: bool = False


class Packet(BaseModel):
    """CTX-03. Lo que recibe un agente de modelo."""

    model_config = ConfigDict(frozen=True)

    agent: str
    version: int = Field(default=1)
    blocks: tuple[Block, ...]
    degraded: bool = Field(
        default=False,
        description="La pierna semantica no aporto. Se marca y se traza (RF-78)",
    )

    @property
    def tokens(self) -> int:
        return sum(b.tokens for b in self.blocks)

    @property
    def cacheable_prefix(self) -> str:
        """El tramo inicial identico en todas las llamadas de este agente.

        **Nada voluble delante**: el cache casa por prefijo, asi que un byte
        distinto --una marca de tiempo, un contador de intento-- invalida la
        llamada entera sin dar error.
        """
        return "\n\n".join(
            b.content for b in self.blocks if b.priority is Priority.UNTOUCHABLE and b.name == "ancla"
        )

    def body(self) -> str:
        """Todo lo que va detras del prefijo cacheable."""
        return "\n\n".join(
            b.content for b in self.blocks if not (b.priority is Priority.UNTOUCHABLE and b.name == "ancla")
        )


def compact(blocks: Sequence[Block], *, budget: int) -> list[Block]:
    """Reduce por prioridad inversa hasta caber. Nunca trunca.

    Un bloque compactable se **quita entero**, no se corta: medio bloque de
    fragmentos recuperados es peor que ninguno, porque el agente no sabe que le
    falta y se fia de lo que quedo.

    Se quitan de uno en uno y se recomprueba, en vez de calcular cuantos sobran:
    asi se conserva todo lo que quepa, que es el objetivo.
    """
    resultado = list(blocks)
    total = sum(b.tokens for b in resultado)
    if total <= budget:
        return resultado

    for nivel in sorted(Priority):
        if nivel is Priority.UNTOUCHABLE:
            break
        # Dentro de un nivel, el ultimo primero: en los bloques de fragmentos, el
        # orden es de mas a menos relevante, asi que cortar por el final quita lo
        # que menos aporta.
        candidatos = [i for i, b in enumerate(resultado) if b.priority is nivel]
        for i in reversed(candidatos):
            if total <= budget:
                return resultado
            total -= resultado[i].tokens
            resultado[i] = resultado[i].model_copy(
                update={"content": "", "tokens": 0, "compacted": True}
            )

    return [b for b in resultado if b.tokens > 0 or b.priority is Priority.UNTOUCHABLE]


def assemble(
    *,
    agent: str,
    blocks: Sequence[Block],
    budget: int = MAX_PACKET_TOKENS,
    degraded: bool = False,
) -> Packet:
    """Monta el paquete. **Funcion pura**: no muta lo que recibe.

    El orden lo fija quien llama, porque lo fija la receta del agente destino, no
    esta funcion. Lo unico que se impone aqui es que la especificacion de escena
    vaya al final y el ancla al principio (RF-34), que es aprovechar el sesgo de
    recencia en vez de sufrirlo.
    """
    ordenados = _order(blocks)
    ajustados = compact(ordenados, budget=budget)
    return Packet(agent=agent, blocks=tuple(ajustados), degraded=degraded)


def _order(blocks: Sequence[Block]) -> list[Block]:
    """Ancla al principio, especificacion al final, lo demas como venia."""
    ancla = [b for b in blocks if b.name == "ancla"]
    spec = [b for b in blocks if b.name == "especificacion"]
    resto = [b for b in blocks if b.name not in {"ancla", "especificacion"}]
    return [*ancla, *resto, *spec]
