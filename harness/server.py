# -*- coding: utf-8 -*-
"""API local sobre el harness. No reimplementa nada: llama a los scripts.

    python harness/server.py            # http://127.0.0.1:8770

Sirve la UI de ui/dist si esta construida. Los endpoints son un envoltorio
delgado: la fuente de verdad sigue siendo el canon en disco y las puertas
siguen siendo los mismos scripts que corren en la terminal.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

RAIZ = Path(__file__).resolve().parents[1]
SCRIPTS = RAIZ / "harness" / "scripts"
LIBROS = RAIZ / "books"
LOGS = RAIZ / "harness" / ".logs"
UI = RAIZ / "ui" / "dist"

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(RAIZ))
import yaml  # noqa: E402
from common import Libro, contar_palabras, cargar_config  # noqa: E402
import traza as TZ  # noqa: E402
import nuevo_libro as NL  # noqa: E402

PUERTO = 8770
_corriendo: dict[str, subprocess.Popen] = {}


# --------------------------------------------------------------------------- #
# Lecturas
# --------------------------------------------------------------------------- #
def derivar(est: dict, tol: dict) -> dict:
    """La misma cuenta que hace el harness. Vive aqui solo para que la UI pueda
    mostrarla mientras se escribe el formulario, sin crear nada."""
    lineas = est["parrafos_por_escena"] * est["lineas_por_parrafo"]
    ppe = lineas * est["palabras_por_linea"]
    ppe_max = lineas * (est["palabras_por_linea"] + tol.get("palabras_por_linea", 0))
    total = est["capitulos"] * est["escenas_por_capitulo"]
    return {"lineas_por_escena": lineas, "palabras_por_escena": ppe,
            "palabras_por_escena_max": ppe_max, "escenas_totales": total,
            "palabras_libro": ppe * total, "techo_palabras": ppe_max * total}


def estado_libro(slug: str) -> dict:
    try:
        L = Libro(LIBROS / slug)
    except Exception as e:
        return {"slug": slug, "error": str(e)}
    escenas = []
    escritas = 0
    for e in L.escenas:
        ruta = L.ruta_prosa(e)
        n = contar_palabras(ruta.read_text(encoding="utf-8")) if ruta.exists() else 0
        if e.get("estado") == "aprobada":
            escritas += n
        escenas.append({"id": e.get("id"), "capitulo": e.get("capitulo"),
                        "fecha": str(e.get("fecha")), "estado": e.get("estado"),
                        "cierra": e.get("cierra") or [], "palabras": n,
                        "tiene_prosa": ruta.exists(),
                        "tiene_critica": ruta.with_suffix(".critique.json").exists()})
    return {"slug": slug,
            "titulo": L.premise.get("titulo") or slug,
            "eje": L.premise.get("eje"),
            "deporte": L.premise.get("deporte"),
            "epoca": {k: str(v) for k, v in (L.premise.get("epoca") or {}).items()},
            "forma": L.forma, "escenas": escenas, "palabras_escritas": escritas,
            "aprobadas": sum(1 for e in L.escenas if e.get("estado") == "aprobada"),
            "corriendo": slug in _corriendo and _corriendo[slug].poll() is None}


def listar() -> list:
    if not LIBROS.exists():
        return []
    return [estado_libro(d.name) for d in sorted(LIBROS.iterdir())
            if (d / "context" / "premise.yaml").exists()]


def script(nombre: str, *args) -> dict:
    r = subprocess.run([sys.executable, str(SCRIPTS / nombre), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=RAIZ)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "errores": [{"regla": nombre,
                                          "mensaje": (r.stdout or r.stderr).strip()[:400],
                                          "arreglo": "revisa el script a mano"}]}


# --------------------------------------------------------------------------- #
# Escrituras
# --------------------------------------------------------------------------- #
def crear(datos: dict) -> dict:
    """Escribe el canon de un libro nuevo. Las mismas derivaciones que usa
    nuevo_libro.py en la terminal: no hay dos caminos para lo mismo."""
    slug = (datos.get("slug") or "").strip().lower().replace(" ", "-")
    if not slug or not slug.replace("-", "").replace("_", "").isalnum():
        return {"ok": False, "error": "El nombre de carpeta solo admite letras, numeros y guiones."}
    destino = LIBROS / slug
    if destino.exists():
        return {"ok": False, "error": "Ya existe books/%s." % slug}

    est = datos["estructura"]
    r = datos["respuestas"]
    ka, kb = NL.clave(r["persona_a"]["nombre"]), NL.clave(r["persona_b"]["nombre"])
    ctx = destino / "context"
    (ctx / "characters").mkdir(parents=True, exist_ok=True)
    (destino / "manuscript").mkdir(parents=True, exist_ok=True)
    (destino / "reports").mkdir(parents=True, exist_ok=True)

    (ctx / "intake.json").write_text(json.dumps(
        {"version": 1, "fecha": datos.get("fecha", ""), "respuestas": r,
         "pendiente_investigar": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    NL.escribir_yaml(destino / "config.yaml", {"estructura": est})
    NL.escribir_yaml(ctx / "premise.yaml", {
        "eje": datos.get("eje") or "%s en %s" % (r["persona_a"]["rol"], r["epoca"]["desde"][:4]),
        "titulo": datos.get("titulo") or slug.replace("-", " ").title(),
        "deporte": r["deporte"], "lugar": r["lugar"], "epoca": r["epoca"],
        "estilo": "Tercera persona, pasado.",
        "pregunta_dramatica": "Que renuncia %s: %s. Y %s: %s." % (
            r["persona_a"]["nombre"].split()[0], r["precio"]["a"],
            r["persona_b"]["nombre"].split()[0], r["precio"]["b"]),
        "hilos": [{"id": "H1", "que": r["hilos"][0]}, {"id": "H2", "que": r["hilos"][1]}]})
    NL.escribir_yaml(ctx / "epoca.yaml", {
        "anio": int(r["epoca"]["desde"][:4]),
        "prohibido": datos.get("prohibido") or [],
        "existia": [], "notas": datos.get("notas_epoca") or "",
        "fuentes": datos.get("fuentes") or []})
    NL.escribir_yaml(ctx / "calendario.yaml", {
        "deporte": r["deporte"], "nivel": r["nivel"],
        "temporada": r["epoca"], "hitos": []})
    NL.escribir_yaml(ctx / "relacion.yaml", NL.derivar_relacion(ka, kb, r["epoca"], r))
    NL.escribir_yaml(ctx / "characters" / (ka + ".yaml"), NL.derivar_personaje(r["persona_a"], r["epoca"]))
    NL.escribir_yaml(ctx / "characters" / (kb + ".yaml"), NL.derivar_personaje(r["persona_b"], r["epoca"]))
    NL.escribir_yaml(ctx / "real-figures.yaml", [])
    NL.escribir_yaml(ctx / "timeline.yaml", NL.derivar_timeline(
        est["capitulos"], est["escenas_por_capitulo"], r["epoca"], r["lugar"], [ka, kb]))
    (ctx / "voz.md").write_text(
        (RAIZ / "harness" / "voz-base.md").read_text(encoding="utf-8"), encoding="utf-8")

    return {"ok": True, "slug": slug, "g0": script("validate_canon.py", "books/" + slug)}


def lanzar(slug: str) -> dict:
    """Corre el ciclo en segundo plano. La UI hace polling del log: el proceso
    tarda minutos y no tiene sentido bloquear una peticion HTTP."""
    if slug in _corriendo and _corriendo[slug].poll() is None:
        return {"ok": False, "error": "Ya esta corriendo."}
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / (slug + ".log")
    fh = log.open("w", encoding="utf-8")
    _corriendo[slug] = subprocess.Popen(
        [sys.executable, str(RAIZ / "crear_novela.py"), "books/" + slug],
        stdout=fh, stderr=subprocess.STDOUT, cwd=RAIZ)
    return {"ok": True, "slug": slug}


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):            # sin ruido en la consola
        pass

    def _responder(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, datos, codigo: int = 200) -> None:
        self._responder(codigo, json.dumps(datos, ensure_ascii=False, default=str).encode("utf-8"),
                        "application/json; charset=utf-8")

    def do_OPTIONS(self):
        self._responder(204, b"", "text/plain")

    def do_GET(self):
        ruta = unquote(urlparse(self.path).path)
        partes = [p for p in ruta.split("/") if p]

        if ruta == "/api/config":
            cfg = cargar_config(RAIZ)
            return self._json({"estructura": cfg["estructura"], "tolerancia": cfg["tolerancia"],
                               "rubrica": cfg["rubrica"], "ciclo": cfg["ciclo"],
                               "genero": cfg["genero"], "perfiles": NL.PERFILES})
        if ruta == "/api/books":
            return self._json(listar())
        if len(partes) == 3 and partes[:2] == ["api", "books"]:
            return self._json(estado_libro(partes[2]))
        if len(partes) == 4 and partes[:2] == ["api", "books"] and partes[3] == "log":
            log = LOGS / (partes[2] + ".log")
            texto = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
            vivo = partes[2] in _corriendo and _corriendo[partes[2]].poll() is None
            return self._json({"log": texto[-20000:], "corriendo": vivo})
        if len(partes) == 4 and partes[:2] == ["api", "books"] and partes[3] == "traza":
            eventos = TZ.leer(LIBROS / partes[2])
            return self._json({"eventos": eventos, "resumen": TZ.resumen(eventos),
                               "corriendo": partes[2] in _corriendo
                               and _corriendo[partes[2]].poll() is None})
        if len(partes) == 4 and partes[:2] == ["api", "books"] and partes[3] == "novela":
            p = LIBROS / partes[2] / "manuscript" / "novela.md"
            return self._json({"texto": p.read_text(encoding="utf-8") if p.exists() else ""})

        # estatico: la UI construida
        rel = ruta.lstrip("/") or "index.html"
        archivo = UI / rel
        if not archivo.is_file():
            archivo = UI / "index.html"
        if archivo.is_file():
            tipos = {".html": "text/html; charset=utf-8", ".js": "text/javascript",
                     ".css": "text/css", ".svg": "image/svg+xml", ".json": "application/json"}
            return self._responder(200, archivo.read_bytes(),
                                   tipos.get(archivo.suffix, "application/octet-stream"))
        return self._json({"error": "No encontrado. Construi la UI con: cd ui && npm run build"}, 404)

    def do_POST(self):
        ruta = unquote(urlparse(self.path).path)
        partes = [p for p in ruta.split("/") if p]
        largo = int(self.headers.get("Content-Length") or 0)
        try:
            datos = json.loads(self.rfile.read(largo) or b"{}")
        except json.JSONDecodeError:
            return self._json({"ok": False, "error": "JSON invalido"}, 400)

        if ruta == "/api/books":
            try:
                return self._json(crear(datos))
            except Exception as e:
                return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, 400)
        if len(partes) == 4 and partes[:2] == ["api", "books"]:
            slug, accion = partes[2], partes[3]
            if accion == "run":
                return self._json(lanzar(slug))
            if accion == "reset":
                TZ.Traza(LIBROS / slug).borrar()
                return self._json(script("run_scene.py", "books/" + slug, "reset"))
            if accion == "validar":
                return self._json(script("validate_book.py", "books/" + slug))
        return self._json({"error": "No encontrado"}, 404)


def main() -> int:
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Handler)
    print("Story-Maker  ->  http://127.0.0.1:%d" % PUERTO)
    print("UI construida:" , "si" if (UI / "index.html").exists() else "no (cd ui && npm run build)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nchau")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
