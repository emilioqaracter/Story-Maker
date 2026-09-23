"""`dispatch`. La frontera de confianza.

RF-21, RI-25, RNF-10. Es donde el texto de un modelo se convierte en objeto
tipado, y **concentra el riesgo del sistema entero**: todo lo que pase de aqui
sin validar contamina el canon, y no hay revision humana detras que lo detecte.

Tres cosas ocurren aqui y en ningun otro sitio:

1. **La salida se valida contra su esquema.** Si no valida, la llamada cuenta
   como fallida y consume un reintento. No se intenta arreglar el texto: un
   modelo que devuelve algo que no encaja ha entendido mal el encargo, y
   remendar su salida esconde el problema.
2. **Se aplica el tope de salida.** En el codigo, no como herramienta: un tope
   que el modelo decide si invoca no es un tope.
3. **Se sirve el bucle de herramientas** para los agentes que las declaran, con
   su lista cerrada y su cupo.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from commons.provider.port import Completion, ProviderPort, ToolServer
from commons.tracing.trace import Trace

#: RF-16. Red de seguridad: impide que la salida de un agente ocupe sola la
#: ventana del siguiente. No sustituye a los topes de longitud narrativa por
#: agente, que son los que impiden una escena de 6.000 palabras.
MAX_OUTPUT_TOKENS = 50_000


class OutputValidationError(RuntimeError):
    """La salida del modelo no encaja con su esquema.

    Cuenta como llamada fallida y consume un reintento (RI-18).
    """


class DispatchResult(BaseModel):
    """Lo que devuelve una llamada, ya validado."""

    model_config = ConfigDict(frozen=True)

    agent: str
    raw: str
    completion: Completion
    tool_calls: int = Field(default=0, ge=0)
    #: RF-235. Lo que tardo la llamada, bucle de herramientas incluido.
    duration_ms: int = Field(default=0, ge=0)

    @property
    def real_input_tokens(self) -> int:
        """Recuento **real**, sumando los tres campos de entrada.

        Leer solo el primero da la cola no cacheada y no el tamano del prompt:
        lo servido desde cache ocupa ventana igual.
        """
        return self.completion.usage.total_input


def dispatch(
    port: ProviderPort,
    *,
    agent: str,
    cacheable_prefix: str,
    packet: str,
    instruction: str,
    output_schema: str,
    max_output_tokens: int,
    tools: Sequence[str] = (),
    server: ToolServer | None = None,
    parse: object | None = None,
    trace: Trace | None = None,
    estimated_input: int | None = None,
    context: Mapping[str, JsonValue] | None = None,
) -> DispatchResult:
    """Llama al agente que toca y valida lo que devuelve.

    `parse` es el modelo pydantic que la salida tiene que satisfacer. Se pasa
    como argumento porque cada agente tiene el suyo y `dispatch` no debe conocer
    a ninguno: si tuviera un mapa de agente a esquema, anadir un agente exigiria
    tocar la frontera de confianza, que es lo ultimo que conviene tocar a menudo.

    `trace`, `estimated_input` y `context` son la traza de la llamada (RI-16):
    agente, lo que se estimo, lo que costo de verdad y el andamiaje que el
    transporte anadio (D-35). Se compara estimado mas andamiaje contra real,
    porque el `usage` incluye el andamiaje y el estimado del paquete no.
    """
    tope = min(max_output_tokens, MAX_OUTPUT_TOKENS)
    # El esquema JSON real del artefacto, para el proveedor que sepa hacerlo
    # cumplir. La validacion de abajo no se relaja por ello (RI-18).
    esquema_json = (
        json.dumps(parse.model_json_schema(), ensure_ascii=False)  # type: ignore[attr-defined]
        if parse is not None
        else None
    )

    if tools and server is None:
        raise ValueError(f"{agent!r} declara herramientas y no se le paso quien las sirve")

    # RF-235. Reloj monotono alrededor de la llamada entera, bucle de
    # herramientas incluido: es la latencia que ve el ciclo, no la del proveedor.
    inicio = time.monotonic()
    if tools:
        assert server is not None
        completion = port.complete_with_tools(
            cacheable_prefix=cacheable_prefix,
            packet=packet,
            instruction=instruction,
            output_schema=output_schema,
            max_output_tokens=tope,
            tools=tools,
            server=server,
            json_schema=esquema_json,
        )
    else:
        completion = port.complete_once(
            cacheable_prefix=cacheable_prefix,
            packet=packet,
            instruction=instruction,
            output_schema=output_schema,
            max_output_tokens=tope,
            json_schema=esquema_json,
        )
    duracion = max(0, round((time.monotonic() - inicio) * 1000))

    real = completion.usage.total_input
    harness = completion.harness_tokens
    ok = True
    error: str | None = None
    if parse is not None:
        try:
            parse.model_validate_json(completion.text)  # type: ignore[attr-defined]
        except ValidationError as exc:
            ok = False
            # Los tres primeros errores con su ruta: es lo que el reintento le
            # devuelve al modelo, y "no encaja" sin decir donde no corrige nada.
            detalles = "; ".join(
                f"{'.'.join(str(x) for x in e['loc']) or '(raiz)'}: {e['msg']}"
                for e in exc.errors()[:3]
            )
            error = (
                f"la salida de {agent!r} no encaja con su esquema: {exc.error_count()} "
                f"error(es) [{detalles}]. Cuenta como llamada fallida"
            )

    if trace is not None:
        trace.emit(
            "call",
            agent=agent,
            estimated_input=estimated_input,
            real_input=real,
            harness_tokens=harness,
            output_tokens=completion.usage.output_tokens,
            # RF-235: los cuatro campos de uso por separado, para que el espejo
            # pueda dar la generation con su cache; `real_input` es su suma.
            input_tokens=completion.usage.input_tokens,
            cache_creation_tokens=completion.usage.cache_creation_tokens,
            cache_read_tokens=completion.usage.cache_read_tokens,
            model=completion.model or None,
            cost_usd=completion.cost_usd,
            duration_ms=duracion,
            tool_calls=len(completion.tool_calls),
            # RNF-19: el estimado mas el andamiaje nunca queda por debajo del
            # real. Si queda, el factor del contador se ha quedado corto.
            estimate_short=(estimated_input is not None and estimated_input + harness < real),
            ok=ok,
            error=error,
            raw_head=None if ok else completion.text[:400],
            **dict(context or {}),
        )

    if not ok:
        raise OutputValidationError(error or "salida invalida")

    return DispatchResult(
        agent=agent,
        raw=completion.text,
        completion=completion,
        tool_calls=len(completion.tool_calls),
        duration_ms=duracion,
    )
