"""La traza local. RI-16, RNF-13. Metodo VER-05."""

from __future__ import annotations

from pathlib import Path

from commons.tracing.trace import Trace


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
