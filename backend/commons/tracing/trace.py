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

**Observadores** (`specs/srs-backend-v4.md` RF-233, D-85). Quien quiera ver los
registros segun se escriben --el espejo de Langfuse-- se suscribe como
observador. Recibe cada registro ya escrito en el fichero, dentro del mismo
cerrojo, asi que lo ve en el orden del fichero. Un observador tiene que volver
enseguida y no puede gobernar: si lanza, se cuenta en `failures` y la tirada
sigue, igual que un fallo de escritura.
"""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Callable, Iterator, Mapping
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


#: Quien recibe cada registro escrito. Tiene que volver enseguida: corre dentro
#: del cerrojo de la traza.
Observer = Callable[[TraceRecord], None]

#: Quien decide, al abrir una traza con fichero, si le cuelga un observador. Es
#: como el espejo de Langfuse ve tambien las trazas que abren las rutas.
ObserverFactory = Callable[["Trace"], Observer | None]

_FACTORIES: list[ObserverFactory] = []


def add_observer_factory(factory: ObserverFactory) -> None:
    """Toda traza con fichero que se abra desde ahora pasa por `factory`."""
    if factory not in _FACTORIES:
        _FACTORIES.append(factory)


def remove_observer_factory(factory: ObserverFactory) -> None:
    if factory in _FACTORIES:
        _FACTORIES.remove(factory)


class Trace:
    """Escritor y lector de la traza de una tirada.

    `path=None` desactiva la escritura y conserva el recuento: es lo que usan
    las pruebas con dobles que no necesitan leer la traza. Una traza sin
    fichero no tiene observadores de fabrica: lo que no queda en el JSONL no
    puede salir hacia ningun espejo.
    """

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._seq = 0
        self.failures = 0
        self._warned = False
        # Las instancias del Jurado trazan desde tres hilos: el numero de orden
        # y la escritura van juntos o dos registros compartirian `seq`.
        # Reentrante: un observador puede dejar su propio registro --el
        # `export.disabled` del espejo-- sin bloquearse contra si mismo.
        self._lock = threading.RLock()
        self._observers: list[Observer] = []
        if path is not None:
            for factory in tuple(_FACTORIES):
                try:
                    observer = factory(self)
                except Exception:  # un espejo roto no impide abrir la traza
                    self.failures += 1
                    continue
                if observer is not None:
                    self._observers.append(observer)

    @classmethod
    def disabled(cls) -> Trace:
        return cls(None)

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def emitted(self) -> int:
        return self._seq

    @property
    def observers(self) -> tuple[Observer, ...]:
        return tuple(self._observers)

    def subscribe(self, observer: Observer) -> None:
        """Cuelga un observador que vera los registros que se escriban desde ahora."""
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def unsubscribe(self, observer: Observer) -> None:
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def emit(self, kind: str, **fields: JsonValue) -> None:
        """Escribe un registro. **Nunca lanza** (RNF-13).

        Se abre y cierra el fichero en cada registro a proposito: si alguien lo
        borra a mitad de tirada, el siguiente registro lo vuelve a crear en vez
        de escribir en un descriptor huerfano.

        Los observadores ven el registro solo si quedo escrito: todo lo que
        muestre un espejo tiene que poder reconstruirse desde el JSONL (D-11).
        """
        with self._lock:
            record = self._write(kind, fields)
            if record is None:
                return
            for observer in tuple(self._observers):
                try:
                    observer(record)
                except Exception:  # el espejo observa, no gobierna (RNF-53)
                    self.failures += 1

    def _write(self, kind: str, fields: dict[str, JsonValue]) -> TraceRecord | None:
        record = TraceRecord(
            seq=self._seq,
            at=datetime.now(UTC).isoformat(timespec="seconds"),
            kind=kind,
            fields=fields,
        )
        self._seq += 1
        if self._path is None:
            return None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(record.model_dump_json() + "\n")
        except OSError as exc:
            self.failures += 1
            if not self._warned:
                self._warned = True
                sys.stderr.write(f"traza: no se pudo escribir en {self._path}: {exc}\n")
            return None
        return record

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
