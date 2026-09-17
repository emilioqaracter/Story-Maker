"""G0 - el canon. V21 (intake completo y tipado) y V13 (una sola epoca).

Corre una vez, tras la entrevista y la investigacion. Si esto falla no se
escribe una sola linea de prosa.

    python harness/scripts/validate_canon.py books/<slug>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ERRORES_CARGA, Error, Libro, emitir, fecha,  # noqa: E402
                    libro_de_argv, salida)

# Campos que la entrevista (SPEC §3) tiene que dejar completos.
ESQUEMA = {
    "deporte": "texto",
    "epoca": "rango",
    "lugar": "texto",
    "nivel": "texto",
    "protagonista": "persona",
    "meta": "texto",
    "obstaculo": "texto",
    "precio": "texto",
    "hilos": "lista2",
}


def _tipo_ok(valor, tipo: str) -> str | None:
    """Devuelve el motivo del fallo, o None si el valor encaja."""
    if valor is None or valor == "" or valor == [] or valor == {}:
        return "esta vacio"
    if tipo == "texto":
        return None if isinstance(valor, str) and valor.strip() else "no es texto"
    if tipo == "rango":
        if not isinstance(valor, dict):
            return "no es un rango"
        if not fecha(valor.get("desde")) or not fecha(valor.get("hasta")):
            return "desde/hasta no son fechas ISO (AAAA-MM-DD)"
        return None if fecha(valor["desde"]) <= fecha(valor["hasta"]) else "desde es posterior a hasta"
    if tipo == "persona":
        if not isinstance(valor, dict):
            return "no es una persona"
        # `nacimiento` dejo de ser obligatorio en la v9.0: la edad ya no es una
        # regla dura. Si viene, tiene que ser una fecha; si no viene, no pasa nada.
        faltan = [k for k in ("nombre", "rol") if not valor.get(k)]
        if faltan:
            return "le faltan campos: " + ", ".join(faltan)
        if valor.get("nacimiento") and not fecha(valor["nacimiento"]):
            return "nacimiento no es una fecha ISO"
        return None
    if tipo == "lista2":
        if not isinstance(valor, list):
            return "no es una lista"
        return None if len(valor) == 2 else f"tiene {len(valor)} hilos y hacen falta 2"
    return None


def v21_intake(libro: Libro) -> list[Error]:
    if libro.intake is None:
        return [Error("V21", "No existe context/intake.json.",
                      "Corre la entrevista (agente interviewer) antes de validar el canon.")]
    resp = libro.intake.get("respuestas") or {}
    errores = []
    for campo, tipo in ESQUEMA.items():
        motivo = _tipo_ok(resp.get(campo), tipo)
        if motivo:
            errores.append(Error(
                "V21",
                f"El campo '{campo}' del intake {motivo}.",
                f"Volve a preguntar '{campo}' en la entrevista; no lo rellenes a mano."))
    pendientes = libro.intake.get("pendiente_investigar") or []
    if pendientes:
        errores.append(Error(
            "V21",
            "Quedan campos marcados para investigar: " + ", ".join(map(str, pendientes)) + ".",
            "El researcher tiene que resolverlos antes de G0."))
    return errores


def v13_una_epoca(libro: Libro) -> list[Error]:
    rango = (libro.premise.get("epoca") or {})
    desde, hasta = fecha(rango.get("desde")), fecha(rango.get("hasta"))
    if not desde or not hasta:
        return [Error("V13", "premise.yaml no declara una epoca con desde/hasta.",
                      "Completa premise.epoca con dos fechas ISO.")]
    errores = []

    # Una epoca vacia pasaba todas las comprobaciones por no tener nada que
    # contradecir, y dejaba el libro entrar a produccion con V8 sin lista de
    # anacronismos y V20 sin hitos. Una puerta que no puede cerrarse nunca no
    # es una puerta.
    if not (libro.epoca.get("prohibido") or []):
        errores.append(Error(
            "V13", "epoca.yaml no trae ningun anacronismo en 'prohibido'.",
            "El researcher no investigo, o no guardo lo que encontro. Sin esa "
            "lista, V8 no tiene nada que vetar y la epoca es decorativa."))
    # Las fuentes dejaron de ser obligatorias en la v9.0. Lo que se le pide a
    # la epoca es que sea COHERENTE, no exhaustiva: que en 1800 no haya moviles
    # y en 2010 si haya internet. Para eso no hace falta una bibliografia, y
    # exigirla empujaba al researcher a buscar la fecha exacta de cada partido.

    anio = libro.epoca.get("anio")
    if anio is not None and not (desde.year <= int(anio) <= hasta.year):
        errores.append(Error(
            "V13", f"epoca.yaml dice anio {anio}, fuera de {desde.year}-{hasta.year}.",
            "Una sola epoca para todo el mundo narrado: corrige epoca.yaml o premise.epoca."))

    # 'existia' puede empezar antes (un Walkman de 1979 existe en 1990), pero
    # nada puede empezar despues del final de la epoca.
    for item in libro.epoca.get("existia") or []:
        d = fecha(item.get("desde"))
        if d and d > hasta:
            errores.append(Error(
                "V13", f"'{item.get('que')}' aparece con desde {d}, posterior a la epoca.",
                "Descartalo: el researcher se fue de rango."))

    return errores


def v16_arco(libro: Libro) -> list[Error]:
    """El arco de tres actos: completo, en orden y con las escenas repartidas.

    Sustituye a la comprobacion de las cinco etapas de pareja. Lo que se
    comprueba ya no es una relacion que avanza, sino que la historia del
    protagonista tenga sus tres tiempos y que ninguno se quede vacio: un acto
    sin escenas no es un acto, es una etiqueta."""
    orden = libro.config["genero"]["actos"]
    arco = libro.arco
    errores = []

    if not arco.get("protagonista"):
        errores.append(Error("V16", "arco.yaml no dice quien es el protagonista.",
                             "La novela es de uno: declara `protagonista` con su clave."))
    elif arco["protagonista"] not in libro.personajes:
        errores.append(Error(
            "V16", "El protagonista '%s' no tiene ficha en context/characters/." % arco["protagonista"],
            "Crea su YAML o corrige la clave en arco.yaml."))

    for campo, que in (("meta", "que quiere"), ("obstaculo", "que se lo impide"),
                       ("precio", "que le cuesta")):
        if not str(arco.get(campo) or "").strip():
            errores.append(Error(
                "V16", "arco.yaml no declara '%s' (%s)." % (campo, que),
                "Sin las tres cosas no hay historia: hay alguien haciendo deporte."))

    tramos = arco.get("actos") or []
    if not tramos:
        errores.append(Error("V16", "arco.yaml no declara actos.",
                             "Los tres actos se derivan de la epoca: planteamiento, desarrollo, desenlace."))
        return errores

    vistos, anterior = [], None
    for tramo in tramos:
        acto, f = tramo.get("acto"), fecha(tramo.get("desde"))
        if acto not in orden:
            errores.append(Error("V16", "Acto desconocido: '%s'." % acto,
                                 "Usa uno de genero.actos: " + ", ".join(orden)))
            continue
        if vistos and orden.index(acto) <= orden.index(vistos[-1]):
            errores.append(Error(
                "V16", "El arco va de '%s' a '%s': retrocede o repite." % (vistos[-1], acto),
                "Los tres actos van en orden y una sola vez."))
        if f and anterior and f <= anterior:
            errores.append(Error(
                "V16", "El acto '%s' empieza en %s, no despues del anterior (%s)." % (acto, f, anterior),
                "Las fechas del arco son estrictamente crecientes."))
        vistos.append(acto)
        anterior = f or anterior

    faltan = [a for a in orden if a not in vistos]
    if faltan:
        errores.append(Error("V16", "Al arco le faltan actos: %s." % ", ".join(faltan),
                             "Los tres tienen que estar: sin desenlace no hay novela."))

    # Un acto sin escenas: el plan no lo cubre. Solo se exige cuando hay
    # escenas suficientes: un documento de una escena no puede tener tres
    # actos, y pedirselo seria una regla que no se puede cumplir.
    if len(libro.escenas) >= len(orden) and not faltan:
        por_acto = {}
        for esc in libro.escenas:
            por_acto.setdefault(libro.acto_de(esc), []).append(esc["id"])
        vacios = [a for a in orden if not por_acto.get(a)]
        if vacios:
            errores.append(Error(
                "V16", "Ningun escena cae en: %s." % ", ".join(vacios),
                "Corre mas escenas, o mueve sus fechas: cada acto necesita al menos una."))
    return errores


def v16_arco_res(libro: Libro) -> list[Error]:
    """Alias de `v16_arco` con nombre propio para los tests y para quien lea la
    traza: dice que devuelve una lista de errores, no un booleano."""
    return v16_arco(libro)


def plan_cabe(libro: Libro) -> list[Error]:
    """G0 tambien comprueba que el plan quepa: si no cabe, se sabe antes de escribir."""
    forma = libro.forma
    n = len(libro.escenas)
    if not n:
        return [Error("G0", "El timeline no tiene escenas.", "El planner tiene que planificar antes de G0.")]
    necesarias = n * forma["palabras_por_escena_max"]
    if necesarias > forma["techo_palabras"]:
        return [Error(
            "G0",
            f"El plan pide {n} escenas ({necesarias} palabras) y el techo es {forma['techo_palabras']}.",
            "O sobran hilos, o el perfil de config.yaml es chico. Se decide ahora, no escribiendo.")]
    return []


def main(argv: list[str]) -> int:
    libro = libro_de_argv(argv, "validate_canon.py books/<slug>")
    errores = list(ERRORES_CARGA)
    if not errores:
        errores = v21_intake(libro) + v13_una_epoca(libro) + v16_arco(libro) + plan_cabe(libro)
    extra = {"forma": libro.forma,
             "protagonista": libro.protagonista,
             "actos": {a: [e["id"] for e in libro.escenas if libro.acto_de(e) == a]
                       for a in libro.config["genero"]["actos"]}}
    return emitir(salida("canon", errores, extra), libro=libro, paso="G0")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
