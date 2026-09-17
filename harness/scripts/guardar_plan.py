# -*- coding: utf-8 -*-
"""Guarda en el canon lo que devuelven el researcher y el planner.

    python harness/scripts/guardar_plan.py <libro> epoca < datos.json
    python harness/scripts/guardar_plan.py <libro> beats < plan.json

Existe por la regla 2 del proyecto: **ningun agente escribe archivos**. En el
camino desatendido el YAML lo escribia `crear_novela.py`; en el camino agentico
lo escribe esto. Un agente componiendo YAML a mano mete un ':' sin comillas en
una nota larga y deja el canon ilegible, y ese fallo aparece tres pasos mas
tarde disfrazado de otra cosa.

Ademas acota **que** se puede tocar. `beats` escribe `resumen` y `beats` de las
escenas que nombra, y nada mas: ni fechas, ni presentes, ni estado. El plan se
replanifica; el canon no se toca.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]


def _leer_json() -> dict:
    crudo = sys.stdin.read().strip()
    if not crudo:
        raise SystemExit("no llego nada por stdin")
    # Tolerante con el modelo que envuelve en ``` o antepone un preambulo.
    if "```" in crudo:
        trozos = crudo.split("```")
        cuerpos = [trozos[i] for i in range(1, len(trozos), 2)]
        if cuerpos:
            crudo = max(cuerpos, key=len)
            if "\n" in crudo and len(crudo.split("\n", 1)[0].split()) <= 1:
                crudo = crudo.split("\n", 1)[1]
    i, j = crudo.find("{"), crudo.rfind("}")
    return json.loads(crudo[i:j + 1] if i != -1 else crudo)


def _escribir(ruta: Path, datos) -> None:
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")


def epoca(ctx: Path, datos: dict) -> dict:
    """La epoca y los hitos del calendario. Lo que no trae fuente no entra
    igual: de eso se encarga V13 en G0, no este script."""
    anio = datos.get("anio")
    if not anio:
        raise SystemExit("el JSON no trae 'anio'")
    _escribir(ctx / "epoca.yaml", {
        "anio": int(anio),
        "prohibido": datos.get("prohibido") or [],
        "existia": datos.get("existia") or [],
        "notas": datos.get("notas") or "",
        "fuentes": datos.get("fuentes") or []})

    cal = yaml.safe_load((ctx / "calendario.yaml").read_text(encoding="utf-8")) or {}
    cal["hitos"] = datos.get("hitos") or []
    _escribir(ctx / "calendario.yaml", cal)
    return {"ok": True, "anacronismos": len(datos.get("prohibido") or []),
            "hitos": len(cal["hitos"]), "fuentes": len(datos.get("fuentes") or [])}


def beats(ctx: Path, plan: dict) -> dict:
    """Solo `resumen` y `beats`, y solo de las escenas que el plan nombra."""
    ruta = ctx / "timeline.yaml"
    t = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    porid = {e.get("id"): e for e in (plan.get("escenas") or [])}
    puestas, ignoradas = [], []
    for esc in t.get("escenas") or []:
        nuevo = porid.pop(esc.get("id"), None)
        if nuevo and nuevo.get("beats"):
            esc["resumen"] = nuevo.get("resumen") or esc.get("resumen")
            esc["beats"] = list(nuevo["beats"])
            puestas.append(esc["id"])
    ignoradas = list(porid)
    _escribir(ruta, t)
    return {"ok": True, "planificadas": puestas,
            "ignoradas": ignoradas,
            "aviso": ("Estas escenas no existen en el timeline y no se tocaron: %s"
                      % ", ".join(ignoradas)) if ignoradas else None}


def main(argv: list) -> int:
    if len(argv) < 3 or argv[2] not in ("epoca", "beats"):
        print("uso: guardar_plan.py <libro> epoca|beats   (el JSON por stdin)",
              file=sys.stderr)
        return 2
    ctx = Path(argv[1]).resolve() / "context"
    if not ctx.exists():
        print("no existe %s" % ctx, file=sys.stderr)
        return 2
    datos = _leer_json()
    res = epoca(ctx, datos) if argv[2] == "epoca" else beats(ctx, datos)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
