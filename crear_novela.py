# -*- coding: utf-8 -*-
"""Crea una novela entera: te pregunta, investiga, escribe, critica y compila.

    python crear_novela.py                 # pregunta todo y arranca
    python crear_novela.py books/<slug>    # sigue un libro ya empezado

Encadena las dos mitades del sistema. Los pasos que tienen una respuesta
correcta son scripts (las puertas, el canon resuelto, el recuento). Los que
piden criterio son llamadas a `claude -p`, cada una con contexto limpio.

El ciclo lo lleva este archivo, no el modelo: un LLM iterando cuarenta veces
deriva. Claude escribe y critica; el codigo decide si pasa.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8")
    except Exception:
        pass

RAIZ = Path(__file__).resolve().parent
SCRIPTS = RAIZ / "harness" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import yaml  # noqa: E402

TIMEOUT = 600

# En Windows `claude` es un shim .cmd: hay que resolverlo, porque pasar el
# prompt por shell rompe el comillado en cuanto tiene comillas o saltos.
CLAUDE = shutil.which("claude") or "claude"


# --------------------------------------------------------------------------- #
# Presentacion
# --------------------------------------------------------------------------- #
def titulo(t: str) -> None:
    print("\n" + "=" * 70 + "\n  " + t + "\n" + "=" * 70)


def paso(t: str) -> None:
    print("\n--- " + t)


def nota(t: str) -> None:
    print("  " + t)


# --------------------------------------------------------------------------- #
# Las dos mitades
# --------------------------------------------------------------------------- #
def script(nombre: str, *args) -> dict:
    """Un paso con respuesta correcta. Devuelve su JSON."""
    r = subprocess.run([sys.executable, str(SCRIPTS / nombre), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=RAIZ)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "errores": [{"regla": nombre,
                                          "mensaje": (r.stdout or r.stderr or "").strip()[:300],
                                          "arreglo": "revisa el script a mano"}]}


def claude(prompt: str, herramientas: str = "Read,Write,Edit") -> str:
    """Un paso que pide criterio. Contexto limpio en cada llamada: por eso los
    criticos no se ven entre si ni saben en que intento van."""
    t0 = time.time()
    try:
        cmd = [CLAUDE, "-p", "--permission-mode", "acceptEdits", "--add-dir", str(RAIZ)]
        if herramientas:
            cmd += ["--allowedTools", herramientas]
        # El prompt va por STDIN, nunca como argumento: en Windows `claude` es un
        # shim .cmd y cmd.exe corta el argumento en el primer salto de linea. Con
        # argv el modelo recibia un prompt mutilado o vacio, contestaba "no me
        # llego ninguna escena", y esa queja terminaba escrita como si fuera prosa.
        r = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=RAIZ, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        nota("    (se paso de %ds)" % TIMEOUT)
        return ""
    nota("    claude: %s en %.0fs" % ("ok" if r.returncode == 0 else "fallo", time.time() - t0))
    if r.returncode != 0 and r.stderr:
        nota("    " + r.stderr.strip()[:200])
    return r.stdout or ""


def limpiar(texto: str) -> str:
    """Parseo tolerante: los modelos envuelven en ``` y anteponen preambulos.

    El archivo lo escribe el script, no el modelo. Eso quita de en medio toda
    la superficie de permisos y deja un solo dueno del estado: el codigo."""
    t = texto.strip()
    if "```" in t:
        trozos = t.split("```")
        # Se queda con el bloque mas largo: es la prosa, no el comentario.
        cuerpos = [trozos[i] for i in range(1, len(trozos), 2)]
        if cuerpos:
            t = max(cuerpos, key=len)
            if "\n" in t and len(t.split("\n", 1)[0].split()) <= 1:
                t = t.split("\n", 1)[1]          # quita el lenguaje del fence
    return t.strip() + "\n"


def extraer_json(texto: str) -> dict:
    t = texto.strip()
    if "```" in t:
        t = limpiar(t)
    i, j = t.find("{"), t.rfind("}")
    if i == -1 or j == -1:
        return {}
    # Del bloque mas grande hacia adentro: si el modelo dejo texto con llaves
    # alrededor, el primer intento falla y el siguiente acierta.
    for fin in range(j, i, -1):
        if t[fin] != "}":
            continue
        try:
            return json.loads(t[i:fin + 1])
        except json.JSONDecodeError:
            continue
    return {}


