# -*- coding: utf-8 -*-
"""Escenas-trampa: un error plantado por regla, y la regla que debe cazarlo.

Es el fixture del que habla el SPEC: sin LLM, sin red, sin gastar un token.
Si una regla no tiene su trampa aqui, no esta comprobada.

    python -m pytest tests -q
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "harness" / "scripts"))

from common import Libro  # noqa: E402
import gate_scene as G  # noqa: E402
import validate_book as B  # noqa: E402
import validate_canon as C  # noqa: E402
import validate_scene as V  # noqa: E402

ORIGEN = RAIZ / "books" / "marco-1990"
SID = "S001"


# --------------------------------------------------------------------------- #
# Andamio
# --------------------------------------------------------------------------- #
@pytest.fixture
def dir_libro(tmp_path):
    """Una copia del libro de ejemplo, en estado conocido.

    Normaliza la escena a 'aprobada': los tests no pueden depender de si
    alguien corrio el ciclo antes, o pasan segun el dia."""
    destino = tmp_path / "libro"
    shutil.copytree(ORIGEN, destino)
    p = destino / "context" / "timeline.yaml"
    t = yaml.safe_load(p.read_text(encoding="utf-8"))
    t["escenas"][0]["estado"] = "aprobada"
    p.write_text(yaml.safe_dump(t, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return destino


def libro(dir_libro) -> Libro:
    return Libro(dir_libro)


def escribir_yaml(dir_libro: Path, rel: str, datos) -> None:
    (dir_libro / "context" / rel).write_text(
        yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")


def leer_yaml(dir_libro: Path, rel: str):
    return yaml.safe_load((dir_libro / "context" / rel).read_text(encoding="utf-8"))


def escribir_prosa(dir_libro: Path, texto: str) -> None:
    (dir_libro / "manuscript" / "ch01" / (SID + ".md")).write_text(texto, encoding="utf-8")


def prosa(dir_libro: Path) -> str:
    return (dir_libro / "manuscript" / "ch01" / (SID + ".md")).read_text(encoding="utf-8")


def reglas(res) -> set:
    """Las reglas que fallaron. Acepta el JSON de un validador o la lista de
    Error que devuelve una regla suelta."""
    lista = res["errores"] if isinstance(res, dict) else res
    return {(e["regla"] if isinstance(e, dict) else e.regla) for e in lista}


def reglas_escena(dir_libro: Path) -> set:
    return reglas(V.validar(libro(dir_libro), SID))


# --------------------------------------------------------------------------- #
# El caso bueno: todo verde
# --------------------------------------------------------------------------- #
def test_el_fixture_pasa_las_cuatro_puertas(dir_libro):
    L = libro(dir_libro)
    assert V.validar(L, SID)["ok"], "G1 deberia abrir con el libro tal cual"
    critica = json.loads((dir_libro / "manuscript" / "ch01" / (SID + ".critique.json")).read_text("utf-8"))
    assert G.evaluar(L, SID, critica)["ok"], "G2 deberia abrir"
    errores = (B.v10_hilos_cierran(L) + B.v11_hilos_declarados(L) + B.v12_techo(L)
               + B.v17_tres_actos(L) + B.v18_desenlace(L))
    assert not errores, [e.mensaje for e in errores]
    assert all(c["ok"] for c in B.condiciones(L).values())


def test_la_forma_derivada_es_la_del_perfil_v1(dir_libro):
    assert libro(dir_libro).forma == {
        "palabras_por_escena": 144,      # 3 x 4 x 12, el objetivo al escribir
        "palabras_por_escena_max": 180,  # 3 x 4 x 15, lo que V15 tolera
        "escenas_totales": 1,
        "techo_palabras": 180}           # el techo presupuesta el maximo


# --------------------------------------------------------------------------- #
# Hechos (V1-V9)
# --------------------------------------------------------------------------- #
def test_v1_fecha_fuera_de_epoca(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    t["escenas"][0]["fecha"] = "1991-02-01"
    escribir_yaml(dir_libro, "timeline.yaml", t)
    assert "V1" in reglas_escena(dir_libro)


def test_v2_el_capitulo_retrocede(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    previa = copy.deepcopy(t["escenas"][0])
    previa.update({"id": "S000", "fecha": "1990-12-01", "cierra": []})
    t["escenas"].insert(0, previa)
    escribir_yaml(dir_libro, "timeline.yaml", t)
    assert "V2" in reglas_escena(dir_libro)


def test_v2_el_flashback_declarado_no_es_un_error(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    previa = copy.deepcopy(t["escenas"][0])
    previa.update({"id": "S000", "fecha": "1990-12-01", "cierra": []})
    t["escenas"].insert(0, previa)
    t["escenas"][1]["flashback"] = True
    escribir_yaml(dir_libro, "timeline.yaml", t)
    assert "V2" not in reglas_escena(dir_libro)




def test_v5_un_evento_unico_se_narra_dos_veces(dir_libro):
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Afuera la cancha ya estaba llena y el ruido entraba igual.",
        "Se rompió otra vez, igual que en agosto, y la cancha quedó muda."))
    assert "V5" in reglas_escena(dir_libro)


def test_v6_hace_algo_que_su_estado_impide(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    t["escenas"][0]["fecha"] = "1990-09-10"          # tramo lesionado
    escribir_yaml(dir_libro, "timeline.yaml", t)
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Nadie lo había llamado para la final, y esta vez él no preguntó.",
        "Marco entrenó toda la mañana y después se quedó pateando al arco."))
    assert "V6" in reglas_escena(dir_libro)



def test_v8_anacronismo_de_la_lista_prohibida(dir_libro):
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Sofía entró con la carpeta bajo el brazo y cerró la puerta.",
        "Sofía entró mirando el celular y cerró la puerta sin levantar la vista."))
    assert "V8" in reglas_escena(dir_libro)




# --------------------------------------------------------------------------- #
# Forma (V14-V15): lo que hace verificable el objetivo de la v1
# --------------------------------------------------------------------------- #
def test_v14_cuatro_parrafos_en_vez_de_tres(dir_libro):
    escribir_prosa(dir_libro, prosa(dir_libro).rstrip() + "\n\nUn cuarto parrafo que sobra y rompe la forma declarada.\n")
    assert "V14" in reglas_escena(dir_libro)


def test_v15_un_parrafo_con_cinco_lineas(dir_libro):
    texto = prosa(dir_libro).replace(
        "Nadie lo había llamado para la final, y esta vez él no preguntó.",
        "Nadie lo había llamado para la final, y esta vez él no preguntó.\n"
        "Una linea de mas que rompe el parrafo y la forma del documento.")
    escribir_prosa(dir_libro, texto)
    assert "V15" in reglas_escena(dir_libro)


def test_v15_una_linea_demasiado_corta(dir_libro):
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Era su licencia del colegio médico, doblada en dos.", "Era su licencia."))
    assert "V15" in reglas_escena(dir_libro)


def test_v15_una_linea_demasiado_larga(dir_libro):
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Era su licencia del colegio médico, doblada en dos.",
        "Era su licencia del colegio médico, doblada en dos, con el sello azul "
        "y la firma temblorosa que ella misma había puesto esa misma mañana."))
    assert "V15" in reglas_escena(dir_libro)


# --------------------------------------------------------------------------- #
# Genero (V16-V20)
# --------------------------------------------------------------------------- #






# --------------------------------------------------------------------------- #
# Obra (V10-V12)
# --------------------------------------------------------------------------- #
def test_v10_un_hilo_queda_sin_cerrar(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    t["escenas"][0]["cierra"] = ["H1"]
    escribir_yaml(dir_libro, "timeline.yaml", t)
    errores = B.v10_hilos_cierran(libro(dir_libro))
    assert errores and "H2" in errores[0].mensaje


def test_v10_un_hilo_se_cierra_dos_veces(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    extra = copy.deepcopy(t["escenas"][0])
    extra.update({"id": "S002", "cierra": ["H1"], "estado": "aprobada"})
    t["escenas"].append(extra)
    escribir_yaml(dir_libro, "timeline.yaml", t)
    errores = B.v10_hilos_cierran(libro(dir_libro))
    assert errores and "2 veces" in errores[0].mensaje


def test_v11_cierra_un_hilo_que_nadie_declaro(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    t["escenas"][0]["cierra"] = ["H1", "H2", "H9"]
    escribir_yaml(dir_libro, "timeline.yaml", t)
    errores = B.v11_hilos_declarados(libro(dir_libro))
    assert errores and "no crece" in errores[0].arreglo


def test_v12_la_proyeccion_se_pasa_del_techo(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    extra = copy.deepcopy(t["escenas"][0])
    extra.update({"id": "S002", "cierra": [], "estado": "planificada"})
    t["escenas"].append(extra)
    escribir_yaml(dir_libro, "timeline.yaml", t)
    errores = B.v12_techo(libro(dir_libro))
    assert errores and "proyeccion" in errores[0].mensaje


def test_el_regulador_avisa_cuando_el_final_deja_de_caber(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    extra = copy.deepcopy(t["escenas"][0])
    extra.update({"id": "S002", "cierra": ["H1"], "estado": "planificada"})
    t["escenas"].append(extra)
    escribir_yaml(dir_libro, "timeline.yaml", t)
    reg = B.cabe_el_final(libro(dir_libro))
    assert reg["cabe"] is False and reg["escenas_de_cierre_pendientes"] == ["S002"]


def test_el_regulador_no_dispara_al_principio_del_libro(dir_libro):
    """El fallo del regulador anterior: en el capitulo 2 cualquier libro sano
    iba 'atrasado'. Este mide capacidad, no ritmo."""
    t = leer_yaml(dir_libro, "timeline.yaml")
    t["escenas"][0]["estado"] = "planificada"
    for i in range(1, 6):
        extra = copy.deepcopy(t["escenas"][0])
        extra.update({"id": "S00%d" % (i + 1), "cierra": [], "estado": "planificada"})
        t["escenas"].append(extra)
    escribir_yaml(dir_libro, "timeline.yaml", t)
    L = libro(dir_libro)
    L.config["estructura"]["escenas_por_capitulo"] = 6
    assert B.cabe_el_final(L)["cabe"], "sin escenas de cierre pendientes, el final cabe"


# --------------------------------------------------------------------------- #
# Canon (V21, V13) y G0
# --------------------------------------------------------------------------- #
def test_v21_falta_un_campo_del_intake(dir_libro):
    p = dir_libro / "context" / "intake.json"
    datos = json.loads(p.read_text(encoding="utf-8"))
    datos["respuestas"]["obstaculo"] = ""
    p.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    errores = C.v21_intake(libro(dir_libro))
    assert errores and "obstaculo" in errores[0].mensaje


def test_v21_una_fecha_que_no_es_fecha(dir_libro):
    p = dir_libro / "context" / "intake.json"
    datos = json.loads(p.read_text(encoding="utf-8"))
    datos["respuestas"]["protagonista"]["nacimiento"] = "por ahi en los sesenta"
    p.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    assert C.v21_intake(libro(dir_libro))


def test_v21_hilos_de_menos(dir_libro):
    p = dir_libro / "context" / "intake.json"
    datos = json.loads(p.read_text(encoding="utf-8"))
    datos["respuestas"]["hilos"] = ["uno solo"]
    p.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    errores = C.v21_intake(libro(dir_libro))
    assert errores and "hacen falta 2" in errores[0].mensaje


def test_v21_queda_algo_por_investigar(dir_libro):
    p = dir_libro / "context" / "intake.json"
    datos = json.loads(p.read_text(encoding="utf-8"))
    datos["pendiente_investigar"] = ["nivel"]
    p.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    assert C.v21_intake(libro(dir_libro))


def test_v13_dos_epocas_distintas(dir_libro):
    e = leer_yaml(dir_libro, "epoca.yaml")
    e["anio"] = 1950
    escribir_yaml(dir_libro, "epoca.yaml", e)
    errores = C.v13_una_epoca(libro(dir_libro))
    assert errores and "1950" in errores[0].mensaje



def test_g0_avisa_si_el_plan_no_cabe_antes_de_escribir(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    for i in range(3):
        extra = copy.deepcopy(t["escenas"][0])
        extra.update({"id": "S20%d" % i, "cierra": []})
        t["escenas"].append(extra)
    escribir_yaml(dir_libro, "timeline.yaml", t)
    errores = C.plan_cabe(libro(dir_libro))
    assert errores and "techo" in errores[0].mensaje


# --------------------------------------------------------------------------- #
# La puerta G2: la rubrica
# --------------------------------------------------------------------------- #
def critica_base() -> dict:
    """Una critica valida: veredicto con motivo y toda nota con su cita.

    Desde la v9.0 el que decide es el critico: la rubrica acompana como medida,
    no como puerta."""
    return {"escena": SID, "intento": 1,
            "veredicto": {"pasa": True, "motivo": "la escena cumple lo que pedia el plan"},
            "continuidad": {"veto": False, "hallazgos": []},
            "calidad": {d: {"nota": 2, "cita": "un fragmento literal de la escena"}
                        for d in ("conflicto", "voz", "concrecion", "frescura", "avance")}}


def critica_sin_citas() -> dict:
    """El camino barato: 2 en todo y ninguna evidencia."""
    c = critica_base()
    for dim in c["calidad"]:
        c["calidad"][dim] = {"nota": 2, "cita": None}
    return c


def test_g2_el_veto_de_continuidad_cierra_la_puerta(dir_libro):
    c = critica_base()
    c["continuidad"] = {"veto": True, "hallazgos": [
        {"que": "aparece un coche que no existe", "cita": "arrancó el Falcon"}]}
    assert not G.evaluar(libro(dir_libro), SID, c)["ok"]



def test_g2_una_nota_sin_cita_es_un_error(dir_libro):
    c = critica_base()
    c["calidad"]["voz"] = {"nota": 1, "cita": None}
    res = G.evaluar(libro(dir_libro), SID, c)
    assert not res["ok"]
    assert any("sin citar" in e["mensaje"] for e in res["errores"])


def test_g2_la_critica_generica_no_abre_la_puerta(dir_libro):
    c = critica_base()
    c["calidad"]["frescura"] = {"nota": 1, "cita": "   "}
    assert not G.evaluar(libro(dir_libro), SID, c)["ok"]





def test_g2_nota_fuera_de_escala(dir_libro):
    c = critica_base()
    c["calidad"]["conflicto"] = {"nota": 7, "cita": None}
    res = G.evaluar(libro(dir_libro), SID, c)
    assert not res["ok"] and any("fuera de" in e["mensaje"] for e in res["errores"])


# --------------------------------------------------------------------------- #
# Todo error es accionable
# --------------------------------------------------------------------------- #
def test_todo_error_dice_que_pasa_y_como_se_arregla(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    t["escenas"][0]["fecha"] = "1991-02-01"
    escribir_yaml(dir_libro, "timeline.yaml", t)
    escribir_prosa(dir_libro, "Una linea corta.\n\nOtra.\n")
    for e in V.validar(libro(dir_libro), SID)["errores"]:
        assert e["regla"] and e["mensaje"].strip() and e["arreglo"].strip()
        assert e["mensaje"].endswith((".", "!")), e["mensaje"]


# --------------------------------------------------------------------------- #
# G0 no puede abrir con la epoca vacia
# --------------------------------------------------------------------------- #
def test_g0_rechaza_una_epoca_sin_investigar(dir_libro):
    """Una epoca vacia pasaba V13 por no tener nada que contradecir, y dejaba
    el libro entrar a produccion con V8 y V20 sin nada que comprobar."""
    escribir_yaml(dir_libro, "epoca.yaml",
                  {"anio": 1990, "prohibido": [], "existia": [], "notas": "", "fuentes": []})
    errores = C.v13_una_epoca(libro(dir_libro))
    assert errores, "una epoca sin investigar no puede abrir G0"
    assert any("prohibido" in e.mensaje or "investig" in e.mensaje.lower() for e in errores)



# --------------------------------------------------------------------------- #
# La puerta G2 no se abre sin evidencia
# --------------------------------------------------------------------------- #

def test_g2_un_hallazgo_de_continuidad_cierra_aunque_el_critico_apruebe(dir_libro):
    """Las dos lentes son independientes: la de calidad puede estar encantada y
    la de continuidad haber encontrado una contradiccion con el canon. Encontrar
    una y dejarla pasar no es una salida coherente."""
    c = critica_base()
    c["veredicto"] = {"pasa": True, "motivo": "esta muy bien escrita"}
    c["continuidad"] = {"veto": False, "hallazgos": [
        {"que": "usa un dato que el canon no le da", "cita": "sabia lo del parte"}]}
    res = G.evaluar(libro(dir_libro), SID, c)
    assert not res["ok"]
    assert "G2/continuidad" in reglas(res)

# --------------------------------------------------------------------------- #
# El techo y la forma tienen que hablar del mismo hecho
# --------------------------------------------------------------------------- #
def test_el_techo_presupuesta_lo_que_V15_permite(dir_libro):
    """V15 acepta palabras_por_linea +- tolerancia, asi que una escena puede
    llegar al maximo sin romper nada. Si el techo se calcula con el nominal,
    un libro pasa todas las reglas de escena y revienta C2 igual."""
    L = libro(dir_libro)
    est, tol = L.config["estructura"], L.config["tolerancia"]
    maximo = (est["parrafos_por_escena"] * est["lineas_por_parrafo"]
              * (est["palabras_por_linea"] + tol["palabras_por_linea"]))
    assert L.forma["palabras_por_escena_max"] == maximo
    assert L.forma["techo_palabras"] == maximo * L.forma["escenas_totales"], (
        "el techo tiene que presupuestar la escena mas larga que V15 deja pasar")


def test_una_escena_en_el_maximo_no_revienta_el_techo(dir_libro):
    """El caso que aparecio corriendo el ciclo: cuatro escenas legales que
    sumadas se pasaban del techo."""
    L = libro(dir_libro)
    est, tol = L.config["estructura"], L.config["tolerancia"]
    por_escena = est["parrafos_por_escena"] * est["lineas_por_parrafo"] * (
        est["palabras_por_linea"] + tol["palabras_por_linea"])
    assert por_escena * L.forma["escenas_totales"] <= L.forma["techo_palabras"]


# --------------------------------------------------------------------------- #
# Scratchpads viejos: una critica de un intento anterior no puede abrir G2
# --------------------------------------------------------------------------- #
def test_g2_no_abre_con_una_critica_mas_vieja_que_la_prosa(dir_libro):
    """Si la escena se reescribio despues de que la criticaran, esa critica
    habla de un texto que ya no existe. Abrir con ella es aprobar a ciegas."""
    import os
    import time
    d = dir_libro / "manuscript" / "ch01"
    critica = d / (SID + ".critique.json")
    critica.write_text(json.dumps(critica_base(), ensure_ascii=False), encoding="utf-8")
    # El caso real: la escena se corrige DESPUES de que la criticaran.
    escribir_prosa(dir_libro, prosa(dir_libro))
    ahora = time.time() + 5
    os.utime(dir_libro / "manuscript" / "ch01" / (SID + ".md"), (ahora, ahora))
    res = G.evaluar(libro(dir_libro), SID, json.loads(critica.read_text("utf-8")),
                    ruta_critica=critica)
    assert not res["ok"]
    assert any("mas vieja" in e["mensaje"] or "posterior" in e["mensaje"]
               for e in res["errores"])


def test_g2_abre_si_la_critica_es_posterior_a_la_prosa(dir_libro):
    d = dir_libro / "manuscript" / "ch01"
    critica = d / (SID + ".critique.json")
    critica.write_text(json.dumps(critica_base(), ensure_ascii=False), encoding="utf-8")
    res = G.evaluar(libro(dir_libro), SID, json.loads(critica.read_text("utf-8")),
                    ruta_critica=critica)
    assert res["ok"]


# --------------------------------------------------------------------------- #
# El reporte a Langfuse es un espejo: si falla, no se lleva el ciclo por delante
# --------------------------------------------------------------------------- #
import reportar as R  # noqa: E402


def test_sin_claves_no_manda_nada_y_no_falla(monkeypatch, dir_libro):
    """Un libro tiene que poder escribirse sin cuenta de Langfuse."""
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setattr(R, "RAIZ", dir_libro)        # sin .env que leer
    (dir_libro / "reports").mkdir(exist_ok=True)
    (dir_libro / "reports" / "traza.jsonl").write_text(
        json.dumps({"t": "2026-01-01", "paso": "G1", "tipo": "puerta", "ok": True,
                    "escena": SID, "errores": []}) + "\n", encoding="utf-8")
    res = R.reportar(dir_libro)
    assert res["ok"] and res["enviado"] == 0


def test_sin_traza_no_hay_nada_que_mandar(dir_libro):
    (dir_libro / "reports" / "traza.jsonl").unlink(missing_ok=True)
    assert R.reportar(dir_libro)["ok"]


def test_el_env_no_pisa_lo_que_ya_esta_exportado(monkeypatch, tmp_path):
    """Quien exporta una clave en su shell o en CI manda sobre el .env."""
    (tmp_path / ".env").write_text(
        "LANGFUSE_HOST=https://del-archivo\nLANGFUSE_PUBLIC_KEY=del-archivo\n",
        encoding="utf-8")
    monkeypatch.setenv("LANGFUSE_HOST", "https://del-entorno")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    R.cargar_env(tmp_path / ".env")
    assert os.environ["LANGFUSE_HOST"] == "https://del-entorno"
    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "del-archivo"


# --------------------------------------------------------------------------- #
# G3: la lee un agente, pero la decision sigue siendo del script
# --------------------------------------------------------------------------- #
import gate_chapter as CH  # noqa: E402


def test_g3_abre_con_una_lectura_limpia(dir_libro):
    libro = Libro(dir_libro)
    res = CH.evaluar(libro, 1, {"hallazgos": []})
    assert res["ok"], res["errores"]


def test_g3_un_hallazgo_bloqueante_cierra_el_capitulo(dir_libro):
    """Un lector que senala algo que saca del libro para el capitulo."""
    libro = Libro(dir_libro)
    texto = libro.ruta_prosa(libro.escena(SID)).read_text(encoding="utf-8")
    cita = " ".join(texto.split()[:6])
    res = CH.evaluar(libro, 1, {"hallazgos": [
        {"que": "El mismo gesto en dos escenas", "cita": cita,
         "escena": SID, "bloquea": True}]})
    assert not res["ok"]
    assert any(e["regla"] == "G3/capitulo" for e in res["errores"])


def test_g3_no_abre_con_una_lectura_que_cita_lo_que_no_esta(dir_libro):
    """Una cita inventada quiere decir que el lector no leyo el capitulo, y una
    lectura asi no puede abrir ninguna puerta ni cerrarla."""
    libro = Libro(dir_libro)
    res = CH.evaluar(libro, 1, {"hallazgos": [
        {"que": "algo", "cita": "zzzqqq una frase que no existe en el capitulo",
         "escena": SID, "bloquea": False}]})
    assert not res["ok"]
    assert any(e["regla"] == "G3/lectura" for e in res["errores"])


def test_g3_un_hallazgo_sin_cita_no_cuenta_igual_que_en_g2(dir_libro):
    libro = Libro(dir_libro)
    res = CH.evaluar(libro, 1, {"hallazgos": [{"que": "algo", "bloquea": False}]})
    assert not res["ok"]
    assert any(e["regla"] == "G3/lectura" for e in res["errores"])


def test_g3_no_abre_con_escenas_sin_aprobar(dir_libro):
    import yaml as _yaml
    t = _yaml.safe_load((dir_libro / "context" / "timeline.yaml").read_text(encoding="utf-8"))
    t["escenas"][0]["estado"] = "planificada"
    (dir_libro / "context" / "timeline.yaml").write_text(
        _yaml.safe_dump(t, allow_unicode=True, sort_keys=False), encoding="utf-8")
    res = CH.evaluar(Libro(dir_libro), 1, {"hallazgos": []})
    assert not res["ok"]
    assert any(e["regla"] == "G3/completo" for e in res["errores"])


def test_g3_una_cita_con_tilde_no_se_pierde_por_stdin(dir_libro):
    """El stdin de Windows llega en cp1252: sin forzar utf-8, una cita con
    tilde llegaba rota y el script acusaba al lector de citar lo que no existe."""
    import subprocess
    prosa = (dir_libro / "manuscript" / "ch01" / (SID + ".md")).read_text(encoding="utf-8")
    cita = next((l for l in prosa.splitlines() if any(c in l for c in "aeiou")), "")
    lectura = json.dumps({"hallazgos": [
        {"que": "prueba", "cita": cita, "escena": SID, "bloquea": False}]},
        ensure_ascii=False)
    r = subprocess.run(
        [sys.executable, str(RAIZ / "harness" / "scripts" / "gate_chapter.py"),
         str(dir_libro), "1"],
        input=lectura.encode("utf-8"), capture_output=True)
    res = json.loads(r.stdout.decode("utf-8"))
    assert res["ok"], res["errores"]


# --------------------------------------------------------------------------- #
# El arco de tres actos (v9.0): sustituye a las etapas de la pareja
# --------------------------------------------------------------------------- #
def test_v16_el_arco_sin_protagonista(dir_libro):
    a = leer_yaml(dir_libro, "arco.yaml")
    a.pop("protagonista")
    escribir_yaml(dir_libro, "arco.yaml", a)
    assert "V16" in reglas(C.v16_arco_res(libro(dir_libro)))


def test_v16_el_protagonista_no_tiene_ficha(dir_libro):
    """Declarar un protagonista que no existe deja al escritor sin nadie."""
    a = leer_yaml(dir_libro, "arco.yaml")
    a["protagonista"] = "fulano"
    escribir_yaml(dir_libro, "arco.yaml", a)
    assert "V16" in reglas(C.v16_arco_res(libro(dir_libro)))


def test_v16_sin_meta_no_hay_historia(dir_libro):
    """Sin meta, obstaculo y precio hay alguien haciendo deporte, no una novela."""
    for campo in ("meta", "obstaculo", "precio"):
        a = leer_yaml(dir_libro, "arco.yaml")
        a[campo] = ""
        escribir_yaml(dir_libro, "arco.yaml", a)
        assert "V16" in reglas(C.v16_arco_res(libro(dir_libro))), campo


def test_v16_al_arco_le_falta_el_desenlace(dir_libro):
    a = leer_yaml(dir_libro, "arco.yaml")
    a["actos"] = [t for t in a["actos"] if t["acto"] != "desenlace"]
    escribir_yaml(dir_libro, "arco.yaml", a)
    assert "V16" in reglas(C.v16_arco_res(libro(dir_libro)))


def test_v16_los_actos_no_pueden_retroceder(dir_libro):
    a = leer_yaml(dir_libro, "arco.yaml")
    a["actos"] = list(reversed(a["actos"]))
    escribir_yaml(dir_libro, "arco.yaml", a)
    assert "V16" in reglas(C.v16_arco_res(libro(dir_libro)))


def test_el_acto_de_una_escena_se_calcula_por_su_fecha(dir_libro):
    """No se declara en ningun lado: se deriva, igual que todo lo demas."""
    L = libro(dir_libro)
    esc = L.escena(SID)
    assert L.acto_de(esc) == "desenlace"
    assert "acto" not in esc, "el acto no se guarda en el timeline"


def test_un_libro_de_una_escena_no_tiene_que_cubrir_tres_actos(dir_libro):
    """Una regla que no se puede cumplir no es una regla: el perfil de prueba
    tiene una sola escena y no puede repartirse en tres actos."""
    assert C.v16_arco_res(libro(dir_libro)) == []
    assert B.v17_tres_actos(libro(dir_libro)) == []


# --------------------------------------------------------------------------- #
# G2 (v9.0): decide el critico, el script comprueba que pueda decidir
# --------------------------------------------------------------------------- #
def test_g2_sin_veredicto_no_abre(dir_libro):
    c = critica_base()
    c.pop("veredicto")
    res = G.evaluar(libro(dir_libro), SID, c)
    assert not res["ok"]
    assert "G2/veredicto" in reglas(res)


def test_g2_un_no_pasa_sin_motivo_no_le_sirve_al_corrector(dir_libro):
    c = critica_base()
    c["veredicto"] = {"pasa": False, "motivo": ""}
    res = G.evaluar(libro(dir_libro), SID, c)
    assert not res["ok"]
    assert "G2/veredicto" in reglas(res)


def test_g2_el_critico_rechaza_y_su_motivo_llega_al_corrector(dir_libro):
    """El motivo del critico tiene que viajar con la forma de un error del
    harness: regla, mensaje y arreglo. Si no, el corrector no sabe que tocar."""
    c = critica_base()
    c["veredicto"] = {"pasa": False, "motivo": "el protagonista no decide nada en toda la escena"}
    res = G.evaluar(libro(dir_libro), SID, c)
    assert not res["ok"]
    err = [e for e in res["errores"] if e["regla"] == "G2/criterio"]
    assert err and "no decide nada" in err[0]["mensaje"]
    assert err[0]["arreglo"]


def test_g2_la_rubrica_ya_no_decide(dir_libro):
    """Una suma baja no cierra la puerta si el critico aprobo: la rubrica es
    medida, no puerta. Pero la suma queda visible en la salida."""
    c = critica_base()
    for dim in c["calidad"]:
        c["calidad"][dim] = {"nota": 0, "cita": "un fragmento literal"}
    res = G.evaluar(libro(dir_libro), SID, c)
    assert res["ok"], "el critico dijo que pasa"
    assert res["suma"] == 0
