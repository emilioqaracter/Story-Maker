"""La traza de la tirada. Un JSONL append-only junto al SQLite de la novela.

RI-16, RI-17, RI-23, RNF-13, D-11. `architecture.md` §11.

Sin servicio externo: la traza es **parte del estado de la tirada** y se copia
con ella. Un registro por llamada, admision, reintento, defecto, arbitraje y
decision del Orquestador, con la regla aplicada. Es lo que permite responder
"por que entro este fragmento" o "por que se rehizo este capitulo" sin
reconstruir la ejecucion.

Dos reglas, y las dos son la misma idea:

- **La traza observa, no gobierna.** Un fallo al escribirla se cuenta y la
  tirada continua. Parar una novela de 200.000 palabras porque no se pudo
  registrar una llamada seria darle a la traza un poder que no le toca.
- **Nada de la traza se duplica en tablas del canon** (RI-17). SQLite guarda
  lo que es verdad; esto guarda lo que paso.

Vive en fichero y no en memoria porque una caida en el capitulo 28 se llevaria
por delante todo lo que explica como se llego hasta ahi, que es justo cuando
mas falta hace.
"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class TraceRecord(BaseModel):
    """Una linea de la traza."""

    model_config = ConfigDict(frozen=True)

    seq: int = Field(ge=0, description="Orden de escritura dentro de la tirada")
    at: str = Field(description="Instante real, ISO 8601 UTC")
    kind: str = Field(min_length=1, description="call, admission, retry, defect, arbitration, ...")
    fields: Mapping[str, JsonValue] = Field(default_factory=dict)


class Trace:
    """Escritor y lector de la traza de una tirada.

    `path=None` desactiva la escritura y conserva el recuento: es lo que usan
    las pruebas con dobles que no necesitan leer la traza.
    """

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._seq = 0
        self.failures = 0
        self._warned = False
        # Las instancias del Jurado trazan desde tres hilos: el numero de orden
        # y la escritura van juntos o dos registros compartirian `seq`.
        self._lock = threading.Lock()

    @classmethod
    def disabled(cls) -> Trace:
        return cls(None)

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def emitted(self) -> int:
        return self._seq

    def emit(self, kind: str, **fields: JsonValue) -> None:
        """Escribe un registro. **Nunca lanza** (RNF-13).

        Se abre y cierra el fichero en cada registro a proposito: si alguien lo
        borra a mitad de tirada, el siguiente registro lo vuelve a crear en vez
        de escribir en un descriptor huerfano.
        """
        with self._lock:
            self._write(kind, fields)

    def _write(self, kind: str, fields: dict[str, JsonValue]) -> None:
        record = TraceRecord(
            seq=self._seq,
            at=datetime.now(UTC).isoformat(timespec="seconds"),
            kind=kind,
            fields=fields,
        )
        self._seq += 1
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(record.model_dump_json() + "\n")
        except OSError as exc:
            self.failures += 1
            if not self._warned:
                self._warned = True
                sys.stderr.write(f"traza: no se pudo escribir en {self._path}: {exc}\n")

    def read(self) -> Iterator[TraceRecord]:
        """Los registros en orden de escritura. Vacio si no hay fichero."""
        if self._path is None or not self._path.exists():
            return
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield TraceRecord.model_validate(json.loads(line))

    def records(self, kind: str | None = None) -> list[TraceRecord]:
        return [r for r in self.read() if kind is None or r.kind == kind]
