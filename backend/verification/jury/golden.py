"""El conjunto dorado de defectos (CAL-10), sembrado sin intervencion.

RF-133, RF-134, D-41. Se parte de capitulos **congelados**, que pasaron todas
las puertas, y se les siembra un defecto conocido con una transformacion
determinista. Cada caso guarda que se le hizo y que dimension tiene que
detectarlo. Es lo que sustituye a la calibracion por revision manual: si el
Jurado deja de ver lo que se le sembro, ha derivado.

Las cinco transformaciones de la spec, y lo que siembran:

| Transformacion | Dimension |
|---|---|
| Intercambio de las lineas de dialogo entre dos escenas de POV distinto | voz |
| Insercion de terminos proscritos y de cliche | guia de estilo |
| Duplicacion de un parrafo | ritmo |
| Supresion de la frase que realiza el cambio de valor, la ultima | ritmo |
| Sustitucion de un nombre por otro de la obra | voz |

Tension, subtexto y tema no tienen transformacion que los degrade sin juicio:
quedan en el riesgo aceptado de la SRS v2 §7.4.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from commons.types.rubrics import Dimension
from verification.jury.verdict import JuryVerdict

#: D-41. Suelo de deteccion: el mismo que la mutacion de RF-50.
DETECTION_FLOOR = 0.90

#: Cliches que la guia de la semilla veta de forma explicita, mas los terminos
#: proscritos del fichero. Lo sembrado tiene que ser inequivoco.
_CLICHES = ("se dejo el alma en el campo", "el gol de la esperanza", "lucho como un titan")

_DIALOGUE = re.compile(r"^\s*[—-].*$", re.M)
_SENTENCE = re.compile(r"[^.!?…]+[.!?…]+")


class GoldenCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    transformation: str
    dimension: Dimension
    scene_ids: tuple[str, ...]
    povs: tuple[str, ...]
    texts: tuple[str, ...]


def _paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def swap_dialogue(a: str, b: str) -> tuple[str, str] | None:
    la, lb = _DIALOGUE.findall(a), _DIALOGUE.findall(b)
    if not la or not lb:
        return None
    return a.replace(la[0], lb[0], 1), b.replace(lb[0], la[0], 1)


def insert_cliches(text: str, proscribed: Sequence[str]) -> str:
    parrafos = _paragraphs(text)
    terminos = [*proscribed[:2], *_CLICHES]
    for i, termino in enumerate(terminos):
        idx = min(len(parrafos) - 1, i * max(1, len(parrafos) // len(terminos)))
        parrafos[idx] = parrafos[idx].rstrip() + f" Aquella tarde {termino}."
    return "\n\n".join(parrafos)


def duplicate_paragraph(text: str) -> str | None:
    parrafos = _paragraphs(text)
    if len(parrafos) < 2:
        return None
    medio = len(parrafos) // 2
    return "\n\n".join([*parrafos[: medio + 1], parrafos[medio], *parrafos[medio + 1 :]])


def drop_last_sentence(text: str) -> str | None:
    frases = _SENTENCE.findall(text.strip())
    if len(frases) < 3:
        return None
    ultima = frases[-1]
    return text.strip()[: text.strip().rfind(ultima)].rstrip()


def swap_name(text: str, name: str, other: str) -> str | None:
    if name not in text or name == other:
        return None
    return text.replace(name, other)


def build(con: sqlite3.Connection, *, limit: int = 10) -> list[GoldenCase]:
    """Casos desde la prosa congelada del fichero. Determinista y acotado."""
    escenas = con.execute(
        "SELECT id, pov_entity FROM prose_scene ORDER BY chapter, scene_number"
    ).fetchall()
    textos: dict[str, str] = {}
    for fila in escenas:
        trozos = [
            r["text"]
            for r in con.execute(
                "SELECT text FROM prose_chunk WHERE scene_id = ? ORDER BY ordinal", (fila["id"],)
            )
        ]
        # Deshacer el solape: el primer parrafo de cada trozo repite el ultimo del anterior.
        parrafos: list[str] = []
        for t in trozos:
            ps = _paragraphs(t)
            if parrafos and ps and ps[0] == parrafos[-1]:
                ps = ps[1:]
            parrafos.extend(ps)
        textos[fila["id"]] = "\n\n".join(parrafos)
    proscritos = [r["term"] for r in con.execute("SELECT term FROM proscribed ORDER BY term")]
    nombres = [
        r["name"] for r in con.execute("SELECT name FROM entity WHERE kind = 'person' ORDER BY id")
    ]

    casos: list[GoldenCase] = []
    ids = [f["id"] for f in escenas]
    povs = {f["id"]: f["pov_entity"] for f in escenas}
    for i, sid in enumerate(ids):
        texto = textos[sid]
        pov = povs[sid]
        if (t := duplicate_paragraph(texto)) is not None:
            casos.append(
                GoldenCase(
                    id=f"{sid}-dup",
                    transformation="duplicar-parrafo",
                    dimension=Dimension.PACING,
                    scene_ids=(sid,),
                    povs=(pov,),
                    texts=(t,),
                )
            )
        if (t := drop_last_sentence(texto)) is not None:
            casos.append(
                GoldenCase(
                    id=f"{sid}-cierre",
                    transformation="suprimir-cambio-de-valor",
                    dimension=Dimension.PACING,
                    scene_ids=(sid,),
                    povs=(pov,),
                    texts=(t,),
                )
            )
        casos.append(
            GoldenCase(
                id=f"{sid}-cliche",
                transformation="insertar-proscritos",
                dimension=Dimension.STYLE_GUIDE,
                scene_ids=(sid,),
                povs=(pov,),
                texts=(insert_cliches(texto, proscritos),),
            )
        )
        presentes = [n for n in nombres if n in texto]
        otros = [n for n in nombres if n not in presentes]
        if presentes and otros and (t := swap_name(texto, presentes[0], otros[0])) is not None:
            casos.append(
                GoldenCase(
                    id=f"{sid}-nombre",
                    transformation="sustituir-nombre",
                    dimension=Dimension.VOICE,
                    scene_ids=(sid,),
                    povs=(pov,),
                    texts=(t,),
                )
            )
        otra = next((o for o in ids[i + 1 :] if povs[o] != pov), None)
        if otra is not None and (par := swap_dialogue(texto, textos[otra])) is not None:
            casos.append(
                GoldenCase(
                    id=f"{sid}-{otra}-voz",
                    transformation="intercambiar-dialogo",
                    dimension=Dimension.VOICE,
                    scene_ids=(sid, otra),
                    povs=(pov, povs[otra]),
                    texts=par,
                )
            )
    # Reparto estable entre transformaciones para que el limite no deje ninguna fuera.
    por_tipo: dict[str, list[GoldenCase]] = {}
    for c in casos:
        por_tipo.setdefault(c.transformation, []).append(c)
    out: list[GoldenCase] = []
    while len(out) < limit and any(por_tipo.values()):
        for tipo in sorted(por_tipo):
            if por_tipo[tipo] and len(out) < limit:
                out.append(por_tipo[tipo].pop(0))
    return out


def detected(case: GoldenCase, verdict: JuryVerdict) -> bool:
    """Detecta si la dimension sembrada no pasa: bajo umbral o invalida."""
    d = verdict.get(case.dimension)
    return d is not None and not d.passed


def detection_rate(results: Sequence[tuple[GoldenCase, JuryVerdict]]) -> float:
    if not results:
        return 0.0
    return sum(1 for c, v in results if detected(c, v)) / len(results)
