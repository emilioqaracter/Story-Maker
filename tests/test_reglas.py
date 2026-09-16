# -*- coding: utf-8 -*-
"""Escenas-trampa: un error plantado por regla, y la regla que debe cazarlo.

Es el fixture del que habla el SPEC: sin LLM, sin red, sin gastar un token.
Si una regla no tiene su trampa aqui, no esta comprobada.

    python -m pytest tests -q
"""
from __future__ import annotations

import copy
import json
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


def reglas(res: dict) -> set:
    return {e["regla"] for e in res["errores"]}


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
               + B.v17_una_crisis(L) + B.v18_promesa(L) + B.v19_coinciden(L))
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


def test_v3_la_edad_no_coincide_con_el_nacimiento(dir_libro):
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Marco se ató los botines despacio, dos veces cada uno, sin mirar.",
        "Marco tenía 35 años y se ató los botines despacio, sin mirar."))
    assert "V3" in reglas_escena(dir_libro)


def test_v4_el_cumpleanos_cae_en_otra_fecha(dir_libro):
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Sofía entró con la carpeta bajo el brazo y cerró la puerta.",
        "Sofía entró con una torta: era el cumpleaños de Marco y nadie lo sabía."))
    assert "V4" in reglas_escena(dir_libro)


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


def test_v7_reacciona_a_algo_que_todavia_no_sabe(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    t["escenas"][0]["fecha"] = "1990-07-01"          # antes del 25 de noviembre
    escribir_yaml(dir_libro, "timeline.yaml", t)
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Era su licencia del colegio médico, doblada en dos.",
        "Marco ya sabía lo del parte y no dijo una sola palabra."))
    assert "V7" in reglas_escena(dir_libro)


def test_v8_anacronismo_de_la_lista_prohibida(dir_libro):
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Sofía entró con la carpeta bajo el brazo y cerró la puerta.",
        "Sofía entró mirando el celular y cerró la puerta sin levantar la vista."))
    assert "V8" in reglas_escena(dir_libro)


def test_v9_persona_real_fuera_de_su_vida(dir_libro):
    escribir_yaml(dir_libro, "real-figures.yaml", [
        {"nombre": "Obdulio Varela", "wikipedia": "https://es.wikipedia.org/wiki/Obdulio_Varela",
         "nacimiento": "1917-09-20", "muerte": "1996-08-02"},
        {"nombre": "Zinedine Zidane", "wikipedia": "https://es.wikipedia.org/wiki/Zinedine_Zidane",
         "nacimiento": "1972-06-23", "muerte": None},
    ])
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Después Marco juntó las dos hojas y se las guardó en el bolsillo.",
        "Obdulio lo miró desde la puerta y Marco guardó las dos hojas."))
    assert "V9" not in reglas_escena(dir_libro), "Obdulio vivia en 1990"
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Obdulio lo miró desde la puerta y Marco guardó las dos hojas.",
        "Zinedine lo miró desde la puerta y Marco guardó las dos hojas."))
    assert "V9" not in reglas_escena(dir_libro), "Zidane ya habia nacido en 1990"
    t = leer_yaml(dir_libro, "timeline.yaml")
    t["escenas"][0]["fecha"] = "1990-01-05"
    escribir_yaml(dir_libro, "timeline.yaml", t)
    escribir_prosa(dir_libro, prosa(dir_libro).replace("Zinedine", "Obdulio"))
    assert "V9" not in reglas_escena(dir_libro)


def test_v9_caza_a_quien_ya_habia_muerto(dir_libro):
    escribir_yaml(dir_libro, "real-figures.yaml", [
        {"nombre": "Alguien Temprano", "wikipedia": "https://es.wikipedia.org/wiki/X",
         "nacimiento": "1900-01-01", "muerte": "1989-12-31"}])
    escribir_prosa(dir_libro, prosa(dir_libro).replace(
        "Después Marco juntó las dos hojas y se las guardó en el bolsillo.",
        "Alguien lo miró desde la puerta y Marco guardó las dos hojas."))
    assert "V9" in reglas_escena(dir_libro)


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
def test_v16_la_relacion_salta_una_etapa(dir_libro):
    r = leer_yaml(dir_libro, "relacion.yaml")
    r["etapas"] = [e for e in r["etapas"] if e["etapa"] != "intimidad"]
    escribir_yaml(dir_libro, "relacion.yaml", r)
    assert "V16" in reglas_escena(dir_libro)


