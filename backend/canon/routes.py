"""Rutas HTTP que sirve `canon/`.

RI-01, RI-04 a RI-06, RI-31, RI-42 a RI-46. Cada funcionalidad lleva las suyas dentro: no hay
carpeta `api/` transversal, porque seria una capa tecnica con otro nombre y es
justo lo que la organizacion por funcionalidad evita. La aplicacion se compone
en `orchestration/`, que monta este router junto a los demas.

Dos reglas gobiernan todo lo de aqui:

- **Ninguna ruta escribe canon.** La unica escritura que la API provoca es la
  carga del brief, y ocurre **antes** del ciclo, nunca dentro (RI-09).
- **Solo sale lo congelado.** Ni borradores, ni defectos, ni el registro en
  crudo. Un lector no puede ver texto que todavia puede desaparecer (RF-65).
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from canon import entities, manuscript
from canon.brief import Brief, create_novel, load_brief
from canon.db import connection
from canon.skills import read
from commons.settings import NOVEL_ID_PATTERN, InvalidNovelIdError, Settings
from commons.types.primitives import ISO_INSTANT_PATTERN, WorldTime

router = APIRouter(tags=["canon"])


class ErrorDetail(BaseModel):
    """Cuerpo de todo error de esta API.

    Se declara porque un contrato que dice "puede devolver 404" sin decir con
    que forma deja al cliente generado adivinando, que es la mitad del problema
    que el contrato existe para quitar.
    """

    model_config = ConfigDict(frozen=True)

    detail: str


#: Los errores que cada ruta puede devolver, declarados. Un codigo que la API
#: produce y el esquema no documenta es una mentira del contrato, y es
#: exactamente lo que la comprobacion generativa encuentra.
# El tipo lo impone la firma de FastAPI; el `object` mantiene nuestra parte
# tipada sin pelearse con la suya.
_Responses = dict[int | str, dict[str, object]]

_NOT_FOUND: _Responses = {status.HTTP_404_NOT_FOUND: {"model": ErrorDetail}}
_BAD_ID: _Responses = {status.HTTP_400_BAD_REQUEST: {"model": ErrorDetail}}
_CONFLICT: _Responses = {status.HTTP_409_CONFLICT: {"model": ErrorDetail}}


def get_settings() -> Settings:
    return Settings.from_env()


SettingsDep = Annotated[Settings, Depends(get_settings)]

#: El identificador va con su forma declarada en el contrato, no solo validada
#: dentro. Un cliente generado desde un contrato que dice "texto" enviaria
#: cualquier cosa; con el patron, sabe que forma tiene antes de llamar.
NovelId = Annotated[str, Path(pattern=NOVEL_ID_PATTERN, description="Identificador de la novela")]


# ------------------------------------------------------------------ respuestas


class NovelCreated(BaseModel):
    model_config = ConfigDict(frozen=True)

    novel_id: str
    events_loaded: int = Field(description="Hechos que el brief aporto al canon")


class ChapterSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapter: int
    scenes: int
    words: int
    ends_at: str = Field(description="Instante de mundo de su ultima escena, ISO 8601")
    ends_seq: int = Field(ge=0, description="Desempate de ese instante")


class ChapterList(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapters: tuple[ChapterSummary, ...]


class SceneProse(BaseModel):
    model_config = ConfigDict(frozen=True)

    scene_number: int
    pov: str
    text: str


class ChapterProse(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapter: int
    scenes: tuple[SceneProse, ...]


# --------------------------------------------------------------------- ayudas


def _path(settings: Settings, novel_id: str):  # type: ignore[no-untyped-def]
    try:
        path = settings.novel_path(novel_id)
    except InvalidNovelIdError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not path.exists():
        # RI-10: error explicito, nunca una coleccion vacia que parezca una
        # novela recien empezada. Confundir "no existe" con "no tiene nada" es
        # como un fallo de configuracion pasa por un estado legitimo.
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la novela {novel_id!r}")
    return path


# --------------------------------------------------------------------- rutas


@router.post(
    "/novels",
    status_code=status.HTTP_201_CREATED,
    responses={**_BAD_ID, **_CONFLICT},
)
def create(
    brief: Brief,
    settings: SettingsDep,
    novel_id: Annotated[
        str, Query(pattern=NOVEL_ID_PATTERN, description="Identificador de la novela")
    ],
) -> NovelCreated:
    """RI-01. Carga el brief. Es la unica escritura que la API provoca."""
    try:
        path = settings.novel_path(novel_id)
    except InvalidNovelIdError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if path.exists():
        raise HTTPException(status.HTTP_409_CONFLICT, f"la novela {novel_id!r} ya existe")
    return NovelCreated(novel_id=novel_id, events_loaded=create_novel(path, brief))


@router.get("/novels/{novel_id}/chapters", responses={**_BAD_ID, **_NOT_FOUND})
def list_chapters(novel_id: NovelId, settings: SettingsDep) -> ChapterList:
    """RI-04. Solo capitulos congelados: son los unicos que estan en el indice."""
    with connection.reader(_path(settings, novel_id)) as con:
        rows = con.execute(
            "SELECT s.chapter AS chapter, count(DISTINCT s.id) AS scenes, "
            "       sum(length(c.text) - length(replace(c.text, ' ', '')) + 1) AS words, "
            "       (SELECT z.world_time FROM prose_scene z WHERE z.chapter = s.chapter "
            "         ORDER BY z.world_time DESC, z.world_seq DESC LIMIT 1) AS ends_at, "
            "       (SELECT z.world_seq FROM prose_scene z WHERE z.chapter = s.chapter "
            "         ORDER BY z.world_time DESC, z.world_seq DESC LIMIT 1) AS ends_seq "
            "  FROM prose_scene s LEFT JOIN prose_chunk c ON c.scene_id = s.id "
            " GROUP BY s.chapter ORDER BY s.chapter"
        ).fetchall()
    return ChapterList(
        chapters=tuple(
            ChapterSummary(
                chapter=r["chapter"],
                scenes=r["scenes"],
                words=r["words"] or 0,
                ends_at=r["ends_at"],
                ends_seq=r["ends_seq"],
            )
            for r in rows
        )
    )


@router.get("/novels/{novel_id}/chapters/{number}", responses={**_BAD_ID, **_NOT_FOUND})
def get_chapter(novel_id: NovelId, number: int, settings: SettingsDep) -> ChapterProse:
    """RI-05. La prosa de un capitulo congelado."""
    with connection.reader(_path(settings, novel_id)) as con:
        scenes = con.execute(
            "SELECT id, scene_number, pov_entity FROM prose_scene "
            " WHERE chapter = ? ORDER BY scene_number",
            (number,),
        ).fetchall()
        if not scenes:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"el capitulo {number} no esta congelado",
            )
        out: list[SceneProse] = []
        for scene in scenes:
            chunks = con.execute(
                "SELECT text FROM prose_chunk WHERE scene_id = ? ORDER BY ordinal",
                (scene["id"],),
            ).fetchall()
            out.append(
                SceneProse(
                    scene_number=scene["scene_number"],
                    pov=scene["pov_entity"],
                    text="\n\n".join(c["text"] for c in chunks),
                )
            )
    return ChapterProse(chapter=number, scenes=tuple(out))


@router.get("/novels/{novel_id}/state", responses={**_BAD_ID, **_NOT_FOUND})
def get_state(
    novel_id: NovelId,
    settings: SettingsDep,
    at: Annotated[
        str,
        Query(
            description="Instante de mundo, ISO 8601",
            pattern=ISO_INSTANT_PATTERN,
        ),
    ],
    seq: Annotated[int, Query(ge=0)] = 0,
) -> read.WorldState:
    """RI-06. El estado del mundo en un instante.

    El instante es obligatorio: un estado sin instante no significa nada en un
    sistema donde todo tiene vigencia.

    El formato se declara **en el contrato** y no solo en el validador. Mientras
    vivio solo en el codigo, el esquema prometia aceptar cualquier texto y la
    ruta rechazaba casi todos: un cliente generado desde ese contrato habria
    enviado basura convencido de que era valida. Lo encontro la comprobacion
    generativa, que es para lo que esta.
    """
    with connection.reader(_path(settings, novel_id)) as con:
        return read.state_at(con, WorldTime(stamp=at, seq=seq))


class RetconEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    fact_key: str
    previous_value: str
    new_value: str
    refrozen_scenes: tuple[str, ...]
    rule: str
    chapter_origin: int


class RetconList(BaseModel):
    model_config = ConfigDict(frozen=True)

    retcons: tuple[RetconEntry, ...]


@router.get("/novels/{novel_id}/retcons", responses={**_BAD_ID, **_NOT_FOUND})
def list_retcons(novel_id: NovelId, settings: SettingsDep) -> RetconList:
    """RI-31. Los retcons aplicados, con la regla que los admitio."""
    from canon.arbiter.refreeze import read_retcons

    with connection.reader(_path(settings, novel_id)) as con:
        filas = read_retcons(con)
    return RetconList(
        retcons=tuple(
            RetconEntry(
                fact_key=str(f["fact_key"]),
                previous_value=str(f["previous_value"]),
                new_value=str(f["new_value"]),
                refrozen_scenes=tuple(str(x) for x in f["refrozen_scenes"]),  # type: ignore[attr-defined]
                rule=str(f["rule"]),
                chapter_origin=int(str(f["chapter_origin"])),
            )
            for f in filas
        )
    )


# ------------------------------------------------ versiones y fichas · v3 §4.2


class VersionList(BaseModel):
    model_config = ConfigDict(frozen=True)

    versions: tuple[manuscript.VersionInfo, ...]


class ChapterAtVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    chapter: int
    version: int
    scenes: tuple[manuscript.SceneAt, ...]


class EntityList(BaseModel):
    model_config = ConfigDict(frozen=True)

    entities: tuple[entities.EntitySummary, ...]


EntityKind = Literal["person", "place", "institution", "object"]


@router.get("/novels/{novel_id}/versions", responses={**_BAD_ID, **_NOT_FOUND})
def list_versions(novel_id: NovelId, settings: SettingsDep) -> VersionList:
    """RI-42. Versiones del manuscrito (PRO-08): la 1 es la tirada, cada enmienda una mas."""
    with connection.reader(_path(settings, novel_id)) as con:
        return VersionList(versions=tuple(manuscript.versions(con)))


@router.get("/novels/{novel_id}/versions/{version}", responses={**_BAD_ID, **_NOT_FOUND})
def get_manifest(
    novel_id: NovelId, version: Annotated[int, Path(ge=1)], settings: SettingsDep
) -> manuscript.Manifest:
    """RI-43. Portada e indice de una version, con los capitulos cambiados marcados."""
    path = _path(settings, novel_id)
    brief = load_brief(path)
    with connection.reader(path) as con:
        out = manuscript.manifest(
            con,
            version,
            title=brief.title,
            dedication=brief.dedication,
            recipient_name=brief.recipient_name(),
        )
    if out is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"la novela no tiene la version {version}")
    return out


@router.get(
    "/novels/{novel_id}/versions/{version}/chapters/{number}", responses={**_BAD_ID, **_NOT_FOUND}
)
def get_chapter_at(
    novel_id: NovelId,
    version: Annotated[int, Path(ge=1)],
    number: Annotated[int, Path(ge=1)],
    settings: SettingsDep,
) -> ChapterAtVersion:
    """RI-44. Un capitulo tal como estaba en una version, con sus escenas cambiadas marcadas."""
    with connection.reader(_path(settings, novel_id)) as con:
        if version > manuscript.current_version(con):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"la novela no tiene la version {version}"
            )
        escenas = manuscript.chapter_at(con, number, version)
    if escenas is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"el capitulo {number} no esta en la version {version}"
        )
    return ChapterAtVersion(chapter=number, version=version, scenes=tuple(escenas))


@router.get("/novels/{novel_id}/entities", responses={**_BAD_ID, **_NOT_FOUND})
def list_entities(
    novel_id: NovelId,
    settings: SettingsDep,
    kind: Annotated[
        EntityKind | None, Query(alias="type", description="PER-01, MUN-01, MUN-03 o MUN-02")
    ] = None,
) -> EntityList:
    """RI-45. Personajes, lugares, instituciones y objetos, con los capitulos donde aparecen."""
    with connection.reader(_path(settings, novel_id)) as con:
        return EntityList(entities=tuple(entities.list_entities(con, kind)))


@router.get("/novels/{novel_id}/entities/{entity_id}", responses={**_BAD_ID, **_NOT_FOUND})
def get_entity(
    novel_id: NovelId,
    entity_id: Annotated[str, Path(min_length=1, max_length=200)],
    settings: SettingsDep,
) -> entities.EntityFile:
    """RI-46. La ficha: compacta, hechos con procedencia, relaciones vigentes y apariciones."""
    with connection.reader(_path(settings, novel_id)) as con:
        ficha = entities.entity_file(con, entity_id)
    if ficha is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no existe la entidad {entity_id!r}")
    return ficha
