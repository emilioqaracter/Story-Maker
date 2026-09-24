"""La traza local. RI-16, RNF-13, RF-253, RD-45. Metodos VER-05 y VER-06."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from commons.tracing.trace import UNDECLARED, Trace, record_hash, verify_chain


def test_cada_registro_es_una_linea_legible(tmp_path: Path) -> None:
    traza = Trace(tmp_path / "n.trace.jsonl")
    traza.emit("call", agent="escritor", chapter=1, attempt=1, real_input=1200)
    traza.emit("retry", level="escena", action="reintentar")

    registros = traza.records()
    assert [r.kind for r in registros] == ["call", "retry"]
    assert registros[0].fields["agent"] == "escritor"
    assert registros[0].seq == 0 and registros[1].seq == 1


def test_borrar_el_fichero_a_mitad_no_detiene_nada(tmp_path: Path) -> None:
    """RNF-13. El siguiente registro vuelve a crear el fichero."""
    path = tmp_path / "n.trace.jsonl"
    traza = Trace(path)
    traza.emit("call", agent="a")
    path.unlink()
    traza.emit("call", agent="b")

    assert [r.fields["agent"] for r in traza.records()] == ["b"]
    assert traza.failures == 0


def test_un_fallo_de_escritura_se_cuenta_y_se_sigue(tmp_path: Path) -> None:
    """La observabilidad observa, no gobierna (D-11)."""
    # Un directorio donde deberia ir el fichero: abrirlo en modo anadir falla.
    path = tmp_path / "ocupado"
    path.mkdir()
    traza = Trace(path)
    traza.emit("call", agent="a")
    traza.emit("call", agent="b")

    assert traza.failures == 2
    assert traza.emitted == 2


def test_desactivada_cuenta_pero_no_escribe(tmp_path: Path) -> None:
    traza = Trace.disabled()
    traza.emit("call")
    assert traza.emitted == 1
    assert traza.records() == []


# ------------------------------------------------ cadena de hashes · RF-253, RD-45


def _lineas(path: Path) -> list[str]:
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _escribe(path: Path, lineas: list[str]) -> None:
    path.write_text("".join(ln + "\n" for ln in lineas), encoding="utf-8")


def _traza_de(path: Path, n: int) -> None:
    traza = Trace(path)
    for i in range(n):
        traza.emit("call", agent=f"a{i}", attempt=i)


def test_cada_registro_apunta_al_anterior_y_el_primero_a_vacio(tmp_path: Path) -> None:
    path = tmp_path / "n.trace.jsonl"
    _traza_de(path, 3)
    datos = [json.loads(ln) for ln in _lineas(path)]
    assert datos[0]["prev_hash"] == ""
    assert datos[1]["prev_hash"] == record_hash(datos[0])
    assert datos[2]["prev_hash"] == record_hash(datos[1])
    assert verify_chain(path) is None
    assert Trace(path).verify() is None


def test_editar_un_campo_rompe_el_siguiente(tmp_path: Path) -> None:
    path = tmp_path / "n.trace.jsonl"
    _traza_de(path, 3)
    lineas = _lineas(path)
    lineas[1] = lineas[1].replace('"a1"', '"otro"')
    _escribe(path, lineas)
    assert verify_chain(path) == 3


def test_borrar_una_linea_rompe_la_que_ocupa_su_sitio(tmp_path: Path) -> None:
    """La puerta de T45: borrar una linea de una traza lo senala `verify_chain`."""
    path = tmp_path / "n.trace.jsonl"
    _traza_de(path, 3)
    lineas = _lineas(path)
    del lineas[1]
    _escribe(path, lineas)
    assert verify_chain(path) == 2


def test_borrar_la_primera_rompe_la_primera(tmp_path: Path) -> None:
    path = tmp_path / "n.trace.jsonl"
    _traza_de(path, 3)
    _escribe(path, _lineas(path)[1:])
    assert verify_chain(path) == 1


def test_reordenar_rompe(tmp_path: Path) -> None:
    path = tmp_path / "n.trace.jsonl"
    _traza_de(path, 3)
    a, b, c = _lineas(path)
    _escribe(path, [a, c, b])
    assert verify_chain(path) == 2


def test_una_linea_que_no_es_json_rompe_en_ella(tmp_path: Path) -> None:
    path = tmp_path / "n.trace.jsonl"
    _traza_de(path, 2)
    lineas = _lineas(path)
    _escribe(path, [lineas[0], "{cortada", lineas[1]])
    assert verify_chain(path) == 2


def test_sin_fichero_no_hay_nada_roto(tmp_path: Path) -> None:
    assert verify_chain(tmp_path / "no.jsonl") is None
    assert Trace.disabled().verify() is None


def test_otra_instancia_continua_la_misma_cadena(tmp_path: Path) -> None:
    """Una tirada reanudada o una ruta que abre su `Trace` no empiezan cadena nueva."""
    path = tmp_path / "n.trace.jsonl"
    primera, segunda = Trace(path), Trace(path)
    primera.emit("call", agent="a")
    segunda.emit("call", agent="b")
    primera.emit("call", agent="c")
    Trace(path).emit("call", agent="d")
    assert len(_lineas(path)) == 4
    assert verify_chain(path) is None


def test_borrar_el_fichero_empieza_otra_cadena_valida(tmp_path: Path) -> None:
    path = tmp_path / "n.trace.jsonl"
    traza = Trace(path)
    traza.emit("call", agent="a")
    path.unlink()
    traza.emit("call", agent="b")
    traza.emit("call", agent="c")
    assert json.loads(_lineas(path)[0])["prev_hash"] == ""
    assert verify_chain(path) is None


def test_los_campos_existentes_no_cambian(tmp_path: Path) -> None:
    """RD-45. `prev_hash` es un campo mas; lo que leen evals y rutas sigue igual."""
    path = tmp_path / "n.trace.jsonl"
    Trace(path).emit("call", agent="escritor", chapter=1)
    dato = json.loads(_lineas(path)[0])
    assert set(dato) == {"seq", "at", "kind", "fields", "prev_hash"}
    assert dato["fields"] == {"agent": "escritor", "chapter": 1}


@settings(max_examples=60, deadline=None)
@given(
    n=st.integers(min_value=2, max_value=8),
    data=st.data(),
    cambio=st.sampled_from(["editar", "borrar", "reordenar"]),
)
def test_cualquier_cambio_con_algo_detras_se_detecta(
    n: int, data: st.DataObject, cambio: str
) -> None:
    """VER-06. Editar, borrar o reordenar senala el primer registro afectado.

    El limite declarado: lo que se toca en el ultimo registro no tiene a nadie
    detras que apunte a el, asi que editar o borrar el ultimo no se detecta.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "n.trace.jsonl"
        _traza_de(path, n)
        lineas = _lineas(path)
        i = data.draw(st.integers(min_value=0, max_value=n - 2), label="indice")
        if cambio == "editar":
            lineas[i] = lineas[i].replace(f'"a{i}"', '"cambiado"')
            esperado = i + 2
        elif cambio == "borrar":
            del lineas[i]
            esperado = i + 1
        else:
            lineas[i], lineas[i + 1] = lineas[i + 1], lineas[i]
            esperado = i + 1
        _escribe(path, lineas)
        assert verify_chain(path) == esperado


