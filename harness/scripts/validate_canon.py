"""G0 - el canon. V21 (intake completo y tipado) y V13 (una sola epoca).

Corre una vez, tras la entrevista y la investigacion. Si esto falla no se
escribe una sola linea de prosa.

    python harness/scripts/validate_canon.py books/<slug>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ERRORES_CARGA, Error, Libro, emitir, etapa_en, fecha,  # noqa: E402
                    libro_de_argv, salida)

# Campos que la entrevista (SPEC §3) tiene que dejar completos.
ESQUEMA = {
    "deporte": "texto",
    "epoca": "rango",
    "lugar": "texto",
    "nivel": "texto",
    "persona_a": "persona",
    "persona_b": "persona",
    "encuentro": "texto",
    "obstaculo": "texto",
    "precio": "par",
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
        faltan = [k for k in ("nombre", "nacimiento", "rol") if not valor.get(k)]
        if faltan:
            return "le faltan campos: " + ", ".join(faltan)
        return None if fecha(valor["nacimiento"]) else "nacimiento no es una fecha ISO"
    if tipo == "par":
        if not isinstance(valor, dict) or not valor.get("a") or not valor.get("b"):
            return "necesita 'a' y 'b'"
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
    elif not (libro.epoca.get("fuentes") or []):
        errores.append(Error(
            "V13", "epoca.yaml trae datos pero ninguna fuente.",
            "Lo que no trae fuente no entra en el canon: es la misma regla que "
            "ya valia para las personas reales."))

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

    for hito in (libro.calendario.get("hitos") or []):
        f = fecha(hito.get("fecha"))
        if f and not (desde <= f <= hasta):
            errores.append(Error(
                "V13", f"El hito '{hito.get('que')}' cae en {f}, fuera de la epoca.",
                "El calendario deportivo tiene que caer dentro de premise.epoca."))
    return errores


def v16_arco(libro: Libro) -> list[Error]:
    """El arco declarado tiene que seguir el orden del genero, sin saltos."""
    orden = libro.config["genero"]["etapas_relacion"]
    tramos = libro.relacion.get("etapas") or []
    if not tramos:
        return [Error("V16", "relacion.yaml no declara etapas.",
                      "El planner deriva el arco del encuentro y el obstaculo del intake.")]
    errores, anterior_idx, anterior_fecha = [], None, None
    for tramo in tramos:
        etapa, f = tramo.get("etapa"), fecha(tramo.get("desde"))
        if etapa not in orden:
            errores.append(Error("V16", f"Etapa desconocida: '{etapa}'.",
                                 "Usa una de genero.etapas_relacion: " + ", ".join(orden)))
            continue
        idx = orden.index(etapa)
        if anterior_idx is not None:
            if idx <= anterior_idx:
                errores.append(Error(
                    "V16", f"La relacion va de '{orden[anterior_idx]}' a '{etapa}': retrocede o repite.",
                    "El arco avanza; para retroceder hace falta una ruptura declarada."))
            elif idx > anterior_idx + 1:
                errores.append(Error(
                    "V16", f"La relacion salta de '{orden[anterior_idx]}' a '{etapa}'.",
                    f"Falta la etapa '{orden[anterior_idx + 1]}': se avanza de a una."))
        if f and anterior_fecha and f <= anterior_fecha:
            errores.append(Error(
                "V16", f"La etapa '{etapa}' empieza en {f}, no despues de la anterior ({anterior_fecha}).",
                "Las fechas del arco son estrictamente crecientes."))
        anterior_idx, anterior_fecha = idx, f or anterior_fecha
    return errores


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
             "etapa_final_declarada": etapa_en(libro.relacion, fecha(
                 (libro.premise.get("epoca") or {}).get("hasta")))}
    return emitir(salida("canon", errores, extra))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
