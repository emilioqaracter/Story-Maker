"""Ajustes del proceso.

Vive en `commons/` porque lo usan varias funcionalidades: `canon/` para saber
donde esta el fichero de una novela, `orchestration/` para el directorio de la
tirada, `commons/tracing` para la cola local.

Un solo sitio donde se resuelve una ruta. Si cada funcionalidad compusiera la
suya, el dia que cambie el directorio de tiradas habria que buscarlo en cinco
carpetas y alguna se quedaria atras.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

#: Un identificador de novela acaba siendo un nombre de fichero, asi que se
#: acota a lo que no puede salirse del directorio: sin barras, sin puntos, sin
#: nada que `..` pueda aprovechar.
NOVEL_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{2,63}$"
NOVEL_ID = re.compile(NOVEL_ID_PATTERN)


class InvalidNovelIdError(ValueError):
    """El identificador no sirve como nombre de fichero de forma segura."""


@dataclass(frozen=True)
class Settings:
    runs_dir: Path

    @classmethod
    def from_env(cls) -> Settings:
        raw = os.environ.get("STORY_MAKER_RUNS", "")
        return cls(runs_dir=Path(raw) if raw else Path.cwd() / "runs")

    def novel_path(self, novel_id: str) -> Path:
        """Ruta del fichero de una novela.

        Valida el identificador aqui y no en cada ruta HTTP: es el unico punto
        por el que un nombre llega a tocar el sistema de ficheros, y validar en
        el borde de entrada deja la puerta abierta a que una via nueva se salte
        la comprobacion.
        """
        if not NOVEL_ID.match(novel_id):
            raise InvalidNovelIdError(
                f"identificador de novela invalido: {novel_id!r}. "
                "Minusculas, digitos y guiones, entre 3 y 64 caracteres"
            )
        return self.runs_dir / f"{novel_id}.sqlite"
