"""Carga del canon, derivaciones y utilidades compartidas.

Regla del proyecto: lo que se puede calcular no se guarda. Todo lo que este
modulo deriva (edad, etapa de la relacion, estado a una fecha, techo de
palabras) NO existe en ningun archivo.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Errores
# --------------------------------------------------------------------------- #
@dataclass
class Error:
    """Un incumplimiento. El mensaje dice que esta mal y cual es la verdad;
    el arreglo dice como salir de ahi. Sin las tres cosas no es accionable."""
    regla: str
    mensaje: str
    arreglo: str

    def dict(self):
        return asdict(self)


def salida(nombre: str, errores: list[Error], extra: dict | None = None) -> dict:
    d = {"objeto": nombre, "ok": not errores, "errores": [e.dict() for e in errores]}
    if extra:
        d.update(extra)
    return d


def emitir(res: dict, destino: Path | None = None) -> int:
    texto = json.dumps(res, ensure_ascii=False, indent=2)
    if destino:
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return 0 if res["ok"] else 1


# --------------------------------------------------------------------------- #
# Carga
# --------------------------------------------------------------------------- #
def cargar_config(raiz: Path = RAIZ) -> dict:
    return yaml.safe_load((raiz / "harness" / "config.yaml").read_text(encoding="utf-8"))


def _yaml(p: Path):
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None


class Libro:
    """Todo el canon de un libro, ya cargado. Solo lectura."""

    def __init__(self, dir_libro: str | Path, raiz: Path = RAIZ):
        self.dir = Path(dir_libro).resolve()
        self.ctx = self.dir / "context"
        # El harness trae los valores por defecto; el libro puede sobreescribir
        # su forma (cuantos parrafos, cuantas escenas) sin tocar el harness.
        self.config = cargar_config(raiz)
        propio = _yaml(self.dir / "config.yaml")
        if propio:
            for seccion, valores in propio.items():
                if isinstance(valores, dict) and isinstance(self.config.get(seccion), dict):
                    self.config[seccion].update(valores)
                else:
                    self.config[seccion] = valores
        self.intake = json.loads((self.ctx / "intake.json").read_text(encoding="utf-8")) \
            if (self.ctx / "intake.json").exists() else None
        self.premise = _yaml(self.ctx / "premise.yaml") or {}
        self.epoca = _yaml(self.ctx / "epoca.yaml") or {}
        self.calendario = _yaml(self.ctx / "calendario.yaml") or {}
        self.relacion = _yaml(self.ctx / "relacion.yaml") or {}
        self.timeline = _yaml(self.ctx / "timeline.yaml") or {"escenas": []}
        self.reales = _yaml(self.ctx / "real-figures.yaml") or []
        self.personajes = {}
        d = self.ctx / "characters"
        if d.exists():
            for f in sorted(d.glob("*.yaml")):
                self.personajes[f.stem] = _yaml(f)

    # -- derivaciones ------------------------------------------------------- #
    @property
    def forma(self) -> dict:
        e = self.config["estructura"]
        ppe = e["parrafos_por_escena"] * e["lineas_por_parrafo"] * e["palabras_por_linea"]
        tot = e["capitulos"] * e["escenas_por_capitulo"]
        return {"palabras_por_escena": ppe, "escenas_totales": tot,
                "techo_palabras": ppe * tot}

    @property
    def escenas(self) -> list[dict]:
        return self.timeline.get("escenas") or []

    def escena(self, sid: str) -> dict | None:
        return next((e for e in self.escenas if e.get("id") == sid), None)

    def ruta_prosa(self, esc: dict) -> Path:
        return self.dir / "manuscript" / f"ch{esc['capitulo']:02d}" / f"{esc['id']}.md"

    @property
    def protagonistas(self) -> list[str]:
        return list(self.relacion.get("entre") or [])


# --------------------------------------------------------------------------- #
# Fechas y estado a una fecha
# --------------------------------------------------------------------------- #
def fecha(v) -> _dt.date | None:
    if isinstance(v, _dt.datetime):
        return v.date()
    if isinstance(v, _dt.date):
        return v
    if isinstance(v, str):
        try:
            return _dt.date.fromisoformat(v.strip()[:10])
        except ValueError:
            return None
    return None


def edad(nacimiento, en: _dt.date) -> int | None:
    n = fecha(nacimiento)
    if not n or not en:
        return None
    return en.year - n.year - ((en.month, en.day) < (n.month, n.day))


def estado_en(personaje: dict, en: _dt.date) -> dict:
    """El estado vigente a una fecha. No existe 'el estado actual'."""
    for tramo in personaje.get("estados") or []:
        d, h = fecha(tramo.get("desde")), fecha(tramo.get("hasta"))
        if d and d <= en and (h is None or en <= h):
            return tramo
    return {}


def sabe_en(personaje: dict, en: _dt.date) -> list[dict]:
    return [s for s in (personaje.get("sabe") or [])
            if (f := fecha(s.get("desde"))) and f <= en]


def etapa_en(relacion: dict, en: _dt.date) -> str | None:
    """La etapa de la pareja se calcula a una fecha, igual que la edad."""
    actual = None
    for tramo in relacion.get("etapas") or []:
        d = fecha(tramo.get("desde"))
        if d and d <= en:
            actual = tramo.get("etapa")
    return actual


# --------------------------------------------------------------------------- #
# Prosa: parrafos, lineas, palabras
# --------------------------------------------------------------------------- #
def parrafos(texto: str) -> list[list[str]]:
    """Un parrafo es un bloque de lineas; los bloques se separan por linea vacia."""
    bloques, actual = [], []
    for linea in texto.replace("\r\n", "\n").split("\n"):
        if linea.strip():
            actual.append(linea.strip())
        elif actual:
            bloques.append(actual)
            actual = []
    if actual:
        bloques.append(actual)
    return bloques


def palabras(linea: str) -> int:
    return len([p for p in re.split(r"\s+", linea.strip()) if p])


def contar_palabras(texto: str) -> int:
    return sum(palabras(l) for p in parrafos(texto) for l in p)


# --------------------------------------------------------------------------- #
# Texto: normalizacion para buscar menciones en prosa
# --------------------------------------------------------------------------- #
def plano(s: str) -> str:
    """Minusculas y sin tildes, para comparar menciones sin falsos negativos."""
    s = unicodedata.normalize("NFD", str(s).lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def menciona(texto: str, termino: str) -> bool:
    """Busca el termino como palabra completa, ignorando tildes y mayusculas."""
    t, x = plano(texto), plano(termino).strip()
    if not x:
        return False
    return re.search(r"(?<!\w)" + re.escape(x) + r"(?!\w)", t) is not None


def nombre_pila(personaje: dict) -> str:
    return str(personaje.get("nombre", "")).split()[0] if personaje.get("nombre") else ""


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def libro_de_argv(argv: list[str], uso: str) -> Libro:
    if len(argv) < 2:
        print(f"uso: {uso}", file=sys.stderr)
        raise SystemExit(2)
    return Libro(argv[1])