def test_v16_la_relacion_retrocede_sin_ruptura(dir_libro):
    r = leer_yaml(dir_libro, "relacion.yaml")
    r["etapas"] = [{"etapa": "desconocidos", "desde": "1990-01-01"},
                   {"etapa": "atraccion", "desde": "1990-02-11"},
                   {"etapa": "desconocidos", "desde": "1990-05-03"}]
    escribir_yaml(dir_libro, "relacion.yaml", r)
    assert "V16" in reglas_escena(dir_libro)


def test_v17_dos_crisis(dir_libro):
    r = leer_yaml(dir_libro, "relacion.yaml")
    r["etapas"].append({"etapa": "ruptura", "desde": "1990-12-01"})
    escribir_yaml(dir_libro, "relacion.yaml", r)
    assert B.v17_una_crisis(libro(dir_libro))


def test_v17_la_crisis_antes_de_la_intimidad(dir_libro):
    r = leer_yaml(dir_libro, "relacion.yaml")
    for e in r["etapas"]:
        if e["etapa"] == "ruptura":
            e["desde"] = "1990-04-01"
    escribir_yaml(dir_libro, "relacion.yaml", r)
    assert B.v17_una_crisis(libro(dir_libro))


def test_v18_el_libro_no_cierra_en_union(dir_libro):
    r = leer_yaml(dir_libro, "relacion.yaml")
    for e in r["etapas"]:
        if e["etapa"] == "union":
            e["desde"] = "1990-12-30"          # posterior a la ultima escena
    escribir_yaml(dir_libro, "relacion.yaml", r)
    errores = B.v18_promesa(libro(dir_libro))
    assert errores and "promesa del genero" in errores[0].arreglo


