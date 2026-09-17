# -*- coding: utf-8 -*-
"""G2 - el criterio. Decide el critico; este script comprueba que pueda hacerlo.

    python harness/scripts/gate_scene.py books/<slug> S001

**Hasta la v9.0 decidia este script**: el critico daba cinco notas y aqui se
sumaban y se comparaban contra un umbral. Ahora el veredicto es del critico y
se acata. Lo que queda es lo que un modelo no puede juzgar sobre si mismo:

1. **Que haya critica**, y que hable del texto que hay ahora. Una critica mas
   vieja que la prosa describe un texto que ya no existe: aprobar con ella es
   aprobar a ciegas, y es el error mas barato de cometer del ciclo.
2. **Que el veredicto venga con motivo.** Un `pasa: false` sin decir que esta
   mal no es accionable: el corrector no tiene a que agarrarse y el intento
   siguiente sale igual.
3. **Que las notas de la rubrica traigan cita.** La rubrica ya no decide nada,
   pero sigue siendo la unica medida comparable entre corridas. Una nota sin
   cita es una afirmacion, no una observacion, y no sirve para comparar.

La rubrica se sigue sumando y se sigue informando — como **medida**, no como
puerta. Si la suma es baja y el critico aprobo igual, eso aparece en la salida
y en la traza: no bloquea, pero queda visible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Error, Libro, emitir, salida  # noqa: E402


def evaluar(libro: Libro, sid: str, critica: dict, ruta_critica: Path | None = None) -> dict:
    cfg = libro.config["rubrica"]
    dimensiones = cfg["dimensiones"]
    errores = []

    # --- 1. la critica tiene que hablar del texto que hay ahora ------------ #
    esc = libro.escena(sid)
    if ruta_critica and esc:
        prosa = libro.ruta_prosa(esc)
        if prosa.exists() and ruta_critica.exists():
            if ruta_critica.stat().st_mtime < prosa.stat().st_mtime:
                errores.append(Error(
                    "G2/traza",
                    "La critica es mas vieja que la prosa: habla de un texto que ya cambio.",
                    "Vuelve a convocar las dos lentes sobre la escena actual."))

    # --- 2. el veredicto ---------------------------------------------------- #
    veredicto = critica.get("veredicto") or {}
    pasa = veredicto.get("pasa")
    motivo = str(veredicto.get("motivo") or "").strip()

    if pasa is None:
        errores.append(Error(
            "G2/veredicto", "La critica no trae veredicto: falta 'pasa'.",
            "El critico decide: tiene que devolver {\"veredicto\": {\"pasa\": true|false, \"motivo\": \"...\"}}."))
    elif not motivo:
        errores.append(Error(
            "G2/veredicto", "El veredicto no dice por que.",
            "Un 'pasa' sin motivo no se puede revisar, y un 'no pasa' sin motivo "
            "no le dice al corrector que tocar."))
    elif pasa is False:
        # No es un fallo del formato: es la puerta haciendo su trabajo. Va como
        # error para que el corrector reciba el motivo con la misma forma que
        # el resto de los errores del harness.
        errores.append(Error(
            "G2/criterio", motivo,
            "Corrige eso concreto y vuelve a pasar la escena por las dos lentes."))

    # --- 3. el veto de continuidad ------------------------------------------ #
    # Tambien es la decision de un agente, no una cuenta: la lente de
    # continuidad encontro una contradiccion con el canon y la escena no entra.
    # Se releva tal cual, con su cita, para que el corrector sepa que tocar.
    cont = critica.get("continuidad") or {}
    for h in (cont.get("hallazgos") or []):
        errores.append(Error(
            "G2/continuidad", "Contradice el canon: %s" % h.get("que"),
            "Corrige eso concreto. Cita: %s" % (h.get("cita") or "(sin cita)")))
    if cont.get("veto") and not (cont.get("hallazgos") or []):
        errores.append(Error(
            "G2/continuidad", "Veto de continuidad sin hallazgo declarado.",
            "La lente tiene que decir QUE contradice el canon, con su cita."))

    # --- 4. la rubrica: medida, no puerta ---------------------------------- #
    calidad = critica.get("calidad") or {}
    suma, detalle, sin_cita = 0, {}, []
    for dim in dimensiones:
        entrada = calidad.get(dim)
        if entrada is None:
            detalle[dim] = None
            continue
        nota, cita = entrada.get("nota"), entrada.get("cita")
        if nota not in cfg["niveles"]:
            errores.append(Error(
                "G2/rubrica", "'%s' trae nota %r, fuera de %s." % (dim, nota, cfg["niveles"]),
                "Solo 0, 1 o 2: son tres conductas descritas, no una escala."))
            continue
        if not (cita and str(cita).strip()):
            sin_cita.append(dim)
            continue
        detalle[dim] = nota
        suma += nota

    if sin_cita:
        errores.append(Error(
            "G2/rubrica", "Estas dimensiones puntuan sin citar el texto: %s." % ", ".join(sin_cita),
            "Toda nota exige una cita textual de la escena, el 2 incluido: sin "
            "evidencia la nota no se puede comparar con la de otra corrida."))

    maximo = 2 * len([d for d in dimensiones if detalle.get(d) is not None])
    return salida(sid, errores, {
        "puerta": "G2",
        "pasa": bool(pasa) and not errores,
        "motivo": motivo,
        "suma": suma, "maximo": maximo, "dimensiones": detalle,
        "decide": "el critico"})


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
    return emitir(evaluar(libro, sid, critica, ruta_critica=ruta), libro=libro, paso="G2")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
