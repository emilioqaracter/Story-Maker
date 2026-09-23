"""`check.forbidden`: normalizacion, variantes, niveles. RF-236, RF-237, RF-239.

Metodos VER-12 y VER-05, y VER-06 para la propiedad de normalizacion
(`specs/srs-backend-v4.md` §7.3). El bucle con reintento, reparacion y aborto
esta en `orchestration/test_loop.py` y `orchestration/test_engine.py`.
"""

from __future__ import annotations

import sqlite3
import unicodedata
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from canon.brief import Brief, BriefEntity, create_novel, store_forbidden
from canon.db import connection
from canon.db.migrations import MIGRATIONS
from commons.types.primitives import Severity
from verification.checks.forbidden import (
    KIND,
    ForbiddenTerm,
    check_forbidden,
    describe,
    normalize,
    occurrences,
    read_style_terms,
    read_terms,
    variants,
)


def _t(term: str, level: str = "cliente") -> ForbiddenTerm:
    return ForbiddenTerm(term=term, level=level)  # type: ignore[arg-type]


def _casa(term: str, texto: str) -> bool:
    return bool(check_forbidden(texto, terms=[_t(term)]))


# ------------------------------------------------------------ normalizacion


def test_normalize_pliega_mayusculas_tildes_y_compatibilidad() -> None:
    assert normalize("CABRÓN") == normalize("cabron") == "cabron"
    assert normalize("ﬁn") == "fin"
    assert normalize("Straße") == "strasse"


def test_mar_no_casa_en_marcos_ni_en_amar() -> None:
    """D-90: por palabra completa. La subcadena hacia saltar «mar» en «Marcos»."""
    assert not _casa("mar", "Marcos corre hacia el area.")
    assert not _casa("mar", "Aprendio a amar el futbol en marzo.")
    assert _casa("mar", "Olia a mar.")


def test_luz_casa_en_luces() -> None:
    """RF-237: la `z` final a `ces`."""
    assert _casa("luz", "Se apagaron las luces del estadio.")


def test_forbidden_variante_acento() -> None:
    """Termino con tilde y texto sin ella, en mayusculas; y al reves."""
    assert _casa("cabrón", "CABRON de mierda")
    assert _casa("cabron", "Ese Cabrón no pasa")


def test_forbidden_variante_plural() -> None:
    """`+s`, `+es` y `z` a `ces`."""
    assert _casa("cabrón", "los cabrones del fondo")
    assert _casa("balón", "dos balones")
    assert _casa("gato", "tres gatos")
    assert _casa("lápiz", "los LAPICES rotos")


def test_variante_de_genero_en_los_dos_sentidos() -> None:
    assert _casa("gato", "la gata negra")
    assert _casa("gata", "el gato negro")
    assert not _casa("gato", "el gatillo")


def test_un_termino_de_varias_palabras_es_una_secuencia() -> None:
    assert _casa("silencio sepulcral", "Un SILENCIO   sepulcral.")
    assert _casa("silencio sepulcral", "silencios sepulcrales")
    assert not _casa("silencio sepulcral", "silencio, casi sepulcral")


def test_las_variantes_son_exactamente_las_declaradas() -> None:
    assert variants("luz") == {"luz", "luzs", "luzes", "luces"}
    assert variants("gato") == {"gato", "gatos", "gatoes", "gata"}
    assert variants("gata") == {"gata", "gatas", "gataes", "gato"}
    assert variants("mar") == {"mar", "mars", "mares"}
    assert variants("") == frozenset()


def test_la_cita_es_el_texto_original_con_su_posicion() -> None:
    texto = "Entro. Olia a LINIMENTO y a lluvia."
    [occ] = occurrences(texto, "linimento")
    assert occ.quote == "LINIMENTO"
    assert texto[occ.offset : occ.offset + len(occ.quote)] == "LINIMENTO"


# ------------------------------------------------------------------ defecto


def test_una_prohibida_presente_es_un_s1_con_termino_nivel_y_cita() -> None:
    """RF-236."""
    texto = "El vestuario olia a linimento."
    [d] = check_forbidden(texto, terms=[_t("linimento", "global")])
    assert d.kind == KIND == "check.forbidden"
    assert d.severity is Severity.S1
    assert d.evidence.quote == "linimento"
    assert d.evidence.offset == texto.index("linimento")
    assert describe(d) == _t("linimento", "global")


def test_ausente_no_da_nada() -> None:
    assert check_forbidden("El vestuario olia a lluvia.", terms=[_t("linimento")]) == []
    assert check_forbidden("linimento", terms=[]) == []


