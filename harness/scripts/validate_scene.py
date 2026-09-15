"""G1 - los hechos de una escena. V1-V9, V14-V16, V20. Sin LLM, sin red.

Corre en cada vuelta del ciclo, antes que el critico: es instantaneo y no
falla, asi que filtrar aqui es lo que mantiene barato el ciclo.

    python harness/scripts/validate_scene.py books/<slug> S001
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (Error, Libro, contar_palabras, edad, emitir, estado_en,  # noqa: E402
                    fecha, menciona, nombre_pila, palabras, parrafos, salida)
from validate_canon import v16_arco  # noqa: E402

RE_EDAD = re.compile(r"(\d{1,3})\s+a[nnñ]os", re.IGNORECASE)
MARCAS_CUMPLE = ("cumpleanos", "cumplio anos", "cumplia anos", "soplar las velitas")


def _presentes(libro: Libro, esc: dict) -> dict:
    return {k: libro.personajes[k] for k in (esc.get("presentes") or []) if k in libro.personajes}


def v1_fecha(libro: Libro, esc: dict) -> list:
    f = fecha(esc.get("fecha"))
    rango = libro.premise.get("epoca") or {}
    d, h = fecha(rango.get("desde")), fecha(rango.get("hasta"))
    if not f:
        return [Error("V1", "%s no tiene fecha." % esc["id"],
                      "Toda escena lleva fecha absoluta en timeline.yaml.")]
    if d and h and not (d <= f <= h):
        return [Error("V1", "%s ocurre el %s, fuera de la epoca (%s a %s)." % (esc["id"], f, d, h),
                      "Mueve la escena dentro de la epoca, o corrige premise.epoca.")]
    return []


def v2_orden(libro: Libro, esc: dict) -> list:
    if esc.get("flashback"):
        return []
    f = fecha(esc.get("fecha"))
    previas = [e for e in libro.escenas
               if e.get("capitulo") == esc.get("capitulo")
               and str(e.get("id")) < str(esc.get("id"))
               and not e.get("flashback")]
    for p in previas:
        fp = fecha(p.get("fecha"))
        if f and fp and f < fp:
            return [Error("V2",
                          "%s (%s) va antes que %s (%s) en el mismo capitulo." % (esc["id"], f, p["id"], fp),
                          "Reordena las fechas, o declara flashback: true en la escena.")]
    return []


def v3_edad(libro: Libro, esc: dict, texto: str) -> list:
    f = fecha(esc.get("fecha"))
    if not f:
        return []
    validas = {edad(p.get("nacimiento"), f) for p in _presentes(libro, esc).values()}
    validas.discard(None)
    errores = []
    for m in RE_EDAD.finditer(texto):
        dicha = int(m.group(1))
        if validas and dicha not in validas:
            errores.append(Error(
                "V3",
                "La prosa dice '%s' pero a esa fecha las edades son %s." % (m.group(0), sorted(validas)),
                "La edad no se declara: se deriva de nacimiento. Corrige la prosa."))
    return errores


def v4_cumple(libro: Libro, esc: dict, texto: str) -> list:
    f = fecha(esc.get("fecha"))
    if not f or not any(menciona(texto, m) for m in MARCAS_CUMPLE):
        return []
    errores = []
    for p in _presentes(libro, esc).values():
        n = fecha(p.get("nacimiento"))
        if not n:
            continue
        if menciona(texto, nombre_pila(p)) and (f.month, f.day) != (n.month, n.day):
            errores.append(Error(
                "V4",
                "Se celebra el cumpleanos de %s el %02d-%02d, pero nacio el %02d-%02d."
                % (p.get("nombre"), f.day, f.month, n.day, n.month),
                "Cambia el motivo de la celebracion, o mueve la escena a su aniversario."))
    return errores


def v5_evento_unico(libro: Libro, esc: dict, texto: str) -> list:
    f = fecha(esc.get("fecha"))
    errores = []
    for p in _presentes(libro, esc).values():
        for ev in p.get("eventos_unicos") or []:
            fe = fecha(ev.get("fecha"))
            marcas = ev.get("marcadores") or [ev.get("que", "")]
            if fe and f and f != fe and any(menciona(texto, m) for m in marcas if m):
                errores.append(Error(
                    "V5",
                    "La escena del %s narra '%s', que ocurre una sola vez el %s." % (f, ev.get("que"), fe),
                    "Un evento unico no se repite: quitalo de aqui o mueve la escena."))
    return errores


def v6_estado(libro: Libro, esc: dict, texto: str) -> list:
    f = fecha(esc.get("fecha"))
    errores = []
    for p in _presentes(libro, esc).values():
        est = estado_en(p, f) if f else {}
        for prohibido in est.get("prohibe") or []:
            if menciona(texto, prohibido):
                errores.append(Error(
                    "V6",
                    "%s '%s' el %s, pero su estado lo impide (%s)." % (
                        p.get("nombre"), prohibido, f, est.get("que") or est.get("lesion")),
                    "Cambia la accion, o mueve la escena fuera de ese tramo de estados."))
    return errores


def v7_sabe(libro: Libro, esc: dict, texto: str) -> list:
    f = fecha(esc.get("fecha"))
    errores = []
    for p in _presentes(libro, esc).values():
        for s in p.get("sabe") or []:
            desde = fecha(s.get("desde"))
            marcas = s.get("marcadores") or []
            if desde and f and f < desde and any(menciona(texto, m) for m in marcas if m):
                errores.append(Error(
                    "V7",
                    "%s reacciona a '%s' el %s, y no lo sabe hasta el %s." % (
                        p.get("nombre"), s.get("que"), f, desde),
                    "Quita la reaccion, o adelanta el 'desde' en characters/."))
    return errores


def v8_anacronismos(libro: Libro, texto: str) -> list:
    return [Error("V8", "Aparece '%s', que no existe en esta epoca." % t,
                  "Quitalo: la lista sale de epoca.yaml, no de un criterio.")
            for t in libro.epoca.get("prohibido") or [] if menciona(texto, t)]


def v9_reales(libro: Libro, esc: dict, texto: str) -> list:
    f = fecha(esc.get("fecha"))
    errores = []
    for real in libro.reales or []:
        nombre = str(real.get("nombre") or "")
        if not nombre or not menciona(texto, nombre.split()[0]):
            continue
        n, m = fecha(real.get("nacimiento")), fecha(real.get("muerte"))
        if f and n and f < n:
            errores.append(Error("V9", "%s aparece el %s y nacio el %s." % (nombre, f, n),
                                 "Quitalo de la escena o mueve la escena."))
        if f and m and f > m:
            errores.append(Error("V9", "%s aparece el %s y murio el %s." % (nombre, f, m),
                                 "Quitalo de la escena o mueve la escena."))
    return errores


def v14_parrafos(libro: Libro, bloques: list) -> list:
    esperados = libro.config["estructura"]["parrafos_por_escena"]
    if len(bloques) != esperados:
        return [Error("V14",
                      "La escena tiene %d parrafos y la forma declarada son %d." % (len(bloques), esperados),
                      "Reescribela en exactamente %d parrafos separados por linea en blanco." % esperados)]
    return []


def v15_lineas(libro: Libro, bloques: list) -> list:
    est, tol = libro.config["estructura"], libro.config["tolerancia"]
    nl, npal = est["lineas_por_parrafo"], est["palabras_por_linea"]
    tl, tp = tol["lineas_por_parrafo"], tol["palabras_por_linea"]
    errores = []
    for i, bloque in enumerate(bloques, 1):
        if abs(len(bloque) - nl) > tl:
            errores.append(Error(
                "V15", "El parrafo %d tiene %d lineas; la forma pide %d (+-%d)." % (i, len(bloque), nl, tl),
                "Reescribe ese parrafo con %d lineas." % nl))
        for j, linea in enumerate(bloque, 1):
            n = palabras(linea)
            if abs(n - npal) > tp:
                errores.append(Error(
                    "V15",
                    "Parrafo %d, linea %d: %d palabras; la forma pide %d (+-%d)." % (i, j, n, npal, tp),
                    "Deja esa linea entre %d y %d palabras." % (npal - tp, npal + tp)))
    return errores


def v20_hito(libro: Libro, esc: dict) -> list:
    nombre = esc.get("hito")
    if not nombre:
        return []
    f = fecha(esc.get("fecha"))
    for h in libro.calendario.get("hitos") or []:
        if h.get("que") == nombre:
            fh = fecha(h.get("fecha"))
            if fh and f and fh != f:
                return [Error("V20",
                              "%s dice hito '%s' pero cae el %s y el hito es el %s." % (esc["id"], nombre, f, fh),
                              "Ajusta la fecha de la escena a la del calendario.")]
            return []
    return [Error("V20", "%s declara el hito '%s', que no esta en calendario.yaml." % (esc["id"], nombre),
                  "Usa un hito real del calendario, o quita el campo.")]


def validar(libro: Libro, sid: str) -> dict:
    esc = libro.escena(sid)
    if not esc:
        return salida(sid, [Error("V1", "%s no existe en timeline.yaml." % sid,
                                  "Revisa el id o planifica la escena.")])
    ruta = libro.ruta_prosa(esc)
    if not ruta.exists():
        return salida(sid, [Error("V14", "No hay prosa en %s." % ruta.name,
                                  "Escribe la escena antes de validarla.")])
    texto = ruta.read_text(encoding="utf-8")
    bloques = parrafos(texto)
    errores = (v1_fecha(libro, esc) + v2_orden(libro, esc) + v3_edad(libro, esc, texto)
               + v4_cumple(libro, esc, texto) + v5_evento_unico(libro, esc, texto)
               + v6_estado(libro, esc, texto) + v7_sabe(libro, esc, texto)
               + v8_anacronismos(libro, texto) + v9_reales(libro, esc, texto)
               + v14_parrafos(libro, bloques) + v15_lineas(libro, bloques)
               + v16_arco(libro) + v20_hito(libro, esc))
    return salida(sid, errores, {"palabras": contar_palabras(texto), "parrafos": len(bloques)})


def main(argv: list) -> int:
    if len(argv) < 3:
        print("uso: validate_scene.py books/<slug> <SID>", file=sys.stderr)
        return 2
    libro = Libro(argv[1])
    esc = libro.escena(argv[2])
    destino = libro.ruta_prosa(esc).with_suffix(".validation.json") if esc else None
    return emitir(validar(libro, argv[2]), destino)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
