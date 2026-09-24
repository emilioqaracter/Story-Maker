"""Carga del brief como eventos.

RF-11, D-09. El brief **no se guarda como documento**: se descompone en eventos
con procedencia `brief` y sin capitulo de origen. Desde la primera fila el canon
ya es una proyeccion, sin casos especiales.

Esta es la unica escritura de canon fuera de la congelacion, y vive aqui porque
`canon/` es el dueno de los almacenes y la unica carpeta desde la que se importa
la conexion de escritura.

El brief llega **ya estructurado**, con sus entidades identificadas: convertir
texto libre a estructura es trabajo de modelo y en la version 1 nadie lo ha
presupuestado.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from canon import brief_rules, normalize
from canon.db import connection
from canon.events import log
from canon.events.types import (
    AliasAdded,
    AttributeSet,
    CompetenceSet,
    DocumentVersion,
    EntityCreated,
    Event,
    RelationSet,
)
from canon.projections import rebuild
from commons.types import rubrics
from commons.types.length import LengthProfile, LengthProfileName
from commons.types.length import of as length_profile_of
from commons.types.primitives import Provenance, WorldTime

#: RF-248, RI-64, D-93. El brief, sus partes y la salida de la extraccion
#: rechazan campos de mas: un campo que el sistema no lee es un campo que la
#: persona cree haber pedido. RI-01 lo devuelve como 422 con la ruta del campo.
STRICT = ConfigDict(frozen=True, extra="forbid")

#: RF-249, RD-41. Atributos reservados del destinatario: los escribe la carga
#: del brief desde `Recipient`, no la entidad.
RESERVED_RECIPIENT_ATTRIBUTES = ("age", "birth_date")

#: El identificador de una entrevista (RI-38): doce hexadecimales. Es el mismo
#: patron que `brief/store.py`; se repite porque `canon/` no importa de `brief/`.
INTERVIEW_ID_PATTERN = r"^[a-f0-9]{12}$"


class BriefEntity(BaseModel):
    model_config = STRICT

    id: str = Field(min_length=1)
    kind: str = Field(min_length=1, description="person | place | institution | object")
    name: str = Field(min_length=1)
    aliases: tuple[str, ...] = Field(default_factory=tuple)
    attributes: tuple[tuple[str, str], ...] = Field(default_factory=tuple)
    competences: tuple[tuple[str, str], ...] = Field(default_factory=tuple)


class BriefRelation(BaseModel):
    model_config = STRICT

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    kind: str = Field(min_length=1)


class Recipient(BaseModel):
    """RF-200, RD-42. Para quien es la novela: una entidad del brief, con lo que la entrevista recogio.

    `birth_date` y `optional` son opcionales para que los briefs anteriores
    sigan valiendo. `optional` es el subconjunto de rasgos y recuerdos que no
    son obligatorios (RF-260): lo que no esta en `traits` ni en `memories` no
    puede ser opcional, porque no hay nada que eximir.
    """

    model_config = STRICT

    entity_id: str = Field(min_length=1)
    age: int = Field(ge=0, le=120)
    birth_date: date | None = Field(
        default=None,
        description="ISO 8601, AAAA-MM-DD. RF-249: la entrevista la pregunta tras la edad",
    )
    traits: tuple[str, ...] = Field(default_factory=tuple)
    memories: tuple[str, ...] = Field(default_factory=tuple)
    optional: tuple[str, ...] = Field(
        default_factory=tuple, description="Rasgos y recuerdos que no son obligatorios (RD-42)"
    )
    role: str = Field(min_length=1, description="Papel en la historia")

    @model_validator(mode="after")
    def _optional_is_a_subset(self) -> Self:
        sobran = set(self.optional) - set(self.traits) - set(self.memories)
        if sobran:
            raise ValueError(
                f"optional solo admite rasgos o recuerdos del destinatario: {sorted(sobran)}"
            )
        return self


class Brief(BaseModel):
    """El encargo de la obra.

    `start` es el instante en que arranca el mundo: todo lo que el brief
    establece es cierto desde ahi, y nada anterior existe.

    Lo que va despues de `word_tolerance` lo trae la entrevista (RF-200). Es
    opcional para que un brief escrito a mano, sin destinatario, siga valiendo.
    """

    model_config = STRICT

    title: str = Field(min_length=1)
    start: WorldTime
    entities: tuple[BriefEntity, ...]
    relations: tuple[BriefRelation, ...] = Field(default_factory=tuple)
    style_guide: str = Field(min_length=1, description="POE-06")
    rulebook: str = Field(default="", description="DEP-02, vacio si no es deportiva")
    target_words: int = Field(gt=0)
    word_tolerance: float = Field(default=0.1, gt=0, lt=1)
    length_profile: LengthProfileName = Field(
        default=LengthProfileName.NOVELA,
        description="T53. Perfil de extension: novela, o prueba para una obra minima",
    )
    genre: str = ""
    tone: str = ""
    dedication: str = ""
    recipient: Recipient | None = None
    forbidden_words: tuple[str, ...] = Field(default_factory=tuple)
    forbidden_themes: tuple[str, ...] = Field(default_factory=tuple)
    origin_interview: str | None = Field(
        default=None,
        pattern=INTERVIEW_ID_PATTERN,
        description="RF-249: la entrevista de la que sale el brief, si sale de una",
    )

    @model_validator(mode="after")
    def _extension_fits_profile(self) -> Self:
        # T53. Un perfil con rango de obra propio no admite una extension fuera
        # de el: el brief pediria una obra que su perfil no puede planificar.
        perfil = self.profile()
        if perfil.work_words is not None:
            low, high = perfil.work_words
            if not low <= self.target_words <= high:
                raise ValueError(
                    f"el perfil de extension «{perfil.name}» admite una obra de {low} a "
                    f"{high} palabras y el brief pide {self.target_words}"
                )
        return self

    @model_validator(mode="after")
    def _relations_point_somewhere(self) -> Self:
        known = {e.id for e in self.entities}
        for rel in self.relations:
            missing = {rel.source, rel.target} - known
            if missing:
                raise ValueError(
                    f"la relacion {rel.kind!r} apunta a entidades que el brief no "
                    f"declara: {sorted(missing)}"
                )
        if len(known) != len(self.entities):
            raise ValueError("hay identificadores de entidad repetidos en el brief")
        if self.recipient is not None and self.recipient.entity_id not in known:
            raise ValueError(
                f"el destinatario {self.recipient.entity_id!r} no es una entidad del brief"
            )
        if self.recipient is not None:
            # RF-249: la edad y el nacimiento del destinatario los escribe la
            # carga desde `recipient`. Declararlos tambien en la entidad seria
            # dar dos valores del mismo hecho y que uno se perdiera sin avisar.
            ent = next(e for e in self.entities if e.id == self.recipient.entity_id)
            dobles = sorted({n for n, _ in ent.attributes} & set(RESERVED_RECIPIENT_ATTRIBUTES))
            if dobles:
                raise ValueError(
                    f"el destinatario declara {dobles} en sus atributos: son reservados "
                    "y van en recipient"
                )
        # RF-201, `srs-frontend-v1.md` RI-41: un brief contradictorio no se carga.
        encontradas = self.contradictions()
        if encontradas:
            raise ValueError("el brief se contradice: " + " ".join(c.message for c in encontradas))
        return self

    def contradictions(self) -> list[brief_rules.Contradiction]:
        return brief_rules.contradictions(
            age=self.recipient.age if self.recipient else None,
            genre=self.genre,
            tone=self.tone,
            title=self.title,
            dedication=self.dedication,
            names=[e.name for e in self.entities],
            forbidden_words=self.forbidden_words,
            forbidden_themes=self.forbidden_themes,
        )

    def recipient_name(self) -> str:
        if self.recipient is None:
            return ""
        return next((e.name for e in self.entities if e.id == self.recipient.entity_id), "")

    def profile(self) -> LengthProfile:
        """T53. Los rangos de longitud de la obra: los lee todo consumidor."""
        return length_profile_of(self.length_profile)

    def word_range(self) -> tuple[int, int]:
        """Rango de longitud aceptable de la obra.

        Lo consulta la condicion de cierre: una novela dentro de rango es una de
        las cuatro cosas que tienen que cumplirse para dar la obra por terminada.

        Con un perfil que fija el rango de obra, la tolerancia no lo desborda:
        una obra de prueba de 500 palabras no admite 550.
        """
        margin = int(self.target_words * self.word_tolerance)
        low, high = self.target_words - margin, self.target_words + margin
        obra = self.profile().work_words
        if obra is not None:
            low, high = max(low, obra[0]), min(high, obra[1])
        return (low, high)


def to_events(brief: Brief) -> list[Event]:
    """Descompone el brief en eventos.

    Todos con procedencia `brief` y sin capitulo de origen, que es la unica
    combinacion que el esquema acepta para esta procedencia.

    El `seq` crece a lo largo de la carga y no se reinicia por entidad: dos
    eventos del brief en el mismo instante y con el mismo `seq` sobre el mismo
    atributo harian que el orden de carga decidiera el resultado, que es la
    ambiguedad que la prueba deterministica de las proyecciones deja fijada.
    """
    events: list[Event] = []
    seq = 0

    def at() -> WorldTime:
        nonlocal seq
        t = WorldTime(stamp=brief.start.stamp, seq=seq)
        seq += 1
        return t

    def add(payload: object, entities: set[str]) -> None:
        events.append(
            Event(
                world_time=at(),
                payload=payload,  # type: ignore[arg-type]
                provenance=Provenance.BRIEF,
                chapter_origin=None,
                entities=frozenset(entities),
            )
        )

    # Las entidades primero y enteras: una relacion o un atributo sobre algo
    # que todavia no existe rompe la clave ajena al proyectar.
    for ent in brief.entities:
        add(EntityCreated(entity_id=ent.id, kind=ent.kind, name=ent.name), {ent.id})

    for ent in brief.entities:
        for alias in ent.aliases:
            add(AliasAdded(entity_id=ent.id, alias=alias), {ent.id})
        for name, value in ent.attributes:
            add(AttributeSet(entity_id=ent.id, name=name, value=value), {ent.id})
        for name, level in ent.competences:
            add(CompetenceSet(entity_id=ent.id, name=name, level=level), {ent.id})

    # RF-249, RD-41. La edad y la fecha de nacimiento del destinatario entran
    # como los atributos reservados de su entidad, con procedencia `brief`: son
    # los que lee la cronologia y el invariante I1 de Lean. Sin fecha no se
    # inventa ninguna: se deriva despues, y consta como derivada (RD-41).
    if brief.recipient is not None:
        rid = brief.recipient.entity_id
        add(AttributeSet(entity_id=rid, name="age", value=str(brief.recipient.age)), {rid})
        if brief.recipient.birth_date is not None:
            nacimiento = brief.recipient.birth_date.isoformat()
            add(AttributeSet(entity_id=rid, name="birth_date", value=nacimiento), {rid})

    for rel in brief.relations:
        add(
            RelationSet(source_id=rel.source, target_id=rel.target, kind=rel.kind),
            {rel.source, rel.target},
        )

    # La guia de estilo y el reglamento entran por el registro y se proyectan a
    # versiones (D-08), en vez de vivir en una tabla aparte: asi el canon
    # estructurado sigue siendo proyeccion pura.
    anchor = {brief.entities[0].id}
    add(DocumentVersion(doc_kind="style_guide", body=brief.style_guide), anchor)
    if brief.rulebook:
        add(DocumentVersion(doc_kind="rulebook", body=brief.rulebook), anchor)
    # El brief entero tambien, por la misma puerta: es lo que la ruta de
    # arranque (RI-02) necesita para componer el motor sin que nadie lo pase.
    add(DocumentVersion(doc_kind="brief", body=brief.model_dump_json()), anchor)
    # RNF-37. Las rubricas del Jurado son datos del fichero, no constantes del
    # juez: cambiar una es un despliegue (RF-157), y entra por la misma puerta.
    add(DocumentVersion(doc_kind="rubrics", body=rubrics.dumps(rubrics.DEFAULT_RUBRICS)), anchor)

    return events


def load_brief(path: Path) -> Brief:
    """El brief con el que se creo la novela, desde su version en el canon."""
    with connection.reader(path) as con:
        row = con.execute(
            "SELECT body FROM document_version WHERE doc_kind = 'brief' "
            "ORDER BY version DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise ValueError(f"la novela {path.name} no guarda su brief")
    return Brief.model_validate_json(row["body"])


# ------------------------------------------------------ niveles de prohibidas

#: RF-239, D-91. Los tres niveles del guardarrail, del mas fuerte al mas debil.
#: `estilo` no es guardarrail: son los n-gramas de POE-12 que proscribe la
#: congelacion, y los mira `check.repetition`, no `check.forbidden`.
ForbiddenLevel = Literal["global", "cliente", "novela"]
FORBIDDEN_LEVELS: tuple[ForbiddenLevel, ...] = ("global", "cliente", "novela")
STYLE_LEVEL = "estilo"
_RANK = {"global": 0, "cliente": 1, "novela": 2, STYLE_LEVEL: 3}

#: RD-38. La lista global, versionada, un termino por linea. Se copia a cada
#: novela al crearla para que el fichero de la novela siga siendo el estado
#: completo (AGENTS.md §3.2). Nace vacia: no se inventa una lista.
GLOBAL_FORBIDDEN = Path(__file__).parent / "db" / "forbidden_global.txt"


def read_global_forbidden(path: Path = GLOBAL_FORBIDDEN) -> tuple[str, ...]:
    """Los terminos de la lista global. Las lineas vacias y las `#` no cuentan."""
    if not path.exists():
        # Fallo cerrado: sin el fichero versionado no se sabe que falta.
        raise FileNotFoundError(f"falta la lista global de prohibidas: {path}")
    lineas = path.read_text(encoding="utf-8").splitlines()
    return tuple(t.strip() for t in lineas if t.strip() and not t.strip().startswith("#"))


def store_forbidden(
    con: sqlite3.Connection, term: str, *, level: ForbiddenLevel, chapter: int = 0
) -> str | None:
    """Guarda una prohibida en su nivel. Devuelve el nivel en que queda.

    D-91: un termino que ya esta en otro nivel se queda en el **mas fuerte**
    --global, cliente, novela-- y uno que era un n-grama de estilo sube al
    guardarrail. Dos terminos son el mismo si normalizan igual (RF-237):
    «Cabrón» del cliente y «cabron» de la global son una fila, no dos. Quien
    llama compara el nivel devuelto con el pedido para trazar el colapso.

    `None` si el termino no tiene ninguna palabra: una prohibida en blanco no
    prohibe nada. La usa la carga del brief y la usara la solicitud de cambio de
    tipo `forbid` (RF-256), siempre con la conexion de escritura de canon.
    """
    limpio = term.strip().lower()
    clave = normalize.key(limpio)
    if not clave:
        return None
    for row in con.execute("SELECT term, level FROM proscribed"):
        if normalize.key(row["term"]) != clave:
            continue
        actual = str(row["level"])
        if _RANK[actual] <= _RANK[level]:
            return actual
        con.execute(
            "UPDATE proscribed SET level = ?, kind = 'term' WHERE term = ?", (level, row["term"])
        )
        return level
    con.execute(
        "INSERT INTO proscribed (term, kind, level, added_chapter, added_at) "
        "VALUES (?, 'term', ?, ?, datetime('now'))",
        (limpio, level, chapter),
    )
    return level


def create_novel(path: Path, brief: Brief, *, global_terms: Sequence[str] | None = None) -> int:
    """Crea el fichero de la novela y carga el brief. Devuelve cuantos eventos.

    Todo dentro de una transaccion: un brief a medias dejaria una novela con
    entidades sin relaciones y nadie sabria que falta.

    `global_terms` sustituye a la lista global versionada; si no se pasa, se lee
    `forbidden_global.txt` (RD-38).
    """
    globales = read_global_forbidden() if global_terms is None else tuple(global_terms)
    connection.create(path)
    events = to_events(brief)
    with connection.canon_writer(path) as con:
        log.append(con, events)
        rebuild.rebuild(con)
        # RF-239, D-91. Las prohibidas entran por niveles desde la primera
        # escena: la global primero, porque es la mas fuerte, y despues las que
        # quien encarga dio en la entrevista. Las detecta `check.forbidden`.
        for term in globales:
            store_forbidden(con, term, level="global")
        for word in brief.forbidden_words:
            store_forbidden(con, word, level="cliente")
    return len(events)
