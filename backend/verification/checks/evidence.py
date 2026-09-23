"""`check.evidence`. La cita de un veredicto existe de verdad.

RF-110, RF-111, RI-19. `verification.md` §5.11. Hoy "sin cita no hay defecto"
seria una instruccion de prompt, y una instruccion de prompt la cumple
formalmente cualquier modelo inventandose la cita. Esto la comprueba.

La regla de coincidencia es literal y estricta a proposito:

- La cita se **normaliza** --espacios, comillas tipograficas, guiones de dialogo,
  mayusculas, la barra con que un juez marca el salto de parrafo y los puntos
  suspensivos tipograficos-- y nada mas. Ni lematizacion ni coincidencia difusa.
  La barra y los puntos son forma de copiar, no de leer: medido en la primera
  tirada real, un juez unia dos parrafos con " / " y la cita, literal por lo
  demas, se descartaba.
- Tiene **ocho palabras o mas**. Dos n-gramas de cuatro localizan sin
  ambiguedad; menos, y la cita podria estar en cualquier sitio.
- Aparece **exactamente una vez** en la escena citada. Si aparece dos, no es
  una posicion, y el Reparador no sabria donde tocar; el juez la alarga, que le
  cuesta cero.

Lo que devuelve es una posicion en el texto **original**, no en el normalizado:
es lo que el Reparador recibe.
"""

from __future__ import annotations

import re
import unicodedata

from commons.types.primitives import Evidence

#: Minimo de palabras de una cita valida. `verification.md` §5.11: dos n-gramas
#: de cuatro, la unidad que `check.repetition` ya trata como detectable.
MIN_QUOTE_WORDS = 8

_QUOTES = dict.fromkeys("«»“”„‟‹›\"'‘’‚‛", " ")  # noqa: RUF001
_DASHES = dict.fromkeys("—–‒―-", " ")  # noqa: RUF001
_BREAKS = {"/": " ", "…": "..."}
_TABLE = str.maketrans({**_QUOTES, **_DASHES, **_BREAKS})


def _normalized_with_map(text: str) -> tuple[str, list[int]]:
    """Texto normalizado y, por cada caracter suyo, el indice en el original.

    Normalizar sin el mapa daria una posicion en un texto que no existe. El
    Reparador trabaja sobre el original, asi que la posicion tiene que ser suya.
    """
    out: list[str] = []
    positions: list[int] = []
    last_space = True
    for i, ch in enumerate(text):
        c = ch.translate(_TABLE).lower()
        c = unicodedata.normalize("NFD", c)
        c = "".join(x for x in c if unicodedata.category(x) != "Mn")
        if not c:
            continue
        if c.isspace():
            if last_space:
                continue
            out.append(" ")
            positions.append(i)
            last_space = True
            continue
        for x in c:
            out.append(x)
            positions.append(i)
        last_space = False
    return "".join(out).strip(), positions


def normalize(text: str) -> str:
    return _normalized_with_map(text)[0]


def anchor(text: str, quote: str) -> Evidence | None:
    """La cita anclada en `text`, o `None` si no ancla.

    `None` significa que el veredicto se descarta sin evaluarlo y se anota como
    defecto de proceso de quien lo emitio, nunca como defecto del texto.
    """
    q = normalize(quote)
    if len(q.split()) < MIN_QUOTE_WORDS:
        return None

    t, positions = _normalized_with_map(text)
    # Cuenta de apariciones sin solapamiento entre ellas: dos es ya ambiguo.
    first = t.find(q)
    if first < 0:
        return None
    if t.find(q, first + 1) >= 0:
        return None

    start = positions[first] if first < len(positions) else 0
    end_norm = first + len(q) - 1
    end = positions[end_norm] + 1 if end_norm < len(positions) else len(text)
    return Evidence(quote=text[start:end], offset=start)


def occurrences(text: str, quote: str) -> int:
    """Cuantas veces aparece la cita normalizada. Para diagnosticar un descarte."""
    q = normalize(quote)
    if not q:
        return 0
    t = normalize(text)
    return len(re.findall(re.escape(q), t))
