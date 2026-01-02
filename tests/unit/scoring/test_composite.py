import unittest

from regime_engine.contracts.regimes import Regime
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.scoring import score_all


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


class TestCompositeScoring(unittest.TestCase):
    def test_score_all_order_and_count(self) -> None:
        snapshot = _make_snapshot()
        scores = score_all(snapshot)

        expected_order = [
            Regime.CHOP_BALANCED,
            Regime.CHOP_STOPHUNT,
            Regime.LIQUIDATION_UP,
            Regime.LIQUIDATION_DOWN,
            Regime.SQUEEZE_UP,
            Regime.SQUEEZE_DOWN,
            Regime.TREND_BUILD_UP,
            Regime.TREND_BUILD_DOWN,
            Regime.TREND_EXHAUSTION,
        ]

        self.assertEqual([score.regime for score in scores], expected_order)
        self.assertEqual(len(scores), len(expected_order))


if __name__ == "__main__":
    unittest.main()
