"""`match.narrate`: la cronologia entra como dato. RF-44. VER-05."""

from __future__ import annotations

from commons.types.primitives import WorldTime
from commons.types.scene import (
    DramaticFunction,
    ExpectedOutput,
    SceneConstraints,
    SceneContent,
    SceneFunction,
    SceneIdentity,
    SceneSpec,
)
from generation.sports.narrate import chronology, expected_score, scorers
from generation.sports.simulate import MatchResult, Milestone, MilestoneKind

NOMBRES = {
    "marcos": "Marcos Vela",
    "rival9": "Iker Landa",
    "casa": "el Sporting",
    "fuera": "el Racing",
}


def _result() -> MatchResult:
    return MatchResult(
        home_team="casa",
        away_team="fuera",
        home_goals=2,
        away_goals=1,
        at=WorldTime(stamp="2026-09-01"),
        milestones=(
            Milestone(minute=12, kind=MilestoneKind.GOAL, team_id="casa", player_id="marcos"),
            Milestone(minute=40, kind=MilestoneKind.GOAL, team_id="fuera", player_id="rival9"),
            Milestone(minute=77, kind=MilestoneKind.GOAL, team_id="casa", player_id="marcos"),
            Milestone(
                minute=80,
                kind=MilestoneKind.INJURY,
                team_id="casa",
                player_id="marcos",
                detail="se retira",
            ),
        ),
        injuries=("marcos",),
    )


def test_la_cronologia_lleva_nombres_minutos_y_marcador() -> None:
    texto = chronology(_result(), NOMBRES)
    assert "el Sporting 2 - 1 el Racing" in texto
    assert "min 12: GOL de Marcos Vela" in texto
    assert "min 80: LESION de Marcos Vela" in texto


def test_lo_que_check_ledger_espera_sale_de_la_misma_cronologia() -> None:
    assert expected_score(_result()) == "2-1"
    assert scorers(_result(), NOMBRES) == ("Marcos Vela", "Iker Landa", "Marcos Vela")


def _spec() -> SceneSpec:
    return SceneSpec(
        identity=SceneIdentity(
            scene_id="c2e1",
            chapter=2,
            ordinal=1,
            pov="marcos",
            place="estadio",
            world_time=WorldTime(stamp="2026-09-01"),
        ),
        function=DramaticFunction(
            function=SceneFunction.ESTABLISH,
            value_change="de la duda a la decision",
            objective="ganar",
            obstacle="el Racing",
        ),
        content=SceneContent(cast=("marcos",), beats=("juega",)),
        output=ExpectedOutput(target_words=500, ends_with="el pitido final"),
        constraints=SceneConstraints(),
    )


def test_con_perfil_prueba_el_resultado_del_ledger_es_obligatorio_y_literal() -> None:
    """D-115. La instruccion de `prueba` dice el marcador, los goleadores con su
    minuto y que la ultima frase lleve el marcador; la de `novela` no cambia."""
    from commons.types.length import NOVELA, PRUEBA
    from generation.sports.narrate import instruction

    texto = instruction(_spec(), _result(), NOMBRES, profile=PRUEBA)
    assert "RESULTADO OBLIGATORIO" in texto
    assert "el Sporting 2-1 el Racing" in texto and "«2-1»" in texto
    assert "min 12: Marcos Vela" in texto and "min 40: Iker Landa" in texto
    assert "La ultima frase de la escena dice el marcador final en cifras: «2-1»" in texto
    assert "RESULTADO OBLIGATORIO" not in instruction(_spec(), _result(), NOMBRES, profile=NOVELA)
    assert instruction(_spec(), _result(), NOMBRES) == instruction(
        _spec(), _result(), NOMBRES, profile=NOVELA
    )

