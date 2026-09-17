# -*- coding: utf-8 -*-
"""G3 - la puerta del capitulo. Lee la lectura y decide.

    python harness/scripts/gate_chapter.py books/<slug> 1 < lectura.json

Hasta la v8.0 esta puerta la abria una persona: leia el capitulo y decidia. En
el camino autonomo no hay persona, asi que la lectura la hace el agente
`lector-capitulo` y **la decision sigue sin ser suya**: devuelve hallazgos con
cita y este script aplica el umbral. La regla no cambia — ningun agente abre su
propia puerta —, cambia quien lee.

Comprueba tres cosas:

1. Lo que no necesita criterio: que todas las escenas del capitulo esten
   aprobadas y que el capitulo no se salga de su presupuesto de palabras.
2. Los hallazgos bloqueantes de la lectura. Uno solo cierra la puerta.
3. Que la lectura hable del capitulo que hay: si cita algo que no esta en el
   texto, no lo leyo.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Error, Libro, contar_palabras, emitir, menciona, salida  # noqa: E402

# Cuanto puede desviarse un capitulo de su presupuesto antes de que sea un
# problema de forma y no de estilo. Las escenas ya pasaron V15 una por una;
# esto caza la suma.
MARGEN = 0.25


def evaluar(libro: Libro, capitulo: int, lectura: dict) -> dict:
    errores = []
    escenas = [e for e in libro.escenas if e.get("capitulo") == capitulo]
    if not escenas:
        return salida("ch%02d" % capitulo, [Error(
            "G3", "El capitulo %s no existe en timeline.yaml." % capitulo,
            "Revisa el numero de capitulo.")])

    # --- 1. lo que no necesita criterio ------------------------------------ #
    sin_aprobar = [e["id"] for e in escenas if e.get("estado") != "aprobada"]
    if sin_aprobar:
        errores.append(Error(
            "G3/completo",
            "El capitulo %d tiene escenas sin aprobar: %s." % (capitulo, ", ".join(sin_aprobar)),
            "G3 se abre sobre un capitulo terminado. Cierra antes esas escenas."))

    texto = ""
    for e in escenas:
        p = libro.ruta_prosa(e)
        if p.exists():
            texto += p.read_text(encoding="utf-8") + "\n\n"
    palabras = contar_palabras(texto)
    presupuesto = libro.forma["palabras_por_escena"] * len(escenas)
    if palabras > presupuesto * (1 + MARGEN):
        errores.append(Error(
            "G3/forma",
            "El capitulo %d suma %d palabras y su presupuesto es %d." % (capitulo, palabras, presupuesto),
            "Contrae la escena mas larga: el techo del libro se reparte entre todos los capitulos."))

    # --- 2. la lectura habla del texto que hay ----------------------------- #
    hallazgos = (lectura or {}).get("hallazgos") or []
    for h in hallazgos:
        cita = (h.get("cita") or "").strip()
        if not cita:
            errores.append(Error(
                "G3/lectura", "Un hallazgo del capitulo %d no cita el texto: %s" % (capitulo, h.get("que")),
                "Todo hallazgo exige cita textual, igual que en G2: sin evidencia es una opinion."))
            continue
        # Una cita que no esta en el capitulo quiere decir que la lectura habla
        # de otro texto, y una lectura asi no puede abrir ninguna puerta.
        trozo = " ".join(cita.split()[:6])
        if trozo and not menciona(texto, trozo.split()[0]):
            errores.append(Error(
                "G3/lectura", "La cita '%s' no aparece en el capitulo %d." % (cita[:60], capitulo),
                "Vuelve a leer el capitulo tal como esta en disco."))

    # --- 3. los hallazgos bloqueantes -------------------------------------- #
    for h in hallazgos:
        if h.get("bloquea"):
            errores.append(Error(
                "G3/capitulo", "%s (escena %s)" % (h.get("que"), h.get("escena") or "?"),
                "Corrige esa escena y vuelve a pasar sus puertas. Cita: %s" % (h.get("cita") or "(sin cita)")))

    return salida("ch%02d" % capitulo, errores, {
        "puerta": "G3", "capitulo": capitulo, "escenas": [e["id"] for e in escenas],
        "palabras": palabras, "presupuesto": presupuesto,
        "hallazgos": len(hallazgos),
        "bloqueantes": len([h for h in hallazgos if h.get("bloquea")])})


def main(argv: list) -> int:
    if len(argv) < 3:
        print("uso: gate_chapter.py books/<slug> <capitulo>  (la lectura va por stdin)",
              file=sys.stderr)
        return 2
    libro = Libro(argv[1])
    # La consola de Windows entrega stdin en cp1252: sin esto, una cita con
    # tilde llega rota y el script acusa al lector de citar lo que no existe.
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                               # noqa: BLE001
        pass
    try:
        crudo = sys.stdin.read().strip()
        lectura = json.loads(crudo) if crudo else {}
    except json.JSONDecodeError as e:
        return emitir(salida("ch" + argv[2], [Error(
            "G3", "La lectura no es JSON valido: %s" % e,
            "El lector devuelve {\"hallazgos\": [{\"que\":..., \"cita\":..., \"escena\":..., \"bloquea\": true}]}")]))
    return emitir(evaluar(libro, int(argv[2]), lectura), libro=libro, paso="G3")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
