"""El canon resuelto a la fecha de una escena, en prosa.

Atajo de `run_scene.py contexto`. Existe porque la skill resolver-canon se
invoca sola mucho mas a menudo que el resto del ciclo.

    python harness/scripts/resolver_canon.py books/<slug> S001
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Libro
from run_scene import contexto


def main(argv):
    if len(argv) < 3:
        print("uso: resolver_canon.py books/<slug> <SID>", file=sys.stderr)
        return 2
    print(contexto(Libro(argv[1]), argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
