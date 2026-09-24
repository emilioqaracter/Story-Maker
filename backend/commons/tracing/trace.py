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

**Cadena de hashes** (`specs/srs-backend-v4.md` RF-253, RD-45, D-92). Cada
registro lleva `prev_hash`: el sha256 del JSON canonico del registro anterior
del fichero, vacio en el primero. La traza sigue siendo un fichero que se puede
editar o borrar --RI-16 y RI-17 no cambian--, pero `verify_chain` detecta
cualquier linea cambiada, borrada, insertada o reordenada y devuelve la primera
afectada. El eslabon se calcula contra la **ultima linea del fichero**, no
contra lo que recuerda esta instancia: una tirada reanudada, una ruta que abre
su propia `Trace` sobre la misma novela o un proceso nuevo --el hook de
politica-- continuan la misma cadena.

Limite declarado: borrar las ultimas lineas no deja eslabon roto, porque nadie
apunta a ellas. Lo que se detecta es cualquier cambio con algo detras.
"""

from __future__ import annotations

import hashlib
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
    prev_hash: str = Field(
        default="",
        description="sha256 del JSON canonico del registro anterior; vacio en el primero (RD-45)",
    )


#: RF-253. Las decisiones del motor de politicas: llevan siempre `decision` y
#: `rule`; el instante es `at`.
POLICY_KINDS = frozenset({"arbitration", "retcon.proposal", "guardrail.match", "formal.lean"})

#: Lo que se escribe cuando quien emite una decision no la declara y no se
#: puede deducir de sus campos. Se ve en la traza en vez de quedar en blanco.
UNDECLARED = "no-declarada"

#: `prev_hash` del primer registro de un fichero.
GENESIS = ""


def canonical_json(data: Mapping[str, object]) -> str:
    """El JSON canonico de un registro: claves ordenadas, sin espacios, UTF-8."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def record_hash(data: Mapping[str, object]) -> str:
    """El eslabon que apunta a `data`: sha256 de su JSON canonico."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def _line_hash(raw: str) -> str:
    """El hash de una linea tal como esta en el fichero.

    Una linea que no es JSON --una escritura cortada-- se encadena por sus bytes:
    el siguiente registro sigue apuntando a algo, y `verify_chain` la senala.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        return record_hash(data)
    return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()


def _last_line(path: Path) -> str | None:
    """La ultima linea no vacia del fichero, leida desde el final."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            pos = fh.tell()
            buf = b""
            while pos > 0:
                step = min(8192, pos)
                pos -= step
                fh.seek(pos)
                buf = fh.read(step) + buf
                if b"\n" in buf.rstrip():
                    break
    except FileNotFoundError:
        return None
    body = buf.rstrip()
    if not body:
        return None
    return body.rsplit(b"\n", 1)[-1].decode("utf-8", errors="replace")


def verify_chain(path: Path) -> int | None:
    """RF-253. El numero de linea (desde 1) del primer registro que no verifica.

    `None` si la cadena esta entera o si no hay fichero. Un registro no verifica
    si no es JSON o si su `prev_hash` no es el hash del registro anterior --el
    vacio, en el primero--. Borrar una linea rompe la siguiente; cambiar un campo
    rompe la siguiente; reordenar rompe la primera movida. Las lineas en blanco
    no cuentan, igual que al leer.
    """
    if not path.exists():
        return None
    esperado = GENESIS
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for numero, linea in enumerate(fh, start=1):
            if not linea.strip():
                continue
            try:
                data = json.loads(linea)
            except json.JSONDecodeError:
                return numero
            if not isinstance(data, dict) or data.get("prev_hash", GENESIS) != esperado:
                return numero
            esperado = record_hash(data)
    return None


def _decision_fields(kind: str, fields: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """RF-253. Toda decision del motor de politicas sale con `decision` y `rule`.

    Lo que el emisor declara gana siempre. Si no lo declara, se deduce de sus
    propios campos --que ya dicen que paso--, y si ni eso, queda `no-declarada`
    a la vista. Asi el registro cumple aunque el emisor sea anterior a la regla.
    """
    out = dict(fields)
    if "decision" not in out:
        out["decision"] = _derived_decision(kind, out)
    if "rule" not in out:
        out["rule"] = _derived_rule(kind, out)
    return out


def _derived_decision(kind: str, f: Mapping[str, JsonValue]) -> JsonValue:
    if kind == "arbitration":
        # Con valor rechazado, el congelado gano al delta (PRO-10, regla 1).
        return "rechaza-el-delta" if "rejected_value" in f else "resuelve-conflicto"
    if kind == "retcon.proposal" and "propose" in f and "admissible" in f:
        return "aplica-retcon" if f["propose"] and f["admissible"] else "gana-el-congelado"
    if kind == "formal.lean" and isinstance(f.get("passed"), bool):
        return "demuestra" if f["passed"] else "falla"
    return UNDECLARED


def _derived_rule(kind: str, f: Mapping[str, JsonValue]) -> JsonValue:
    if kind == "retcon.proposal":
        if f.get("admissible") is False and f.get("reason"):
            return f["reason"]
        if f.get("propose") is False:
            return "el arbitro no propone el retcon"
        if f.get("reason"):
            return f["reason"]
    if kind == "guardrail.match" and f.get("level"):
        return f"check.forbidden nivel {f['level']}"
    if kind == "formal.lean" and f.get("theorem"):
        return f["theorem"]
    return UNDECLARED


_PATH_LOCKS: dict[str, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _lock_for(path: Path | None) -> threading.RLock:
    """Un cerrojo por fichero, compartido por todas las `Trace` que lo abren.

    Dos instancias sobre la misma novela --la tirada y una ruta-- tienen que
    turnarse o las dos leerian la misma ultima linea y la cadena se bifurcaria.
    """
    if path is None:
        return threading.RLock()
    clave = str(path.resolve())
    with _PATH_LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(clave, threading.RLock())


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
        self._lock = _lock_for(path)
        # (tamano del fichero, hash de su ultima linea) tras la ultima escritura
        # propia. Si el tamano no cambio, nadie escribio detras: no hace falta
        # releer la cola.
        self._tail: tuple[int, str] | None = None
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
        if kind in POLICY_KINDS:
            fields = _decision_fields(kind, fields)
        seq = self._seq
        self._seq += 1
        if self._path is None:
            return None
        try:
            record = TraceRecord(
                seq=seq,
                at=datetime.now(UTC).isoformat(timespec="seconds"),
                kind=kind,
                fields=fields,
                prev_hash=self._previous_hash(self._path),
            )
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(record.model_dump_json() + "\n")
            self._tail = (self._path.stat().st_size, record_hash(record.model_dump(mode="json")))
        except OSError as exc:
            self.failures += 1
            if not self._warned:
                self._warned = True
                sys.stderr.write(f"traza: no se pudo escribir en {self._path}: {exc}\n")
            return None
        return record

    def _previous_hash(self, path: Path) -> str:
        """El eslabon: hash de la ultima linea del fichero, o vacio si no hay."""
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return GENESIS
        if self._tail is not None and self._tail[0] == size:
            return self._tail[1]
        last = _last_line(path)
        return GENESIS if last is None else _line_hash(last)

    def verify(self) -> int | None:
        """`verify_chain` sobre el fichero de esta traza; `None` sin fichero."""
        return None if self._path is None else verify_chain(self._path)

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
