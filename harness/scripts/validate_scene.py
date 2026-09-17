"""G1 - los hechos. Lo que se puede comprobar contando y comparando.

    python harness/scripts/validate_scene.py books/<slug> S001

Determinista y gratis: corre SIEMPRE antes que G2, porque filtrar aqui antes de
convocar a un critico es lo que mantiene el ciclo barato.

Lo que comprueba (v9.0):

- **V1/V2** la escena cae dentro de la epoca y en orden.
- **V5** un evento unico no ocurre dos veces.
- **V6** el estado del protagonista manda: si esta lesionado hasta cierto punto
  de la historia, no puede jugar antes. Es lo que sostiene un arco de
  recuperacion.
- **V8** anacronismos: lo que no existia en esa epoca no aparece.
- **V14/V15** la forma: parrafos, lineas y palabras por linea.
- **V16** el arco de tres actos sigue siendo coherente.

Lo que **dejo** de comprobar en la v9.0, y por que: la edad a la fecha (V3), el
cumpleanos (V4), lo que cada personaje sabe (V7), las figuras reales (V9) y el
hito del calendario (V20). No eran malas reglas; eran demasiada precision para
lo que se le pide a estas novelas. Lo que el canon sigue sabiendo —quien sabe
que, y cuando— le llega igual al escritor en el contexto resuelto, y las
contradicciones que queden son trabajo del critico de continuidad, que para eso
lee. Se cambio el liston, no se quito la vigilancia.
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


def v8_anacronismos(libro: Libro, texto: str) -> list:
    return [Error("V8", "Aparece '%s', que no existe en esta epoca." % t,
                  "Quitalo: la lista sale de epoca.yaml, no de un criterio.")
            for t in libro.epoca.get("prohibido") or [] if menciona(texto, t)]


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
    errores = (v1_fecha(libro, esc) + v2_orden(libro, esc)
               + v5_evento_unico(libro, esc, texto) + v6_estado(libro, esc, texto)
               + v8_anacronismos(libro, texto)
               + v14_parrafos(libro, bloques) + v15_lineas(libro, bloques)
               + v16_arco(libro))
    return salida(sid, errores, {"palabras": contar_palabras(texto),
                                 "parrafos": len(bloques),
                                 "acto": libro.acto_de(esc)})


def main(argv: list) -> int:
    if len(argv) < 3:
        print("uso: validate_scene.py books/<slug> <SID>", file=sys.stderr)
        return 2
    libro = Libro(argv[1])
    esc = libro.escena(argv[2])
    destino = libro.ruta_prosa(esc).with_suffix(".validation.json") if esc else None
    return emitir(validar(libro, argv[2]), destino, libro=libro, paso="G1")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
