import unittest

from regime_engine.confidence import synthesize_confidence
from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.resolution.types import ConfidenceInputs, ResolutionResult
from regime_engine.veto.types import VetoResult


def _make_resolution(
    *,
    winner: RegimeScore | None,
    runner_up: RegimeScore | None,
    score_spread: float | None,
    vetoes: list[VetoResult],
) -> ResolutionResult:
    ranked = []
    if winner is not None:
        ranked.append(winner)
    if runner_up is not None:
        ranked.append(runner_up)
    return ResolutionResult(
        winner=winner,
        runner_up=runner_up,
        ranked=ranked,
        vetoes=vetoes,
        confidence_inputs=ConfidenceInputs(
            top_score=winner.score if winner else None,
            runner_up_score=runner_up.score if runner_up else None,
            score_spread=score_spread,
            contributor_overlap_count=None,
        ),
    )


class TestConfidenceSynthesis(unittest.TestCase):
    def test_confidence_none_without_winner(self) -> None:
        resolution = _make_resolution(
            winner=None,
            runner_up=None,
            score_spread=None,
            vetoes=[],
        )
        result = synthesize_confidence(
            resolution,
            spread_transform=lambda x: x,
            agreement_transform=lambda x: x,
            veto_penalty_transform=lambda _: 1.0,
        )
        self.assertIsNone(result.confidence)
        self.assertIsNone(result.breakdown.score_spread)
        self.assertIsNone(result.breakdown.pillar_overlap_ratio)

    def test_monotonicity_agreement(self) -> None:
        winner = RegimeScore(regime=Regime.CHOP_BALANCED, score=2.0, contributors=["market.a"])
        runner_low = RegimeScore(
            regime=Regime.SQUEEZE_UP, score=1.0, contributors=["flow.b"]
        )
        runner_high = RegimeScore(
            regime=Regime.SQUEEZE_UP, score=1.0, contributors=["market.c"]
        )
        base_kwargs = dict(
            spread_transform=lambda _: 0.0,
            agreement_transform=lambda x: x,
            veto_penalty_transform=lambda _: 1.0,
        )

        low = synthesize_confidence(
            _make_resolution(
                winner=winner,
                runner_up=runner_low,
                score_spread=1.0,
                vetoes=[],
            ),
            **base_kwargs,
        )
        high = synthesize_confidence(
            _make_resolution(
                winner=winner,
                runner_up=runner_high,
                score_spread=1.0,
                vetoes=[],
            ),
            **base_kwargs,
        )
        self.assertLess(low.confidence or 0.0, high.confidence or 0.0)

    def test_monotonicity_spread(self) -> None:
        winner = RegimeScore(regime=Regime.CHOP_BALANCED, score=2.0, contributors=["market.a"])
        runner = RegimeScore(regime=Regime.SQUEEZE_UP, score=1.0, contributors=["market.b"])
        base_kwargs = dict(
            spread_transform=lambda x: x,
            agreement_transform=lambda _: 0.0,
            veto_penalty_transform=lambda _: 1.0,
        )

        low = synthesize_confidence(
            _make_resolution(
                winner=winner,
                runner_up=runner,
                score_spread=0.5,
                vetoes=[],
            ),
            **base_kwargs,
        )
        high = synthesize_confidence(
            _make_resolution(
                winner=winner,
                runner_up=runner,
                score_spread=1.5,
                vetoes=[],
            ),
            **base_kwargs,
        )
        self.assertLess(low.confidence or 0.0, high.confidence or 0.0)

    def test_confidence_is_number_with_winner(self) -> None:
        winner = RegimeScore(regime=Regime.CHOP_BALANCED, score=2.0, contributors=["market.a"])
        resolution = _make_resolution(
            winner=winner,
            runner_up=None,
            score_spread=None,
            vetoes=[],
        )
        result = synthesize_confidence(
            resolution,
            spread_transform=lambda x: x,
            agreement_transform=lambda x: x,
            veto_penalty_transform=lambda _: 1.0,
        )
        self.assertIsInstance(result.confidence, float)


if __name__ == "__main__":
    unittest.main()
