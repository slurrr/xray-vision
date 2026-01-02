import unittest

from regime_engine.confidence.pillars import (
    compute_pillar_agreement,
    contributor_to_pillar,
    contributors_to_pillars,
)
from regime_engine.contracts.regimes import Regime, RegimeScore


class TestPillars(unittest.TestCase):
    def test_contributor_to_pillar(self) -> None:
        self.assertEqual(contributor_to_pillar("market.atr_zscore"), "market")
        self.assertEqual(contributor_to_pillar("flow.cvd_slope"), "flow")

    def test_contributors_to_pillars(self) -> None:
        pillars = contributors_to_pillars(["market.x", "market.y", "flow.z"])
        self.assertEqual(pillars, frozenset({"market", "flow"}))

    def test_compute_pillar_agreement_overlap(self) -> None:
        winner = RegimeScore(
            regime=Regime.CHOP_BALANCED,
            score=1.0,
            contributors=["market.x", "flow.y"],
        )
        runner_up = RegimeScore(
            regime=Regime.SQUEEZE_UP,
            score=0.5,
            contributors=["flow.z", "derivatives.a"],
        )
        agreement = compute_pillar_agreement(winner, runner_up)
        self.assertEqual(agreement.overlap_count, 1)
        self.assertEqual(agreement.union_count, 3)
        self.assertAlmostEqual(agreement.overlap_ratio or 0.0, 1.0 / 3.0)

    def test_unknown_pillar_does_not_inflate(self) -> None:
        winner = RegimeScore(
            regime=Regime.CHOP_BALANCED,
            score=1.0,
            contributors=[".mystery"],
        )
        runner_up = RegimeScore(
            regime=Regime.SQUEEZE_UP,
            score=0.5,
            contributors=[".mystery"],
        )
        agreement = compute_pillar_agreement(winner, runner_up)
        self.assertEqual(agreement.overlap_count, 0)
        self.assertEqual(agreement.union_count, 0)
        self.assertEqual(agreement.overlap_ratio, 0.0)


if __name__ == "__main__":
    unittest.main()
