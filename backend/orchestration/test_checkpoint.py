"""El punto de reanudacion.

RF-20, PRO-I2, RNF-09. Lo que se comprueba: se escribe por escena, descarta lo
posterior, y una caida pierde como mucho una escena.

La segunda mitad son los contraejemplos de TLC (`orchestration/model/README.md`
§7.1) sobre el bucle real: una caida simulada en el punto exacto de la traza y
una segunda tirada que reanuda sobre el mismo fichero.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pytest

from canon.brief import create_novel
from canon.db import connection
from commons.db.working_memory import working_memory_writer
from commons.tracing.trace import Trace
from commons.types.primitives import Defect, Evidence, Severity
from commons.types.scene import SceneSpec
from orchestration.checkpoint import (
    ResumePoint,
    clear,
    load,
    load_outline,
    save,
    save_budget,
    save_outline,
)
from orchestration.loop import RunAbortedError, run
from orchestration.retries import CHAPTER_ATTEMPTS
from orchestration.test_loop import _brief, _engine, _outline, _specs
from planning.outline.types import Outline
from supervision.prompts import HealthVerdict


@pytest.fixture
def novela(tmp_path: Path) -> Path:
    path = tmp_path / "n.sqlite"
    connection.create(path)
    return path


def _borrador(path: Path, chapter: int, scene: int) -> None:
    with working_memory_writer(path) as wm:
        wm.execute(
            "INSERT INTO wm_draft (chapter, scene_number, text, created_at) "
            "VALUES (?, ?, 'texto', datetime('now'))",
            (chapter, scene),
        )


def _borradores(path: Path) -> list[int]:
    con = sqlite3.connect(path)
    filas = [r[0] for r in con.execute("SELECT scene_number FROM wm_draft ORDER BY 1")]
    con.close()
    return filas


def test_sin_tirada_no_hay_punto(novela: Path) -> None:
    assert load(novela) is None


def test_se_guarda_y_se_recupera(novela: Path) -> None:
    save(novela, ResumePoint(chapter=3, last_closed_scene=2))
    punto = load(novela)
    assert punto is not None
    assert (punto.chapter, punto.last_closed_scene) == (3, 2)


def test_la_siguiente_escena_sale_del_punto(novela: Path) -> None:
    assert ResumePoint(chapter=1).next_scene() == 1
    assert ResumePoint(chapter=1, last_closed_scene=4).next_scene() == 5


def test_guardar_descarta_los_borradores_posteriores(novela: Path) -> None:
    """PRO-I2. Un borrador posterior puede estar a medias y no ha pasado ninguna
    puerta: conservarlo dejaria entrar texto que nadie aprobo por la puerta de
    atras de una interrupcion."""
    for escena in (1, 2, 3, 4):
        _borrador(novela, 3, escena)

    save(novela, ResumePoint(chapter=3, last_closed_scene=2))
    assert _borradores(novela) == [1, 2]


def test_una_caida_pierde_como_mucho_una_escena(novela: Path) -> None:
    """RNF-09. Se guarda al cerrar CADA escena, asi que lo perdido es siempre la
    que estaba en curso."""
    save(novela, ResumePoint(chapter=2, last_closed_scene=1))
    _borrador(novela, 2, 2)  # la que estaba escribiendose cuando cayo

    punto = load(novela)
    assert punto is not None
    assert punto.next_scene() == 2  # se reanuda justo en la que se perdio


def test_el_punto_sobrevive_a_la_congelacion(novela: Path) -> None:
    """Se borra al terminar la obra, no al congelar un capitulo: si se borrara,
    una caida justo despues de congelar dejaria la tirada sin saber por donde
    iba."""
    from canon.freeze.freeze import purge_working_memory

    save(novela, ResumePoint(chapter=2, last_closed_scene=3))
    with connection.canon_writer(novela) as con:
        purge_working_memory(con, chapter=2)

    assert load(novela) is not None


def test_al_terminar_la_obra_se_limpia(novela: Path) -> None:
    save(novela, ResumePoint(chapter=9, last_closed_scene=4))
    clear(novela)
    assert load(novela) is None


def test_el_presupuesto_consumido_se_guarda_con_el_punto(novela: Path) -> None:
    """`architecture.md` §7.4: el punto conserva la cuenta de reintentos."""
    save(novela, ResumePoint(chapter=2, last_closed_scene=1, chapter_attempts=1, arc_replans=1))
    punto = load(novela)
    assert punto is not None
    assert (punto.chapter_attempts, punto.arc_replans) == (1, 1)


def test_un_punto_de_la_version_5_se_lee_sin_migrar(novela: Path) -> None:
    """RD-10: leer no migra. El punto de un fichero anterior se lee con la cuenta
    a cero y sin escaleta, que es lo que ese fichero sabia."""
    from canon.db.test_migration_6 import como_version_5

    como_version_5(novela)
    punto = load(novela)
    assert punto is not None and (punto.chapter, punto.last_closed_scene) == (3, 1)
    assert (punto.chapter_attempts, punto.arc_replans) == (0, 0)
    assert load_outline(novela) is None


def test_guardar_la_escaleta_no_mueve_el_punto(novela: Path) -> None:
    save(novela, ResumePoint(chapter=2, last_closed_scene=1, chapter_attempts=1))
    save_outline(novela, '{"escaleta": 1}')
    save_budget(novela, chapter=2, chapter_attempts=1, arc_replans=1)
    punto = load(novela)
    assert punto == ResumePoint(chapter=2, last_closed_scene=1, chapter_attempts=1, arc_replans=1)
    assert load_outline(novela) == '{"escaleta": 1}'


# ------------------------------------------------ la tirada entera, con caidas


class _Caida(BaseException):
    """El proceso muere. `BaseException` para que ningun `except Exception` del
    bucle la trate como un fallo recuperable: una caida no se reintenta."""


@pytest.fixture
def tirada(tmp_path: Path) -> tuple[Path, Trace]:
    path = tmp_path / "t.sqlite"
    create_novel(path, _brief())
    return path, Trace(tmp_path / "t.trace.jsonl")


def _texto(spec: SceneSpec) -> str:
    return f"{spec.identity.scene_id} " + " ".join(["palabra"] * spec.output.target_words)


def _s1_en(spec: SceneSpec) -> list[Defect]:
    return [
        Defect(
            kind="check.format",
            severity=Severity.S1,
            evidence=Evidence(quote=spec.identity.scene_id, offset=0),
            rule="en presente",
        )
    ]


def test_b1_una_caida_tras_congelar_no_recongela_el_capitulo(tirada: tuple[Path, Trace]) -> None:
    """B1, `NoChapterDuplicated`. La caida llega en el Supervisor del capitulo 1:
    ya congelado, con el punto aun en `(1, ultima escena)`. Reanudar no lo
    reescribe ni duplica su delta: sigue desde su puerta de acto."""
    path, traza = tirada
    escritas: list[str] = []
    caidas: list[int] = []

    def escribe(spec: SceneSpec, _p: object) -> str:
        escritas.append(spec.identity.scene_id)
        return _texto(spec)

    def supervisa(n: int, _t: int, _o: Outline, _m: object) -> HealthVerdict:
        if n == 1 and not caidas:
            caidas.append(n)
            raise _Caida("el proceso muere entre commit_chapter y save(chapter=2)")
        return HealthVerdict(healthy=True)

    motor = _engine(write_scene=escribe, supervise=supervisa)
    with pytest.raises(_Caida):
        run(path, _brief(), motor, novel_id="t", chapters=2, specs_for=_specs, trace=traza)
    punto = load(path)
    assert punto is not None and punto.chapter == 1, "el punto no llego a avanzar"

    run(path, _brief(), motor, novel_id="t", chapters=2, specs_for=_specs, trace=traza)

    assert [r.fields["chapter"] for r in traza.records("chapter.frozen")] == [1, 2]
    assert escritas == ["c1e1", "c1e2", "c2e1", "c2e2"], "el capitulo 1 no se reescribio"
    with connection.reader(path) as con:
        eventos = con.execute(
            "SELECT count(*) AS n FROM event WHERE chapter_origin = 1"
        ).fetchone()["n"]
    assert eventos == 1, "el delta del capitulo 1 entro una sola vez en el registro"


def test_b3_una_escena_que_no_paso_su_puerta_no_se_reutiliza(tirada: tuple[Path, Trace]) -> None:
    """B3, `ResumeOnlyClosed` y `NeverPublishUngated`. `c1e2` agota su escalera
    sin pasar; la caida llega en la replanificacion de la cuarentena. Reanudar
    no la toma por cerrada: se vuelve a escribir y, como sigue sin pasar, el
    capitulo 1 no congela nunca."""
    path, traza = tirada
    caidas: list[int] = []

    def verifica(spec: SceneSpec, _t: str) -> list[Defect]:
        return _s1_en(spec) if spec.identity.scene_id == "c1e2" else []

    def replanifica(
        outline: Outline, _a: int, _f: int, _u: Sequence[str], _r: Sequence[str]
    ) -> Outline:
        if not caidas:
            caidas.append(1)
            raise _Caida("el proceso muere antes de que la cuarentena rehaga nada")
        return outline

    motor = _engine(verify_scene=verifica, replan_act=replanifica)
    with pytest.raises(_Caida):
        run(path, _brief(), motor, novel_id="t", chapters=2, specs_for=_specs, trace=traza)
    punto = load(path)
    assert punto is not None and (punto.last_closed_scene or 0) < 2, "c1e2 no esta cerrada"
    assert 2 not in _borradores(path), "ni su borrador"

    with pytest.raises(RunAbortedError):
        run(path, _brief(), motor, novel_id="t", chapters=2, specs_for=_specs, trace=traza)

    assert 2 not in [r.fields["scene"] for r in traza.records("scene.resumed")]
    assert not traza.records("chapter.frozen")
    with connection.reader(path) as con:
        assert con.execute("SELECT count(*) AS n FROM prose_scene").fetchone()["n"] == 0


def test_b4_reanudar_conserva_los_reintentos_consumidos(tirada: tuple[Path, Trace]) -> None:
    """B4, `RetriesWithinLimit`, `architecture.md` §7.4. `c1e2` agota sus tres
    intentos y se reespecifica, lo que gasta un intento de capitulo; la caida
    llega en la reespecificacion. Al reanudar, la escalera sigue donde iba: la
    escena no se reespecifica otra vez antes de que el tramo se replanifique."""
    path, traza = tirada
    llamadas: list[str] = []

    def verifica(spec: SceneSpec, _t: str) -> list[Defect]:
        return _s1_en(spec) if spec.identity.scene_id == "c1e2" else []

    def reespecifica(specs: Sequence[SceneSpec], _d: Sequence[Defect]) -> Sequence[SceneSpec]:
        llamadas.append("respec-escena" if len(specs) == 1 else "respec-capitulo")
        if llamadas == ["respec-escena"]:
            raise _Caida("el proceso muere al reespecificar c1e2")
        return specs

    def replanifica(
        outline: Outline, _a: int, _f: int, _u: Sequence[str], _r: Sequence[str]
    ) -> Outline:
        llamadas.append("replan")
        return outline

    motor = _engine(verify_scene=verifica, respec=reespecifica, replan_act=replanifica)
    with pytest.raises(_Caida):
        run(path, _brief(), motor, novel_id="t", chapters=2, specs_for=_specs, trace=traza)

    with pytest.raises(RunAbortedError):
        run(path, _brief(), motor, novel_id="t", chapters=2, specs_for=_specs, trace=traza)

    antes_del_tramo = llamadas[: llamadas.index("replan")]
    assert antes_del_tramo.count("respec-escena") <= CHAPTER_ATTEMPTS - 1, llamadas


def test_r1_reanudar_sigue_con_la_escaleta_vigente(tirada: tuple[Path, Trace]) -> None:
    """R1. El Supervisor replanifica el capitulo 2 tras congelar el 1; la caida
    llega escribiendo `c2e1`. Reanudar no vuelve a pedir la escaleta al
    Arquitecto: sigue con la replanificada."""
    path, traza = tirada
    planes: list[int] = []
    vistas: list[str] = []

    def arquitecto(_b: object, _c: int, _d: Sequence[object]) -> Outline:
        planes.append(1)
        return _outline()

    def supervisa(n: int, _t: int, _o: Outline, _m: object) -> HealthVerdict:
        return HealthVerdict(
            healthy=n != 1, signal="narrative_debt", act=2, from_chapter=2, reason="la deuda crece"
        )

    def replanifica(
        outline: Outline, _a: int, _f: int, _u: Sequence[str], _r: Sequence[str]
    ) -> Outline:
        escenas = tuple(
            e.model_copy(update={"value_change": "de la calma a la furia"}) if e.chapter == 2 else e
            for e in outline.scenes
        )
        return outline.model_copy(update={"scenes": escenas})

    def escribe(spec: SceneSpec, _p: object) -> str:
        if spec.identity.chapter == 2:
            vistas.append(spec.function.value_change)
            if len(vistas) == 1:
                raise _Caida("el proceso muere escribiendo c2e1")
        return _texto(spec)

    motor = _engine(
        plan_outline=arquitecto, supervise=supervisa, replan_act=replanifica, write_scene=escribe
    )
    with pytest.raises(_Caida):
        run(path, _brief(), motor, novel_id="t", chapters=2, specs_for=_specs, trace=traza)

    run(path, _brief(), motor, novel_id="t", chapters=2, specs_for=_specs, trace=traza)

    assert planes == [1], "la escaleta no se volvio a pedir"
    assert set(vistas) == {"de la calma a la furia"}, "el capitulo 2 es el replanificado"
