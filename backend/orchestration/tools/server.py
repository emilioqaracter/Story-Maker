"""Las dos herramientas que un agente puede invocar durante su turno.

RF-91 a RF-100, CTX-21, CTX-22. Se sirven desde `orchestration/` porque es quien
lleva el contador de la llamada; `canon.lookup` delega en las skills de lectura
de `canon/` y no abre la base por su cuenta.

**La asimetria que esto aprovecha**: dentro de una llamada con herramientas, lo
que el agente sabe de si mismo es **exacto** --el recuento real viene en la
respuesta anterior-- y solo lo que todavia no ha entrado se estima. Que el
candidato se sobreestime es el lado bueno del error: como mucho se niega un
resultado que habria cabido, y el agente pide uno mas corto.

**Ninguna herramienta escribe.** La congelacion sigue siendo la unica operacion
que toca el canon.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from canon.skills import read
from commons.provider.port import ToolCall, ToolResult
from commons.types.primitives import BlockProvenance, WorldTime


def _as_ids(raw: JsonValue) -> list[str]:
    """Identificadores de una lista que llega de JSON.

    Lo que el modelo manda es texto libre hasta que se comprueba: una lista de
    numeros, o `None`, o un solo identificador suelto son todos posibles, y
    ninguno debe reventar aqui sino salir como consulta vacia o acotada.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(x) for x in raw]
    return [str(raw)]


class ToolNotAllowedError(RuntimeError):
    """El agente invoco algo fuera de su lista cerrada (RF-91).

    Se rechaza y se traza, y consume un reintento: una llamada a una herramienta
    que no le toca no es un despiste, es el modelo saliendose de su contrato.
    """


class QuotaExhaustedError(RuntimeError):
    """El cupo de tiron se agoto. No se amplia en caliente."""


class CallBudget(BaseModel):
    """El contador de una llamada en curso."""

    model_config = ConfigDict(frozen=False)

    ceiling: int = Field(gt=0)
    #: Recuento **real**, del `usage` de la ultima respuesta. No es una
    #: estimacion: por eso `context.budget` puede devolver un numero fiable.
    consumed: int = Field(default=0, ge=0)
    quota: int = Field(default=0, ge=0, description="CTX-22")
    quota_used: int = Field(default=0, ge=0)
    queries: int = Field(default=0, ge=0)

    @property
    def available(self) -> int:
        return max(0, min(self.ceiling - self.consumed, self.quota - self.quota_used))


class ToolServer:
    """Sirve las herramientas de un agente contra el contador de su llamada."""

    def __init__(
        self,
        con: sqlite3.Connection,
        budget: CallBudget,
        *,
        allowed: Sequence[str],
        at: WorldTime,
        estimate: object,
        model_id: str,
    ) -> None:
        self._con = con
        self._budget = budget
        self._allowed = frozenset(allowed)
        self._at = at
        self._estimate = estimate
        self._model_id = model_id

    def serve(self, call: ToolCall) -> ToolResult:
        if call.name not in self._allowed:
            raise ToolNotAllowedError(
                f"{call.name!r} no esta en la lista de este agente: {sorted(self._allowed)}"
            )
        self._budget.queries += 1

        if call.name == "context.budget":
            return self._budget_tool()
        if call.name == "canon.lookup":
            return self._lookup(json.loads(call.arguments))
        raise ToolNotAllowedError(f"{call.name!r} no es una herramienta conocida")

    # ------------------------------------------------------- context.budget

    def _budget_tool(self) -> ToolResult:
        """RF-92. Devuelve un numero **medido**, no una estimacion."""
        cuerpo = (
            f"consumido: {self._budget.consumed} tokens\n"
            f"disponible: {self._budget.available} tokens\n"
            f"techo: {self._budget.ceiling} tokens\n"
            f"consultas hechas: {self._budget.queries}"
        )
        return ToolResult(content=cuerpo, provenance=BlockProvenance.PLAN, tokens=0)

    # --------------------------------------------------------- canon.lookup

    def _lookup(self, args: Mapping[str, JsonValue]) -> ToolResult:
        """RF-93 a RF-96. Mide el candidato **antes** de entregarlo."""
        kind = str(args.get("kind", ""))
        contenido, procedencia = self._resolve(kind, args)

        coste = self._estimate.estimate(contenido, self._model_id)  # type: ignore[attr-defined]

        if coste > self._budget.available:
            # No se trunca: se niega y se dice cuanto ocupaba, para que el agente
            # pueda acotar. Media ficha de personaje es peor que ninguna, porque
            # el agente no sabe que le falta y se fia de lo que llego.
            return ToolResult(
                content=(
                    f"no cabe: el resultado ocupa {coste} tokens y quedan "
                    f"{self._budget.available}. Acota la consulta --menos entidades, "
                    f"un instante mas concreto-- y vuelve a pedirla"
                ),
                provenance=BlockProvenance.PLAN,
                tokens=0,
                refused=True,
            )

        self._budget.quota_used += coste
        return ToolResult(content=contenido, provenance=procedencia, tokens=coste)

    def _resolve(self, kind: str, args: Mapping[str, JsonValue]) -> tuple[str, BlockProvenance]:
        """Delega en las skills de lectura de `canon/`.

        Toda respuesta sale con procedencia: sin ella, un fragmento de prosa que
        describia una intencion se lee igual que un hecho canonico (RF-95).
        """
        at = self._at
        match kind:
            case "entity":
                ids = _as_ids(args.get("entity_ids"))
                cards = read.query(self._con, ids, at=at, full=bool(args.get("full")))
                return (
                    "\n".join(
                        f"{c.name} ({c.entity_id}): "
                        + ", ".join(f"{k}={v}" for k, v in c.attributes)
                        for c in cards
                    ),
                    BlockProvenance.CANON,
                )
            case "knowledge":
                quien = str(args.get("entity_id", ""))
                hechos = read.knowledge_of(self._con, quien, at)
                return ("\n".join(sorted(hechos)), BlockProvenance.CANON)
            case "related":
                semillas = _as_ids(args.get("entity_ids"))
                return (
                    "\n".join(sorted(read.related(self._con, semillas, at=at))),
                    BlockProvenance.CANON,
                )
            case _:
                raise ToolNotAllowedError(
                    f"tipo de consulta desconocido: {kind!r}. Validos: entity, knowledge, related"
                )
