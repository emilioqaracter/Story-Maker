"""Admision de llamadas. El semaforo de tokens.

RF-14, RF-15, RF-97, CTX-20, CTX-I1. `architecture.md` §7.4.

Lo que se cuenta es **entrada**, no llamadas: tres jueces y un Continuista
ocupan cosas muy distintas. Y para un agente con herramientas se reserva su
**cupo de tiron entero desde el principio**, aunque acabe sin usarlo.

Esa reserva anticipada es la decision que mas facil es tomar al reves. Admitir
por lo que ocupa al empezar y dejar que crezca durante el turno rompe el techo
sin que salte nada: cuando la llamada se pasa, ya esta en vuelo y no hay donde
devolverla.

Tres reglas que no se negocian:

- **FIFO estricta.** Reordenar por hueco mata de hambre al Arquitecto y al
  Continuista, que son las llamadas grandes: siempre habria alguien pequeno
  colandose por delante.
- **Fallo cerrado.** Si el presupuesto de una llamada no se puede estimar, no se
  admite.
- **El cupo no se amplia en caliente.** Un cupo que se estira no acota nada.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager

from pydantic import BaseModel, ConfigDict, Field

#: CTX-20. Techo de tokens de ENTRADA en vuelo en el mismo instante.
CONCURRENCY_CEILING = 100_000


class BudgetUnknownError(RuntimeError):
    """No se pudo estimar el presupuesto de una llamada. No se admite."""


class CeilingTooSmallError(RuntimeError):
    """Una sola llamada no cabe ni con el sistema vacio.

    No es un problema de concurrencia sino de diseno del paquete: encolarla
    seria dejarla esperando para siempre, asi que se lanza en vez de aceptar un
    bloqueo silencioso.
    """


class Reservation(BaseModel):
    """Lo que una llamada ocupa mientras esta en vuelo."""

    model_config = ConfigDict(frozen=True)

    agent: str
    packet_tokens: int = Field(ge=0)
    tool_quota: int = Field(default=0, ge=0, description="CTX-22, reservado entero")

    @property
    def total(self) -> int:
        return self.packet_tokens + self.tool_quota


class Admission:
    """Semaforo de tokens con cola FIFO estricta."""

    def __init__(self, ceiling: int = CONCURRENCY_CEILING) -> None:
        self._ceiling = ceiling
        self._in_flight = 0
        self._queue: deque[str] = deque()

    @property
    def in_flight(self) -> int:
        return self._in_flight

    @property
    def queued(self) -> int:
        return len(self._queue)

    def would_fit(self, reservation: Reservation) -> bool:
        return self._in_flight + reservation.total <= self._ceiling

    def admit(self, reservation: Reservation, *, call_id: str) -> bool:
        """Intenta admitir. Devuelve si entro; si no, queda encolada.

        **FIFO estricta**: si hay alguien esperando, nadie adelanta aunque quepa.
        Sin esa regla, una llamada grande no entra nunca mientras lleguen
        pequenas, y las grandes son justo las que menos veces corren.
        """
        if reservation.total > self._ceiling:
            raise CeilingTooSmallError(
                f"{reservation.agent!r} pide {reservation.total} tokens y el techo es "
                f"{self._ceiling}: no cabe ni con el sistema vacio"
            )

        if self._queue or not self.would_fit(reservation):
            if call_id not in self._queue:
                self._queue.append(call_id)
            return False

        self._in_flight += reservation.total
        return True

    def release(self, reservation: Reservation) -> str | None:
        """Libera y devuelve el siguiente de la cola, si lo hay."""
        self._in_flight = max(0, self._in_flight - reservation.total)
        return self._queue.popleft() if self._queue else None

    @contextmanager
    def hold(self, reservation: Reservation) -> Iterator[None]:
        """Reserva mientras dura el bloque, y libera pase lo que pase.

        Con `finally` y no solo en el camino feliz: una llamada que lanza y no
        libera va dejando el techo mas bajo cada vez, y el sistema acaba
        bloqueado sin que nada lo explique.
        """
        self._in_flight += reservation.total
        try:
            yield
        finally:
            self._in_flight = max(0, self._in_flight - reservation.total)


def reserve(
    *, agent: str, packet_tokens: int | None, tool_quota: int = 0
) -> Reservation:
    """Construye la reserva. Fallo cerrado si no hay estimacion.

    `packet_tokens` es `None` cuando el contador no supo estimar --por ejemplo,
    un modelo sin factor calibrado--. Admitir a ciegas seria romper el techo sin
    que salte nada, que es peor que no correr.
    """
    if packet_tokens is None:
        raise BudgetUnknownError(
            f"sin estimacion de presupuesto para {agent!r}: la llamada no se admite"
        )
    return Reservation(agent=agent, packet_tokens=packet_tokens, tool_quota=tool_quota)
