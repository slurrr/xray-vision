import unittest

from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.resolution import resolve_regime
from regime_engine.veto import rules as veto_rules


def _make_snapshot() -> RegimeInputSnapshot:
    return RegimeInputSnapshot(
        symbol="TEST",
        timestamp=180_000,
        market=MarketSnapshot(
            price=1.0,
            vwap=1.0,
            atr=1.0,
            atr_z=1.0,
            range_expansion=0.0,
            structure_levels={},
            acceptance_score=0.0,
            sweep_score=0.0,
        ),
        derivatives=DerivativesSnapshot(
            open_interest=1.0,
            oi_slope_short=0.0,
            oi_slope_med=0.0,
            oi_accel=0.0,
            funding_rate=0.0,
            funding_slope=0.0,
            funding_z=0.0,
            liquidation_intensity=None,
        ),
        flow=FlowSnapshot(
            cvd=0.0,
            cvd_slope=0.0,
            cvd_efficiency=0.0,
            aggressive_volume_ratio=0.0,
        ),
        context=ContextSnapshot(
            rs_vs_btc=0.0,
            beta_to_btc=0.0,
            alt_breadth=0.0,
            btc_regime=None,
            eth_regime=None,
        ),
    )


class TestConfidenceInputs(unittest.TestCase):
    def test_confidence_inputs_two_scores(self) -> None:
        snapshot = _make_snapshot()
        candidates = [
            RegimeScore(regime=Regime.SQUEEZE_UP, score=2.0, contributors=["a", "b"]),
            RegimeScore(regime=Regime.CHOP_BALANCED, score=1.0, contributors=["b", "c"]),
        ]

        original_registry = veto_rules.rule_registry
        veto_rules.rule_registry = lambda: ()
        try:
            result = resolve_regime(candidates, snapshot, weights={})
        finally:
            veto_rules.rule_registry = original_registry

        inputs = result.confidence_inputs
        self.assertEqual(inputs.top_score, 2.0)
        self.assertEqual(inputs.runner_up_score, 1.0)
        self.assertEqual(inputs.score_spread, 1.0)
        self.assertEqual(inputs.contributor_overlap_count, 1)

    def test_confidence_inputs_single_score(self) -> None:
        snapshot = _make_snapshot()
        candidates = [
            RegimeScore(regime=Regime.SQUEEZE_UP, score=2.0, contributors=["a", "b"]),
        ]

        original_registry = veto_rules.rule_registry
        veto_rules.rule_registry = lambda: ()
        try:
            result = resolve_regime(candidates, snapshot, weights={})
        finally:
            veto_rules.rule_registry = original_registry

        inputs = result.confidence_inputs
        self.assertEqual(inputs.top_score, 2.0)
        self.assertIsNone(inputs.runner_up_score)
        self.assertIsNone(inputs.score_spread)
        self.assertIsNone(inputs.contributor_overlap_count)


if __name__ == "__main__":
    unittest.main()