def test_v19_la_pareja_no_coincide_nunca(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    for i in range(3):
        extra = copy.deepcopy(t["escenas"][0])
        extra.update({"id": "S10%d" % i, "presentes": ["marco"], "cierra": [],
                      "fecha": "1990-12-0%d" % (i + 1), "estado": "aprobada"})
        t["escenas"].append(extra)
    escribir_yaml(dir_libro, "timeline.yaml", t)
    L = libro(dir_libro)
    L.config["ciclo"]["escenas_sin_coincidir_max"] = 2
    errores = B.v19_coinciden(L)
    assert errores and "3 escenas seguidas" in errores[0].mensaje


def test_v20_el_hito_no_cae_en_su_fecha(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    t["escenas"][0]["hito"] = "el clásico"      # existe, pero es del 19 de agosto
    escribir_yaml(dir_libro, "timeline.yaml", t)
    c = leer_yaml(dir_libro, "calendario.yaml")
    c["hitos"][1]["que"] = "el clásico"
    escribir_yaml(dir_libro, "calendario.yaml", c)
    assert "V20" in reglas_escena(dir_libro)


def test_v20_hito_inventado(dir_libro):
    t = leer_yaml(dir_libro, "timeline.yaml")
    t["escenas"][0]["hito"] = "la superfinal intergalactica"
    escribir_yaml(dir_libro, "timeline.yaml", t)
    assert "V20" in reglas_escena(dir_libro)


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
    datos["respuestas"]["persona_a"]["nacimiento"] = "por ahi en los sesenta"
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


def test_v13_el_calendario_se_va_de_epoca(dir_libro):
    c = leer_yaml(dir_libro, "calendario.yaml")
    c["hitos"][0]["fecha"] = "1978-06-25"
    escribir_yaml(dir_libro, "calendario.yaml", c)
    assert C.v13_una_epoca(libro(dir_libro))


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
    """Una critica valida: toda nota lleva su cita, el 2 incluido."""
    return {"escena": SID, "intento": 1,
            "continuidad": {"veto": False, "hallazgos": []},
            "calidad": {d: {"nota": 2, "cita": "un fragmento literal de la escena"}
                        for d in ("conflicto", "dialogo", "concrecion", "frescura", "quimica")}}


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


def test_g2_un_cero_tumba_la_escena_aunque_la_suma_alcance(dir_libro):
    c = critica_base()
    c["calidad"]["conflicto"] = {"nota": 0, "cita": "no pasa nada"}
    res = G.evaluar(libro(dir_libro), SID, c)
    assert res["suma"] == 8 and res["suma"] >= res["umbral"]
    assert not res["ok"], "un 0 tumba la escena aunque la suma pase el umbral"


def test_g2_sin_cita_la_dimension_no_cuenta(dir_libro):
    c = critica_base()
    c["calidad"]["dialogo"] = {"nota": 1, "cita": None}
    res = G.evaluar(libro(dir_libro), SID, c)
    assert not res["ok"]
    assert any("sin citar" in e["mensaje"] for e in res["errores"])


def test_g2_la_critica_generica_no_abre_la_puerta(dir_libro):
    c = critica_base()
    c["calidad"]["frescura"] = {"nota": 1, "cita": "   "}
    assert not G.evaluar(libro(dir_libro), SID, c)["ok"]


def test_g2_no_llega_al_umbral(dir_libro):
    c = critica_base()
    for d in ("conflicto", "dialogo", "concrecion"):
        c["calidad"][d] = {"nota": 1, "cita": "un fragmento citado"}
    res = G.evaluar(libro(dir_libro), SID, c)
    assert res["suma"] == 7 and res["ok"], "7 sobre 10 pasa el umbral de 6"
    c["calidad"]["frescura"] = {"nota": 1, "cita": "otro fragmento"}
    c["calidad"]["quimica"] = {"nota": 1, "cita": "otro mas"}
    res = G.evaluar(libro(dir_libro), SID, c)
    assert res["suma"] == 5 and not res["ok"], "5 sobre 10 no llega a 6"


def test_g2_escena_sin_pareja_baja_el_umbral(dir_libro):
    c = critica_base()
    c["calidad"]["quimica"] = None
    res = G.evaluar(libro(dir_libro), SID, c)
    assert res["umbral"] == 5 and res["maximo"] == 8 and res["ok"]


def test_g2_falta_una_dimension(dir_libro):
    c = critica_base()
    del c["calidad"]["conflicto"]
    res = G.evaluar(libro(dir_libro), SID, c)
    assert not res["ok"] and any("Falta la dimension" in e["mensaje"] for e in res["errores"])


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


def test_g0_rechaza_datos_de_epoca_sin_fuente(dir_libro):
    e = leer_yaml(dir_libro, "epoca.yaml")
    e["fuentes"] = []
    escribir_yaml(dir_libro, "epoca.yaml", e)
    errores = C.v13_una_epoca(libro(dir_libro))
    assert errores and any("fuente" in x.mensaje.lower() for x in errores)


# --------------------------------------------------------------------------- #
# La puerta G2 no se abre sin evidencia
# --------------------------------------------------------------------------- #
def test_g2_un_2_sin_cita_tampoco_cuenta(dir_libro):
    """El camino mas barato para aprobar era poner 2 en todo y no citar nada.
    Un 2 sin evidencia es una afirmacion, no una observacion."""
    res = G.evaluar(libro(dir_libro), SID, critica_sin_citas())
    assert not res["ok"], "10/10 sin una sola cita no puede abrir la puerta"


def test_g2_abre_con_todo_en_2_si_cada_uno_cita(dir_libro):
    assert G.evaluar(libro(dir_libro), SID, critica_base())["ok"]


def test_g2_un_hallazgo_de_continuidad_cuenta_aunque_no_vete(dir_libro):
    """Encontrar una contradiccion y no vetarla no es una salida coherente:
    la lente existe justo para encontrarlas."""
    c = critica_base()
    c["continuidad"] = {"veto": False, "hallazgos": [
        {"que": "sabe algo que el canon no le da", "cita": "dijo Tomas despacio"}]}
    res = G.evaluar(libro(dir_libro), SID, c)
    assert not res["ok"] and res["veto_continuidad"]


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
