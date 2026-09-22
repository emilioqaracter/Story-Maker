"""Serializacion y comparacion de vectores.

Vive en `commons/` porque **cruza funcionalidades**: `canon/` los empaqueta al
escribir el indice y `context/` los desempaqueta al puntuar la pierna semantica.
Mientras estuvo en `context/`, `canon/` tenia que importar de un piso superior,
que es lo que la regla de los tres pisos prohibe.

Es la segunda vez que pasa lo mismo en este backend --antes con la
especificacion de escena-- y la leccion se repite: cuando dos funcionalidades
necesitan lo mismo, el sitio no es ninguna de las dos.
"""

from __future__ import annotations

import math
import struct
from collections.abc import Sequence


def pack_vector(values: Sequence[float]) -> bytes:
    """Serializa un vector para guardarlo en la base."""
    return struct.pack(f"<{len(values)}f", *values)


def unpack_vector(blob: bytes) -> tuple[float, ...]:
    return struct.unpack(f"<{len(blob) // 4}f", blob)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Similitud de coseno, en Python.

    Sin extension nativa (D-12): una obra da 600 a 1.200 fragmentos, y la
    recuperacion filtra antes por metadatos, asi que el conjunto a puntuar es
    todavia menor. Sobre esas cifras el recorrido exhaustivo es exacto e
    inmediato, y un indice aproximado solo anadiria error.
    """
    num = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0 or nb == 0 else num / (na * nb)
