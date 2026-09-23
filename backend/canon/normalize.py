"""La normalizacion de palabras, una sola para todo el backend.

RF-237, D-90. `architecture.md` §9.1. La usan el guardarrail de prohibidas
(`verification/checks/forbidden.py`) y las reglas del brief (RF-247), y por eso
vive en `canon/`: es el unico sitio del que las dos pueden importar sin romper
los tres pisos de `architecture.md` §2.3 --`canon/` no importa de
`verification/`--.

Tres reglas, y ninguna necesita un modelo:

- **Se compara texto normalizado**: descomposicion NFKD, `casefold` y sin marcas
  combinantes. «Cabrón», «CABRON» y «cabron» son la misma palabra.
- **Por palabra completa, nunca por subcadena.** «mar» no casa en «Marcos» ni en
  «amar». La subcadena hacia saltar el guardarrail en prosa correcta.
- **Con las variantes simples del termino**: `+s`, `+es`, `z` final a `ces`, y
  `o` final a `a` y al reves. «luz» casa en «luces». Un termino de varias
  palabras se busca como secuencia de palabras, con las variantes en cada una.

Lo que no hace, a proposito: lematizar. Un lematizador es una dependencia
pesada con falsos positivos propios, y las variantes simples cubren el caso
(`specs/srs-backend-v4.md` §8, fuera de alcance).

Consecuencia de quitar las marcas que conviene saber: la «ñ» pierde la tilde,
asi que «año» y «ano» normalizan igual. Es el precio de que «cabrón» y «cabron»
sean la misma palabra, y es el mismo en el termino que en el texto.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

#: Una palabra: letras y cifras, con las marcas combinantes que traiga un texto
#: ya descompuesto (U+0300 a U+036F). El guion bajo no es letra: separa.
_WORD = re.compile(r"(?:[^\W_]|[\u0300-\u036f])+")


def normalize(text: str) -> str:
    """NFKD, `casefold` y sin marcas combinantes (RF-237).

    Es la funcion publica que comparten el guardarrail y las reglas del brief.
    No parte en palabras ni quita puntuacion: solo pliega mayusculas, tildes y
    formas de compatibilidad («ﬁ» a «fi»).
    """
    descompuesto = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


@dataclass(frozen=True)
class Token:
    """Una palabra del texto, normalizada, con su posicion en el original."""

    norm: str
    start: int
    end: int


@dataclass(frozen=True)
class Occurrence:
    """Una aparicion de un termino: el fragmento literal y donde empieza."""

    quote: str
    offset: int


def tokens(text: str) -> list[Token]:
    """Las palabras del texto, normalizadas una a una.

    Se parte **antes** de normalizar para que la posicion sea la del texto
    original: la cita de un defecto tiene que poder localizarse en lo que el
    Reparador recibe, no en una version plegada que nadie lee.
    """
    out: list[Token] = []
    for m in _WORD.finditer(text):
        norm = normalize(m.group(0))
        if norm:
            out.append(Token(norm=norm, start=m.start(), end=m.end()))
    return out


def words(term: str) -> tuple[str, ...]:
    """El termino como secuencia de palabras normalizadas."""
    return tuple(t.norm for t in tokens(term))


def key(term: str) -> str:
    """La identidad de un termino: dos terminos con la misma clave son el mismo.

    «Cabrón» y «cabron» dan la misma clave; es lo que decide, al guardar, si un
    termino ya esta en otro nivel (D-91).
    """
    return " ".join(words(term))


def variants(word: str) -> frozenset[str]:
    """Las variantes simples de una palabra ya normalizada (D-90).

    Exactamente las declaradas: la palabra, `+s`, `+es`, `z` final a `ces`, y
    `o` final a `a` y al reves. Ninguna mas: cada variante nueva es una fuente
    nueva de falsos positivos, y se decide en la spec, no aqui.
    """
    if not word:
        return frozenset()
    out = {word, word + "s", word + "es"}
    if word.endswith("z"):
        out.add(word[:-1] + "ces")
    if word.endswith("o"):
        out.add(word[:-1] + "a")
    elif word.endswith("a"):
        out.add(word[:-1] + "o")
    return frozenset(out)


def pattern(term: str) -> tuple[frozenset[str], ...]:
    """Lo que tiene que casar en cada posicion para que el termino aparezca."""
    return tuple(variants(w) for w in words(term))


def scan(text: str, toks: Sequence[Token], pat: Sequence[frozenset[str]]) -> list[Occurrence]:
    """Las apariciones de un patron sobre un texto ya partido en palabras.

    Separada de `occurrences` para partir el texto una sola vez cuando se
    buscan muchos terminos en el mismo texto.
    """
    k = len(pat)
    if k == 0:
        return []
    out: list[Occurrence] = []
    for i in range(len(toks) - k + 1):
        if all(toks[i + j].norm in pat[j] for j in range(k)):
            inicio, fin = toks[i].start, toks[i + k - 1].end
            out.append(Occurrence(quote=text[inicio:fin], offset=inicio))
    return out


def occurrences(text: str, term: str) -> list[Occurrence]:
    """Cada aparicion de `term` en `text`, por palabra completa y con variantes.

    Es la funcion de coincidencia publica: la usa el guardarrail y la pueden
    usar las reglas del brief (RF-247) para decir si una palabra esta en un
    campo.
    """
    return scan(text, tokens(text), pattern(term))


def contains(text: str, term: str) -> bool:
    """Si `term` aparece en `text` con las reglas de `occurrences`."""
    return bool(occurrences(text, term))
