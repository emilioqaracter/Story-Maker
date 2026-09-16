# -*- coding: utf-8 -*-
"""La traza del ciclo: que hizo cada agente, cuanto tardo y que fallo.

Un evento por linea en `books/<slug>/reports/traza.jsonl`. Es append-only y se
escribe en el momento, no al final: si el ciclo se corta a la mitad, lo que
paso hasta ahi queda igual.

Existe porque el log en texto respondia "que paso" y no "por que tardo tanto",
"cuanto costo" ni "que fallo en el intento 2". Un sistema que no se puede mirar
por dentro se depura reescribiendo prompts, que es justo lo que no queremos.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path


class Traza:
    """Append-only. Nunca lee para escribir: dos procesos pueden anotar a la vez."""

    def __init__(self, dir_libro: Path):
        self.ruta = Path(dir_libro) / "reports" / "traza.jsonl"
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self._t0 = {}

    def abrir(self, clave: str) -> None:
        self._t0[clave] = time.time()

    def evento(self, paso: str, **campos) -> dict:
        ms = campos.pop("ms", None)
        if ms is None and paso in self._t0:
            ms = int((time.time() - self._t0.pop(paso)) * 1000)
        ev = {"t": datetime.now().isoformat(timespec="seconds"), "paso": paso,
              "ms": ms or 0, **campos}
        with self.ruta.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")
        return ev

    def borrar(self) -> None:
        if self.ruta.exists():
            self.ruta.unlink()


def uso(salida: dict) -> dict:
    """Los tokens tal como los reporta `claude -p --output-format json`.

    Se guardan separados porque no cuestan lo mismo: escribir cache es caro y
    leerla es barato, y sumarlos en un solo numero esconde justo eso."""
    u = (salida or {}).get("usage") or {}
    return {"entrada": u.get("input_tokens", 0),
            "salida": u.get("output_tokens", 0),
            "cache_escrita": u.get("cache_creation_input_tokens", 0),
            "cache_leida": u.get("cache_read_input_tokens", 0)}


def leer(dir_libro: Path) -> list:
    ruta = Path(dir_libro) / "reports" / "traza.jsonl"
    if not ruta.exists():
        return []
    eventos = []
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            eventos.append(json.loads(linea))
        except json.JSONDecodeError:
            continue          # una linea a medias de un corte no tira la traza
    return eventos


def resumen(eventos: list) -> dict:
    """Los totales que importan: tiempo, tokens, plata y cuanto se rehizo."""
    tot = {"llamadas": 0, "ms_modelo": 0, "ms_total": 0, "costo": 0.0,
           "entrada": 0, "salida": 0, "cache_escrita": 0, "cache_leida": 0,
           "puertas_cerradas": 0, "reintentos": 0, "por_agente": {}}
    vistos = set()
    for e in eventos:
        tot["ms_total"] += e.get("ms", 0)
        if e.get("tipo") == "modelo":
            tot["llamadas"] += 1
            tot["ms_modelo"] += e.get("ms", 0)
            tot["costo"] += e.get("costo") or 0.0
            for k in ("entrada", "salida", "cache_escrita", "cache_leida"):
                tot[k] += (e.get("tokens") or {}).get(k, 0)
            a = tot["por_agente"].setdefault(
                e.get("agente", "?"), {"llamadas": 0, "ms": 0, "costo": 0.0, "salida": 0})
            a["llamadas"] += 1
            a["ms"] += e.get("ms", 0)
            a["costo"] += e.get("costo") or 0.0
            a["salida"] += (e.get("tokens") or {}).get("salida", 0)
        if e.get("tipo") == "puerta" and e.get("ok") is False:
            tot["puertas_cerradas"] += 1
        if e.get("escena") and (e.get("intento") or 0) > 1:
            clave = (e["escena"], e["intento"])
            if clave not in vistos:
                vistos.add(clave)
                tot["reintentos"] += 1
    tot["costo"] = round(tot["costo"], 4)
    return tot