def claude_json(prompt: str, que: str, intentos: int = 2, herramientas: str = "") -> dict:
    """El modelo emite evidencia estructurada; si no sale parseable, se repite.

    Parseo tolerante y reintento: es mas barato que abrir la puerta a ciegas."""
    for n in range(1, intentos + 1):
        d = extraer_json(claude(prompt, herramientas=herramientas))
        if d:
            return d
        nota("    (%s no devolvio JSON valido, intento %d/%d)" % (que, n, intentos))
    return {}


def leer_yaml(p: Path):
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def escribir_yaml(p: Path, d) -> None:
    p.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")


def contexto_de(slug: str, sid: str) -> str:
    r = subprocess.run([sys.executable, str(SCRIPTS / "resolver_canon.py"), slug, sid],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=RAIZ)
    return r.stdout.strip()


def errores_de(res: dict) -> str:
    return "\n".join("- [%s] %s\n  ARREGLO: %s" % (e["regla"], e["mensaje"], e["arreglo"])
                     for e in res.get("errores", []))


# --------------------------------------------------------------------------- #
# Fase 1: investigar
# --------------------------------------------------------------------------- #
def investigar(slug: str, libro: Path) -> None:
    titulo("INVESTIGAR  -  la epoca")
    premise = leer_yaml(libro / "context" / "premise.yaml")
    epoca = premise["epoca"]
    anio = str(epoca["desde"])[:4]

    # Si la epoca ya esta escrita, no se toca. Investigar es lo mas lento y lo
    # menos determinista del arranque: un libro con el canon hecho a mano tiene
    # que poder ir derecho al ciclo de redaccion.
    ya = leer_yaml(libro / "context" / "epoca.yaml") or {}
    if ya.get("prohibido"):
        nota("Ya esta escrita (%d anacronismos, %d fuentes). No la toco."
             % (len(ya["prohibido"]), len(ya.get("fuentes") or [])))
        return

    paso("researcher: %s, %s" % (premise.get("deporte"), anio))
    datos = claude_json(
        "Investiga %s en %s (%s) y devolve los datos.\n\n"
        "1. `prohibido`: cosas que NO existian en %s y un escritor descuidado "
        "podria colar (tecnologia, objetos, costumbres, lenguaje).\n"
        "2. `existia`: 3 a 5 cosas caracteristicas del ano, con su fecha de "
        "aparicion.\n"
        "3. `notas`: como se seguia un partido y como era la vida cotidiana.\n"
        "4. `hitos`: 3 a 5 fechas reales de la temporada de %s de ese ano, con "
        "peso 1 a 5 segun cuanto pesan. TODAS entre %s y %s.\n"
        "5. `fuentes`: las URLs en las que te apoyas.\n\n"
        "Regla dura: lo que no podes sostener con una fuente no entra. No "
        "inventes fechas; si no sabes una, no la pongas.\n\n"
        'Formato exacto:\n{"anio": %s, "prohibido": ["..."], '
        '"existia": [{"que": "...", "desde": "AAAA-MM-DD"}], "notas": "...", '
        '"hitos": [{"fecha": "AAAA-MM-DD", "que": "...", "peso": 3}], '
        '"fuentes": ["https://..."]}\n\n'
        "RESPONDE CON EL JSON Y NADA MAS."
        % (premise.get("deporte"), anio, premise.get("lugar"), anio,
           premise.get("deporte"), epoca["desde"], epoca["hasta"], anio),
        "epoca", intentos=2, herramientas="WebSearch,WebFetch")

    if datos:
        # El YAML lo escribe el script. Un agente escribiendo YAML a mano mete
        # un ':' sin comillas y rompe el canon entero.
        escribir_yaml(libro / "context" / "epoca.yaml", {
            "anio": int(anio),
            "prohibido": datos.get("prohibido") or [],
            "existia": datos.get("existia") or [],
            "notas": datos.get("notas") or "",
            "fuentes": datos.get("fuentes") or []})
        cal = leer_yaml(libro / "context" / "calendario.yaml")
        cal["hitos"] = datos.get("hitos") or []
        escribir_yaml(libro / "context" / "calendario.yaml", cal)
        nota("  %d anacronismos, %d hitos, %d fuentes"
             % (len(datos.get("prohibido") or []), len(datos.get("hitos") or []),
                len(datos.get("fuentes") or [])))
        return

    nota("  La investigacion no devolvio datos; el libro sigue sin epoca.")
    return


