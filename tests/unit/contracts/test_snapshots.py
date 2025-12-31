import unittest
from dataclasses import FrozenInstanceError

from regime_engine.contracts.snapshots import (
    MISSING,
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
    is_missing,
    missing_paths,
)
from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.contracts.outputs import RegimeOutput


class TestSnapshots(unittest.TestCase):
    def test_snapshots_are_frozen(self) -> None:
        market = MarketSnapshot(
            price=1.0,
            vwap=1.0,
            atr=1.0,
            atr_z=0.0,
            range_expansion=0.0,
            structure_levels={},
            acceptance_score=0.0,
            sweep_score=0.0,
        )
        with self.assertRaises(FrozenInstanceError):
            market.price = 2.0  # type: ignore[misc]

    def test_missing_sentinel_is_detectable_and_paths_are_reported(self) -> None:
        snapshot = RegimeInputSnapshot(
            symbol="TEST",
            timestamp=180_000,
            market=MarketSnapshot(
                price=MISSING,
                vwap=1.0,
                atr=1.0,
                atr_z=0.0,
                range_expansion=0.0,
                structure_levels={"poc": MISSING},
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

        self.assertTrue(is_missing(MISSING))
        self.assertFalse(is_missing(0.0))
        self.assertEqual(
            missing_paths(snapshot), frozenset({"market.price", "market.structure_levels.poc"})
        )

    def test_other_contracts_are_frozen(self) -> None:
        score = RegimeScore(regime=Regime.CHOP_BALANCED, score=0.0, contributors=[])
        with self.assertRaises(FrozenInstanceError):
            score.score = 1.0  # type: ignore[misc]

        output = RegimeOutput(
            symbol="TEST",
            timestamp=180_000,
            regime=Regime.CHOP_BALANCED,
            confidence=0.0,
            drivers=[],
            invalidations=[],
            permissions=[],
        )
        with self.assertRaises(FrozenInstanceError):
            output.confidence = 1.0  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
