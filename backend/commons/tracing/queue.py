"""Cola local de trazas.

RNF-13, D-11: si Langfuse no responde, la traza se encola en local y **la
tirada continua**. La observabilidad observa, no gobierna: parar una novela de
200.000 palabras porque no se pudo registrar un span seria darle a la traza un
poder que no le toca.

Vive en fichero y no en memoria porque una caida en el capitulo 28 se llevaria
por delante todo lo que explica como se llego hasta ahi, que es justo cuando
mas falta hace.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PendingSpan:
    """Un span que no se pudo enviar."""

    name: str
    payload: Mapping[str, str | int | float | bool | None]


class SpanQueue:
    """Cola de una sola tirada, append-only sobre fichero de lineas JSON."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def enqueue(self, span: PendingSpan) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"name": span.name, "payload": dict(span.payload)}, ensure_ascii=False)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def drain(self) -> Iterator[PendingSpan]:
        """Recorre lo pendiente y vacia el fichero.

        Se vacia al terminar de recorrer y no antes: si el reenvio falla a la
        mitad, lo que queda sigue en disco.
        """
        if not self._path.exists():
            return
        raw = self._path.read_text(encoding="utf-8").splitlines()
        for line in raw:
            if not line.strip():
                continue
            data = json.loads(line)
            yield PendingSpan(name=data["name"], payload=data["payload"])
        self._path.unlink()

    def pending(self) -> int:
        if not self._path.exists():
            return 0
        return sum(1 for line in self._path.read_text(encoding="utf-8").splitlines() if line.strip())
