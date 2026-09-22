"""`prose.chunk`. Troceado de una escena congelada.

RF-69, RF-70, RD-16. Por **parrafos completos** hasta 450 tokens, con un parrafo
de solape con el anterior.

Tres decisiones, y las tres tienen consecuencias:

1. **Por parrafos y no por bloques de N tokens.** Un corte ciego parte una frase
   por la mitad, y el fragmento recuperado llega al paquete sin principio ni
   final. Cortar por parrafo cuesta un poco de desigualdad de tamano y compra
   que todo fragmento sea legible por si solo.
2. **Con un parrafo de solape.** Sin el, una idea que cruza la frontera entre
   dos fragmentos no se encuentra desde ninguno de los dos.
3. **Nunca cruza la frontera de su escena.** Es lo que permite que el fragmento
   herede los metadatos de la suya por clave ajena y que el filtro por metadatos
   siga aplicandose exacto sobre fragmentos.

**Determinista**: la misma escena produce siempre los mismos cortes. Sin eso,
reindexar cambiaria los identificadores de fragmento y las trazas que los citan
dejarian de apuntar a nada.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

#: RF-69. Tope por fragmento. Sale del presupuesto del bloque de recuperacion:
#: 3.000 tokens para 4 a 6 fragmentos, asi que cada uno cabe en 500 contando su
#: cabecera de procedencia.
MAX_CHUNK_TOKENS = 450

#: Aproximacion de tokens por caracter para el corte. No usa el contador real a
#: proposito: el troceado tiene que ser determinista y offline, y aqui un error
#: del 20 % solo mueve la frontera de un parrafo, no rompe ningun techo.
CHARS_PER_TOKEN = 4

_PARAGRAPH = re.compile(r"\n\s*\n")


class Chunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    scene_id: str
    ordinal: int = Field(ge=1)
    text: str = Field(min_length=1)

    @property
    def approx_tokens(self) -> int:
        return max(1, len(self.text) // CHARS_PER_TOKEN)


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in _PARAGRAPH.split(text.strip()) if p.strip()]


def chunk_scene(scene_id: str, text: str, *, max_tokens: int = MAX_CHUNK_TOKENS) -> list[Chunk]:
    """Trocea una escena. Determinista.

    El identificador sale del contenido y no de un contador: asi dos
    reindexaciones de la misma escena producen los mismos identificadores y una
    traza vieja sigue apuntando al mismo sitio.
    """
    parrafos = paragraphs(text)
    if not parrafos:
        return []

    limite = max_tokens * CHARS_PER_TOKEN
    grupos: list[list[str]] = []
    actual: list[str] = []

    for parrafo in parrafos:
        cabe = sum(len(p) for p in actual) + len(parrafo) <= limite
        if actual and not cabe:
            grupos.append(actual)
            # El solape: el ultimo parrafo del grupo anterior abre el siguiente,
            # para que una idea a caballo entre dos se encuentre desde los dos.
            actual = [actual[-1]]
        actual.append(parrafo)

    if actual:
        grupos.append(actual)

    return [
        Chunk(
            id=_chunk_id(scene_id, i, "\n\n".join(g)),
            scene_id=scene_id,
            ordinal=i + 1,
            text="\n\n".join(g),
        )
        for i, g in enumerate(grupos)
    ]


def _chunk_id(scene_id: str, ordinal: int, text: str) -> str:
    firma = hashlib.sha256(f"{scene_id}|{ordinal}|{text}".encode()).hexdigest()[:16]
    return f"{scene_id}-{ordinal:03d}-{firma}"


def contained_in(chunks: Sequence[Chunk], scene_text: str) -> bool:
    """RD-16. Todo fragmento esta contenido en el texto de su escena.

    Se comprueba normalizando espacios: el troceado junta parrafos con dos
    saltos y el original puede traer mas, y eso no es que el texto cambie.
    """
    plano = " ".join(scene_text.split())
    return all(" ".join(c.text.split()) in plano for c in chunks)
