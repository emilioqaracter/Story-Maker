"""Perfiles de extension de una obra (T53).

Un perfil fija los rangos de longitud que la escaleta, las puertas y la
condicion de cierre aplican a una obra: cuanto mide una escena (EST-08), cuanto
un capitulo (EST-07) y, si el perfil lo fija, cuantos capitulos y escenas por
capitulo tiene y en que rango cae la obra entera.

Vive en `commons/` porque lo usan dos pisos que no se importan entre si:
`canon/` valida el brief contra el perfil que declara, y `planning/`,
`verification/` y `orchestration/` leen de el sus rangos. Ningun consumidor lee
un rango de una constante: lo lee del perfil del brief.

- `novela`: los rangos de EST-07 y EST-08. El numero de capitulos sale de la
  extension pedida. Es el perfil por defecto, y un brief sin el campo se
  comporta exactamente como antes de que existiera.
- `prueba`: una obra minima para probar el ciclo entero sin el coste de una
  novela. De 1.200 a 1.800 palabras, exactamente tres capitulos de una escena, y
  cada escena de 400 a 600 palabras, unas 500 por capitulo: lo minimo para que
  las citas del Jurado, de 5 a 25 palabras literales y unicas, anclen en todas
  sus dimensiones (D-113). Cae dentro de EST-08; el capitulo, por debajo de
  EST-07. Tres actos de un capitulo, asi que la puerta de acto corre tras cada
  capitulo. Los resumenes de escena y de
  capitulo miden como mucho la mitad de lo que resumen, y lo que en una novela
  corre cada cinco capitulos --conjunto dorado, resumen de obra-- corre una vez
  al cierre, para que la tirada de prueba tambien lo ejercite. Y el Jurado es
  mas facil de pasar (D-128): aprueba con mediana 2 en vez de 3, y ancla citas
  de 5 palabras en vez de 8. Solo el Jurado: `check.evidence` del Continuista
  sigue en 8, y los verificadores deterministas no cambian. El conjunto dorado
  del cierre juzga un caso y no cinco (D-131): sigue ejercitandose, sin que el
  cierre cueste mas que la obra.
- `breve`: la obra del encargo de la entrega (D-132). Exactamente diez
  capitulos de una escena, escena y capitulo de 1.000 a 1.500 palabras, obra de
  10.000 a 15.000. La escena cae dentro de EST-08; el capitulo, por debajo de
  EST-07. Los actos los planifica el Arquitecto. Lo periodico corre cada cinco
  capitulos, como en `novela`, y los resumenes usan los rangos de su nivel,
  porque una escena de 1.250 palabras ya es mas larga que cualquier resumen. El
  Jurado aprueba con mediana 2, como en `prueba`, y ancla citas de 8 palabras,
  como `check.evidence`; el conjunto dorado juzga un caso por pasada.

`breve` y `prueba` son ademas permisivos (D-136): el encargo mide que el ciclo
produzca una obra completa, asi que una obra con defectos declarados en la
traza vale mas que ninguna. `novela` sigue estricta.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LengthProfileName(StrEnum):
    NOVELA = "novela"
    PRUEBA = "prueba"
    BREVE = "breve"


@dataclass(frozen=True)
class LengthProfile:
    """Los rangos de longitud de una obra, y su forma si el perfil la fija."""

    name: LengthProfileName
    #: EST-07. Rango de longitud de un capitulo.
    chapter_words: tuple[int, int]
    #: EST-08. Rango de longitud de una escena.
    scene_words: tuple[int, int]
    #: Rango de la obra entera. `None`: lo fija solo la extension del brief.
    work_words: tuple[int, int] | None = None
    #: Capitulos de la obra. `None`: la extension sobre el capitulo tipico.
    chapters: int | None = None
    #: Escenas de cada capitulo. `None`: las que planifique el Arquitecto.
    scenes_per_chapter: int | None = None
    #: Actos de la obra y capitulos de cada uno. `None`: los que planifique.
    acts: int | None = None
    chapters_per_act: int | None = None
    #: Tope de un resumen de escena o de capitulo, como fraccion de las palabras
    #: del texto que resume. `None`: solo el rango de su nivel (§4.5).
    summary_ratio: float | None = None
    #: Lo que corre cada cinco capitulos (RF-117, RF-134) corre, en cambio, una
    #: vez al congelar el ultimo capitulo de la obra.
    periodic_at_close: bool = False
    #: D-39, D-128. Nivel minimo de la mediana del Jurado, sobre cinco, para que
    #: una dimension apruebe. `novela`: el de CAL-09, 3.
    jury_threshold: int = 3
    #: D-128. Palabras minimas de una cita del Jurado para que ancle. `novela`:
    #: las de `check.evidence`, 8 (`verification.md` §5.11). El maximo, 25, es
    #: el mismo en todos los perfiles y vive en el prompt del juez.
    quote_min_words: int = 8
    #: RF-134, D-131. Casos del conjunto dorado que el Jurado juzga en cada
    #: pasada. `novela`: 5. `prueba`: 1, porque corre al cierre y cada caso
    #: son tres jueces con sus correcciones de cita.
    golden_cases: int = 5
    #: D-136. Aceptacion permisiva: la tirada prefiere congelar con defectos
    #: declarados en la traza a parar. Solo bloquean los S1 deterministas y, aun
    #: asi, agotada la reparacion se congela el mejor intento. `novela`: estricta.
    lenient: bool = False

    def typical_chapter(self) -> int:
        """El punto medio del rango de capitulo: lo que mide un capitulo tipico."""
        return (self.chapter_words[0] + self.chapter_words[1]) // 2

    def summary_cap(self, words: int) -> int | None:
        """Cuantas palabras puede tener el resumen de un texto de `words`, si hay tope."""
        if self.summary_ratio is None:
            return None
        return max(1, int(words * self.summary_ratio))

    def periodic_due(self, chapter: int, *, last_chapter: int, every: int) -> bool:
        """Si en este capitulo toca lo periodico: cada `every`, o al cierre."""
        if self.periodic_at_close:
            return chapter == last_chapter
        return chapter % every == 0


NOVELA = LengthProfile(
    name=LengthProfileName.NOVELA,
    chapter_words=(1_500, 4_000),
    scene_words=(400, 1_500),
)

PRUEBA = LengthProfile(
    name=LengthProfileName.PRUEBA,
    # Un capitulo es su unica escena: su rango es el de la escena.
    chapter_words=(400, 600),
    scene_words=(400, 600),
    work_words=(1_200, 1_800),
    chapters=3,
    scenes_per_chapter=1,
    acts=3,
    chapters_per_act=1,
    summary_ratio=0.5,
    periodic_at_close=True,
    jury_threshold=2,
    quote_min_words=5,
    golden_cases=1,
    lenient=True,
)

BREVE = LengthProfile(
    name=LengthProfileName.BREVE,
    # D-132. Un capitulo es su unica escena: su rango es el de la escena.
    chapter_words=(1_000, 1_500),
    scene_words=(1_000, 1_500),
    work_words=(10_000, 15_000),
    chapters=10,
    scenes_per_chapter=1,
    jury_threshold=2,
    golden_cases=1,
    lenient=True,
)

PROFILES: dict[LengthProfileName, LengthProfile] = {p.name: p for p in (NOVELA, PRUEBA, BREVE)}

#: Los limites de escena de todos los perfiles juntos. Es lo que admite el
#: esquema de una entrada de escaleta; el rango del perfil de la obra lo
#: comprueba `outline.check`, que es quien sabe de que obra es la escaleta.
SCENE_WORDS_BOUNDS = (
    min(p.scene_words[0] for p in PROFILES.values()),
    max(p.scene_words[1] for p in PROFILES.values()),
)


def of(name: LengthProfileName | str) -> LengthProfile:
    return PROFILES[LengthProfileName(name)]