# --------------------------------- decisiones del motor de politicas · RF-253


def test_las_decisiones_llevan_decision_regla_e_instante(tmp_path: Path) -> None:
    path = tmp_path / "n.trace.jsonl"
    traza = Trace(path)
    traza.emit(
        "arbitration",
        chapter=2,
        fact="f",
        frozen_value="a",
        rejected_value="b",
        rule="canon-congelado-sobre-delta-nuevo",
    )
    traza.emit("retcon.proposal", fact="f", propose=True, admissible=False, reason="tocaria 9")
    traza.emit("guardrail.match", term="x", level="cliente", decision="reintentar")
    traza.emit("formal.lean", passed=False, theorem="I1")
    traza.emit("formal.lean")

    arb, ret, guard, lean, vacio = traza.records()
    for r in (arb, ret, guard, lean, vacio):
        assert r.fields["decision"] and r.fields["rule"]
        assert datetime.fromisoformat(r.at).tzinfo is not None
    assert arb.fields["decision"] == "rechaza-el-delta"
    assert arb.fields["rule"] == "canon-congelado-sobre-delta-nuevo"
    assert ret.fields["decision"] == "gana-el-congelado"
    assert ret.fields["rule"] == "tocaria 9"
    assert guard.fields["decision"] == "reintentar"
    assert guard.fields["rule"] == "check.forbidden nivel cliente"
    assert (lean.fields["decision"], lean.fields["rule"]) == ("falla", "I1")
    assert vacio.fields["decision"] == UNDECLARED
    assert verify_chain(path) is None


def test_lo_que_declara_el_emisor_gana(tmp_path: Path) -> None:
    traza = Trace(tmp_path / "n.trace.jsonl")
    traza.emit("formal.lean", passed=True, decision="congela", rule="Invariants")
    (r,) = traza.records()
    assert (r.fields["decision"], r.fields["rule"]) == ("congela", "Invariants")


def test_un_registro_corriente_no_gana_campos(tmp_path: Path) -> None:
    traza = Trace(tmp_path / "n.trace.jsonl")
    traza.emit("call", agent="a")
    (r,) = traza.records()
    assert dict(r.fields) == {"agent": "a"}
