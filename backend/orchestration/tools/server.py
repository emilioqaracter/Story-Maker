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

**Cada llamada queda trazada** (RF-264, RD-46): servida o rechazada, un registro
`tool` con su nombre, un resumen de sus argumentos, los tokens del resultado,
su procedencia, si se nego, el error y lo que tardo, y el agente, capitulo y
escena de la llamada que la hizo. Lleva el `call_id` de esa llamada, que es como
en Langfuse sale hija de su generation. El resumen no copia los argumentos: los
identificadores que pide un agente son de la novela.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Mapping, Sequence
from typing import Any, Literal, assert_never

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from canon.skills import read
from commons.provider.port import ToolCall, ToolResult
from commons.tracing.trace import Trace
from commons.types.primitives import BlockProvenance, WorldTime


class LookupArgs(BaseModel):
    """Argumentos de `canon.lookup`. Es el esquema **y** el validador.

    Estricto y cerrado a proposito: lo que el modelo manda es texto libre hasta
    que se comprueba, y un argumento mal tipado no se corrige aqui, se rechaza
    con el motivo. Coercionarlo --`"full": "no"` como `True`, `5` como `["5"]`--
    entrega algo que el modelo no pidio sin que se entere, y se fia de ello.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    kind: Literal["entity", "knowledge", "related"]
    entity_ids: tuple[str, ...] = ()
    entity_id: str = ""
    full: bool = False


class BudgetArgs(BaseModel):
    """`context.budget` no lleva argumentos: cualquier clave es de mas."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


#: El esquema de entrada que se le puede ensenar al modelo. Sale del mismo
#: modelo que valida: dos copias --una en prosa, otra en codigo-- se desalinean.
LOOKUP_INPUT_SCHEMA: dict[str, Any] = LookupArgs.model_json_schema()

#: Los esquemas de entrada por herramienta, para ensenarselos al modelo.
INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "canon.lookup": LOOKUP_INPUT_SCHEMA,
    "context.budget": BudgetArgs.model_json_schema(),
}


class ToolArgumentsError(RuntimeError):
    """Los argumentos de una herramienta no encajan con su esquema (RF-91).

    Incluye el JSON malformado. Es un error **de la llamada**, no de la tirada:
    el bucle de herramientas se lo devuelve al modelo con el motivo y cuenta
    como una negativa, igual que una herramienta fuera de lista.
    """


def _parse[A: BaseModel](model: type[A], call: ToolCall) -> A:
    """Valida los argumentos crudos contra su modelo, sin coercion.

    Los tres primeros errores con su ruta, como hace `dispatch` con la salida de
    un agente: "no encaja" sin decir donde no le deja al modelo corregir nada.
    """
    try:
        return model.model_validate_json(call.arguments)
    except ValidationError as exc:
        detalles = "; ".join(
            f"{'.'.join(str(x) for x in e['loc']) or '(raiz)'}: {e['msg']}"
            for e in exc.errors()[:3]
        )
        raise ToolArgumentsError(
            f"argumentos de {call.name!r} rechazados: {exc.error_count()} error(es) "
            f"[{detalles}]. Esquema: {model.model_json_schema()}"
        ) from exc


def _summary(arguments: str) -> dict[str, JsonValue]:
    """RF-264. Que se pidio, sin copiar lo pedido: claves, tamanos y el tipo de consulta."""
    try:
        crudo = json.loads(arguments)
    except ValueError:
        return {"malformed": True, "chars": len(arguments)}
    if not isinstance(crudo, dict):
        return {"malformed": True, "chars": len(arguments)}
    out: dict[str, JsonValue] = {}
    for k, v in sorted(crudo.items()):
        if k == "kind" and isinstance(v, str):
            out[k] = v[:40]
        elif isinstance(v, list):
            out[k] = len(v)
        elif isinstance(v, bool):
            out[k] = v
        else:
            out[k] = type(v).__name__
    return out


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
        trace: Trace | None = None,
        context: Mapping[str, JsonValue] | None = None,
    ) -> None:
        self._con = con
        self._budget = budget
        self._allowed = frozenset(allowed)
        self._at = at
        self._estimate = estimate
        self._model_id = model_id
        self._trace = trace
        #: Agente, capitulo, escena e intento de la llamada que sirve (RF-264).
        self._context = dict(context or {})
        self._call_id: str | None = None

    def bind_call(self, call_id: str) -> None:
        """`dispatch` dice a que llamada pertenecen las herramientas que se sirvan ahora."""
        self._call_id = call_id

    def input_schemas(self) -> dict[str, dict[str, Any]]:
        """RF-230. El esquema de entrada de cada herramienta de la lista, el mismo que valida.

        Es lo que el transporte le ensena al modelo (`claude_cli._tool_protocol`):
        `commons/` no puede importar este modulo, asi que el servidor se lo da.
        """
        return {k: v for k, v in INPUT_SCHEMAS.items() if k in self._allowed}

    def serve(self, call: ToolCall) -> ToolResult:
        """Sirve una herramienta y deja su registro `tool`, tambien si se rechaza (RF-264)."""
        inicio = time.monotonic()
        try:
            resultado = self._serve(call)
        except Exception as exc:
            self._record(call, inicio, None, error=f"{type(exc).__name__}: {exc}"[:300])
            raise
        self._record(call, inicio, resultado)
        return resultado

    def _record(
        self, call: ToolCall, inicio: float, result: ToolResult | None, *, error: str | None = None
    ) -> None:
        if self._trace is None:
            return
        self._trace.emit(
            "tool",
            **self._context,
            call=self._call_id,
            name=call.name,
            args=_summary(call.arguments),
            tokens=result.tokens if result else 0,
            provenance=str(result.provenance.value) if result else None,
            refused=bool(result.refused) if result else True,
            error=error,
            duration_ms=max(0, round((time.monotonic() - inicio) * 1000)),
        )

    def _serve(self, call: ToolCall) -> ToolResult:
        if call.name not in self._allowed:
            raise ToolNotAllowedError(
                f"{call.name!r} no esta en la lista de este agente: {sorted(self._allowed)}"
            )
        self._budget.queries += 1

        if call.name == "context.budget":
            _parse(BudgetArgs, call)
            return self._budget_tool()
        if call.name == "canon.lookup":
            return self._lookup(_parse(LookupArgs, call))
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

    def _lookup(self, args: LookupArgs) -> ToolResult:
        """RF-93 a RF-96. Mide el candidato **antes** de entregarlo."""
        contenido, procedencia = self._resolve(args)

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

    def _resolve(self, args: LookupArgs) -> tuple[str, BlockProvenance]:
        """Delega en las skills de lectura de `canon/`.

        Toda respuesta sale con procedencia: sin ella, un fragmento de prosa que
        describia una intencion se lee igual que un hecho canonico (RF-95).
        """
        at = self._at
        match args.kind:
            case "entity":
                cards = read.query(self._con, list(args.entity_ids), at=at, full=args.full)
                return (
                    "\n".join(
                        f"{c.name} ({c.entity_id}): "
                        + ", ".join(f"{k}={v}" for k, v in c.attributes)
                        for c in cards
                    ),
                    BlockProvenance.CANON,
                )
            case "knowledge":
                hechos = read.knowledge_of(self._con, args.entity_id, at)
                return ("\n".join(sorted(hechos)), BlockProvenance.CANON)
            case "related":
                return (
                    "\n".join(sorted(read.related(self._con, list(args.entity_ids), at=at))),
                    BlockProvenance.CANON,
                )
            case _:  # pragma: no cover - el Literal de LookupArgs lo hace inalcanzable
                assert_never(args.kind)
