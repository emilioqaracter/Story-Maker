"""Conduce el ciclo. El ciclo lo lleva este script, no el modelo.

Claude Code hace las partes de modelo (escribir, criticar, corregir); este
script decide QUE toca, cuenta los intentos, aplica las puertas y guarda el
estado. Por eso los intentos viven en state.json y no en la conversacion: si
no, reanudar manana reinicia la cuenta y una escena imposible se reintenta
para siempre.

Subcomandos:
    next      que toca ahora, y por que
    contexto  el canon resuelto EN PROSA para una escena
    validar   G1
    puerta    G2
    aprobar   marca aprobada, recuenta y comprueba que el final quepa
    estado    el state.json tal cual

    python harness/scripts/run_scene.py books/<slug> next
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (Libro, contar_palabras, edad, estado_en, etapa_en, fecha,  # noqa: E402
                    parrafos, sabe_en)
from gate_scene import evaluar  # noqa: E402
from validate_book import cabe_el_final, condiciones, palabras_escritas  # noqa: E402
from validate_scene import validar  # noqa: E402

ESTADO_INICIAL = {"escena_actual": None, "intento": 0, "ultima_aprobada": None,
                  "palabras_escritas": 0, "contracciones": 0}


# --------------------------------------------------------------------------- #
# Estado
# --------------------------------------------------------------------------- #
def ruta_estado(libro: Libro) -> Path:
    return libro.dir / "state.json"


def leer_estado(libro: Libro) -> dict:
    p = ruta_estado(libro)
    if p.exists():
        return {**ESTADO_INICIAL, **json.loads(p.read_text(encoding="utf-8"))}
    return dict(ESTADO_INICIAL)


def escribir_estado(libro: Libro, estado: dict) -> None:
    ruta_estado(libro).write_text(
        json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def guardar_timeline(libro: Libro) -> None:
    import yaml
    (libro.ctx / "timeline.yaml").write_text(
        yaml.safe_dump(libro.timeline, allow_unicode=True, sort_keys=False), encoding="utf-8")


# --------------------------------------------------------------------------- #
# resolver-canon: el canon, ya resuelto, en prosa
# --------------------------------------------------------------------------- #
def contexto(libro: Libro, sid: str) -> str:
    """Nadie interpreta YAML por su cuenta: aqui sale ya resuelto a una fecha.

    Es un script y no un agente porque tiene una respuesta correcta."""
    esc = libro.escena(sid)
    if not esc:
        return "No existe la escena %s." % sid
    f = fecha(esc.get("fecha"))
    L = []
    L.append("ESCENA %s - capitulo %s - %s - %s" % (
        esc["id"], esc.get("capitulo"), f, esc.get("lugar", "sin lugar")))
    L.append("Resumen del plan: %s" % esc.get("resumen", "(sin resumen)"))
    if esc.get("hito"):
        L.append("Coincide con el hito deportivo: %s" % esc["hito"])
    L.append("")

    L.append("QUIEN ESTA:")
    for clave in esc.get("presentes") or []:
        p = libro.personajes.get(clave)
        if not p:
            L.append("- %s (no esta en el canon)" % clave)
            continue
        trozos = ["%s, %s anos" % (p.get("nombre"), edad(p.get("nacimiento"), f))]
        est = estado_en(p, f)
        if est:
            etiqueta = est.get("que") or est.get("lesion")
            if etiqueta:
                hasta = fecha(est.get("hasta"))
                trozos.append("%s%s" % (etiqueta, " hasta el %s" % hasta if hasta else ""))
        sabidos = [s.get("que") for s in sabe_en(p, f)] if f else []
        ignora = [s.get("que") for s in (p.get("sabe") or [])
                  if s.get("que") not in sabidos]
        if sabidos:
            trozos.append("sabe: " + "; ".join(map(str, sabidos)))
        if ignora:
            trozos.append("TODAVIA NO SABE: " + "; ".join(map(str, ignora)))
        L.append("- " + ". ".join(trozos) + ".")
    L.append("")

    etapa = etapa_en(libro.relacion, f) if f else None
    L.append("LA PAREJA: a esta fecha la relacion esta en '%s'." % etapa)
    if libro.relacion.get("obstaculo"):
        L.append("Lo que los separa: %s" % libro.relacion["obstaculo"])
    L.append("No adelantes ni retrocedas esa etapa en esta escena.")
    L.append("")

    L.append("EPOCA: %s. No puede aparecer: %s." % (
        libro.epoca.get("anio"), ", ".join(libro.epoca.get("prohibido") or []) or "(nada declarado)"))
    if libro.epoca.get("notas"):
        L.append("Como era: %s" % libro.epoca["notas"])
    L.append("")

    est = libro.config["estructura"]
    L.append("FORMA OBLIGATORIA: %d parrafos, %d lineas cada uno, %d palabras por linea (+-%d)." % (
        est["parrafos_por_escena"], est["lineas_por_parrafo"], est["palabras_por_linea"],
        libro.config["tolerancia"]["palabras_por_linea"]))
    L.append("Separa los parrafos con una linea en blanco. Devuelve solo la prosa.")
    if esc.get("cierra"):
        hilos = {h.get("id"): h.get("que") for h in libro.premise.get("hilos") or []}
        L.append("ESTA ESCENA CIERRA: " + "; ".join(
            "%s (%s)" % (h, hilos.get(h, "?")) for h in esc["cierra"]))
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# next: que toca
# --------------------------------------------------------------------------- #
def siguiente(libro: Libro) -> dict:
    estado = leer_estado(libro)
    cfg = libro.config["ciclo"]
    pendientes = [e for e in libro.escenas if e.get("estado") != "aprobada"]

    if not pendientes:
        cond = condiciones(libro)
        termina = all(c["ok"] for c in cond.values())
        return {"accion": "cerrar" if termina else "revisar",
                "motivo": "No quedan escenas sin aprobar; toca G4.",
                "condiciones": cond}

    esc = pendientes[0]
    sid = esc["id"]
    intento = estado["intento"] if estado.get("escena_actual") == sid else 0

    if intento >= cfg["intentos_max"]:
        return {"accion": "parar", "escena": sid, "intento": intento,
                "motivo": "%d intentos sin pasar las puertas. Decide vos: rehacer, cambiar el canon o bajar el liston."
                          % intento}

    prosa = libro.ruta_prosa(esc)
    accion = "escribir" if not prosa.exists() else "corregir"
    return {"accion": accion, "escena": sid, "intento": intento + 1,
            "capitulo": esc.get("capitulo"),
            "motivo": "Sin prosa en disco." if accion == "escribir" else "Hay prosa; falta pasar las puertas.",
            "contexto": "run_scene.py %s contexto %s" % (libro.dir.name, sid),
            "salida_esperada": str(prosa.relative_to(libro.dir))}


# --------------------------------------------------------------------------- #
# aprobar
# --------------------------------------------------------------------------- #
def aprobar(libro: Libro, sid: str) -> dict:
    esc = libro.escena(sid)
    if not esc:
        return {"ok": False, "motivo": "%s no existe." % sid}

    g1 = validar(libro, sid)
    if not g1["ok"]:
        return {"ok": False, "puerta": "G1", "motivo": "G1 no abre.", "errores": g1["errores"]}

    ruta_crit = libro.ruta_prosa(esc).with_suffix(".critique.json")
    if not ruta_crit.exists():
        return {"ok": False, "puerta": "G2", "motivo": "Falta %s: convoca las dos lentes." % ruta_crit.name}
    g2 = evaluar(libro, sid, json.loads(ruta_crit.read_text(encoding="utf-8")))
    if not g2["ok"]:
        return {"ok": False, "puerta": "G2", "motivo": "G2 no abre.", "errores": g2["errores"],
                "suma": g2.get("suma"), "umbral": g2.get("umbral")}

    texto = libro.ruta_prosa(esc).read_text(encoding="utf-8")
    esc["estado"] = "aprobada"
    esc["palabras"] = contar_palabras(texto)
    guardar_timeline(libro)
    fijada = fijar_voz(libro, texto)

    estado = leer_estado(libro)
    estado.update({"escena_actual": None, "intento": 0, "ultima_aprobada": sid,
                   "palabras_escritas": palabras_escritas(libro)})
    escribir_estado(libro, estado)

    reg = cabe_el_final(libro)
    fin_cap = not [e for e in libro.escenas
                   if e.get("capitulo") == esc.get("capitulo") and e.get("estado") != "aprobada"]
    return {"ok": True, "escena": sid, "palabras": esc["palabras"],
            "voz_fijada": fijada, "regulador": reg,
            "aviso": None if reg["cabe"] else "El final ya no cabe: hay que contraer el plan.",
            "puerta_G3": "Cierra el capitulo %s: te toca leerlo." % esc.get("capitulo") if fin_cap else None}


def fijar_voz(libro: Libro, texto: str) -> bool:
    """La muestra de voz sale de la PRIMERA escena aprobada y no se regenera.

    Si mas tarde se revierte esa escena, voz.md se queda como esta: es una
    referencia de registro, no una copia. Regenerarla cada vez seria volver a
    tener una voz que se mueve."""
    destino = libro.ctx / "voz.md"
    # El libro arranca con voz.md = el registro del genero, para que el escritor
    # de la primera escena no se quede sin nada. Aqui se le agrega la muestra.
    if destino.exists() and "## Muestra fija" in destino.read_text(encoding="utf-8"):
        return False
    if destino.exists():
        cabecera = destino.read_text(encoding="utf-8").strip()
    else:
        base = Path(__file__).resolve().parents[1] / "voz-base.md"
        cabecera = base.read_text(encoding="utf-8").strip() if base.exists() else ""
    muestra = "\n\n".join("\n".join(b) for b in parrafos(texto)[:2])
    destino.write_text(
        "%s\n\n---\n\n## Muestra fija\n\nAsi suena este libro. Va con cada llamada a "
        "`escribir-escena` y con la lente de calidad.\n\n%s\n" % (cabecera, muestra),
        encoding="utf-8")
    return True


def marcar_intento(libro: Libro, sid: str) -> dict:
    estado = leer_estado(libro)
    estado["intento"] = estado["intento"] + 1 if estado.get("escena_actual") == sid else 1
    estado["escena_actual"] = sid
    escribir_estado(libro, estado)
    return estado


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    libro, cmd = Libro(argv[1]), argv[2]
    arg = argv[3] if len(argv) > 3 else None

    if cmd == "contexto":
        print(contexto(libro, arg))
        return 0
    if cmd == "next":
        res = siguiente(libro)
    elif cmd == "validar":
        res = validar(libro, arg)
        libro.ruta_prosa(libro.escena(arg)).with_suffix(".validation.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif cmd == "puerta":
        ruta = libro.ruta_prosa(libro.escena(arg)).with_suffix(".critique.json")
        res = evaluar(libro, arg, json.loads(ruta.read_text(encoding="utf-8")))
    elif cmd == "aprobar":
        res = aprobar(libro, arg)
    elif cmd == "intento":
        res = marcar_intento(libro, arg)
    elif cmd == "estado":
        res = leer_estado(libro)
    else:
        print("subcomando desconocido: %s" % cmd, file=sys.stderr)
        return 2

    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
