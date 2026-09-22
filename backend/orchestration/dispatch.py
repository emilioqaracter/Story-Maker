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

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from commons.provider.port import Completion, ProviderPort, ToolServer

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
) -> DispatchResult:
    """Llama al agente que toca y valida lo que devuelve.

    `parse` es el modelo pydantic que la salida tiene que satisfacer. Se pasa
    como argumento porque cada agente tiene el suyo y `dispatch` no debe conocer
    a ninguno: si tuviera un mapa de agente a esquema, anadir un agente exigiria
    tocar la frontera de confianza, que es lo ultimo que conviene tocar a menudo.
    """
    tope = min(max_output_tokens, MAX_OUTPUT_TOKENS)

    if tools:
        if server is None:
            raise ValueError(
                f"{agent!r} declara herramientas y no se le paso quien las sirve"
            )
        completion = port.complete_with_tools(
            cacheable_prefix=cacheable_prefix,
            packet=packet,
            instruction=instruction,
            output_schema=output_schema,
            max_output_tokens=tope,
            tools=tools,
            server=server,
        )
    else:
        completion = port.complete_once(
            cacheable_prefix=cacheable_prefix,
            packet=packet,
            instruction=instruction,
            output_schema=output_schema,
            max_output_tokens=tope,
        )

    if parse is not None:
        try:
            parse.model_validate_json(completion.text)  # type: ignore[attr-defined]
        except ValidationError as exc:
            raise OutputValidationError(
                f"la salida de {agent!r} no encaja con su esquema: {exc.error_count()} "
                f"error(es). Cuenta como llamada fallida"
            ) from exc

    return DispatchResult(
        agent=agent,
        raw=completion.text,
        completion=completion,
        tool_calls=len(completion.tool_calls),
    )
