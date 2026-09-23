"""El brief de la trampa temporal. RF-250, RD-41, RF-249, D-95. VER-10 con VER-05.

`specs/srs-backend-v4.md` §4.7, `03-temporal.json`: el destinatario nace el
2017-04-02 y el brief le atribuye un recuerdo del 14 de marzo de 2015, dos años
antes; otro recuerdo cae en un 31 de junio, que no existe. El brief es valido
--ninguna regla del brief mira fechas dentro de un recuerdo, y no debe: haria
falta leer el texto--, asi que la trampa **llega al canon** y la tienen que cazar
los verificadores de la cronologia:

- **Lean I1** (RF-244): nadie presente en una escena anterior a su nacimiento.
  La fecha de nacimiento entra como el atributo reservado `birth_date`, que es
  lo que exporta el generador; aqui se afirma que el dato esta y que una escena
  en la fecha del recuerdo lo viola. La compilacion es de T43.
- **`check.timeline`**: la fecha narrada no esta en el calendario de la obra.

Un caso que no cae en la trampa no da defecto: si lo diera, el verificador no
distinguiria la trampa del ruido.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from canon.brief import Brief, create_novel
from canon.db import connection
from canon.skills import read
from commons.types.primitives import Severity, WorldTime
from verification.checks.deterministic import check_timeline

BRIEF = Path(__file__).parent / "briefs" / "03-temporal.json"
#: La trampa, tal como la declara el brief.
RECUERDO = date(2015, 3, 14)
IMPOSIBLE = (2015, 6, 31)


def _brief() -> Brief:
    return Brief.model_validate_json(BRIEF.read_text(encoding="utf-8"))


def _calendario(path: Path) -> list[str]:
    """Las fechas que `verify_scene` da por buenas antes de la primera escena."""
    with connection.reader(path) as con:
        return [r["world_time"] for r in con.execute("SELECT DISTINCT world_time FROM event")]


def test_el_brief_es_valido_y_la_trampa_esta_en_sus_datos() -> None:
    brief = _brief()
    assert brief.contradictions() == []
    assert brief.recipient is not None and brief.recipient.birth_date == date(2017, 4, 2)
    assert brief.recipient.birth_date > RECUERDO
    recuerdos = " ".join(brief.recipient.memories)
    assert "14 de marzo de 2015" in recuerdos and "31 de junio" in recuerdos
    # 31 de junio no esta en ningun calendario.
    assert not _existe(*IMPOSIBLE)


def test_el_nacimiento_llega_al_canon_como_dato_exportable(tmp_path: Path) -> None:
    """RF-249, RD-41: lo que el generador de Lean lee para I1."""
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief(), global_terms=())
    inicio = _brief().start
    with connection.reader(path) as con:
        [iria] = read.query(con, ["iria"], at=inicio, full=True)
    atributos = dict(iria.attributes)
    assert atributos["birth_date"] == "2017-04-02"
    assert atributos["age"] == "9"
    # La edad cuadra con el nacimiento en el arranque: la trampa es solo la del recuerdo.
    nacimiento = date.fromisoformat(atributos["birth_date"])
    arranque = date.fromisoformat(inicio.stamp)
    cumplidos = (
        arranque.year
        - nacimiento.year
        - ((arranque.month, arranque.day) < (nacimiento.month, nacimiento.day))
    )
    assert cumplidos == int(atributos["age"])
    # I1: una escena en la fecha del recuerdo con Iria presente es anterior a su nacimiento.
    escena = WorldTime(stamp=RECUERDO.isoformat())
    assert escena.stamp < atributos["birth_date"]


def test_check_timeline_caza_la_fecha_del_recuerdo_narrada(tmp_path: Path) -> None:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief(), global_terms=())
    texto = (
        "Iria se ató las zapatillas como el 14 de marzo le enseñó su abuelo. "
        "Pensó en la final del 31 de junio y apretó el testigo."
    )
    defectos = check_timeline(texto, allowed_dates=_calendario(path))
    assert [d.kind for d in defectos] == ["check.timeline", "check.timeline"]
    assert all(d.severity is Severity.S1 for d in defectos)
    citas = [d.evidence.quote for d in defectos]
    assert any("14 de marzo" in c for c in citas) and any("31 de junio" in c for c in citas)


def test_una_escena_que_no_cae_en_la_trampa_no_da_defecto(tmp_path: Path) -> None:
    path = tmp_path / "n.sqlite"
    create_novel(path, _brief(), global_terms=())
    texto = "Iria se ató las zapatillas como le enseñó su abuelo y apretó el testigo."
    assert check_timeline(texto, allowed_dates=_calendario(path)) == []


def _existe(anio: int, mes: int, dia: int) -> bool:
    try:
        date(anio, mes, dia)
    except ValueError:
        return False
    return True
