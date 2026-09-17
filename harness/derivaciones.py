# -*- coding: utf-8 -*-
"""Las derivaciones del canon: lo que se calcula a partir de las respuestas.

Es una libreria, no un programa. La usan los dos caminos que crean un libro:
`harness/scripts/crear_libro.py` (el agentico, sin preguntas) y la UI, los dos
a traves de `server.crear()`. **Un solo sitio donde se deriva**: dos caminos
para lo mismo es como se desincronizan las reglas.

Lo que se deriva aqui no se guarda como respuesta de nadie:

- la clave de un personaje sale de su nombre;
- las cuatro etapas de la relacion se reparten sobre la ventana de la epoca;
- las fechas de las escenas se reparten sobre esa misma ventana;
- la forma del documento (`PERFILES`) fija cuantas escenas hay y el techo.

Hasta la v8.1 este archivo era ademas la entrevista de doce preguntas por
terminal. Se fue con ella: el arranque agentico deriva lo que puede de la idea
y pregunta solo lo que cambia el libro (skill `preparar-libro`).
"""
from __future__ import annotations

import datetime as dt
import unicodedata
from pathlib import Path

import yaml

PERFILES = {
    "smoke":  dict(capitulos=1, escenas_por_capitulo=1, parrafos_por_escena=3,
                   lineas_por_parrafo=4, palabras_por_linea=12),
    "relato": dict(capitulos=1, escenas_por_capitulo=8, parrafos_por_escena=12,
                   lineas_por_parrafo=5, palabras_por_linea=12),
    "novela": dict(capitulos=9, escenas_por_capitulo=5, parrafos_por_escena=15,
                   lineas_por_parrafo=5, palabras_por_linea=12),
}


# --------------------------------------------------------------------------- #
# Presentacion
# --------------------------------------------------------------------------- #
def titulo(t: str) -> None:
    print("\n" + "=" * 70 + "\n  " + t + "\n" + "=" * 70)


def nota(t: str) -> None:
    print("  " + t)


# --------------------------------------------------------------------------- #
# Preguntas con validacion al recibir
# --------------------------------------------------------------------------- #
def _pedir(etiqueta: str, ayuda: str = "") -> str:
    if ayuda:
        print("     (%s)" % ayuda)
    try:
        return input("  > %s: " % etiqueta).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\n  Cancelado. No se escribio nada.")
        raise SystemExit(1)


def texto(etiqueta: str, ayuda: str = "") -> str:
    while True:
        v = _pedir(etiqueta, ayuda)
        if v:
            return v
        print("     ! No puede quedar vacio.")


def entero(etiqueta: str, defecto: int, minimo: int = 1) -> int:
    while True:
        v = _pedir("%s [%d]" % (etiqueta, defecto))
        if not v:
            return defecto
        if v.isdigit() and int(v) >= minimo:
            return int(v)
        print("     ! Tiene que ser un numero entero >= %d." % minimo)


def opcion(etiqueta: str, opciones: list) -> str:
    print("     " + " | ".join("%d) %s" % (i + 1, o) for i, o in enumerate(opciones)))
    while True:
        v = _pedir(etiqueta)
        if v.isdigit() and 1 <= int(v) <= len(opciones):
            return opciones[int(v) - 1]
        if v in opciones:
            return v
        print("     ! Elegi un numero del 1 al %d." % len(opciones))


def fecha_iso(etiqueta: str, ayuda: str = "AAAA-MM-DD") -> dt.date:
    while True:
        v = _pedir(etiqueta, ayuda)
        try:
            return dt.date.fromisoformat(v)
        except ValueError:
            print("     ! Eso no es una fecha. Escribila como 1962-03-14.")


def rango_epoca() -> dict:
    """Acepta un ano suelto y lo expande. Una sola epoca para todo el libro."""
    while True:
        v = _pedir("Ano o rango", "un ano (1990) o dos fechas (1990-01-01 1990-12-31)")
        if re.fullmatch(r"\d{4}", v):
            return {"desde": "%s-01-01" % v, "hasta": "%s-12-31" % v}
        partes = v.replace(",", " ").split()
        if len(partes) == 2:
            try:
                a, b = (dt.date.fromisoformat(p) for p in partes)
                if a <= b:
                    return {"desde": a.isoformat(), "hasta": b.isoformat()}
                print("     ! La primera fecha tiene que ser anterior.")
                continue
            except ValueError:
                pass
        print("     ! Escribi un ano (1990) o dos fechas ISO separadas por espacio.")


