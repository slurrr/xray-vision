import unittest

from regime_engine.confidence.types import ConfidenceBreakdown, ConfidenceResult, PillarAgreement
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.explainability import build_regime_output
from regime_engine.explainability.validate import ExplainabilityValidationError, validate_explainability
from regime_engine.resolution.types import ConfidenceInputs, ResolutionResult
from regime_engine.veto.types import VetoResult


def _make_confidence(confidence: float | None = 0.5) -> ConfidenceResult:
    return ConfidenceResult(
        confidence=confidence,
        breakdown=ConfidenceBreakdown(
            score_spread=None,
            pillar_overlap_ratio=None,
            veto_present=True,
        ),
        pillar_agreement=PillarAgreement(
            winner_pillars=frozenset(),
            runner_up_pillars=None,
            overlap_count=None,
            union_count=None,
            overlap_ratio=None,
        ),
    )


def _make_resolution(
    winner: RegimeScore | None,
    *,
    runner_up: RegimeScore | None = None,
    vetoes: list[VetoResult] | None = None,
) -> ResolutionResult:
    return ResolutionResult(
        winner=winner,
        runner_up=runner_up,
        ranked=[score for score in (winner, runner_up) if score is not None],
        vetoes=list(vetoes or []),
        confidence_inputs=ConfidenceInputs(
            top_score=None,
            runner_up_score=None,
            score_spread=None,
            contributor_overlap_count=None,
        ),
    )


class TestOrchestration(unittest.TestCase):
    def test_winner_none_fails(self) -> None:
        resolution = _make_resolution(
            None,
            vetoes=[
                VetoResult(
                    regime=Regime.CHOP_BALANCED,
                    vetoed=True,
                    reasons=["acceptance_high_veto_chop"],
                )
            ],
        )
        with self.assertRaises(ExplainabilityValidationError):
            build_regime_output("TEST", 180_000, resolution, _make_confidence())

    def test_empty_lists_fail_validation(self) -> None:
        winner = RegimeScore(regime=Regime.CHOP_BALANCED, score=1.0, contributors=[])
        with self.assertRaises(ExplainabilityValidationError):
            validate_explainability(winner, [], ["x"], ["y"])
        with self.assertRaises(ExplainabilityValidationError):
            validate_explainability(winner, ["x"], [], ["y"])
        with self.assertRaises(ExplainabilityValidationError):
            validate_explainability(winner, ["x"], ["y"], [])

    def test_no_veto_invalidations_fails(self) -> None:
        winner = RegimeScore(
            regime=Regime.CHOP_BALANCED,
            score=1.0,
            contributors=["market.range_expansion"],
        )
        resolution = _make_resolution(winner, vetoes=[])
        with self.assertRaises(ExplainabilityValidationError):
            build_regime_output("TEST", 180_000, resolution, _make_confidence())

    def test_happy_path_returns_output_and_winner_only(self) -> None:
        winner = RegimeScore(
            regime=Regime.SQUEEZE_UP,
            score=2.0,
            contributors=["market.range_expansion", "flow.cvd_slope"],
        )
        runner_up = RegimeScore(
            regime=Regime.CHOP_BALANCED,
            score=1.0,
            contributors=["context.alt_breadth"],
        )
        resolution = _make_resolution(
            winner,
            runner_up=runner_up,
            vetoes=[
                VetoResult(
                    regime=Regime.CHOP_BALANCED,
                    vetoed=True,
                    reasons=["acceptance_high_veto_chop"],
                )
            ],
        )

        output = build_regime_output("TEST", 180_000, resolution, _make_confidence(0.7))

        self.assertIsInstance(output, RegimeOutput)
        self.assertEqual(output.symbol, "TEST")
        self.assertEqual(output.timestamp, 180_000)
        self.assertEqual(output.regime, Regime.SQUEEZE_UP)
        self.assertEqual(output.confidence, 0.7)
        self.assertEqual(
            output.drivers,
            ["Market range expansion", "Flow CVD slope"],
        )
        self.assertNotIn("Context alt breadth", output.drivers)
        self.assertEqual(output.invalidations, ["acceptance high veto: chop"])
        self.assertEqual(output.permissions, ["SQUEEZE_UP"])


if __name__ == "__main__":
    unittest.main()
