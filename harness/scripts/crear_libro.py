# -*- coding: utf-8 -*-
"""Crea un libro nuevo sin preguntar nada, a partir de un JSON.

    python harness/scripts/crear_libro.py <respuestas.json>

Existe para que el ciclo pueda arrancar sin una persona delante: la UI tiene su
formulario y esto es la misma creacion con las respuestas ya decididas, las que
la skill `preparar-libro` deriva de la idea.

**No reimplementa nada**: llama a `server.crear()`, que ya es el camino que usa
la UI y que deriva con `harness/derivaciones.py`. Dos caminos para
crear un libro serian dos sitios donde se desincronizan las derivaciones.

El JSON es el mismo que manda la UI:

    {"slug": "vera-1998",
     "estructura": {"capitulos": 1, "escenas_por_capitulo": 1,
                    "parrafos_por_escena": 3, "lineas_por_parrafo": 4,
                    "palabras_por_linea": 12},
     "titulo": "...", "eje": "...",
     "prohibido": ["..."], "fuentes": ["https://..."], "notas_epoca": "...",
     "respuestas": {
       "deporte": "...", "lugar": "...", "nivel": "amateur|profesional|seleccion",
       "epoca": {"desde": "AAAA-MM-DD", "hasta": "AAAA-MM-DD"},
       "persona_a": {"nombre": "...", "nacimiento": "AAAA-MM-DD", "rol": "..."},
       "persona_b": {...},
       "encuentro": "...", "obstaculo": "...",
       "precio": {"a": "...", "b": "..."},
       "hilos": ["...", "..."]}}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "harness"))
import server  # noqa: E402


def main(argv: list) -> int:
    if len(argv) < 2:
        print("uso: crear_libro.py <respuestas.json>", file=sys.stderr)
        return 2
    datos = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    res = server.crear(datos)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
