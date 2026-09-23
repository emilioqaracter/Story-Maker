"""`match.narrate`: la cronologia entra como dato. RF-44. VER-05."""

from __future__ import annotations

from commons.types.primitives import WorldTime
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
