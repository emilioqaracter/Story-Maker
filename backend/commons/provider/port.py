"""Puerto de proveedor. Ningun agente importa un SDK directamente.

RI-11, RI-24. `architecture.md` 4.8: con el puerto, cambiar de modelo es
cambiar una configuracion y no tocar once agentes.

Dos modos de `complete`, y **quien usa cual no lo decide el agente** sino su
ficha en la matriz de `architecture.md` 6.3:

- `complete_once`: una ida y vuelta. Los agentes sin herramientas.
- `complete_with_tools`: bucle de herramientas. Los cinco que las declaran.

Si el puerto expusiera uno solo, los agentes con herramientas no tendrian
donde vivir.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from commons.types.primitives import BlockProvenance


class Usage(BaseModel):
    """Recuento real que devuelve el proveedor (RI-12).

    La entrada es la **suma de los tres campos**: lo servido desde cache ocupa
    ventana igual que lo demas, asi que leer solo `input_tokens` da la cola no
    cacheada y no el tamano del prompt.
    """

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(ge=0, description="Entrada no cacheada")
    cache_creation_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(ge=0)

    @property
    def total_input(self) -> int:
        return self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens


class ToolCall(BaseModel):
    """Una invocacion de herramienta durante el turno de un agente."""

    model_config = ConfigDict(frozen=True)

    name: str
    arguments: str = Field(description="JSON crudo; lo valida quien sirve la herramienta")


class ToolResult(BaseModel):
    """Lo que se devuelve al agente tras servir una herramienta.

    `provenance` no es decoracion: sin ella un resultado de prosa se lee igual
    que un hecho canonico, que es CTX-13 por la puerta de atras (RF-95).
    """

    model_config = ConfigDict(frozen=True)

    content: str
    provenance: BlockProvenance
    tokens: int = Field(ge=0, description="Coste estimado, ya con factor aplicado")
    refused: bool = Field(
        default=False,
        description="True si no cabia en el presupuesto: entonces `content` dice cuanto ocupaba",
    )


class Completion(BaseModel):
    """Respuesta de una llamada al modelo."""

    model_config = ConfigDict(frozen=True)

    text: str
    usage: Usage
    stop_reason: str
    tool_calls: Sequence[ToolCall] = Field(default_factory=tuple)


class Embedding(BaseModel):
    """Vector con su procedencia tecnica.

    Modelo y dimension viajan con el vector porque mezclar vectores de modelos
    distintos es un error facil de cometer con un modelo local --cambiarlo es
    sustituir un fichero-- y la deteccion es lo unico que lo impide (RD-13).
    """

    model_config = ConfigDict(frozen=True)

    values: tuple[float, ...]
    model_id: str
    dimension: int = Field(gt=0)


@runtime_checkable
class ToolServer(Protocol):
    """Quien sirve una herramienta durante el turno de un agente.

    Vive en `orchestration/`, que es quien lleva el contador de la llamada. El
    puerto solo necesita saber invocarlo.
    """

    def serve(self, call: ToolCall) -> ToolResult: ...


@runtime_checkable
class ProviderPort(Protocol):
    """Contrato unico con los servicios externos."""

    def complete_once(
        self,
        *,
        cacheable_prefix: str,
        packet: str,
        instruction: str,
        output_schema: str,
        max_output_tokens: int,
    ) -> Completion:
        """Una ida y vuelta, sin herramientas."""
        ...

    def complete_with_tools(
        self,
        *,
        cacheable_prefix: str,
        packet: str,
        instruction: str,
        output_schema: str,
        max_output_tokens: int,
        tools: Sequence[str],
        server: ToolServer,
    ) -> Completion:
        """Bucle de herramientas hasta que el agente concluye.

        `tools` es la lista **cerrada** del agente: una llamada a algo que no
        este aqui se rechaza y se traza (RF-91).
        """
        ...

    def embed(self, texts: Sequence[str], *, is_query: bool) -> Sequence[Embedding]:
        """Vectores de uno o varios textos.

        `is_query` no es un detalle de comodidad: el modelo exige el prefijo
        `query: ` para consultas y `passage: ` para lo que se indexa, y sin
        ellos recupera peor sin dar error (RF-102).
        """
        ...

    def count_tokens(self, text: str, model_id: str) -> int:
        """Recuento real del proveedor. Solo lo usa la calibracion de arranque."""
        ...
