# -*- coding: utf-8 -*-
"""Corre TODO el harness de punta a punta y explica que va pasando.

    python demo.py

Se puede correr las veces que quieras: resetea el estado al empezar.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# La consola de Windows viene en cp1252 y se come los acentos.
for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8")
    except Exception:
        pass

RAIZ = Path(__file__).resolve().parent
SCRIPTS = RAIZ / "harness" / "scripts"
BUENO = "books/marco-1990"
MALO = "books/prueba-mala"

sys.path.insert(0, str(SCRIPTS))
import yaml  # noqa: E402

# Los subprocesos tambien tienen que hablar utf-8.
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


# --------------------------------------------------------------------------- #
def titulo(texto: str) -> None:
    print("\n" + "=" * 72)
    print("  " + texto)
    print("=" * 72)


def paso(texto: str) -> None:
    print("\n--- %s" % texto)


def correr(script: str, *args) -> dict:
    """Corre un script del harness y devuelve su JSON."""
    cmd = [sys.executable, str(SCRIPTS / script), *args]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=RAIZ, env=ENTORNO)
    print("  $ python harness/scripts/%s %s" % (script, " ".join(args)))
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        print(r.stdout or r.stderr)
        return {}


def resetear() -> None:
    """Deja los dos libros como recien planificados."""
    for libro in (BUENO, MALO):
        p = RAIZ / libro / "context" / "timeline.yaml"
        t = yaml.safe_load(p.read_text(encoding="utf-8"))
        t["escenas"][0]["estado"] = "planificada"
        t["escenas"][0].pop("palabras", None)
        p.write_text(yaml.safe_dump(t, allow_unicode=True, sort_keys=False), encoding="utf-8")
        for f in ("state.json", "manuscript/novela.md", "reports/final.json"):
            (RAIZ / libro / f).unlink(missing_ok=True)


def mostrar_escena(libro: str) -> None:
    texto = (RAIZ / libro / "manuscript" / "ch01" / "S001.md").read_text(encoding="utf-8")
    for linea in texto.strip().split("\n"):
        print("  | " + linea if linea.strip() else "  |")


# --------------------------------------------------------------------------- #
def main() -> int:
    resetear()

    titulo("1. LOS TESTS  -  47 escenas-trampa, sin red ni tokens")
    r = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=RAIZ, env=ENTORNO)
    print("  $ python -m pytest tests -q")
    print("  " + (r.stdout.strip().split("\n")[-1] if r.stdout else "pytest no instalado"))

    # ----------------------------------------------------------------- #
    titulo("2. LA ESCENA BUENA  -  tiene que llegar hasta el entregable")

    paso("La escena, tal como esta escrita:")
    mostrar_escena(BUENO)

    paso("El canon que recibe el escritor, ya resuelto a la fecha (nadie lee YAML):")
    cmd = [sys.executable, str(SCRIPTS / "resolver_canon.py"), BUENO, "S001"]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", cwd=RAIZ, env=ENTORNO).stdout
    for linea in out.strip().split("\n")[:8]:
        print("  | " + linea)
    print("  | ...")

    paso("G0 - el canon")
    d = correr("validate_canon.py", BUENO)
    print("  -> abre: %s | techo: %s palabras" % (d.get("ok"), d.get("forma", {}).get("techo_palabras")))

    paso("G1 - los hechos (script, 21 reglas, coste cero)")
    d = correr("validate_scene.py", BUENO, "S001")
    print("  -> abre: %s | %s palabras, %s parrafos" % (d.get("ok"), d.get("palabras"), d.get("parrafos")))

    paso("G2 - el criterio (lee la rubrica que escribieron los criticos)")
    d = correr("gate_scene.py", BUENO, "S001")
    print("  -> abre: %s | rubrica %s/%s (umbral %s) | veto: %s"
          % (d.get("ok"), d.get("suma"), d.get("maximo"), d.get("umbral"), d.get("veto_continuidad")))
    for dim, nota in (d.get("dimensiones") or {}).items():
        print("     %-11s %s" % (dim, nota))

    paso("Aprobar la escena")
    d = correr("run_scene.py", BUENO, "aprobar", "S001")
    print("  -> aprobada: %s | %s palabras | el final cabe: %s"
          % (d.get("ok"), d.get("palabras"), (d.get("regulador") or {}).get("cabe")))
    if d.get("puerta_G3"):
        print("  -> G3 (la unica puerta humana): %s" % d["puerta_G3"])

    paso("G4 - la obra: las tres condiciones del final")
    d = correr("validate_book.py", BUENO)
    for k, v in (d.get("condiciones") or {}).items():
        print("     %-15s %s" % (k, v["ok"]))
    print("  -> TERMINA: %s" % d.get("termina"))

    paso("Compilar el entregable")
    d = correr("compilar.py", BUENO)
    print("  -> %s | %s palabras" % (d.get("ruta"), d.get("palabras")))

    # ----------------------------------------------------------------- #
    titulo("3. LA ESCENA MALA  -  tiene que quedar bloqueada")

    paso("La escena, tal como esta escrita:")
    mostrar_escena(MALO)

    paso("G1 - los hechos")
    d = correr("validate_scene.py", MALO, "S001")
    print("  -> abre: %s   <-- ojo: ABRE. No tiene errores de hecho." % d.get("ok"))
    print("     3 parrafos, 4 lineas, fecha correcta, cero anacronismos.")
    print("     Es factualmente impecable y esta muerta. Para eso existe G2.")

    paso("G2 - el criterio")
    d = correr("gate_scene.py", MALO, "S001")
    print("  -> abre: %s | rubrica %s/%s (umbral %s) | veto: %s"
          % (d.get("ok"), d.get("suma"), d.get("maximo"), d.get("umbral"), d.get("veto_continuidad")))
    for dim, nota in (d.get("dimensiones") or {}).items():
        print("     %-11s %s" % (dim, nota))
    print("  -> %d errores. Los tres primeros:" % len(d.get("errores") or []))
    for e in (d.get("errores") or [])[:3]:
        print("     * %s" % e["mensaje"][:88])

    paso("Intentar aprobarla igual")
    d = correr("run_scene.py", MALO, "aprobar", "S001")
    print("  -> aprobada: %s | la frena: %s" % (d.get("ok"), d.get("puerta")))

    paso("Y no dejo rastro:")
    t = yaml.safe_load((RAIZ / MALO / "context" / "timeline.yaml").read_text(encoding="utf-8"))
    print("     estado de la escena: %s" % t["escenas"][0]["estado"])
    print("     state.json:  %s" % (RAIZ / MALO / "state.json").exists())
    print("     novela.md:   %s" % (RAIZ / MALO / "manuscript" / "novela.md").exists())

    # ----------------------------------------------------------------- #
    titulo("4. EL ENTREGABLE")
    novela = RAIZ / BUENO / "manuscript" / "novela.md"
    print()
    for linea in novela.read_text(encoding="utf-8").strip().split("\n"):
        print("  " + linea)
    print("\n  -> %s" % novela.relative_to(RAIZ).as_posix())
    print("\n  La buena llego al entregable. La mala quedo bloqueada en G2.")
    print("  Las dos habian pasado G1.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