# --------------------------------------------------------------------------- #
# Fase 2: planificar
# --------------------------------------------------------------------------- #
def planificar(slug: str, libro: Path) -> None:
    titulo("PLANIFICAR  -  las escenas que los hilos piden")
    t = leer_yaml(libro / "context" / "timeline.yaml")
    sin_plan = [e for e in t["escenas"] if not e.get("beats")]
    if not sin_plan:
        nota("Ya estaba planificado.")
        return

    premise = leer_yaml(libro / "context" / "premise.yaml")
    relacion = leer_yaml(libro / "context" / "relacion.yaml")
    paso("planner: %d escenas" % len(sin_plan))
    pendientes = [{"id": e["id"], "fecha": str(e.get("fecha")), "lugar": e.get("lugar"),
                   "cierra": e.get("cierra") or []} for e in sin_plan]

    plan = claude_json(
        "Planifica las escenas de una novela romantica deportiva. NO escribas prosa.\n\n"
        "Pregunta dramatica: %s\n"
        "Hilos: %s\n"
        "Se conocen asi: %s\n"
        "Los separa: %s\n"
        "Arco de la pareja (la etapa se calcula por fecha): %s\n\n"
        "Escenas a planificar:\n%s\n\n"
        "Para cada una: `resumen` es una frase de que pasa; `beats` son 3 momentos "
        "concretos. Respeta la etapa de la relacion que corresponde a su fecha, y "
        "lo que dice `cierra`: una escena que cierra un hilo tiene que resolverlo "
        "de verdad, no mencionarlo de pasada.\n\n"
        'Formato exacto:\n{"escenas": [{"id": "S001", "resumen": "...", '
        '"beats": ["...", "...", "..."]}]}\n\n'
        "RESPONDE CON EL JSON Y NADA MAS."
        % (premise.get("pregunta_dramatica"),
           json.dumps(premise.get("hilos"), ensure_ascii=False),
           relacion.get("encuentro"), relacion.get("obstaculo"),
           json.dumps(relacion.get("etapas"), ensure_ascii=False, default=str),
           json.dumps(pendientes, ensure_ascii=False, indent=1)),
        "el plan")

    # El timeline lo escribe el script, y solo estos dos campos: el resto del
    # canon no se toca desde aqui.
    porid = {e.get("id"): e for e in (plan.get("escenas") or [])}
    puestas = 0
    for esc in t["escenas"]:
        nuevo = porid.get(esc["id"])
        if nuevo and nuevo.get("beats"):
            esc["resumen"] = nuevo.get("resumen") or esc.get("resumen")
            esc["beats"] = list(nuevo["beats"])
            puestas += 1
    escribir_yaml(libro / "context" / "timeline.yaml", t)
    nota("  %d de %d escenas planificadas" % (puestas, len(sin_plan)))


# --------------------------------------------------------------------------- #
# Fase 3: el ciclo, escena por escena
# --------------------------------------------------------------------------- #
def escribir_escena(slug: str, sid: str, ctx: str, capitulo: int, correccion: str = "") -> bool:
    """El modelo devuelve la prosa; el archivo lo escribe ESTE script.

    Pedirle que escriba el archivo el mismo funciona a veces y a veces reporta
    'permiso pendiente' sin escribir nada. Sacando la escritura de su lado
    desaparece toda esa superficie, y queda un solo dueno del estado."""
    ruta = "%s/manuscript/ch%02d/%s.md" % (slug, capitulo, sid)
    destino = RAIZ / ruta
    voz = RAIZ / slug / "context" / "voz.md"
    voz = voz.read_text(encoding="utf-8").strip() if voz.exists() else ""

    if correccion:
        actual = destino.read_text(encoding="utf-8") if destino.exists() else "(no hay)"
        orden = ("Corregi esta escena y devolvela ENTERA, ya corregida.\n\n"
                 "=== LA ESCENA ACTUAL ===\n%s\n\n"
                 "TOCA SOLO lo que senalan estos errores. Lo que no aparece aca ya "
                 "paso las puertas y se queda igual:\n\n%s\n\n"
                 "El canon manda: si la escena lo contradice, se cambia la escena, "
                 "nunca el canon. Un arreglo que rompe la forma no es un arreglo."
                 % (actual, correccion))
    else:
        orden = "Escribi una escena de novela."

    salida = claude(
        "%s\n\n"
        "=== VOZ (asi suena este libro) ===\n%s\n\n"
        "=== CANON, ya resuelto a la fecha. No lo reinterpretes ===\n%s\n\n"
        "La forma la comprueba un script y es obligatoria: exactamente los "
        "parrafos y las lineas que dice el canon de arriba, separados por linea en "
        "blanco, cada linea con las palabras que pide.\n\n"
        "RESPONDE CON LA PROSA Y NADA MAS: sin titulo, sin encabezado, sin "
        "comentarios, sin preambulo, sin bloques de codigo. La primera linea de tu "
        "respuesta es la primera linea de la escena." % (orden, voz, ctx),
        herramientas="")

    prosa = limpiar(salida)
    if len(prosa.split()) < 20:
        nota("    no devolvio prosa. Dijo: %s" % " ".join(salida.split())[:150])
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(prosa, encoding="utf-8")
    return True