def persona(cual: str) -> dict:
    return {"nombre": texto("%s - nombre y apellido" % cual),
            "nacimiento": fecha_iso("%s - fecha de nacimiento" % cual).isoformat(),
            "rol": texto("%s - que hace en ese mundo" % cual, "una linea")}


# --------------------------------------------------------------------------- #
# Derivaciones (lo que hace el planner)
# --------------------------------------------------------------------------- #
def clave(nombre: str) -> str:
    s = unicodedata.normalize("NFD", nombre.split()[0].lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def en_porcentaje(desde: dt.date, hasta: dt.date, pct: float) -> dt.date:
    return desde + dt.timedelta(days=round((hasta - desde).days * pct))


def derivar_arco(protagonista: str, epoca: dict, intake: dict, reparto: dict) -> dict:
    """Los tres actos repartidos sobre la ventana de la epoca.

    No se declara en que acto esta cada escena: se calcula por su fecha, igual
    que todo lo demas. Si manana se cambia el reparto en `config.yaml`, las
    escenas se reacomodan solas y no hay un segundo sitio que actualizar.

    El reparto por defecto es el clasico (25/50/25). No es una ley de la
    narrativa, es un punto de partida razonable que se puede mover."""
    d, h = dt.date.fromisoformat(epoca["desde"]), dt.date.fromisoformat(epoca["hasta"])
    p1 = reparto.get("planteamiento", 0.25)
    p2 = reparto.get("desarrollo", 0.50)
    return {
        "protagonista": protagonista,
        "meta": intake["meta"],                 # que quiere
        "obstaculo": intake["obstaculo"],       # que se lo impide
        "precio": intake["precio"],             # que le cuesta conseguirlo
        "actos": [
            {"acto": "planteamiento", "desde": d.isoformat()},
            {"acto": "desarrollo", "desde": en_porcentaje(d, h, p1).isoformat()},
            {"acto": "desenlace", "desde": en_porcentaje(d, h, p1 + p2).isoformat()},
        ]}


def derivar_personaje(p: dict, epoca: dict) -> dict:
    """Sin campo 'edad'. `nacimiento` es opcional desde la v9.0: la edad dejo de
    ser una regla dura y solo se muestra al escritor si el canon la trae."""
    ficha = {"nombre": p["nombre"], "rol": p.get("rol", ""),
             "estados": [{"desde": epoca["desde"], "hasta": epoca["hasta"],
                          "que": "en actividad"}],
             "eventos_unicos": [],
             "sabe": []}
    if p.get("nacimiento"):
        ficha["nacimiento"] = p["nacimiento"]
    return ficha


def derivar_timeline(n_cap: int, n_esc: int, epoca: dict, lugar: str,
                     presentes: list) -> dict:
    """Las escenas repartidas sobre la epoca, de la primera a la ultima.

    La ultima cae al final de la ventana para que caiga en el desenlace: un
    libro cuya ultima escena no esta en el tercer acto no puede cerrar."""
    d, h = dt.date.fromisoformat(epoca["desde"]), dt.date.fromisoformat(epoca["hasta"])
    total = n_cap * n_esc
    pasos = [0.95] if total == 1 else [0.05 + (0.90 * i / (total - 1)) for i in range(total)]
    escenas = []
    for i, pct in enumerate(pasos):
        cierra = []
        if total == 1:
            cierra = ["H1", "H2"]
        elif i == total - 2:
            cierra = ["H1"]
        elif i == total - 1:
            cierra = ["H2"]
        escenas.append({
            "id": "S%03d" % (i + 1),
            "capitulo": i // n_esc + 1,
            "fecha": en_porcentaje(d, h, pct).isoformat(),
            "lugar": lugar,
            "presentes": list(presentes),
            "resumen": "(por planificar)",
            "estado": "planificada",
            "cierra": cierra,
            "flashback": False,
            "beats": [],
        })
    return {"escenas": escenas}


def escribir_yaml(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")


# --------------------------------------------------------------------------- #
