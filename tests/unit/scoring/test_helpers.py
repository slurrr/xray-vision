import unittest

from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.scoring.helpers import score_symmetric


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


class TestHelpers(unittest.TestCase):
    def test_score_symmetric_returns_regime_score(self) -> None:
        snapshot = _make_snapshot()
        contributors = ["market.atr_zscore", "flow.cvd_efficiency"]
        score = score_symmetric(snapshot, regime=Regime.SQUEEZE_UP, contributors=contributors)

        self.assertIsInstance(score, RegimeScore)
        self.assertEqual(score.regime, Regime.SQUEEZE_UP)
        self.assertEqual(score.score, 0.0)
        self.assertEqual(score.contributors, contributors)


if __name__ == "__main__":
    unittest.main()
