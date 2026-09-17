# -*- coding: utf-8 -*-
"""Manda a Langfuse lo que paso en un libro, ya ordenado.

    python harness/scripts/reportar.py books/<slug>

El hook de Claude Code ya manda cada turno con sus llamadas y su coste, pero
eso cuenta la conversacion, no la novela: para saber si la escena 3 costo dos
intentos hay que leer veinte tool calls. Esto manda **la otra vista**, la del
libro: una traza por escena, con sus intentos, sus puertas y la rubrica como
scores.

Se lee del disco, no de la memoria de nadie: `reports/traza.jsonl` (lo que
dijeron las puertas) y los `.critique.json` de cada escena (lo que dijeron las
lentes). Por eso se puede correr cuando sea, incluso sobre un libro de la
semana pasada, y da lo mismo quien condujera el ciclo.

**Es opcional y no puede romper nada.** Sin claves en `.env`, sin el paquete
`langfuse` o sin red, no hace nada y devuelve ok.

Como queda en Langfuse:

    sesion = el libro (todas sus corridas juntas)
      traza producir-escena   una por escena, nombrada igual siempre
        span intentar-escena  uno por intento
          evaluator validar-hechos   G1, con sus errores
          evaluator evaluar-rubrica  G2, con el veredicto del critico
        scores: veredicto, rubrica, las cinco dimensiones, intentos
      traza validar-canon / validar-libro / compilar-novela
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from traza import leer, resumen  # noqa: E402

# Como se llama cada puerta en Langfuse. Los nombres son una API: los apuntan
# los dashboards y los evaluadores, asi que no llevan nada variable dentro.
NOMBRE = {"G0": "validar-canon", "G1": "validar-hechos", "G2": "evaluar-rubrica",
          "G3": "evaluar-capitulo", "G4": "validar-libro", "compilar": "compilar-novela"}
# Las puertas juzgan (`evaluator`); compilar cambia el estado del libro (`tool`).
TIPO = {"compilar": "tool"}
DE_ESCENA = {"G1", "G2"}


def cargar_env(ruta: Path | None = None) -> None:
    """Lee `.env` sin pisar lo que ya venga del entorno."""
    ruta = ruta or (RAIZ / ".env")
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if v:
                os.environ.setdefault(k.strip(), v)


def _cliente():
    """El cliente de Langfuse, o None si no se puede. Nunca levanta."""
    cargar_env()
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return None
    try:
        # Se importa DESPUES del .env: el cliente lee las claves al construirse.
        from langfuse import get_client
        cli = get_client()
        return cli if cli.auth_check() else None
    except Exception:                               # noqa: BLE001
        return None


def criticas(dir_libro: Path) -> dict:
    """Lo que dijeron las lentes de cada escena, por id."""
    fuera = {}
    for p in sorted((dir_libro / "manuscript").rglob("*.critique.json")):
        try:
            fuera[p.stem.replace(".critique", "")] = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
    return fuera


def reportar(dir_libro: Path) -> dict:
    eventos = leer(dir_libro)
    if not eventos:
        return {"ok": True, "enviado": 0, "motivo": "no hay traza que mandar"}

    cli = _cliente()
    if cli is None:
        return {"ok": True, "enviado": 0,
                "motivo": "sin claves de Langfuse en .env: no mando nada"}

    from langfuse import propagate_attributes
    slug = dir_libro.name
    crit = criticas(dir_libro)

    # Los eventos de una escena van juntos; el resto son trazas sueltas.
    por_escena, sueltos = {}, []
    for e in eventos:
        sid = e.get("escena")
        if e.get("paso") in DE_ESCENA and sid and sid.startswith("S"):
            por_escena.setdefault(sid, []).append(e)
        elif e.get("tipo") == "puerta":
            sueltos.append(e)

    enviados = 0
    with propagate_attributes(session_id="books/%s" % slug,
                              tags=["story-maker", slug],
                              metadata={"libro": slug}):
        for sid, evs in sorted(por_escena.items()):
            with cli.start_as_current_observation(
                    as_type="span", name="producir-escena",
                    input={"escena": sid},
                    metadata={"libro": slug, "escena": sid}) as tr:
                intento, abierto = 0, None
                for e in evs:
                    if e["paso"] == "G1":
                        intento += 1
                    with cli.start_as_current_observation(
                            as_type="evaluator", name=NOMBRE.get(e["paso"], e["paso"]),
                            input={"escena": sid, "intento": intento},
                            metadata={"libro": slug, "escena": sid, "intento": intento}) as ev:
                        ev.update(output={"ok": e.get("ok"), "errores": e.get("errores") or []},
                                  level=None if e.get("ok") else "WARNING",
                                  status_message=None if e.get("ok") else "la puerta no abre")
                    abierto = e.get("ok")

                c = crit.get(sid) or {}
                ver = c.get("veredicto") or {}
                tr.update(output={"aprobada": bool(abierto), "intentos": intento,
                                  "veredicto": ver.get("motivo")})
                _puntuar(cli, "intentos", intento, comentario="intentos hasta cerrar")
                if ver.get("pasa") is not None:
                    _puntuar(cli, "veredicto", bool(ver["pasa"]), tipo="BOOLEAN",
                             comentario=ver.get("motivo") or "")
                suma = 0
                for dim, v in (c.get("calidad") or {}).items():
                    if isinstance(v, dict) and isinstance(v.get("nota"), int):
                        _puntuar(cli, "rubrica-" + dim, v["nota"], comentario=v.get("cita") or "")
                        suma += v["nota"]
                if c.get("calidad"):
                    _puntuar(cli, "rubrica", suma, comentario="suma de las cinco dimensiones")
                enviados += 1

        for e in sueltos:
            with cli.start_as_current_observation(
                    as_type=TIPO.get(e["paso"], "evaluator"),
                    name=NOMBRE.get(e["paso"], e["paso"]),
                    input={"libro": slug},
                    metadata={"libro": slug}) as ev:
                ev.update(output={"ok": e.get("ok"), "errores": e.get("errores") or []},
                          level=None if e.get("ok") else "WARNING")
            enviados += 1

    try:
        cli.flush()          # sin esto, un script corto termina antes de enviar
    except Exception:        # noqa: BLE001
        pass
    return {"ok": True, "enviado": enviados, "escenas": len(por_escena),
            "resumen": resumen(eventos)}


def _puntuar(cli, nombre: str, valor, tipo: str = "NUMERIC", comentario: str = "") -> None:
    try:
        cli.score_current_trace(name=nombre, value=valor, data_type=tipo,
                                comment=(comentario or None))
    except Exception:                               # noqa: BLE001
        pass                                        # un score perdido no es un fallo


def main(argv: list) -> int:
    if len(argv) < 2:
        print("uso: reportar.py books/<slug>", file=sys.stderr)
        return 2
    res = reportar(Path(argv[1]).resolve())
    print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