def test_un_defecto_por_coincidencia_en_orden_de_aparicion() -> None:
    texto = "sangre y barro, barro y sangre"
    defectos = check_forbidden(texto, terms=[_t("sangre"), _t("barro", "global")])
    assert [d.evidence.offset for d in defectos] == sorted(d.evidence.offset for d in defectos)
    assert len(defectos) == 4


def test_describe_ignora_lo_que_no_es_del_guardarrail() -> None:
    [d] = check_forbidden("sangre", terms=[_t("sangre")])
    assert describe(d.model_copy(update={"kind": "check.repetition"})) is None
    assert describe(d.model_copy(update={"rule": "otra cosa"})) is None


# -------------------------------------------------------------- propiedades

_LETRAS = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=2, max_size=8)
_TILDES = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}


def _disfraza(term: str, flags: list[bool]) -> str:
    """El termino con mayusculas y tildes cambiadas segun `flags`."""
    out = []
    for i, c in enumerate(term):
        f = flags[i % len(flags)] if flags else False
        c = _TILDES.get(c, c) if f else c
        out.append(c.upper() if (i % 2 == 0) == f else c)
    return "".join(out)


def _declaradas(w: str) -> set[str]:
    """El oraculo de la prueba, escrito aparte de `variants`."""
    out = {w + "s", w + "es"}
    if w.endswith("z"):
        out.add(w[:-1] + "ces")
    if w.endswith("o"):
        out.add(w[:-1] + "a")
    if w.endswith("a"):
        out.add(w[:-1] + "o")
    return out


@given(term=_LETRAS, flags=st.lists(st.booleans(), min_size=1, max_size=4))
def test_propiedad_entre_espacios_siempre_casa(term: str, flags: list[bool]) -> None:
    """§7.3: con cualquier mezcla de mayusculas y tildes, entre espacios casa."""
    # Cifras alrededor: ningun termino de letras casa con ellas por accidente.
    texto = f"1 {_disfraza(term, flags)} 2"
    assert _casa(term, texto)
    # Tambien descompuesto: las marcas combinantes no parten la palabra.
    assert _casa(term, unicodedata.normalize("NFD", texto))


@given(term=_LETRAS, sufijo=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=3))
def test_propiedad_pegado_por_la_derecha_solo_casa_si_es_variante(term: str, sufijo: str) -> None:
    """§7.3: pegado a letras por la derecha no casa salvo variante declarada."""
    pegado = term + sufijo
    assert _casa(term, f"1 {pegado} 2") is (pegado in _declaradas(term))


# ------------------------------------------------------------------ niveles


def _brief(words: tuple[str, ...] = ()) -> Brief:
    return Brief(
        title="p",
        start={"stamp": "2026-01-01"},  # type: ignore[arg-type]
        entities=(BriefEntity(id="m", kind="person", name="Marcos"),),
        style_guide="x",
        target_words=1000,
        forbidden_words=words,
    )


def _levels(path: Path) -> dict[str, str]:
    with connection.reader(path) as con:
        return {t.term: t.level for t in read_terms(con)}


def test_forbidden_nivel_global(tmp_path: Path) -> None:
    """RD-38: la lista global se copia a la novela al crearla, y bloquea."""
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief(), global_terms=("linimento", "  "))
    with connection.reader(path) as con:
        terminos = read_terms(con)
    assert terminos == (_t("linimento", "global"),)
    [d] = check_forbidden("Olia a linimento.", terms=terminos)
    assert describe(d) == _t("linimento", "global")


def test_la_lista_global_es_un_termino_por_linea(tmp_path: Path) -> None:
    from canon.brief import read_global_forbidden

    fichero = tmp_path / "global.txt"
    lineas = ["# cabecera", "", "Linimento ", "  # otra", "silencio sepulcral", ""]
    fichero.write_text("\n".join(lineas), encoding="utf-8")
    assert read_global_forbidden(fichero) == ("Linimento", "silencio sepulcral")
    with pytest.raises(FileNotFoundError):
        read_global_forbidden(tmp_path / "no-existe.txt")


def test_la_lista_global_versionada_nace_vacia(tmp_path: Path) -> None:
    """RD-38: no se inventa una lista."""
    from canon.brief import read_global_forbidden

    assert read_global_forbidden() == ()
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief())
    assert _levels(path) == {}


def test_forbidden_nivel_cliente(tmp_path: Path) -> None:
    """Las prohibidas de la entrevista entran como `cliente`."""
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief(("Sangre",)), global_terms=())
    with connection.reader(path) as con:
        terminos = read_terms(con)
    assert terminos == (_t("sangre", "cliente"),)
    [d] = check_forbidden("Habia SANGRES en el cesped.", terms=terminos)
    assert describe(d) == _t("sangre", "cliente")


