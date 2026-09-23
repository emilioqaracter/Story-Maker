"""Las rubricas del Jurado (CAL-02), como datos.

RF-128, RNF-37, D-39. Viven en `commons/` porque las usan dos funcionalidades:
`canon/` las siembra en el fichero de la novela al crearla, como una version de
documento mas (RF-10), y `verification/` las lee para juzgar. Cambiar una
rubrica es un despliegue (RF-157), no una edicion del codigo del juez: por eso
el juez lee la version del fichero y no esta constante.

Cinco niveles con ejemplo cada uno, que es lo que hace que dos evaluadores
coincidan (CAL-02). El nivel 3 es "cumple" y es el umbral (D-39).
"""

from __future__ import annotations

import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Dimension(StrEnum):
    """Las dimensiones de CAL-01 que `definitions.md` asigna a juez (RF-128)."""

    VOICE = "voice"  # 2, en su parte no determinista
    STYLE_GUIDE = "style_guide"  # 5, en su parte no determinista
    PACING = "pacing"  # 4
    SUBTEXT = "subtext"  # 8
    THEME = "theme"  # 9


class Rubric(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: Dimension
    skill: str = Field(description="La skill de §5.2 que la aplica")
    question: str
    levels: tuple[str, str, str, str, str] = Field(description="Del 1 al 5, con su ejemplo")


class RubricSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: int = Field(ge=1)
    rubrics: tuple[Rubric, ...]

    def get(self, dimension: Dimension) -> Rubric:
        return next(r for r in self.rubrics if r.dimension is dimension)


DEFAULT_RUBRICS = RubricSet(
    version=1,
    rubrics=(
        Rubric(
            dimension=Dimension.VOICE,
            skill="voice.audit",
            question="¿Cada personaje habla y piensa con su idiolecto, distinto del de los demas?",
            levels=(
                "Las voces son intercambiables: cualquier linea podria decirla cualquiera.",
                "Se distingue el narrador de los personajes, pero los personajes suenan igual entre si.",
                "Cada POV tiene marcas propias reconocibles; hay alguna linea neutra que no las lleva.",
                "Las voces se distinguen sin atribucion; el idiolecto se sostiene en toda la escena.",
                "Cada linea solo podria ser de quien la dice, y la voz cambia cuando el personaje cambia.",
            ),
        ),
        Rubric(
            dimension=Dimension.STYLE_GUIDE,
            skill="voice.audit",
            question="¿El texto cumple la guia de estilo de la obra en lo que no se cuenta con codigo?",
            levels=(
                "Ignora la guia: valoraciones, cliches y registro contrarios en casi todos los parrafos.",
                "Cumple la letra en algunos pasajes y la contradice en otros.",
                "Cumple la guia; alguna frase se le escapa hacia el cliche o la valoracion.",
                "Cumple la guia en todo el capitulo sin que se note el esfuerzo.",
                "La guia esta interiorizada: el capitulo podria servir de ejemplo de ella.",
            ),
        ),
        Rubric(
            dimension=Dimension.PACING,
            skill="pacing.audit",
            question="¿El capitulo sostiene la tension y cada escena cambia un valor?",
            levels=(
                "Nada cambia: escenas que repiten el estado inicial o lo resumen.",
                "Hay cambio, pero se cuenta en vez de mostrarse, o llega sin preparacion.",
                "Cada escena cambia su valor declarado; hay algun tramo que se estanca.",
                "El ritmo acompana al cambio: se acelera y se detiene donde la escena lo pide.",
                "Cada parrafo empuja; el cierre obliga a seguir leyendo.",
            ),
        ),
        Rubric(
            dimension=Dimension.SUBTEXT,
            skill="subtext.audit",
            question="¿El dialogo dice mas de lo que dice, o lo explica todo?",
            levels=(
                "Los personajes enuncian lo que sienten y lo que quieren, literalmente.",
                "Hay alguna intencion oculta, pero el narrador la explica despues.",
                "El dialogo lleva intenciones que no se nombran; alguna se subraya de mas.",
                "Lo importante se dice por omision o por desvio, y el lector lo entiende.",
                "Cada intercambio tiene una capa que solo se lee al terminar la escena.",
            ),
        ),
        Rubric(
            dimension=Dimension.THEME,
            skill="theme.audit",
            question="¿El capitulo trabaja los motivos de la obra sin anunciarlos?",
            levels=(
                "No hay motivo reconocible, o se enuncia como moraleja.",
                "El motivo aparece, pero decorativo, sin relacion con lo que pasa.",
                "El motivo acompana a la accion; en algun momento se explica de mas.",
                "La accion y el motivo son lo mismo: lo que pasa es lo que significa.",
                "El capitulo resignifica un motivo anterior sin nombrarlo.",
            ),
        ),
    ),
)


def dumps(rubrics: RubricSet) -> str:
    return rubrics.model_dump_json()


def loads(body: str) -> RubricSet:
    return RubricSet.model_validate(json.loads(body))
