import unittest

from regime_engine.contracts.regimes import Regime
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.scoring.stubs import (
    score_chop_balanced,
    score_chop_stophunt,
    score_liquidation_down,
    score_liquidation_up,
    score_squeeze_down,
    score_squeeze_up,
    score_trend_build_down,
    score_trend_build_up,
    score_trend_exhaustion,
)


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


class TestScoringStubs(unittest.TestCase):
    def test_stub_shapes(self) -> None:
        snapshot = _make_snapshot()
        cases = [
            (Regime.CHOP_BALANCED, score_chop_balanced),
            (Regime.CHOP_STOPHUNT, score_chop_stophunt),
            (Regime.LIQUIDATION_UP, score_liquidation_up),
            (Regime.LIQUIDATION_DOWN, score_liquidation_down),
            (Regime.SQUEEZE_UP, score_squeeze_up),
            (Regime.SQUEEZE_DOWN, score_squeeze_down),
            (Regime.TREND_BUILD_UP, score_trend_build_up),
            (Regime.TREND_BUILD_DOWN, score_trend_build_down),
            (Regime.TREND_EXHAUSTION, score_trend_exhaustion),
        ]

        for expected_regime, func in cases:
            with self.subTest(regime=expected_regime.value):
                score = func(snapshot)
                self.assertEqual(score.regime, expected_regime)
                self.assertIsInstance(score.score, float)
                self.assertTrue(all(isinstance(c, str) for c in score.contributors))

    def test_stub_contributors_are_stable(self) -> None:
        snapshot = _make_snapshot()
        expected = {
            Regime.CHOP_BALANCED: [
                "market.atr_zscore",
                "market.range_expansion",
                "flow.cvd_efficiency",
                "derivatives.oi_slope_short",
                "derivatives.funding_level",
            ],
            Regime.CHOP_STOPHUNT: [
                "market.sweep_score",
                "market.acceptance_score",
                "market.range_expansion",
                "flow.aggressive_volume_ratio",
                "derivatives.oi_slope_short",
                "derivatives.funding_level",
            ],
            Regime.LIQUIDATION_UP: [
                "market.range_expansion",
                "market.atr_zscore",
                "market.sweep_score",
                "flow.cvd_slope",
                "flow.cvd_efficiency",
                "derivatives.oi_acceleration",
                "derivatives.funding_level",
                "derivatives.funding_slope",
                "derivatives.funding_zscore",
            ],
            Regime.LIQUIDATION_DOWN: [
                "market.range_expansion",
                "market.atr_zscore",
                "market.sweep_score",
                "flow.cvd_slope",
                "flow.cvd_efficiency",
                "derivatives.oi_acceleration",
                "derivatives.funding_level",
                "derivatives.funding_slope",
                "derivatives.funding_zscore",
            ],
            Regime.SQUEEZE_UP: [
                "derivatives.oi_slope_med",
                "derivatives.oi_acceleration",
                "derivatives.funding_zscore",
                "market.range_expansion",
                "flow.cvd_slope",
                "flow.cvd_efficiency",
            ],
            Regime.SQUEEZE_DOWN: [
                "derivatives.oi_slope_med",
                "derivatives.oi_acceleration",
                "derivatives.funding_zscore",
                "market.range_expansion",
                "flow.cvd_slope",
                "flow.cvd_efficiency",
            ],
            Regime.TREND_BUILD_UP: [
                "flow.cvd_slope",
                "flow.cvd_efficiency",
                "market.acceptance_score",
                "market.range_expansion",
                "derivatives.oi_slope_med",
                "derivatives.funding_slope",
                "context.rs_vs_btc",
                "context.beta_to_btc",
                "context.alt_breadth",
            ],
            Regime.TREND_BUILD_DOWN: [
                "flow.cvd_slope",
                "flow.cvd_efficiency",
                "market.acceptance_score",
                "market.range_expansion",
                "derivatives.oi_slope_med",
                "derivatives.funding_slope",
                "context.rs_vs_btc",
                "context.beta_to_btc",
                "context.alt_breadth",
            ],
            Regime.TREND_EXHAUSTION: [
                "flow.cvd_efficiency",
                "market.sweep_score",
                "market.acceptance_score",
                "market.atr_zscore",
                "derivatives.funding_zscore",
                "derivatives.oi_acceleration",
                "context.rs_vs_btc",
                "context.alt_breadth",
            ],
        }

        cases = [
            (Regime.CHOP_BALANCED, score_chop_balanced),
            (Regime.CHOP_STOPHUNT, score_chop_stophunt),
            (Regime.LIQUIDATION_UP, score_liquidation_up),
            (Regime.LIQUIDATION_DOWN, score_liquidation_down),
            (Regime.SQUEEZE_UP, score_squeeze_up),
            (Regime.SQUEEZE_DOWN, score_squeeze_down),
            (Regime.TREND_BUILD_UP, score_trend_build_up),
            (Regime.TREND_BUILD_DOWN, score_trend_build_down),
            (Regime.TREND_EXHAUSTION, score_trend_exhaustion),
        ]

        for regime, func in cases:
            with self.subTest(regime=regime.value):
                score = func(snapshot)
                self.assertEqual(score.contributors, expected[regime])

    def test_symmetric_pairs_share_contributors(self) -> None:
        snapshot = _make_snapshot()
        self.assertEqual(
            score_liquidation_up(snapshot).contributors,
            score_liquidation_down(snapshot).contributors,
        )
        self.assertEqual(
            score_squeeze_up(snapshot).contributors,
            score_squeeze_down(snapshot).contributors,
        )
        self.assertEqual(
            score_trend_build_up(snapshot).contributors,
            score_trend_build_down(snapshot).contributors,
        )


if __name__ == "__main__":
    unittest.main()