def test_forbidden_nivel_novela(tmp_path: Path) -> None:
    """RF-256 las cargara desde una solicitud de cambio: la tabla y la lectura ya estan."""
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief(), global_terms=())
    with connection.canon_writer(path) as con:
        assert store_forbidden(con, "Tiza", level="novela", chapter=3) == "novela"
    with connection.reader(path) as con:
        terminos = read_terms(con)
        [fila] = con.execute("SELECT added_chapter, kind FROM proscribed").fetchall()
    assert terminos == (_t("tiza", "novela"),)
    assert (fila["added_chapter"], fila["kind"]) == (3, "term")
    [d] = check_forbidden("Las tizas del encerado.", terms=terminos)
    assert describe(d) == _t("tiza", "novela")


def test_un_termino_en_dos_niveles_se_queda_en_el_mas_fuerte(tmp_path: Path) -> None:
    """D-91: global, cliente, novela. Dos terminos que normalizan igual son uno."""
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief(("Cabrón", "sangre")), global_terms=("cabron",))
    assert _levels(path) == {"cabron": "global", "sangre": "cliente"}
    with connection.canon_writer(path) as con:
        assert store_forbidden(con, "SANGRE", level="novela") == "cliente"
        assert store_forbidden(con, "   ", level="novela") is None


def test_un_ngrama_de_estilo_sube_al_guardarrail(tmp_path: Path) -> None:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief(), global_terms=())
    with connection.canon_writer(path) as con:
        con.execute(
            "INSERT INTO proscribed (term, kind, added_chapter, added_at) "
            "VALUES ('silencio sepulcral de la', 'ngram', 1, 'x')"
        )
        assert store_forbidden(con, "silencio sepulcral de la", level="novela") == "novela"
    with connection.reader(path) as con:
        assert read_style_terms(con) == []
        assert read_terms(con) == (_t("silencio sepulcral de la", "novela"),)


def test_el_esquema_impide_bajar_de_nivel_y_mezclar_tipo(tmp_path: Path) -> None:
    """RD-37 y D-91 como disparadores, no como convencion."""
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief(), global_terms=("linimento",))
    con = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="nivel mas fuerte"):
            con.execute("UPDATE proscribed SET level = 'novela' WHERE term = 'linimento'")
        with pytest.raises(sqlite3.DatabaseError, match="no casan"):
            con.execute(
                "INSERT INTO proscribed (term, kind, level, added_chapter, added_at) "
                "VALUES ('x', 'ngram', 'cliente', 0, 'x')"
            )
        with pytest.raises(sqlite3.DatabaseError, match="no casan"):
            con.execute(
                "INSERT INTO proscribed (term, kind, added_chapter, added_at) "
                "VALUES ('y', 'brief', 0, 'x')"
            )
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO proscribed (term, kind, level, added_chapter, added_at) "
                "VALUES ('z', 'term', 'otro', 0, 'x')"
            )
    finally:
        con.close()


def _version_three(path: Path) -> None:
    """Un fichero como los dejaba la version 3: `proscribed` sin `level`."""
    schema = (Path(connection.__file__).with_name("schema.sql")).read_text(encoding="utf-8")
    con = sqlite3.connect(path)
    con.executescript(schema)
    con.execute("INSERT INTO schema_version (version, applied_at) VALUES (1, 'x')")
    for version in (2, 3):
        for paso in MIGRATIONS[version]:
            assert isinstance(paso, str)
            con.execute(paso)
        con.execute("INSERT INTO schema_version (version, applied_at) VALUES (?, 'x')", (version,))
    con.executemany(
        "INSERT INTO proscribed (term, kind, added_chapter, added_at) VALUES (?, ?, ?, 'x')",
        [("sangre", "brief", 0), ("a la luz de", "ngram", 2)],
    )
    con.commit()
    con.close()


def test_un_fichero_anterior_se_lee_sin_migrar_y_migra_al_escribir(tmp_path: Path) -> None:
    """RD-37: `kind='brief'` pasa a nivel `cliente`; los n-gramas a `estilo`."""
    path = tmp_path / "v3.sqlite"
    _version_three(path)
    with connection.reader(path) as con:
        assert read_terms(con) == (_t("sangre", "cliente"),)
        assert read_style_terms(con) == ["a la luz de"]
    with connection.canon_writer(path):
        pass
    with connection.reader(path) as con:
        filas = {
            r["term"]: (r["kind"], r["level"])
            for r in con.execute("SELECT term, kind, level FROM proscribed")
        }
        assert read_terms(con) == (_t("sangre", "cliente"),)
    assert filas == {"sangre": ("term", "cliente"), "a la luz de": ("ngram", "estilo")}
