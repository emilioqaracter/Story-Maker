"""Las rubricas del Jurado (CAL-02), como datos.

RF-128, RNF-37, D-39. Viven en `commons/` porque las usan dos funcionalidades:
`canon/` las siembra en el fichero de la novela al crearla, como una version de
documento mas (RF-10), y `verification/` las lee para juzgar. Cambiar una
rubrica es un despliegue (RF-157), no una edicion del codigo del juez: por eso
el juez lee la version del fichero y no esta constante.

Cinco niveles con ejemplo cada uno, que es lo que hace que dos evaluadores
coincidan (CAL-02). El nivel 3 es "cumple" y es el umbral (D-39).

Version 2 (`specs/srs-backend-v4.md` RF-257, D-94): nueve dimensiones, las cinco
de la version 1 --con `voice` ampliada a la coherencia de la caracterizacion,
voz y decisiones-- y cuatro nuevas: `continuity` (la de lectura; la factual es
del Continuista), `tone`, `arc` y `personalization`. Un fichero creado con la
version 1 la sigue guardando y su Jurado sigue juzgando cinco: las dimensiones
las da el conjunto que lee el juez (`RubricSet.dimensions`), no este enumerado.
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
    CONTINUITY = "continuity"  # 1, la continuidad de lectura
    TONE = "tone"  # 5, frente al tono pedido (POE-04)
    ARC = "arc"  # 3, EST-06 y PER-06
    PERSONALIZATION = "personalization"  # 10, en su parte de juicio


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

    @property
    def dimensions(self) -> tuple[Dimension, ...]:
        """Las dimensiones de este conjunto, en su orden. Son las que se juzgan."""
        return tuple(r.dimension for r in self.rubrics)


DEFAULT_RUBRICS = RubricSet(
    version=2,
    rubrics=(
        Rubric(
            dimension=Dimension.VOICE,
            skill="voice.audit",
            question=(
                "¿Cada personaje es coherente consigo mismo: habla y piensa con su idiolecto, "
                "distinto del de los demas, y decide como decidiria el?"
            ),
            levels=(
                "Voces intercambiables, o un personaje decide lo contrario de lo que es sin motivo.",
                "Se distingue el narrador, pero los personajes suenan igual o deciden por la trama.",
                "Cada POV tiene marcas propias y decide segun su ficha; alguna linea queda neutra.",
                "Las voces se distinguen sin atribucion, y cada decision se explica por quien la toma.",
                "Cada linea y cada decision solo podrian ser de quien las tiene, y cambian con el.",
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
        Rubric(
            dimension=Dimension.CONTINUITY,
            skill="continuity.audit",
            question=(
                "¿El capitulo se lee como continuacion de lo anterior: transiciones, elipsis "
                "y ecos? No si los hechos cuadran, que eso lo comprueba el Continuista."
            ),
            levels=(
                "Se lee suelto: nada enlaza con lo anterior y el salto no se explica.",
                "Enlaza por los hechos, pero las transiciones chirrian o repiten lo ya contado.",
                "Se lee como continuacion; alguna elipsis se nota mas de lo que deberia.",
                "Las transiciones son limpias y las elipsis se entienden sin explicarlas.",
                "Retoma un eco de lo anterior que da sentido nuevo a lo que viene.",
            ),
        ),
        Rubric(
            dimension=Dimension.TONE,
            skill="tone.audit",
            question="¿El tono es el que pide el encargo y se sostiene en todo el capitulo?",
            levels=(
                "El tono contradice el pedido: grave donde se pidio ligero, o al reves.",
                "El tono pedido aparece a ratos y se pierde en otros pasajes.",
                "El tono es el pedido; algun pasaje se sale sin motivo dramatico.",
                "El tono pedido se sostiene y modula con la escena sin romperse.",
                "El tono pedido es la manera de mirar del capitulo, no un barniz.",
            ),
        ),
        Rubric(
            dimension=Dimension.ARC,
            skill="arc.audit",
            question="¿El capitulo hace avanzar los arcos que le tocaba mover?",
            levels=(
                "Ningun arco se mueve: el personaje y el conflicto acaban como empezaron.",
                "Algo cambia, pero por accidente de trama y no por el arco.",
                "El arco del capitulo avanza un paso reconocible; otro queda quieto.",
                "Los arcos avanzan y el paso se gana con lo que ocurre en escena.",
                "El avance del arco reordena lo anterior y hace inevitable lo siguiente.",
            ),
        ),
        Rubric(
            dimension=Dimension.PERSONALIZATION,
            skill="personalization.audit",
            question=(
                "¿El destinatario, sus rasgos y sus recuerdos aparecen integrados en la historia "
                "de forma natural, y no pegados?"
            ),
            levels=(
                "Los rasgos o recuerdos aparecen como lista o dedicatoria, fuera de la historia.",
                "Aparecen, pero forzados: la escena se detiene para colocarlos.",
                "Estan integrados; alguno se nota puesto para cumplir.",
                "Nacen de la escena: quitarlos cambiaria lo que pasa.",
                "Son el corazon de la escena sin que se note que alguien los pidio.",
            ),
        ),
    ),
)


def dumps(rubrics: RubricSet) -> str:
    return rubrics.model_dump_json()


def loads(body: str) -> RubricSet:
    return RubricSet.model_validate(json.loads(body))
