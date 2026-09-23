"""Que entra en la lista de proscripcion al congelar.

RF-49, RF-108, POE-12. `architecture.md` §4.6: todo n-grama de cuatro o mas
usado **dos veces** entra en la lista. La detecta este modulo y la **inserta la
congelacion**, en su transaccion, nunca el verificador que opera sobre
borradores.

Se cuenta sobre el capitulo aprobado mas la prosa ya congelada: un n-grama que
aparece una vez aqui y una vez en el capitulo 3 ya se ha usado dos veces en la
obra, y es el que el Escritor va a repetir una tercera si nadie lo veta.

Los n-gramas hechos solo de palabras funcionales no se proscriben: vetar "de la
que se" haria imposible escribir en espanol, y no es una imagen que se recicle
sino la gramatica.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence

#: Tamano del n-grama detectable. El mismo que `check.repetition`: dos de ellos
#: localizan sin ambiguedad, y es la unidad que `verification.md` §5.11 ya usa.
NGRAM = 4

#: Palabras funcionales del espanol. Un n-grama hecho solo de estas no es una
#: imagen ni una construccion propia: es la lengua, y no se veta.
_FUNCTION_WORDS = frozenset(
    [
        "a",
        "al",
        "ante",
        "bajo",
        "con",
        "contra",
        "de",
        "del",
        "desde",
        "durante",
        "en",
        "entre",
        "hacia",
        "hasta",
        "mediante",
        "para",
        "por",
        "segun",
        "sin",
        "sobre",
        "tras",
        "y",
        "e",
        "o",
        "u",
        "ni",
        "que",
        "como",
        "cuando",
        "donde",
        "mientras",
        "si",
        "pero",
        "sino",
        "aunque",
        "porque",
        "pues",
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "lo",
        "le",
        "les",
        "se",
        "me",
        "te",
        "nos",
        "os",
        "mi",
        "tu",
        "su",
        "mis",
        "tus",
        "sus",
        "este",
        "esta",
        "estos",
        "estas",
        "ese",
        "esa",
        "esos",
        "esas",
        "aquel",
        "aquella",
        "aquellos",
        "aquellas",
        "eso",
        "esto",
        "aquello",
        "yo",
        "el",
        "ella",
        "ellos",
        "ellas",
        "nosotros",
        "vosotros",
        "usted",
        "ustedes",
        "es",
        "era",
        "fue",
        "son",
        "eran",
        "fueron",
        "ser",
        "estar",
        "esta",
        "estaba",
        "estuvo",
        "estan",
        "estaban",
        "ha",
        "habia",
        "hubo",
        "han",
        "habian",
        "hay",
        "he",
        "has",
        "hemos",
        "habeis",
        "muy",
        "mas",
        "menos",
        "tan",
        "tanto",
        "tambien",
        "tampoco",
        "ya",
        "aun",
        "no",
    ]
)


def _normalize(word: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", word.lower())
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")


def ngrams(text: str, *, n: int = NGRAM) -> list[str]:
    palabras = [_normalize(w) for w in re.findall(r"\w+", text)]
    return [" ".join(palabras[i : i + n]) for i in range(len(palabras) - n + 1)]


def _is_only_function_words(ngram: str) -> bool:
    return all(w in _FUNCTION_WORDS for w in ngram.split())


def repeated_ngrams(
    chapter_texts: Sequence[str],
    *,
    frozen_texts: Sequence[str] = (),
    n: int = NGRAM,
) -> tuple[tuple[str, str], ...]:
    """Pares `(termino, 'ngram')` que este capitulo hace repetidos.

    Determinista y ordenado: la misma prosa da la misma lista, en el mismo
    orden, que es lo que permite comprobarlo con propiedades.
    """
    en_capitulo: Counter[str] = Counter()
    for texto in chapter_texts:
        en_capitulo.update(ngrams(texto, n=n))

    congelados: Counter[str] = Counter()
    for texto in frozen_texts:
        congelados.update(ngrams(texto, n=n))

    out = [
        (ngram, "ngram")
        for ngram, veces in en_capitulo.items()
        if veces + congelados.get(ngram, 0) >= 2 and not _is_only_function_words(ngram)
    ]
    out.sort()
    return tuple(out)
