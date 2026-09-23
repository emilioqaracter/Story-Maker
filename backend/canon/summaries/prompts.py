"""Instruccion de `summarize.hierarchical`.

RF-90, RF-116, RF-117, CTX-06. `architecture.md` §4.5: los resumenes se generan
**al congelar**, nunca sobre la marcha, y cada nivel se construye desde el nivel
inferior, no desde el texto completo. Es lo que mantiene la memoria completa
dentro del techo cuando la novela pasa de 150.000 palabras.

La llamada la despacha el Orquestador; aqui vive lo que se le dice al modelo y
el tamano que se le exige en cada nivel.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum


class Level(StrEnum):
    SCENE = "scene"
    CHAPTER = "chapter"
    ARC = "arc"
    WORK = "work"


#: Palabras por nivel, de `architecture.md` §4.5. El de obra no lleva cifra en
#: palabras alli: §4.9 le da 500 tokens, que a 2 tokens por palabra son 250.
WORDS: dict[Level, tuple[int, int]] = {
    Level.SCENE: (60, 100),
    Level.CHAPTER: (150, 250),
    Level.ARC: (300, 300),
    Level.WORK: (250, 250),
}

#: De que nivel se construye cada uno. Nunca del texto completo.
BUILT_FROM: dict[Level, Level | None] = {
    Level.SCENE: None,
    Level.CHAPTER: Level.SCENE,
    Level.ARC: Level.CHAPTER,
    Level.WORK: Level.ARC,
}

SYSTEM = """Resumes partes de una novela para la memoria de un sistema automatico.
No conversas, no valoras, no anades nada que no este en lo que recibes.

REGLAS QUE NO SE NEGOCIAN

1. Solo hechos y cambios: quien, que, donde, cuando, y que cambio entre el
   principio y el final. Nada de adjetivos de valoracion ni de estilo.
2. Nombres canonicos, nunca pronombres ambiguos. Quien lee el resumen no tiene
   el texto delante.
3. La longitud pedida es un rango cerrado. Ni una palabra fuera.
4. Un resumen de nivel superior se construye SOLO desde los resumenes del nivel
   inferior que se te dan. No inventes lo que ellos no dicen.
5. Tercera persona, tiempo pasado, sin dialogo.

Devuelves SOLO el resumen, sin titulo ni notas."""


def instruction(level: Level, parts: Sequence[str], *, value_change: str | None = None) -> str:
    """La parte que cambia: que se resume y a que tamano."""
    low, high = WORDS[level]
    rango = f"exactamente {low}" if low == high else f"entre {low} y {high}"
    que = {
        Level.SCENE: "esta escena",
        Level.CHAPTER: "este capitulo, a partir de los resumenes de sus escenas",
        Level.ARC: "este arco, a partir de los resumenes de sus capitulos",
        Level.WORK: "la obra hasta aqui, a partir de los resumenes de arco y de capitulo",
    }[level]
    cambio = f"\nCAMBIO DE VALOR DECLARADO: {value_change}" if value_change else ""
    cuerpo = "\n\n".join(parts)
    return f"""Resume {que} en {rango} palabras.{cambio}

TEXTO:

{cuerpo}"""
