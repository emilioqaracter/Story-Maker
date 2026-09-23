"""Generador de la cronologia en Lean. `specs/srs-backend-v4.md` RF-243, RD-41, RI-63, D-87.

Una funcion pura de una conexion de lectura del canon y de lo que esta por
congelar. Lee la cronologia (RF-242), los atributos, las vigencias y las
entidades, y escribe un hecho por fila con su origen --tabla y clave-- en el
campo `src`, que es lo que responde a «que fila produjo este hecho».

    python -m verification.formal.generate <novela.sqlite> -o <fichero.lean>

**Determinista.** Mismo canon, mismo fichero byte a byte, sea cual sea el orden
en que se insertaron las filas: todo se ordena por una clave total antes de
escribirse, las entidades se numeran por su identificador ordenado y no se
escribe ni la ruta, ni la fecha, ni nada que no salga del canon.

**El tiempo es un natural**: minutos desde el 1 de enero del año 1 a las 00:00
(D-87). Un natural hace decidibles todas las comparaciones, y los minutos cubren
un instante con hora sin perder los dias.

**El nacimiento nunca se inventa** (RD-41). Sale de `birth_date`; si falta y hay
`age`, se deriva el intervalo de un año compatible con la edad y consta como
derivado (MET-09); si faltan los dos, no hay hecho de nacimiento y I1 no lo usa.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol

from canon.db import connection
from canon.events import log
from canon.events.types import Event
from canon.projections import rebuild
from commons.types.primitives import ISO_INSTANT_PATTERN, WorldTime

#: Teorema del fichero generado por invariante (RF-244). El nombre es estable:
#: `check.py` lo devuelve y T46 lo pone en la regla del defecto S1.
THEOREMS: dict[str, str] = {
    "I1": "i1_born_before_present",
    "I2": "i2_one_place_at_a_time",
    "I3": "i3_validity_ordered",
    "I4": "i4_absent_after_exclusion",
}

#: Lo que dice cada teorema, en castellano: es el comentario que lo precede.
STATEMENTS: dict[str, str] = {
    "I1": "Nadie esta presente en una escena anterior a su nacimiento, y la edad "
    "declarada cuadra con la fecha de nacimiento",
    "I2": "Nadie esta en dos lugares en el mismo instante",
    "I3": "Ninguna vigencia termina antes de empezar ni empieza antes de que exista su entidad",
    "I4": "Nadie esta presente en una escena posterior al instante desde el que esta excluido",
}

#: Espacio de nombres del fichero generado. Fijo, para que el texto dependa
#: solo del canon.
NAMESPACE = "Chronology"

#: Prefijo del origen de un hecho que todavia no esta en el canon.
PENDING = "pending."

#: Atributos reservados de persona (RD-41).
BIRTH_DATE = "birth_date"
AGE = "age"
EXCLUDED = "excluded"

_ISO = re.compile(ISO_INSTANT_PATTERN)
_AGE = re.compile(r"^\s*(\d{1,3})\s*$")
_MINUTES_PER_DAY = 1440


class FormalExportError(ValueError):
    """Un hecho del canon no se puede exportar sin inventar nada.

    Una `birth_date` que no es ISO 8601 o una `age` que no es un entero no se
    reinterpretan: `run_lean` lo devuelve como fallo (`AGENTS.md` §5.3.6).
    """


# ------------------------------------------------------------------- tiempo


def minutes(stamp: str) -> int:
    """Minutos desde 0001-01-01T00:00 de un instante ISO 8601 (D-87).

    Los segundos se descartan: el instante de mundo no los usa para ordenar
    nada, y un natural en minutos es lo que fija D-87.
    """
    date, hour, minute = _parse(stamp)
    return (date.toordinal() - 1) * _MINUTES_PER_DAY + hour * 60 + minute


def _parse(stamp: str) -> tuple[dt.date, int, int]:
    if not _ISO.match(stamp):
        raise FormalExportError(f"instante que no es ISO 8601: {stamp!r}")
    try:
        date = dt.date.fromisoformat(stamp[:10])
    except ValueError as exc:
        raise FormalExportError(f"fecha imposible: {stamp!r}") from exc
    hour = int(stamp[11:13]) if len(stamp) > 10 else 0
    minute = int(stamp[14:16]) if len(stamp) > 10 else 0
    if hour > 23 or minute > 59:
        raise FormalExportError(f"hora imposible: {stamp!r}")
    return date, hour, minute


def _years_before(stamp: str, years: int) -> int | None:
    """Minutos del mismo instante `years` años antes, o None si cae antes del año 1.

    Un 29 de febrero que cae en un año no bisiesto pasa al 28: es la unica
    fecha que no existe en todos los años.
    """
    date, hour, minute = _parse(stamp)
    year = date.year - years
    if year < 1:
        return None
    day = date.day
    if (date.month, day) == (2, 29) and not _leap(year):
        day = 28
    shifted = dt.date(year, date.month, day)
    return (shifted.toordinal() - 1) * _MINUTES_PER_DAY + hour * 60 + minute


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def age_interval(age: int, at: str) -> tuple[int, int]:
    """Nacimientos compatibles con tener `age` años cumplidos en `at`: `[lo, hi]`.

    Tener A años en t es haber nacido en `(t - (A+1) años, t - A años]`. El
    extremo de abajo es abierto, asi que en minutos empieza un minuto despues.
    """
    hi = _years_before(at, age)
    if hi is None:
        raise FormalExportError(f"una edad de {age} en {at} nace antes del año 1")
    below = _years_before(at, age + 1)
    lo = 0 if below is None else below + 1
    return lo, hi


# ------------------------------------------------------------------- hechos


@dataclass(frozen=True, order=True)
class Presence:
    time: int
    seq: int
    src: str
    entity: str
    place: str | None
    stamp: str


@dataclass(frozen=True, order=True)
class Birth:
    src: str
    entity: str
    lo: int
    hi: int
    derived: bool


@dataclass(frozen=True, order=True)
class Age:
    src: str
    entity: str
    lo: int
    hi: int


@dataclass(frozen=True, order=True)
class Existence:
    src: str
    entity: str
    created: int


@dataclass(frozen=True, order=True)
class Validity:
    src: str
    entity: str
    start: int
    stop: int | None


@dataclass(frozen=True, order=True)
class Exclusion:
    src: str
    entity: str
    start: int
    stop: int | None


@dataclass(frozen=True)
class Chronicle:
    """Los hechos que se exportan, ya ordenados."""

    presences: tuple[Presence, ...] = ()
    births: tuple[Birth, ...] = ()
    ages: tuple[Age, ...] = ()
    existences: tuple[Existence, ...] = ()
    validities: tuple[Validity, ...] = ()
    exclusions: tuple[Exclusion, ...] = ()

    def entities(self) -> tuple[str, ...]:
        """Todas las entidades y lugares citados, ordenados: su posicion es su numero."""
        ids: set[str] = set()
        for p in self.presences:
            ids.add(p.entity)
            if p.place is not None:
                ids.add(p.place)
        for group in (self.births, self.ages, self.existences, self.validities, self.exclusions):
            ids.update(f.entity for f in group)
        return tuple(sorted(ids))


class SceneFacts(Protocol):
    """Lo que hace falta de una escena por congelar. `SceneToFreeze` lo cumple."""

    @property
    def id(self) -> str: ...
    @property
    def world_time(self) -> WorldTime: ...
    @property
    def place_entity(self) -> str | None: ...
    @property
    def pov_entity(self) -> str: ...
    @property
    def present(self) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class Pending:
    """Lo que va a entrar: escenas del capitulo y eventos del delta (RF-243).

    Una escena con el identificador de una ya congelada la sustituye, que es lo
    que hace recongelar.
    """

    scenes: Sequence[SceneFacts] = ()
    events: Sequence[Event] = field(default_factory=tuple)


def src(table: str, *key: object) -> str:
    """Origen de un hecho: tabla y clave. `json` hace la clave inequivoca."""
    return table + json.dumps(list(key), ensure_ascii=False)


# ------------------------------------------------------------------- lectura

_HAS_CHRONOLOGY = "SELECT 1 FROM sqlite_master WHERE type = 'view' AND name = 'chronology'"

#: Origen de una presencia: una fila de la vista `chronology` y una entidad de
#: su `present`.
CHRONOLOGY = "chronology"

# RF-242, RD-40. La vista `chronology` (migracion 5, `canon/prose_index/
# chronology.py`) es la fuente: una fila por escena congelada, con `present`
# como lista JSON de entidades, POV incluido. Leer no migra (RI-35), asi que en
# un fichero anterior a la vista se ejecuta el mismo cuerpo sobre las tablas de
# las que es proyeccion. Las dos consultas dan las mismas filas: lo comprueba
# `test_generate.py` contra el cuerpo de la vista.
_CHRONOLOGY = "SELECT scene_id, world_time, world_seq, place_entity, present FROM chronology"
_CHRONOLOGY_UNMIGRATED = """
SELECT
    s.id AS scene_id,
    s.world_time,
    s.world_seq,
    s.place_entity,
    (
        SELECT json_group_array(p.entity_id) FROM (
            SELECT s.pov_entity AS entity_id
            UNION
            SELECT c.entity_id FROM prose_scene_character c WHERE c.scene_id = s.id
            ORDER BY 1
        ) p
    ) AS present
