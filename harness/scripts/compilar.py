"""Concatena las escenas aprobadas en manuscript/novela.md.

No se 'genera' nada interesante aqui: es una concatenacion en orden de
timeline. Existe para que el entregable sea un archivo y no una carpeta que
alguien tenga que montar a mano.

    python harness/scripts/compilar.py books/<slug>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Error, Libro, contar_palabras, emitir, fecha, libro_de_argv, salida  # noqa: E402


def compilar(libro: Libro) -> dict:
    aprobadas = sorted(
        [e for e in libro.escenas if e.get("estado") == "aprobada"],
        key=lambda e: (e.get("capitulo", 0), fecha(e.get("fecha")) or fecha("9999-12-31"), str(e.get("id"))))
    if not aprobadas:
        return salida("novela.md", [Error("compilar", "No hay escenas aprobadas.",
                                          "Produce al menos una escena antes de compilar.")])

    partes, faltan, capitulo_actual = [], [], None
    titulo = libro.premise.get("titulo") or libro.premise.get("eje") or libro.dir.name
    partes.append("# %s\n" % titulo)

    for esc in aprobadas:
        ruta = libro.ruta_prosa(esc)
        if not ruta.exists():
            faltan.append(Error("compilar", "Falta la prosa de %s." % esc["id"],
                                "La escena esta aprobada pero no hay archivo: revisa el estado."))
            continue
        if esc.get("capitulo") != capitulo_actual:
            capitulo_actual = esc.get("capitulo")
            partes.append("\n## Capitulo %d\n" % capitulo_actual)
        partes.append("\n" + ruta.read_text(encoding="utf-8").strip() + "\n")

    texto = "".join(partes)
    destino = libro.dir / "manuscript" / "novela.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8")
    # El recuento es el de la prosa: los titulos no son del libro.
    prosa = sum(contar_palabras(libro.ruta_prosa(e).read_text(encoding="utf-8"))
                for e in aprobadas if libro.ruta_prosa(e).exists())
    return salida("novela.md", faltan,
                  {"escenas": len(aprobadas), "palabras": prosa,
                   "ruta": destino.relative_to(libro.dir).as_posix()})


def main(argv: list) -> int:
    return emitir(compilar(libro_de_argv(argv, "compilar.py books/<slug>")))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
