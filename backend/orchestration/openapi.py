"""El esquema OpenAPI, versionado en el repositorio (RI-08).

Es la unica fuente del contrato entre las dos mitades (`architecture.md` 2.2):
el cliente del frontend se genera desde este fichero (RI-54), no desde un
servidor en marcha. Por eso tiene que estar en el repositorio y coincidir
siempre con lo que la aplicacion genera, y la puerta lo comprueba.

    python -m orchestration.openapi           # reescribe backend/openapi.json
    python -m orchestration.openapi --check   # falla si difiere
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from orchestration.app import create_app

TARGET = Path(__file__).resolve().parent.parent / "openapi.json"


def render() -> str:
    """El esquema con orden de claves estable: un diff solo si cambia el contrato."""
    return json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="falla si el fichero difiere")
    args = parser.parse_args(argv)
    fresh = render()
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != fresh:
            sys.stdout.write(
                "backend/openapi.json no coincide con la aplicacion: "
                "python -m orchestration.openapi\n"
            )
            return 1
        return 0
    TARGET.write_text(fresh, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