FROM prose_scene s
"""
_ENTITIES = "SELECT id, created_at FROM entity"
_ATTRIBUTES = "SELECT entity_id, name, value, valid_from, valid_to FROM attribute"
_ALIASES = "SELECT entity_id, alias, valid_from, valid_to FROM entity_alias"
_RELATIONS = "SELECT source_id, target_id, kind, valid_from, valid_to FROM relation"
_COMPETENCES = "SELECT entity_id, name, valid_from, valid_to FROM competence"


@dataclass(frozen=True)
class _Scene:
    world_time: str
    world_seq: int
    place: str | None
    present: tuple[str, ...]
    table: str


def read_chronicle(con: sqlite3.Connection, pending: Pending | None = None) -> Chronicle:
    """Los hechos del canon mas lo que esta por congelar.

    Los eventos pendientes se proyectan sobre una copia en memoria con la
    misma proyeccion que usa la congelacion (`canon.projections.rebuild`): asi
    lo que se demuestra es lo que quedaria en el canon, y el fichero de la
    novela no se toca.
    """
    pending = pending or Pending()
    base = _read(con, pending.scenes)
    if not pending.events:
        return base
    with _projected(con, pending.events) as mem:
        merged = _read(mem, pending.scenes)
    return _mark_pending(merged, base)


@contextmanager
def _projected(con: sqlite3.Connection, events: Sequence[Event]) -> Iterator[sqlite3.Connection]:
    """Copia en memoria del canon con los eventos pendientes aplicados."""
    mem = sqlite3.connect(":memory:")
    try:
        con.backup(mem)
        mem.row_factory = sqlite3.Row
        ids = set(log.append(mem, events))
        rebuild.apply_all(mem, [s for s in log.read_all(mem) if s.id in ids])
        yield mem
    finally:
        mem.close()


def _mark_pending(merged: Chronicle, base: Chronicle) -> Chronicle:
    """Un hecho que no estaba en el canon lleva el prefijo `pending.` en su origen."""

    def mark[T: (Presence, Birth, Age, Existence, Validity, Exclusion)](
        facts: tuple[T, ...], old: tuple[T, ...]
    ) -> tuple[T, ...]:
        before = set(old)
        out = [f if f in before or f.src.startswith(PENDING) else replace(f, src=PENDING + f.src)
               for f in facts]
        return tuple(sorted(out))

    return Chronicle(
        presences=mark(merged.presences, base.presences),
        births=mark(merged.births, base.births),
        ages=mark(merged.ages, base.ages),
        existences=mark(merged.existences, base.existences),
        validities=mark(merged.validities, base.validities),
        exclusions=mark(merged.exclusions, base.exclusions),
    )


def _read(con: sqlite3.Connection, pending_scenes: Sequence[SceneFacts]) -> Chronicle:
    scenes = _scenes(con, pending_scenes)
    attributes = [tuple(r) for r in con.execute(_ATTRIBUTES).fetchall()]

    presences = [
        Presence(
            time=minutes(s.world_time),
            seq=s.world_seq,
            src=src(s.table, scene_id, entity),
            entity=entity,
            place=s.place,
            stamp=s.world_time,
        )
        for scene_id, s in scenes.items()
        for entity in s.present
    ]

    existences = [
        Existence(src=src("entity", eid), entity=eid, created=minutes(created))
        for eid, created in con.execute(_ENTITIES).fetchall()
    ]

    validities: list[Validity] = []
    for ent, name, _value, start, stop in attributes:
        validities.append(_validity(src("attribute", ent, name, start), ent, start, stop))
    for ent, alias, start, stop in con.execute(_ALIASES).fetchall():
        validities.append(_validity(src("entity_alias", ent, alias, start), ent, start, stop))
    for source, target, kind, start, stop in con.execute(_RELATIONS).fetchall():
        origin = src("relation", source, target, kind, start)
        validities.append(_validity(origin, source, start, stop))
        validities.append(_validity(origin, target, start, stop))
    for ent, name, start, stop in con.execute(_COMPETENCES).fetchall():
        validities.append(_validity(src("competence", ent, name, start), ent, start, stop))

    births, ages = _births_and_ages(attributes)
    exclusions = [
        Exclusion(
            src=src("attribute", ent, name, start),
            entity=ent,
            start=minutes(start),
            stop=None if stop is None else minutes(stop),
        )
        for ent, name, _value, start, stop in attributes
        if name == EXCLUDED
    ]

    return Chronicle(
        presences=tuple(sorted(presences)),
        births=tuple(sorted(births)),
        ages=tuple(sorted(ages)),
        existences=tuple(sorted(existences)),
        validities=tuple(sorted(set(validities))),
        exclusions=tuple(sorted(exclusions)),
    )


def _scenes(con: sqlite3.Connection, pending: Sequence[SceneFacts]) -> dict[str, _Scene]:
    has_view = con.execute(_HAS_CHRONOLOGY).fetchone() is not None
    rows = con.execute(_CHRONOLOGY if has_view else _CHRONOLOGY_UNMIGRATED).fetchall()
    scenes = {
        scene_id: _Scene(
            world_time=stamp,
            world_seq=int(seq),
            place=place,
            present=tuple(sorted(set(json.loads(present)))),
            table=CHRONOLOGY,
        )
        for scene_id, stamp, seq, place, present in rows
    }
    for scene in pending:
        # Igual que la vista: el POV cuenta como presente.
        scenes[scene.id] = _Scene(
            world_time=scene.world_time.stamp,
            world_seq=scene.world_time.seq,
            place=scene.place_entity,
            present=tuple(sorted({scene.pov_entity, *scene.present})),
            table=PENDING + CHRONOLOGY,
        )
    return scenes


def _validity(origin: str, entity: str, start: str, stop: str | None) -> Validity:
    return Validity(
        src=origin,
        entity=entity,
        start=minutes(start),
        stop=None if stop is None else minutes(stop),
    )


def _births_and_ages(
    attributes: Iterable[tuple[str, str, str, str, str | None]],
) -> tuple[list[Birth], list[Age]]:
    """Nacimientos y edades de RD-41.

    La fecha de nacimiento vigente es la de vigencia abierta; si todas estan
    cerradas, la ultima que empezo. Una fecha corregida por un retcon cierra
    la anterior, y la anterior era falsa: no cuenta.
    """
    declared: dict[str, list[tuple[str, str, str | None]]] = {}
    ages: list[Age] = []
    first_age: dict[str, tuple[str, Age, int]] = {}

    for ent, name, value, start, stop in attributes:
        if name == BIRTH_DATE:
            declared.setdefault(ent, []).append((start, value, stop))
        elif name == AGE:
            match = _AGE.match(value)
            if match is None:
                raise FormalExportError(f"la edad de {ent!r} no es un entero: {value!r}")
            years = int(match.group(1))
            lo, hi = age_interval(years, start)
            age = Age(src=src("attribute", ent, name, start), entity=ent, lo=lo, hi=hi)
            ages.append(age)
            if ent not in first_age or start < first_age[ent][0]:
                first_age[ent] = (start, age, years)

    births: list[Birth] = []
    for ent, rows in declared.items():
        open_rows = [r for r in rows if r[2] is None]
        for start, value, _stop in open_rows or [max(rows)]:
            at = minutes(value)
            births.append(
                Birth(src=src("attribute", ent, BIRTH_DATE, start), entity=ent,
                      lo=at, hi=at, derived=False)
            )
    for ent, (_start, age, _years) in first_age.items():
        if ent not in declared:
            births.append(Birth(src=age.src, entity=ent, lo=age.lo, hi=age.hi, derived=True))
    return births, ages


# ------------------------------------------------------------------- escritura


def lean_string(text: str) -> str:
    """Literal de cadena de Lean. Solo escapa lo que Lean exige."""
    out = ['"']
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\x{ord(ch):02x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _opt(value: int | None) -> str:
    return "none" if value is None else f"some {value}"


def _list(name: str, lean_type: str, doc: str, rows: Sequence[tuple[str, str]]) -> list[str]:
    """Una definicion de lista, un hecho por linea con su comentario."""
    lines = [f"/-- {doc} -/", f"def {name} : List {lean_type} :="]
    if not rows:
        lines.append("  []")
        return lines
    for i, (term, comment) in enumerate(rows):
        opener = "[ " if i == 0 else ", "
        lines.append(f"  {opener}{term}  -- {comment}")
    lines.append("  ]")
    return lines


def render(chronicle: Chronicle, *, namespace: str = NAMESPACE, report: bool = False) -> str:
    """El fichero Lean de la cronologia.

    Con `report`, en vez de los teoremas lleva un `main` que imprime, por
    invariante, el origen de cada hecho que la rompe. `check.py` lo ejecuta
    solo cuando un teorema falla, para decir con que filas.
    """
    number = {e: i for i, e in enumerate(chronicle.entities())}

    def n(entity: str) -> int:
        return number[entity]

    def place(p: Presence) -> str:
        return _opt(None if p.place is None else n(p.place))

    lines = [
        "/-",
        "Cronologia de la novela, exportada del canon por `verification/formal/generate.py`",
        "(`specs/srs-backend-v4.md` RF-243). No se edita: se regenera.",
        "",
        "Tiempo: minutos desde 0001-01-01T00:00 (D-87). Cada hecho lleva en `src` la",
        "tabla y la clave de la fila que lo produjo; `pending.` es lo que va a entrar.",
        "-/",
        "import StoryMaker.Invariants",
        "",
        "open StoryMaker",
        "",
        f"namespace {namespace}",
        "",
        "-- Entidades y lugares, numerados por su identificador ordenado:",
    ]
    lines += [f"--   {i} = {json.dumps(e, ensure_ascii=False)}" for e, i in number.items()]
    lines.append("")

    lines += _list(
        "presences", "Presence",
        "Un personaje presente en una escena de `chronology`: entidad, instante, desempate, lugar.",
        [(f"⟨{n(p.entity)}, {p.time}, {p.seq}, {place(p)}, {lean_string(p.src)}⟩",
          f"{p.stamp}#{p.seq}") for p in chronicle.presences],
    )
    lines.append("")
    lines += _list(
        "births", "Birth",
        "Nacimientos: declarados con `birth_date`, o derivados de `age` (MET-09).",
        [(f"⟨{n(b.entity)}, {b.lo}, {b.hi}, {'true' if b.derived else 'false'}, "
          f"{lean_string(b.src)}⟩", "derivado de la edad" if b.derived else "declarado")
         for b in chronicle.births],
    )
    lines.append("")
    lines += _list(
        "ages", "Age",
        "Edades declaradas: el intervalo de nacimientos compatible con cada una.",
        [(f"⟨{n(a.entity)}, {a.lo}, {a.hi}, {lean_string(a.src)}⟩", "edad")
         for a in chronicle.ages],
    )
    lines.append("")
    lines += _list(
        "existences", "Existence",
        "Desde cuando existe cada entidad.",
        [(f"⟨{n(e.entity)}, {e.created}, {lean_string(e.src)}⟩", "creada")
         for e in chronicle.existences],
    )
    lines.append("")
    lines += _list(
        "validities", "Validity",
        "Vigencias de atributos, alias, relaciones y competencias (MET-07).",
        [(f"⟨{n(v.entity)}, {v.start}, {_opt(v.stop)}, {lean_string(v.src)}⟩", "vigencia")
         for v in chronicle.validities],
    )
    lines.append("")
    lines += _list(
        "exclusions", "Exclusion",
        "Vigencias de `excluded`: desde su inicio, la entidad no puede estar presente.",
        [(f"⟨{n(x.entity)}, {x.start}, {_opt(x.stop)}, {lean_string(x.src)}⟩", "excluida")
         for x in chronicle.exclusions],
    )
    lines += [
        "",
        "def chronicle : Chronicle :=",
        "  { presences, births, ages, existences, validities, exclusions }",
        "",
    ]

    if report:
        lines += [f"end {namespace}", "", "def main : IO Unit := do"]
        for inv in THEOREMS:
            lines.append(
                f"  for v in {inv}.violations {namespace}.chronicle do "
                f'IO.println ("{inv}\\t" ++ v)'
            )
        return "\n".join(lines) + "\n"

    # `decide +kernel`: la decision la comprueba el nucleo, sin evaluarla antes
    # en el elaborador. Con `decide` a secas, una novela de un centenar de
    # escenas agota la profundidad de recursion del elaborador; el nucleo es
    # ademas la parte de Lean en la que se confia, asi que no se pierde nada.
    for inv, theorem in THEOREMS.items():
        lines += [
            f"/-- {inv}. {STATEMENTS[inv]}. -/",
            f"theorem {theorem} : {inv}.check chronicle = true := by decide +kernel",
            "",
        ]
    lines.append(f"end {namespace}")
    return "\n".join(lines) + "\n"


def theorem_lines(text: str) -> dict[int, str]:
    """Linea (desde 1) de cada teorema del fichero: donde Lean informa si falla."""
    found: dict[int, str] = {}
    names = {f"theorem {t} " : t for t in THEOREMS.values()}
    for number, line in enumerate(text.splitlines(), start=1):
        for prefix, theorem in names.items():
            if line.startswith(prefix):
                found[number] = theorem
    return found


def generate(con: sqlite3.Connection, pending: Pending | None = None) -> str:
    """El fichero Lean de la cronologia del canon mas lo pendiente (RF-243)."""
    return render(read_chronicle(con, pending))


def write(path: Path, text: str) -> None:
    """Escribe en UTF-8 y con saltos `\\n` en cualquier sistema: byte a byte igual."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exporta la cronologia de una novela a Lean (RI-63)")
    parser.add_argument("novel", type=Path, help="fichero SQLite de la novela")
    parser.add_argument("-o", "--output", type=Path, required=True, help="fichero .lean")
    args = parser.parse_args(argv)
    try:
        with connection.reader(args.novel) as con:
            text = generate(con)
    except (FormalExportError, sqlite3.Error, connection.SchemaVersionError) as exc:
        print(f"no se pudo exportar la cronologia: {exc}", file=sys.stderr)
        return 1
    write(args.output, text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
