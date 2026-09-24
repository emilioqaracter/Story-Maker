"""Del veredicto de tres instancias al veredicto del Jurado.

RF-129 a RF-132, RD-20, D-39. `architecture.md` §9.2. Codigo puro sobre lo que
devolvieron las instancias; las llamadas las hace el Orquestador.

Tres reglas, y las tres impiden que un numero sin significado decida:

1. **La cita se comprueba antes que la puntuacion** (RF-129). Una puntuacion
   cuya cita no ancla literal y unica en una escena del capitulo --la que
   nombra, o la unica que la contiene-- se descarta sin evaluarla y consta
   contra la instancia (RF-111).
2. **Dispersion es rango**: el nivel mas alto menos el mas bajo de las tres. Con
   rango de 2 o mas el veredicto de esa dimension es invalido y **no se
   promedia**: se repite con las semillas cambiadas, y si vuelve a dispersar la
   dimension cuenta como bajo umbral (RF-130).
3. **El resultante es la mediana** y el umbral es 3 (RF-131). La mediana y no la
   media, porque con tres valores la media la arrastra el disidente.

El umbral y el minimo de palabras de la cita salen del perfil de extension de la
obra (D-128): `novela` los de siempre, 3 y 8; `prueba`, 2 y 5. La regla de
dispersion es la misma en los dos.

Una dimension con menos de tres puntuaciones ancladas es invalida igual que una
dispersa: no se puede medir la dispersion de lo que no hay, y una comprobacion
que no puede ejecutarse cuenta como fallida (`AGENTS.md` §5.3).
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from commons.types.length import NOVELA, LengthProfile
from commons.types.primitives import Defect, Evidence, Severity
from commons.types.rubrics import Dimension
from verification.checks import evidence
from verification.jury.prompts import InstanceVerdict

#: D-37. Tres es el minimo que mide dispersion.
INSTANCES = 3
#: D-39. Rango que invalida y umbral de aceptacion, sobre una escala de cinco.
INVALID_SPREAD = 2
#: El del perfil `novela`; cada veredicto lleva el de su perfil (D-128).
THRESHOLD = NOVELA.jury_threshold

#: CAL-06. Una dimension bajo umbral danana el arco o la caracterizacion (S2) o
#: el estilo y el ritmo (S3). D-94: `continuity`, `arc` y `personalization` S2,
#: donde CAL-06 dice arco o caracterizacion; `tone` S3, donde dice estilo.
SEVERITY: dict[Dimension, Severity] = {
    Dimension.VOICE: Severity.S2,
    Dimension.SUBTEXT: Severity.S2,
    Dimension.THEME: Severity.S2,
    Dimension.PACING: Severity.S3,
    Dimension.STYLE_GUIDE: Severity.S3,
    Dimension.CONTINUITY: Severity.S2,
    Dimension.ARC: Severity.S2,
    Dimension.PERSONALIZATION: Severity.S2,
    Dimension.TONE: Severity.S3,
}


class AnchoredScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    instance: str
    seed: int
    dimension: Dimension
    level: int
    scene: str
    evidence: Evidence
    #: RF-259. La de la puntuacion de la instancia, que llega entera a la traza.
    justification: str = Field(min_length=1)


class DimensionVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: Dimension
    scores: tuple[AnchoredScore, ...]
    spread: int = Field(ge=0)
    valid: bool
    level: int | None = Field(default=None, description="Mediana, solo si es valido")
    #: D-128. El umbral del perfil de la obra con que se juzgo.
    threshold: int = Field(default=THRESHOLD, ge=1, le=5)

    @property
    def passed(self) -> bool:
        return self.valid and self.level is not None and self.level >= self.threshold


class JuryVerdict(BaseModel):
    """CAL-11. El veredicto del Jurado sobre un capitulo."""

    model_config = ConfigDict(frozen=True)

    dimensions: tuple[DimensionVerdict, ...]
    discarded: tuple[tuple[str, str], ...] = Field(
        default_factory=tuple, description="(instancia, cita) que no anclo: defecto de proceso"
    )
    rounds: int = Field(default=1, ge=1)
    #: D-128. El umbral del perfil de la obra; el mismo en cada dimension.
    threshold: int = Field(default=THRESHOLD, ge=1, le=5)

    @property
    def passed(self) -> bool:
        return bool(self.dimensions) and all(d.passed for d in self.dimensions)

    def get(self, dimension: Dimension) -> DimensionVerdict | None:
        return next((d for d in self.dimensions if d.dimension is dimension), None)

    def defects(self) -> list[Defect]:
        """RF-132. Cada dimension bajo umbral es un defecto con su evidencia,
        la de la instancia que peor la puntuo: es lo que el Reparador necesita."""
        out: list[Defect] = []
        for d in self.dimensions:
            if d.passed:
                continue
            peor = min(d.scores, key=lambda s: s.level, default=None)
            if len(d.scores) < INSTANCES:
                motivo = f"solo {len(d.scores)} de {INSTANCES} puntuaciones con cita anclada"
            elif not d.valid:
                motivo = f"dispersion {d.spread} entre instancias tras repetir"
            else:
                motivo = f"nivel {d.level} de 5, por debajo de {d.threshold}"
            out.append(
                Defect(
                    kind=f"jury.{d.dimension.value}",
                    severity=SEVERITY[d.dimension],
                    evidence=peor.evidence if peor else Evidence(quote=d.dimension.value, offset=0),
                    rule=f"{d.dimension.value}: {motivo}",
                )
            )
        return out


def _locate(
    scene: str, quote: str, scene_texts: Mapping[str, str], *, min_words: int
) -> tuple[str, Evidence] | None:
    """Donde ancla la cita: en la escena que nombra, o en la unica que la contiene.

    La escena que nombra el juez es una pista, no la prueba: la prueba es la
    cita. El ritmo se juzga sobre el capitulo entero, y un juez que lo cita
    nombrando "el capitulo" o la escena vecina no ha inventado nada si la cita
    esta, literal y una sola vez, en una escena del capitulo. Es la misma regla
    del Continuista, que ancla contra el capitulo y deduce la escena (RF-110).
    Medido en la primera tirada real: el ritmo se quedo sin nivel en todas las
    rondas y era la unica dimension que les pasaba.
    """
    texto = scene_texts.get(scene, "")
    ev = evidence.anchor(texto, quote, min_words=min_words) if texto else None
    if ev is not None:
        return scene, ev
    halladas = [
        (sid, e)
        for sid, t in scene_texts.items()
        if sid != scene and (e := evidence.anchor(t, quote, min_words=min_words)) is not None
    ]
    return halladas[0] if len(halladas) == 1 else None


def unanchored(
    verdict: InstanceVerdict, scene_texts: Mapping[str, str], *, profile: LengthProfile = NOVELA
) -> list[str]:
    """D-71. Por cada puntuacion cuya cita no anclaria, el motivo, dicho al juez.

    Es lo que convierte el descarte en algo corregible: el juez sabe que cita
    fallo y por que, y le cuesta cero copiarla bien. El motivo es el mismo que
    aplicaria `anchor`, asi que corregirlo es anclar.
    """
    minimo = profile.quote_min_words
    out: list[str] = []
    for s in verdict.scores:
        if _locate(s.scene, s.quote, scene_texts, min_words=minimo) is not None:
            continue
        palabras = len(evidence.normalize(s.quote).split())
        if palabras < minimo:
            motivo = f"tiene {palabras} palabras y el minimo es {minimo}"
        elif "..." in s.quote or "\u2026" in s.quote:
            motivo = "recorta con puntos suspensivos: la cita tiene que ser un tramo seguido"
        elif any(evidence.occurrences(t, s.quote) > 1 for t in scene_texts.values()):
            motivo = "aparece mas de una vez: alargala hasta que sea unica"
        else:
            motivo = "no aparece literal en el capitulo: copiala caracter a caracter"
        out.append(f"- {s.dimension.value}: «{s.quote[:100]}» {motivo}")
    return out


def anchor(
    verdicts: Mapping[str, tuple[int, InstanceVerdict]],
    scene_texts: Mapping[str, str],
    *,
    profile: LengthProfile = NOVELA,
) -> tuple[list[AnchoredScore], list[tuple[str, str]]]:
    """RF-129. Cada puntuacion se ancla en una escena del capitulo, o se descarta,
    con el minimo de palabras de cita del perfil de la obra (D-128)."""
    validas: list[AnchoredScore] = []
    descartes: list[tuple[str, str]] = []
    for instancia, (semilla, veredicto) in sorted(verdicts.items()):
        vistas: set[Dimension] = set()
        for s in veredicto.scores:
            sitio = _locate(s.scene, s.quote, scene_texts, min_words=profile.quote_min_words)
            if sitio is None or s.dimension in vistas:
                descartes.append((instancia, s.quote))
                continue
            vistas.add(s.dimension)
            validas.append(
                AnchoredScore(
                    instance=instancia,
                    seed=semilla,
                    dimension=s.dimension,
                    level=s.level,
                    scene=sitio[0],
                    evidence=sitio[1],
                    justification=s.justification,
                )
            )
    return validas, descartes


def judge(
    scores: Sequence[AnchoredScore],
    *,
    dimensions: Sequence[Dimension] = tuple(Dimension),
    threshold: int = THRESHOLD,
) -> list[DimensionVerdict]:
    """RF-130, RF-131. Dispersion, validez y mediana por dimension, con el umbral
    del perfil de la obra (D-128)."""
    out: list[DimensionVerdict] = []
    for d in dimensions:
        propias = tuple(s for s in scores if s.dimension is d)
        niveles = [s.level for s in propias]
        rango = (max(niveles) - min(niveles)) if niveles else 0
        valido = len(niveles) >= INSTANCES and rango < INVALID_SPREAD
        out.append(
            DimensionVerdict(
                dimension=d,
                scores=propias,
                spread=rango,
                valid=valido,
                level=int(statistics.median(niveles)) if valido else None,
                threshold=threshold,
            )
        )
    return out


Run = Callable[[Sequence[int]], Mapping[str, tuple[int, InstanceVerdict]]]


def adjudicate(
    run: Run,
    scene_texts: Mapping[str, str],
    *,
    seeds: Sequence[int],
    dimensions: Sequence[Dimension] = tuple(Dimension),
    profile: LengthProfile = NOVELA,
) -> JuryVerdict:
    """El Jurado entero, con su segunda ronda (RF-130).

    `run` recibe las semillas y devuelve el veredicto de cada instancia. Si
    alguna dimension sale invalida, se repite **solo esa** con las semillas
    cambiadas; si vuelve a dispersar, queda invalida y cuenta como bajo umbral.
    Nunca hay tercera ronda: seria buscar el acuerdo hasta encontrarlo.

    `dimensions` son las del conjunto de rubricas que leyeron los jueces: un
    fichero de la version 1 se juzga en cinco, uno de la 2 en nueve (RF-257).

    `profile` es el perfil de extension de la obra: fija el umbral y el minimo
    de palabras de la cita (D-128).
    """
    umbral = profile.jury_threshold
    validas, descartes = anchor(run(seeds), scene_texts, profile=profile)
    dims = judge(validas, dimensions=dimensions, threshold=umbral)
    invalidas = [d.dimension for d in dims if not d.valid]
    if not invalidas:
        return JuryVerdict(dimensions=tuple(dims), discarded=tuple(descartes), threshold=umbral)

    otras = [s + 1_000 for s in seeds]
    validas2, descartes2 = anchor(run(otras), scene_texts, profile=profile)
    repetidas = {d.dimension: d for d in judge(validas2, dimensions=invalidas, threshold=umbral)}
    final = tuple(repetidas.get(d.dimension, d) for d in dims)
    return JuryVerdict(
        dimensions=final, discarded=tuple(descartes + descartes2), rounds=2, threshold=umbral
    )