RUBRICA = """| dimension | 0 | 1 | 2 |
| conflicto | no pasa nada: termina como empezo | hay tension, se resuelve sin costo | algo cambia y tiene precio |
| dialogo | se cuentan cosas que ambos ya saben | funcional, todos hablan igual | cada uno habla distinto, lo que callan pesa |
| concrecion | se nombran emociones (decir que estaba triste) | mezcla mostrar y explicar | la accion y el detalle fisico llevan el peso |
| frescura | cliche estructural o frases hechas | alguna muletilla o repeticion | limpio |
| quimica | los dos estan y no pasa nada entre ellos | hay tension pero la relacion queda igual | algo se mueve, o se frena a proposito y se nota |"""


def criticar(slug: str, sid: str, ctx: str, capitulo: int) -> None:
    """Las dos lentes, cada una en su llamada: contexto aislado de verdad.

    Ninguna decide si la escena pasa; devuelven evidencia puntuada y el JSON lo
    arma este script, igual que la prosa."""
    d = RAIZ / slug / "manuscript" / ("ch%02d" % capitulo)
    escena = (d / (sid + ".md")).read_text(encoding="utf-8")
    comun = ("No reescribis y NO decidis si la escena pasa: un script suma y "
             "compara contra el umbral.\n\n=== LA ESCENA ===\n%s\n\n"
             "=== CANON ===\n%s\n\n" % (escena, ctx))
    cierre = ("RESPONDE CON EL JSON Y NADA MAS: sin preambulo, sin explicacion, "
              "sin bloque de codigo.")

    cont = claude_json(
        "Sos la lente de CONTINUIDAD de un harness de novelas. Buscas lo que un "
        "script no puede formalizar: objetos o personas que aparecen de la nada, "
        "cambios de caracter sin causa, alguien que actua sabiendo algo que el "
        "canon no le da, y que la escena no adelante ni retroceda la etapa de la "
        "relacion.\n\n" + comun +
        "Cada hallazgo lleva CITA TEXTUAL de la escena. Si no encontras nada, "
        "veto false y lista vacia: es el resultado normal, no fuerces hallazgos. "
        "Ojo: un hallazgo cuenta como veto aunque pongas veto false, asi que no "
        "listes como hallazgo algo que no sea una contradiccion real con el canon.\n\n"
        'Formato exacto:\n{"continuidad": {"veto": false, "hallazgos": '
        '[{"que": "...", "cita": "..."}]}}\n\n' + cierre, "continuidad")

    cal = claude_json(
        "Sos la lente de CALIDAD de un harness de novelas. Puntuas una rubrica de "
        "cinco dimensiones, cada una 0, 1 o 2. No elegis un numero en una escala: "
        "senalas cual de las tres descripciones encaja.\n\n" + RUBRICA + "\n\n" + comun +
        "TODA nota, el 2 incluido, exige CITA TEXTUAL de la escena: sin cita la "
        "dimension no cuenta y la puerta no abre. Un 2 sin evidencia es una "
        "afirmacion, no una observacion, asi que cita el fragmento que te hizo "
        "ponerlo. Si en la escena no estan los dos protagonistas, quimica va en "
        "null entero.\n\n"
        'Formato exacto:\n{"calidad": {"conflicto": {"nota": 2, "cita": "..."}, '
        '"dialogo": {"nota": 1, "cita": "..."}, "concrecion": {...}, '
        '"frescura": {...}, "quimica": {...}}}\n\n' + cierre, "calidad")

    critica = {"escena": sid}
    critica.update(cont or {"continuidad": {"veto": False, "hallazgos": []}})
    critica.update(cal or {})
    if not cal:
        nota("    (la lente de calidad no devolvio JSON valido)")
    (d / (sid + ".critique.json")).write_text(
        json.dumps(critica, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def producir(slug: str, libro: Path) -> bool:
    titulo("PRODUCIR  -  escribir, validar, criticar, corregir")
    cfg = leer_yaml(RAIZ / "harness" / "config.yaml")["ciclo"]
    intentos_max = cfg["intentos_max"]

    while True:
        nxt = script("run_scene.py", slug, "next")
        accion = nxt.get("accion")
        if accion in ("cerrar", "revisar"):
            return accion == "cerrar"
        if accion == "parar":
            nota(nxt.get("motivo", ""))
            return False

        sid = nxt["escena"]
        capitulo = nxt.get("capitulo", 1)
        ctx = contexto_de(slug, sid)
        paso("%s" % sid)

        correccion = ""
        for intento in range(1, intentos_max + 1):
            nota("  intento %d/%d" % (intento, intentos_max))
            if not escribir_escena(slug, sid, ctx, capitulo, correccion):
                correccion = ""
                continue

            g1 = script("validate_scene.py", slug, sid)
            if not g1["ok"]:
                nota("    G1 cierra: %d errores de hecho" % len(g1["errores"]))
                correccion = errores_de(g1)
                continue
            nota("    G1 abre (%s palabras)" % g1.get("palabras"))

            criticar(slug, sid, ctx, capitulo)
            g2 = script("gate_scene.py", slug, sid)
            if not g2["ok"]:
                nota("    G2 cierra: rubrica %s/%s, veto %s"
                     % (g2.get("suma"), g2.get("maximo"), g2.get("veto_continuidad")))
                correccion = errores_de(g2)
                continue
            nota("    G2 abre: rubrica %s/%s" % (g2.get("suma"), g2.get("maximo")))

            ap = script("run_scene.py", slug, "aprobar", sid)
            if ap.get("ok"):
                nota("    APROBADA")
                if ap.get("puerta_G3"):
                    nota("    G3: %s" % ap["puerta_G3"])
                if not (ap.get("regulador") or {}).get("cabe", True):
                    nota("    AVISO: el final ya no cabe. Hay que contraer el plan.")
                break
            correccion = errores_de(ap)
        else:
            nota("  %d intentos sin pasar. Paro y te pregunto." % intentos_max)
            return False


# --------------------------------------------------------------------------- #
def main(argv: list) -> int:
    if len(argv) > 1:
        slug = argv[1].replace("\\", "/").rstrip("/")
    else:
        import nuevo_libro
        if nuevo_libro.main() != 0:
            return 1
        libros = sorted((RAIZ / "books").iterdir(), key=lambda p: p.stat().st_mtime)
        slug = "books/" + libros[-1].name

    libro = RAIZ / slug
    if not (libro / "context" / "intake.json").exists():
        print("No encuentro %s/context/intake.json" % slug)
        return 1

    investigar(slug, libro)

    titulo("G0  -  el canon")
    g0 = script("validate_canon.py", slug)
    if not g0["ok"]:
        nota("NO ABRE. No se escribe una sola linea de prosa:")
        print(errores_de(g0))
        return 1
    nota("ABRE. Techo del libro: %s palabras." % g0["forma"]["techo_palabras"])

    planificar(slug, libro)
    termina = producir(slug, libro)

    titulo("G4  -  las tres condiciones del final")
    g4 = script("validate_book.py", slug)
    for k, v in (g4.get("condiciones") or {}).items():
        nota("%-16s %s" % (k, v["ok"]))
    if not g4.get("termina"):
        nota("El libro todavia no termina:")
        print(errores_de(g4))
        return 1

    comp = script("compilar.py", slug)
    titulo("LISTO")
    nota("%s/%s  -  %s palabras" % (slug, comp.get("ruta"), comp.get("palabras")))
    print()
    print((libro / "manuscript" / "novela.md").read_text(encoding="utf-8"))
    return 0 if termina else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
