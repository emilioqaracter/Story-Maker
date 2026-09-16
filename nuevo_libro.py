# -*- coding: utf-8 -*-
"""Crea una novela nueva: te pregunta todo y escribe el canon.

    python nuevo_libro.py

Primero la forma del documento (cuantos parrafos, cuantas lineas), despues las
doce preguntas del genero. Vos no escribis YAML a mano: es donde entran los
datos malos.

Las preguntas son fijas y cada respuesta se valida al recibirla. Solo se
pregunta lo que solo vos podes decidir: lo verificable es del researcher, lo
derivable es del planner.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8")
    except Exception:
        pass

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "harness" / "scripts"))
import yaml  # noqa: E402

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


def derivar_relacion(a: str, b: str, epoca: dict, intake: dict) -> dict:
    """Las cinco etapas repartidas por la epoca. La ruptura siempre despues de
    la intimidad, y la union al final: es la promesa del genero."""
    d, h = dt.date.fromisoformat(epoca["desde"]), dt.date.fromisoformat(epoca["hasta"])
    reparto = [("desconocidos", 0.0), ("atraccion", 0.20), ("intimidad", 0.45),
               ("ruptura", 0.65), ("union", 0.85)]
    return {"entre": [a, b],
            "encuentro": intake["encuentro"],
            "obstaculo": intake["obstaculo"],
            "etapas": [{"etapa": e, "desde": en_porcentaje(d, h, p).isoformat()}
                       for e, p in reparto]}


def derivar_personaje(p: dict, epoca: dict) -> dict:
    """Sin campo 'edad': se deriva de nacimiento."""
    return {"nombre": p["nombre"], "nacimiento": p["nacimiento"], "rol": p["rol"],
            "estados": [{"desde": epoca["desde"], "hasta": epoca["hasta"], "que": "en actividad"}],
            "eventos_unicos": [],
            "sabe": []}


def derivar_timeline(n_cap: int, n_esc: int, epoca: dict, lugar: str, presentes: list) -> dict:
    """Las escenas que los hilos piden, repartidas por la epoca. La ultima cae
    despues de la union, para que V18 pueda cerrar el libro."""
    d, h = dt.date.fromisoformat(epoca["desde"]), dt.date.fromisoformat(epoca["hasta"])
    total = n_cap * n_esc
    pasos = [0.95] if total == 1 else [0.10 + (0.85 * i / (total - 1)) for i in range(total)]
    escenas = []
    for i, pct in enumerate(pasos):
        cierra = []
        if i == total - 2:
            cierra = ["H1"]
        if i == total - 1:
            cierra = ["H1", "H2"] if total == 1 else ["H2"]
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
def main() -> int:
    titulo("STORY-MAKER  -  una novela nueva")
    nota("Te voy a preguntar dos cosas: que forma tiene el documento")
    nota("y de que va la historia. El YAML lo escribo yo.")

    # ---------------- el libro ---------------- #
    titulo("EL LIBRO")
    while True:
        slug = texto("Nombre corto para la carpeta", "ej: marco-1990, sin espacios")
        slug = re.sub(r"[^a-z0-9-]+", "-", clave(slug) if " " in slug else slug.lower()).strip("-")
        destino = RAIZ / "books" / slug
        if not destino.exists():
            break
        print("     ! Ya existe books/%s. Elegi otro nombre." % slug)

    # ---------------- la forma ---------------- #
    titulo("LA FORMA DEL DOCUMENTO")
    nota("De estos numeros sale todo lo demas: cuantas escenas, y el techo de")
    nota("palabras del libro. No se declaran en ningun lado, se calculan.")
    print()
    perfil = opcion("Perfil", ["smoke (prueba, 1 escena)", "relato", "novela", "personalizado"])
    clave_perfil = perfil.split()[0]

    if clave_perfil == "personalizado":
        print()
        est = dict(
            capitulos=entero("Capitulos", 1),
            escenas_por_capitulo=entero("Escenas por capitulo", 3),
            parrafos_por_escena=entero("Parrafos por escena", 3),
            lineas_por_parrafo=entero("Lineas por parrafo", 4),
            palabras_por_linea=entero("Palabras por linea", 12),
        )
    else:
        est = dict(PERFILES[clave_perfil])
        print()
        for k, v in est.items():
            nota("%-22s %s" % (k, v))

    ppe = est["parrafos_por_escena"] * est["lineas_por_parrafo"] * est["palabras_por_linea"]
    total_esc = est["capitulos"] * est["escenas_por_capitulo"]
    print()
    nota("Derivado (no se guarda, se calcula):")
    nota("  palabras por escena  %d  =  %d x %d x %d"
         % (ppe, est["parrafos_por_escena"], est["lineas_por_parrafo"], est["palabras_por_linea"]))
    nota("  escenas en total     %d" % total_esc)
    nota("  TECHO del libro      %d palabras" % (ppe * total_esc))

    # ---------------- las doce preguntas ---------------- #
    titulo("LA HISTORIA  -  doce preguntas")
    nota("Solo lo que solo vos podes decidir. Lo que se puede averiguar lo")
    nota("busca el researcher; lo que se puede calcular lo deriva el planner.")

    print("\n  [1/12] El mundo")
    deporte = texto("Que deporte")
    epoca = rango_epoca()
    lugar = texto("Donde", "ciudad o pais real")
    nivel = opcion("A que nivel se compite", ["amateur", "profesional", "seleccion"])

    print("\n  [5/12] La pareja")
    pa = persona("Primera persona")
    pb = persona("Segunda persona")

    print("\n  [9/12] Lo que los une y lo que los separa")
    encuentro = texto("Como se cruzan por primera vez", "una frase")
    nota("Sin obstaculo no hay romance, hay dos personas simpaticas.")
    obstaculo = texto("QUE LOS SEPARA", "una frase")
    nota("'Acaban juntos?' ya sabemos que si. La pregunta es que les cuesta.")
    precio_a = texto("Que tiene que perder %s" % pa["nombre"].split()[0])
    precio_b = texto("Que tiene que perder %s" % pb["nombre"].split()[0])

    print("\n  [12/12] Lo demas que esta en juego")
    hilo1 = texto("Hilo 1", "ademas de la relacion")
    hilo2 = texto("Hilo 2")

    # ---------------- escribir ---------------- #
    ka, kb = clave(pa["nombre"]), clave(pb["nombre"])
    ctx = destino / "context"
    (ctx / "characters").mkdir(parents=True, exist_ok=True)
    (destino / "manuscript").mkdir(parents=True, exist_ok=True)
    (destino / "reports").mkdir(parents=True, exist_ok=True)

    intake = {"version": 1, "fecha": dt.date.today().isoformat(),
              "respuestas": {"deporte": deporte, "epoca": epoca, "lugar": lugar, "nivel": nivel,
                             "persona_a": pa, "persona_b": pb,
                             "encuentro": encuentro, "obstaculo": obstaculo,
                             "precio": {"a": precio_a, "b": precio_b},
                             "hilos": [hilo1, hilo2]},
              "pendiente_investigar": []}
    (ctx / "intake.json").write_text(json.dumps(intake, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")

    escribir_yaml(destino / "config.yaml", {"estructura": est})

    escribir_yaml(ctx / "premise.yaml", {
        "eje": "%s en %s" % (pa["rol"], epoca["desde"][:4]),
        "titulo": slug.replace("-", " ").title(),
        "deporte": deporte, "lugar": lugar, "epoca": epoca,
        "estilo": "Tercera persona, pasado.",
        "pregunta_dramatica": "Que renuncia %s: %s. Y %s: %s."
                              % (pa["nombre"].split()[0], precio_a, pb["nombre"].split()[0], precio_b),
        "hilos": [{"id": "H1", "que": hilo1}, {"id": "H2", "que": hilo2}]})

    escribir_yaml(ctx / "epoca.yaml", {
        "anio": int(epoca["desde"][:4]),
        "prohibido": [],
        "existia": [],
        "notas": "PENDIENTE: lo completa el agente researcher.",
        "fuentes": []})

    escribir_yaml(ctx / "calendario.yaml", {
        "deporte": deporte, "nivel": nivel,
        "temporada": epoca, "hitos": []})

    escribir_yaml(ctx / "relacion.yaml",
                  derivar_relacion(ka, kb, epoca, intake["respuestas"]))
    escribir_yaml(ctx / "characters" / (ka + ".yaml"), derivar_personaje(pa, epoca))
    escribir_yaml(ctx / "characters" / (kb + ".yaml"), derivar_personaje(pb, epoca))
    escribir_yaml(ctx / "real-figures.yaml", [])

    # La voz arranca como copia del registro del genero. La muestra concreta la
    # fija el ciclo al aprobar la primera escena; hasta entonces el escritor
    # tiene al menos el registro, y no se frena por un archivo que falta.
    base = RAIZ / "harness" / "voz-base.md"
    (ctx / "voz.md").write_text(base.read_text(encoding="utf-8"), encoding="utf-8")
    escribir_yaml(ctx / "timeline.yaml",
                  derivar_timeline(est["capitulos"], est["escenas_por_capitulo"],
                                   epoca, lugar, [ka, kb]))

    # ---------------- G0 ---------------- #
    titulo("G0  -  el canon")
    r = subprocess.run([sys.executable, str(RAIZ / "harness" / "scripts" / "validate_canon.py"),
                        "books/" + slug],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=RAIZ)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(r.stdout or r.stderr)
        return 1
    if d["ok"]:
        nota("ABRE. El canon esta completo y el plan cabe bajo el techo.")
    else:
        nota("NO ABRE:")
        for e in d["errores"]:
            nota("  [%s] %s" % (e["regla"], e["mensaje"]))
            nota("        -> %s" % e["arreglo"])

    titulo("LISTO  -  books/" + slug)
    nota("Se escribieron %d escenas planificadas y el canon entero." % total_esc)
    print()
    nota("Lo que falta, y por que no lo puede hacer este script:")
    nota("  1. epoca.yaml y calendario.yaml estan vacios. Los llena el agente")
    nota("     'researcher', que necesita buscar y citar fuentes.")
    nota("  2. La prosa la escribe el agente 'escribir-escena'.")
    nota("  3. La rubrica la puntuan los dos criticos.")
    print()
    nota("Mientras tanto ya podes correr:")
    nota("  python harness/scripts/run_scene.py books/%s next" % slug)
    nota("  python harness/scripts/resolver_canon.py books/%s S001" % slug)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
