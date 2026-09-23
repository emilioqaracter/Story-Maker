"""Las dos fixtures de la verificacion formal. `specs/srs-backend-v4.md` RI-63, RF-246.

Dos canones pequeños construidos con la API del canon --brief, congelacion y
delta--, no con filas escritas a mano: asi lo que se demuestra es lo que
produce el sistema de verdad.

- **Limpia**: cumple las cuatro invariantes, y cubre los casos que las rozan:
  un nacimiento declarado, uno derivado de la edad y uno ausente; una
  exclusion con el excluido presente justo en su instante; y dos escenas del
  mismo dia en lugares distintos, separadas por el desempate.
- **Sembrada**: la limpia mas una incoherencia por invariante, cada una
  elegida para romper la suya y ninguna otra. `SEEDED` dice que teorema falla
  y con que filas.

Sus cronologias generadas se versionan en `lean/StoryMaker/Fixture.lean` y
`lean/Seeded.lean`. `python -m verification.formal.fixtures` comprueba que
siguen al dia y las compila; con `--write` las regenera.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from canon.brief import Brief, BriefEntity, create_novel
from canon.db import connection
from canon.events.types import AttributeSet, Event
from canon.freeze.freeze import SceneToFreeze, commit_chapter, prepare
from commons.provider.port import Embedding
from commons.types.primitives import Provenance, WorldTime
from verification.formal.generate import THEOREMS, src

START = WorldTime(stamp="2026-08-01")


class _Embedder:
    """Doble del modelo de vectores: la verificacion formal no los mira."""

    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        return [Embedding(values=(0.1, 0.2), model_id="fixture", dimension=2) for _ in texts]


def _brief(*, seeded: bool) -> Brief:
    people = [
        # Nacimiento declarado, con edad que cuadra: diez años el 2026-08-01.
        BriefEntity(
            id="lucia",
            kind="person",
            name="Lucía",
            attributes=(("age", "10"), ("birth_date", "2016-03-04")),
        ),
        # Solo edad: el nacimiento se deriva, (2013-08-01, 2014-08-01].
        BriefEntity(id="marco", kind="person", name="Marco", attributes=(("age", "12"),)),
        # Ni edad ni fecha: el nacimiento esta ausente y nunca se inventa.
        BriefEntity(id="tomas", kind="person", name="Tomás"),
        BriefEntity(id="rex", kind="object", name="Rex", attributes=(("color", "negro"),)),
        BriefEntity(id="parque", kind="place", name="el parque"),
        BriefEntity(id="estadio", kind="place", name="el estadio"),
    ]
    if seeded:
        # I1: Ana nace el 15 y aparece el 11.
        people.append(
            BriefEntity(
                id="ana", kind="person", name="Ana", attributes=(("birth_date", "2026-08-15"),)
            )
        )
    return Brief(
        title="La fixture de la cronologia",
        start=START,
        entities=tuple(people),
        style_guide="Tercera persona, pasado.",
        target_words=2000,
    )


def _scene(
    cap: int,
    n: int,
    stamp: str,
    place: str,
    present: tuple[str, ...],
    *,
    seq: int = 0,
    pov: str = "lucia",
) -> SceneToFreeze:
    # El POV cuenta como presente: la vista `chronology` lo incluye (RF-242).
    return SceneToFreeze(
        id=f"c{cap}e{n}",
        chapter=cap,
        scene_number=n,
        pov_entity=pov,
        place_entity=place,
        world_time=WorldTime(stamp=stamp, seq=seq),
        function="establecer",
        text=f"Escena {cap}.{n}.",
        summary=f"resumen {cap}.{n}",
        present=present,
    )


def _event(cap: int, stamp: str, payload: AttributeSet) -> Event:
    return Event(
        world_time=WorldTime(stamp=stamp),
        payload=payload,
        provenance=Provenance.PROSE,
        chapter_origin=cap,
        entities=frozenset({payload.entity_id}),
    )


def _chapters(*, seeded: bool) -> list[tuple[list[SceneToFreeze], list[Event]]]:
    first_cast = ("lucia", "rex", "tomas", "ana") if seeded else ("lucia", "rex", "tomas")
    one = [
        _scene(1, 1, "2026-08-11", "parque", first_cast),
        _scene(1, 2, "2026-08-12", "estadio", ("lucia", "marco")),
        # Tomas esta en la escena del instante en que se marcha: vale.
        _scene(1, 3, "2026-08-13", "parque", ("marco", "tomas")),
    ]
    delta_one = [
        # Una vigencia que se cierra sola al cambiar el valor: ordenada.
        _event(1, "2026-08-12", AttributeSet(entity_id="rex", name="color", value="marrón")),
        _event(1, "2026-08-13", AttributeSet(entity_id="tomas", name="excluded", value="marcha")),
    ]
    if seeded:
        # I3: una vigencia que termina antes de empezar.
        delta_one.append(
            _event(
                1,
                "2026-08-12T10:00",
                AttributeSet(
                    entity_id="rex",
                    name="collar",
                    value="rojo",
                    valid_to=WorldTime(stamp="2026-08-05"),
                ),
            )
        )
    second_cast = ("lucia", "marco", "rex", "tomas") if seeded else ("lucia", "marco", "rex")
    two = [
        # I4 en la sembrada: Tomas vuelve despues de haberse marchado.
        _scene(2, 1, "2026-08-21", "estadio", second_cast),
        # Mismo dia y otro lugar, pero otro desempate: otro instante.
        _scene(2, 2, "2026-08-21", "parque", ("lucia",), seq=1),
    ]
    if seeded:
        # I2: Marco en el parque en el mismo instante en que esta en el estadio.
        # Con su propio punto de vista: Lucia, que tambien esta en el estadio,
        # romperia la misma invariante una segunda vez.
        two.append(_scene(2, 3, "2026-08-21", "parque", ("marco",), pov="marco"))
    return [(one, delta_one), (two, [])]


def build(path: Path, *, seeded: bool) -> Path:
    """Crea el SQLite de la fixture en `path`."""
    create_novel(path, _brief(seeded=seeded))
    for cap, (scenes, delta) in enumerate(_chapters(seeded=seeded), start=1):
        prepared = prepare(
            scenes, chapter=cap, chapter_summary=f"capitulo {cap}", embed=_Embedder(), delta=delta
        )
        with connection.canon_writer(path) as con:
            commit_chapter(con, prepared)
    return path


def build_clean(path: Path) -> Path:
    return build(path, seeded=False)


def build_seeded(path: Path) -> Path:
    return build(path, seeded=True)


#: Lo que tiene que fallar en la sembrada: cada teorema, con las filas de origen
#: de su violacion. Ningun otro error cuenta como paso (RF-246).
SEEDED: dict[str, tuple[tuple[str, ...], ...]] = {
    THEOREMS["I1"]: (
        (
            src("chronology", "c1e1", "ana"),
            src("attribute", "ana", "birth_date", "2026-08-01"),
        ),
    ),
    THEOREMS["I2"]: (
        (
            src("chronology", "c2e1", "marco"),
            src("chronology", "c2e3", "marco"),
        ),
    ),
    THEOREMS["I3"]: ((src("attribute", "rex", "collar", "2026-08-12T10:00"),),),
    THEOREMS["I4"]: (
        (
            src("chronology", "c2e1", "tomas"),
            src("attribute", "tomas", "excluded", "2026-08-13"),
        ),
    ),
}

LEAN = Path(__file__).resolve().parent.parent / "lean"

#: Donde se versiona la cronologia generada de cada fixture, y el objetivo de
#: Lake que la compila. La limpia es el objetivo por defecto: `lake build` a
#: secas tiene que pasar.
CLEAN_FILE = LEAN / "StoryMaker" / "Fixture.lean"
SEEDED_FILE = LEAN / "Seeded.lean"
CLEAN_TARGET: str | None = None
SEEDED_TARGET = "Seeded"
