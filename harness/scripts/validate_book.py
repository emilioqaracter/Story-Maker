"""G4 - la obra. V10-V12, V17-V19 y las tres condiciones del final.

La longitud pedida es un TECHO, no una meta: C2 puede impedir que el libro
siga, nunca obligarlo a seguir. C3 es la que manda.

    python harness/scripts/validate_book.py books/<slug>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (Error, Libro, contar_palabras, emitir, etapa_en, fecha,  # noqa: E402
                    libro_de_argv, salida)


def _aprobadas(libro: Libro) -> list:
    return [e for e in libro.escenas if e.get("estado") == "aprobada"]


def _orden(escenas: list) -> list:
    """Orden de lectura: por fecha, y el id desempata."""
    return sorted(escenas, key=lambda e: (fecha(e.get("fecha")) or fecha("9999-12-31"), str(e.get("id"))))


def palabras_escritas(libro: Libro) -> int:
    total = 0
    for esc in _aprobadas(libro):
        ruta = libro.ruta_prosa(esc)
        if ruta.exists():
            total += contar_palabras(ruta.read_text(encoding="utf-8"))
    return total


def v10_hilos_cierran(libro: Libro) -> list:
    declarados = [h.get("id") for h in libro.premise.get("hilos") or []]
    cuenta = {h: 0 for h in declarados}
    for esc in _aprobadas(libro):
        for h in esc.get("cierra") or []:
            if h in cuenta:
                cuenta[h] += 1
    errores = []
    for h, n in cuenta.items():
        que = next((x.get("que") for x in libro.premise["hilos"] if x.get("id") == h), h)
        if n == 0:
            errores.append(Error("V10", "El hilo %s ('%s') no lo cierra ninguna escena aprobada." % (h, que),
                                 "Marca cierra: [%s] en la escena que lo resuelve." % h))
        elif n > 1:
            errores.append(Error("V10", "El hilo %s ('%s') se cierra %d veces." % (h, que, n),
                                 "Un hilo se cierra una sola vez: deja el cierre en una escena."))
    return errores


def v11_hilos_declarados(libro: Libro) -> list:
    declarados = {h.get("id") for h in libro.premise.get("hilos") or []}
    errores = []
    for esc in libro.escenas:
        for h in esc.get("cierra") or []:
            if h not in declarados:
                errores.append(Error(
                    "V11", "%s cierra '%s', que no esta declarado en premise.hilos." % (esc["id"], h),
                    "El numero de hilos no crece durante la produccion: declara el hilo o quita el cierre."))
    return errores


def v12_techo(libro: Libro) -> list:
    forma = libro.forma
    escritas = palabras_escritas(libro)
    pendientes = [e for e in libro.escenas if e.get("estado") != "aprobada"]
    proyeccion = escritas + len(pendientes) * forma["palabras_por_escena_max"]
    errores = []
    if escritas > forma["techo_palabras"]:
        errores.append(Error("V12", "El recuento real es %d y el techo %d." % (escritas, forma["techo_palabras"]),
                             "Ya te pasaste: hay que fusionar escenas que no cierran hilo."))
    if proyeccion > forma["techo_palabras"]:
        errores.append(Error(
            "V12",
            "La proyeccion es %d (%d escritas + %d pendientes) y el techo %d."
            % (proyeccion, escritas, len(pendientes), forma["techo_palabras"]),
            "Contrae el plan ahora, que todavia se puede: fusiona escenas que no cierran hilo."))
    return errores


def v17_una_crisis(libro: Libro) -> list:
    tramos = libro.relacion.get("etapas") or []
    rupturas = [t for t in tramos if t.get("etapa") == "ruptura"]
    intimidades = [t for t in tramos if t.get("etapa") == "intimidad"]
    if len(rupturas) != 1:
        return [Error("V17", "Hay %d rupturas declaradas y tiene que haber exactamente una." % len(rupturas),
                      "La crisis del genero es una sola: ajusta relacion.yaml.")]
    if intimidades:
        fr, fi = fecha(rupturas[0].get("desde")), fecha(intimidades[0].get("desde"))
        if fr and fi and fr <= fi:
            return [Error("V17", "La ruptura (%s) no es posterior a la intimidad (%s)." % (fr, fi),
                          "La crisis va despues del punto de mayor intimidad, o no es una crisis.")]
    return []


def v18_promesa(libro: Libro) -> list:
    obligatoria = libro.config["genero"]["etapa_final_obligatoria"]
    aprobadas = _aprobadas(libro)
    if not aprobadas:
        return [Error("V18", "No hay ninguna escena aprobada.", "Produce antes de cerrar.")]
    ultima = _orden(aprobadas)[-1]
    f = fecha(ultima.get("fecha"))
    etapa = etapa_en(libro.relacion, f) if f else None
    if etapa != obligatoria:
        return [Error(
            "V18",
            "La ultima escena (%s, %s) deja la relacion en '%s' y el genero exige '%s'."
            % (ultima["id"], f, etapa, obligatoria),
            "En romance, que acaben juntos no es una decision narrativa: es la promesa del genero.")]
    return []


def v19_coinciden(libro: Libro) -> list:
    prot = libro.protagonistas
    if len(prot) < 2:
        return []
    limite = libro.config["ciclo"]["escenas_sin_coincidir_max"]
    racha, peor = 0, 0
    for esc in _orden(libro.escenas):
        presentes = set(esc.get("presentes") or [])
        if set(prot) <= presentes:
            racha = 0
        else:
            racha += 1
            peor = max(peor, racha)
    if peor > limite:
        return [Error("V19", "Los protagonistas pasan %d escenas seguidas sin coincidir (maximo %d)." % (peor, limite),
                      "Es una romance: si la pareja no comparte escena, la novela se desarmo.")]
    return []


def condiciones(libro: Libro) -> dict:
    forma = libro.forma
    sin_aprobar = [e["id"] for e in libro.escenas if e.get("estado") != "aprobada"]
    escritas = palabras_escritas(libro)
    c3 = not (v10_hilos_cierran(libro) + v18_promesa(libro))
    return {
        "C1_estructura": {"ok": not sin_aprobar, "sin_aprobar": sin_aprobar},
        "C2_techo": {"ok": escritas <= forma["techo_palabras"],
                     "palabras": escritas, "techo": forma["techo_palabras"]},
        "C3_cierre": {"ok": c3},
    }


def cabe_el_final(libro: Libro) -> dict:
    """El regulador: mide capacidad, no ritmo. Solo se rompe cuando el final
    ha dejado de caber de verdad."""
    forma = libro.forma
    restantes = forma["techo_palabras"] - palabras_escritas(libro)
    cierres = [e for e in libro.escenas
               if e.get("estado") != "aprobada" and (e.get("cierra") or [])]
    cuesta = len(cierres) * forma["palabras_por_escena_max"]
    return {"palabras_restantes": restantes, "cierre_pendiente": cuesta,
            "cabe": restantes >= cuesta,
            "escenas_de_cierre_pendientes": [e["id"] for e in cierres]}


def main(argv: list) -> int:
    libro = libro_de_argv(argv, "validate_book.py books/<slug>")
    errores = (v10_hilos_cierran(libro) + v11_hilos_declarados(libro) + v12_techo(libro)
               + v17_una_crisis(libro) + v18_promesa(libro) + v19_coinciden(libro))
    cond = condiciones(libro)
    extra = {"condiciones": cond, "regulador": cabe_el_final(libro), "forma": libro.forma,
             "termina": all(c["ok"] for c in cond.values()) and not errores}
    destino = libro.dir / "reports" / "final.json"
    return emitir(salida("obra", errores, extra), destino)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
