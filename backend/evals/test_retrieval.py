"""El conjunto dorado de recuperacion, la medida y la malla. RF-121 a RF-125. VER-05, VER-06."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from canon.brief import create_novel
from canon.db import connection
from canon.prose_index.reindex import read_params, reindex, scene_text_from_chunks, scene_texts
from commons.provider.port import Embedding
from commons.tracing.trace import Trace
from commons.types.primitives import Quota
from commons.types.scene import SceneSpec
from evals import compare, grid, retrieval_golden, retrieval_score
from orchestration.loop import run
from orchestration.test_loop import _brief as _loop_brief
from orchestration.test_loop import _engine, _outline, _specs

PARRAFOS = [
    "Marcos entró el último y nadie levantó la vista. —¿Juego? —preguntó, y el técnico dobló la lista sin mirarlo.",
    "El vestuario olía a linimento y a lluvia vieja; alguien silbaba una canción que Marcos no reconoció.",
    "Aurelio se sentó en el banco frío y contó los dorsales con los dedos, como si le faltara uno.",
]


class _Embedder:
    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        # Un vector por longitud: parecido entre parrafos parecidos, distinto entre distintos.
        return [
            Embedding(
                values=(len(t) % 7 / 7.0, len(t) % 11 / 11.0, 0.5), model_id="doble", dimension=3
            )
            for t in texts
        ]


def _estimate(text: str) -> int:
    return max(1, len(text) // 4)


@pytest.fixture
def tirada(tmp_path: Path) -> tuple[Path, Trace]:
    """Una tirada con dobles cuya prosa tiene dialogo y parrafos, y su traza."""
    path = tmp_path / "n.sqlite"
    create_novel(path, _loop_brief())
    traza = Trace(tmp_path / "n.trace.jsonl")

    def prosa(spec: SceneSpec, _p: object) -> str:
        return "\n\n".join(f"{p} ({spec.identity.scene_id})" for p in PARRAFOS * 3)

    run(
        path,
        _loop_brief(),
        _engine(write_scene=prosa, embed=_Embedder()),
        novel_id="p",
        chapters=2,
        specs_for=_specs,
        trace=traza,
    )
    return path, traza


def test_la_escaleta_se_recupera_de_la_traza(tirada: tuple[Path, Trace]) -> None:
    _path, traza = tirada
    outline = retrieval_golden.outline_from_trace(traza)
    assert outline.scene_ids() == _outline().scene_ids()


def test_el_conjunto_dorado_sale_de_la_escaleta_y_el_canon(tirada: tuple[Path, Trace]) -> None:
    """RF-121. Sin nadie que marque nada: la promesa esperada es la escena que la planto."""
    path, traza = tirada
    golden = retrieval_golden.build(path, retrieval_golden.outline_from_trace(traza))
    por_escena = {q.spec.identity.scene_id: q for q in golden}
    # c2e1 cobra "la-lista", plantada en c1e1: sus fragmentos son los esperados del cupo promesa.
    assert "c2e1" in por_escena
    esperados = por_escena["c2e1"].expected[Quota.PROMISE]
    with connection.reader(path) as con:
        de_c1e1 = {r["id"] for r in con.execute("SELECT id FROM prose_chunk WHERE scene_id='c1e1'")}
    assert esperados == de_c1e1
    # La voz espera dialogo de escenas anteriores del mismo POV, menos la literal.
    assert por_escena["c2e1"].expected[Quota.VOICE]
    assert json.loads(retrieval_golden.dump(golden))


def test_la_medida_es_determinista_y_esta_entre_cero_y_uno(tirada: tuple[Path, Trace]) -> None:
    """RF-122."""
    path, traza = tirada
    golden = retrieval_golden.build(path, retrieval_golden.outline_from_trace(traza))
    a = retrieval_score.score(path, golden, estimate=_estimate, embed=_Embedder())
    b = retrieval_score.score(path, golden, estimate=_estimate, embed=_Embedder())
    assert a == b
    assert 0.0 <= a.aggregate <= 1.0
    assert a.queries == len(golden)


def test_la_malla_recorre_copias_y_elige_sin_tocar_la_novela(
    tirada: tuple[Path, Trace], tmp_path: Path
) -> None:
    """RF-123, RF-124, RD-27."""
    path, traza = tirada
    golden = retrieval_golden.build(path, retrieval_golden.outline_from_trace(traza))
    with connection.reader(path) as con:
        antes = con.execute("SELECT count(*) AS n FROM prose_chunk").fetchone()["n"]

    resultado = grid.run_grid(
        path,
        golden,
        estimate=_estimate,
        embed=_Embedder(),
        workdir=tmp_path / "malla",
        chunk_tokens=(120, 450),
        fusion_k=(60,),
        quota_orders={"base": tuple(Quota)},
    )
    assert len(resultado.points) == 2
    assert resultado.best in resultado.points
    with connection.reader(path) as con:
        assert con.execute("SELECT count(*) AS n FROM prose_chunk").fetchone()["n"] == antes
    with connection.reader(tmp_path / "malla" / "grid-120.sqlite") as con:
        params = read_params(con)
        assert params is not None and params[0] == 120
        assert con.execute("SELECT count(*) AS n FROM prose_chunk").fetchone()["n"] > antes
    assert "| fragmento |" in resultado.as_table()


def test_reindexar_conserva_el_texto_de_cada_escena(
    tirada: tuple[Path, Trace], tmp_path: Path
) -> None:
    """RF-124. Deshacer el solape devuelve la escena entera, y volver a cortar no la cambia."""
    path, _traza = tirada
    with connection.reader(path) as con:
        antes = scene_texts(con)
    reindex(path, chunk_tokens=150, embed=_Embedder(), fusion_k=60)
    with connection.reader(path) as con:
        despues = scene_texts(con)
    assert antes == despues
    assert scene_text_from_chunks(["a\n\nb", "b\n\nc"]) == "a\n\nb\n\nc"


def test_comparar_dos_tiradas_dice_que_empeora(tirada: tuple[Path, Trace], tmp_path: Path) -> None:
    """RF-125, RF-157."""
    path, traza = tirada
    ref = compare.measure(path, traza.path)  # type: ignore[arg-type]
    peor = ref.model_copy(update={"s1_per_1000": ref.s1_per_1000 + 1.0, "quarantines": 3})
    c = compare.compare(ref, peor)
    assert not c.promotable
    assert set(c.worse) >= {"s1_por_1000", "cuarentenas"}
    assert compare.compare(ref, ref).promotable
    assert ref.words > 0 and ref.chapters == 2
