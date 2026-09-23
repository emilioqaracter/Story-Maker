"""La novela de prueba del recorrido visual (`specs/srs-backend-v4.md` RF-267, T49).

Crea, en el directorio que se le da, una novela congelada con brief de prueba:
tres capitulos, destinatario y dedicatoria. Sin modelo: los capitulos se
congelan con la misma transaccion que usa el Archivero (`canon.freeze`) y un
embebedor doble, como las pruebas del backend.

El recorrido nunca lee `backend/runs-golden/` ni `backend/runs-real/`: siembra
aqui su propia novela y trabaja sobre copias de ella.

    python seed.py create <fichero.sqlite>            # novela sana, imprime lo esperado en JSON
    python seed.py strip-dedication <fichero.sqlite>  # la misma copia, sin dedicatoria

Importa los paquetes de `backend/` desde su carpeta, sea cual sea el
directorio de trabajo. Todos los nombres son de prueba.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from canon.brief import Brief, BriefEntity, Recipient, create_novel
from canon.db import connection
from canon.freeze.freeze import SceneToFreeze, commit_chapter, prepare
from commons.provider.port import Embedding
from commons.types.primitives import WorldTime

TITLE = "El verano del faro"
DEDICATION = "Para Irene, que aprendió a nadar junto al faro."
RECIPIENT = "Irene"
PLACE = "el faro"

#: Capitulo -> escenas: (texto, entidades presentes).
CHAPTERS: dict[int, list[tuple[str, tuple[str, ...]]]] = {
    1: [
        ("Irene llegó al faro con Tomás al caer la tarde.", ("irene", "tomas")),
        ("Irene miró el mar desde la barandilla, sola.", ("irene",)),
    ],
    2: [("Tomás le enseñó a flotar en la cala del faro.", ("irene", "tomas"))],
    3: [("Al final del verano, Irene cruzó la cala a nado.", ("irene", "tomas"))],
}


class _Embedder:
    """Doble del embebedor: el recorrido no mide recuperacion."""

    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        return [Embedding(values=(0.1, 0.2), model_id="doble", dimension=2) for _ in texts]


def _brief() -> Brief:
    return Brief(
        title=TITLE,
        start=WorldTime(stamp="2026-07-01"),
        entities=(
            BriefEntity(id="irene", kind="person", name=RECIPIENT),
            BriefEntity(id="tomas", kind="person", name="Tomás", attributes=(("oficio", "farero"),)),
            BriefEntity(id="faro", kind="place", name=PLACE),
        ),
        style_guide="Tercera persona, pasado.",
        target_words=2000,
        tone="cálido",
        dedication=DEDICATION,
        recipient=Recipient(entity_id="irene", age=10, role="protagonista"),
    )


def create(path: Path) -> dict[str, object]:
    if path.exists():
        raise SystemExit(f"{path} ya existe: el recorrido siembra siempre en un directorio nuevo")
    create_novel(path, _brief(), global_terms=())
    for cap, escenas in CHAPTERS.items():
        congeladas = [
            SceneToFreeze(
                id=f"c{cap}e{n}",
                chapter=cap,
                scene_number=n,
                pov_entity="irene",
                place_entity="faro",
                world_time=WorldTime(stamp=f"2026-07-{cap:02d}"),
                function="establecer",
                text=texto,
                summary=f"resumen {cap}.{n}",
                present=presentes,
            )
            for n, (texto, presentes) in enumerate(escenas, start=1)
        ]
        prep = prepare(congeladas, chapter=cap, chapter_summary=f"capitulo {cap}", embed=_Embedder())
        with connection.canon_writer(path) as con:
            commit_chapter(con, prep)
    return {
        "title": TITLE,
        "dedication": DEDICATION,
        "recipient": RECIPIENT,
        "chapters": sorted(CHAPTERS),
        "person": RECIPIENT,
        "place": PLACE,
    }


def strip_dedication(path: Path) -> None:
    """El defecto de datos que la puerta de T49 provoca: el brief de la copia pierde la dedicatoria.

    Toca solo la copia, y solo el brief que lee el manifiesto de RI-43.
    """
    con = sqlite3.connect(path)
    try:
        row = con.execute(
            "SELECT rowid, body FROM document_version WHERE doc_kind = 'brief' "
            "ORDER BY version DESC LIMIT 1"
        ).fetchone()
        if row is None:
            raise SystemExit(f"{path} no guarda su brief")
        body = json.loads(row[1])
        body["dedication"] = ""
        con.execute(
            "UPDATE document_version SET body = ? WHERE rowid = ?",
            (json.dumps(body, ensure_ascii=False), row[0]),
        )
        con.commit()
    finally:
        con.close()


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in {"create", "strip-dedication"}:
        print(__doc__, file=sys.stderr)
        return 2
    path = Path(argv[1])
    if argv[0] == "create":
        # ASCII: quien lo lee es otro proceso, y la consola de Windows no es UTF-8.
        sys.stdout.write(json.dumps(create(path)) + "\n")
    else:
        strip_dedication(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
