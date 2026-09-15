"""G2 - la puerta del criterio. Lee la rubrica y decide.

El critico no decide: emite notas y citas en SNNN.critique.json. Aqui se suma
y se compara contra el umbral de config.yaml. Ningun agente abre su propia
puerta.

    python harness/scripts/gate_scene.py books/<slug> S001
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Error, Libro, emitir, salida  # noqa: E402


def evaluar(libro: Libro, sid: str, critica: dict) -> dict:
    cfg = libro.config["rubrica"]
    dimensiones = cfg["dimensiones"]
    errores = []

    # --- veto de continuidad: binario, y manda sobre todo lo demas ---------- #
    cont = critica.get("continuidad") or {}
    if cont.get("veto"):
        for h in cont.get("hallazgos") or [{"que": "sin detalle"}]:
            errores.append(Error(
                "G2/continuidad",
                "Veto de continuidad: %s" % h.get("que"),
                "Corrige eso concreto. Cita: %s" % (h.get("cita") or "(sin cita)")))

    # --- rubrica de calidad ------------------------------------------------ #
    calidad = critica.get("calidad") or {}
    suma, evaluadas, detalle = 0, 0, {}
    for dim in dimensiones:
        entrada = calidad.get(dim)
        if entrada is None:
            if dim == "quimica":
                detalle[dim] = None          # escena que no es de pareja
                continue
            errores.append(Error("G2/rubrica", "Falta la dimension '%s' en la critica." % dim,
                                 "La lente de calidad tiene que puntuar las cinco."))
            continue
        nota, cita = entrada.get("nota"), entrada.get("cita")
        if nota not in cfg["niveles"]:
            errores.append(Error("G2/rubrica", "'%s' trae nota %r, fuera de %s." % (dim, nota, cfg["niveles"]),
                                 "Solo 0, 1 o 2: son tres conductas, no una escala."))
            continue
        # Sin cita, no hay puntuacion: cuenta como no evaluada.
        if nota < 2 and not (cita and str(cita).strip()):
            errores.append(Error(
                "G2/rubrica", "'%s' puntua %d sin citar el fragmento." % (dim, nota),
                "Toda nota menor que 2 exige una cita textual, o la dimension no cuenta."))
            continue
        detalle[dim] = nota
        suma += nota
        evaluadas += 1
        if nota == 0 and cfg.get("cero_prohibido", True):
            errores.append(Error(
                "G2/rubrica", "'%s' esta en 0: %s" % (dim, cita),
                "Un 0 tumba la escena aunque la suma alcance. Reescribe esa dimension."))

    con_quimica = detalle.get("quimica") is not None
    umbral = cfg["umbral"] if con_quimica else cfg["umbral_sin_quimica"]
    maximo = 2 * (len(dimensiones) if con_quimica else len(dimensiones) - 1)

    faltan = [d for d in dimensiones if d not in detalle]
    if not faltan and suma < umbral:
        errores.append(Error(
            "G2/rubrica", "La rubrica suma %d sobre %d y el umbral es %d." % (suma, maximo, umbral),
            "Sube la dimension mas baja; no hace falta brillantez, hace falta pasar el minimo."))

    return salida(sid, errores, {"puerta": "G2", "suma": suma, "maximo": maximo,
                                 "umbral": umbral, "dimensiones": detalle,
                                 "veto_continuidad": bool(cont.get("veto"))})


def main(argv: list) -> int:
    if len(argv) < 3:
        print("uso: gate_scene.py books/<slug> <SID>", file=sys.stderr)
        return 2
    libro = Libro(argv[1])
    sid = argv[2]
    esc = libro.escena(sid)
    if not esc:
        return emitir(salida(sid, [Error("G2", "%s no existe en timeline.yaml." % sid, "Revisa el id.")]))
    ruta = libro.ruta_prosa(esc).with_suffix(".critique.json")
    if not ruta.exists():
        return emitir(salida(sid, [Error("G2", "No hay critica en %s." % ruta.name,
                                         "Convoca las dos lentes antes de abrir G2.")]))
    critica = json.loads(ruta.read_text(encoding="utf-8"))
    return emitir(evaluar(libro, sid, critica))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
