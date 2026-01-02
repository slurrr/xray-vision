import unittest
from unittest.mock import patch

from regime_engine.contracts.regimes import Regime
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.veto import rules


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


class TestVetoRules(unittest.TestCase):
    def test_acceptance_high_no_liquidation_true(self) -> None:
        snapshot = _make_snapshot()
        with patch("regime_engine.veto.rules.acceptance_is_high", return_value=True):
            results = rules.rule_acceptance_high_no_liquidation(snapshot, [])

        self.assertEqual(
            [r.regime for r in results],
            [Regime.LIQUIDATION_UP, Regime.LIQUIDATION_DOWN],
        )
        for result in results:
            self.assertTrue(result.vetoed)
            self.assertEqual(result.reasons, ["acceptance_high_veto_liquidation"])

    def test_acceptance_high_no_liquidation_false(self) -> None:
        snapshot = _make_snapshot()
        with patch("regime_engine.veto.rules.acceptance_is_high", return_value=False):
            results = rules.rule_acceptance_high_no_liquidation(snapshot, [])

        self.assertEqual(results, [])

    def test_acceptance_high_no_chop_true(self) -> None:
        snapshot = _make_snapshot()
        with patch("regime_engine.veto.rules.acceptance_is_high", return_value=True):
            results = rules.rule_acceptance_high_no_chop(snapshot, [])

        self.assertEqual(
            [r.regime for r in results],
            [Regime.CHOP_BALANCED, Regime.CHOP_STOPHUNT],
        )
        for result in results:
            self.assertTrue(result.vetoed)
            self.assertEqual(result.reasons, ["acceptance_high_veto_chop"])

    def test_oi_contracting_atr_expanding_no_trend_build_up_true(self) -> None:
        snapshot = _make_snapshot()
        with (
            patch("regime_engine.veto.rules.oi_is_contracting", return_value=True),
            patch("regime_engine.veto.rules.atr_is_expanding", return_value=True),
        ):
            results = rules.rule_oi_contracting_atr_expanding_no_trend_build_up(snapshot, [])

        self.assertEqual([r.regime for r in results], [Regime.TREND_BUILD_UP])
        self.assertEqual(
            results[0].reasons, ["oi_contracting_atr_expanding_veto_trend_build"]
        )

    def test_oi_contracting_atr_expanding_no_trend_build_down_true(self) -> None:
        snapshot = _make_snapshot()
        with (
            patch("regime_engine.veto.rules.oi_is_contracting", return_value=True),
            patch("regime_engine.veto.rules.atr_is_expanding", return_value=True),
        ):
            results = rules.rule_oi_contracting_atr_expanding_no_trend_build_down(snapshot, [])

        self.assertEqual([r.regime for r in results], [Regime.TREND_BUILD_DOWN])
        self.assertEqual(
            results[0].reasons, ["oi_contracting_atr_expanding_veto_trend_build"]
        )

    def test_force_chop_balanced_true(self) -> None:
        snapshot = _make_snapshot()
        with (
            patch("regime_engine.veto.rules.oi_is_flat", return_value=True),
            patch("regime_engine.veto.rules.atr_is_compressed", return_value=True),
        ):
            results = rules.rule_oi_flat_atr_compressed_force_chop_balanced(snapshot, [])

        expected = [regime for regime in Regime if regime is not Regime.CHOP_BALANCED]
        self.assertEqual([r.regime for r in results], expected)
        for result in results:
            self.assertTrue(result.vetoed)
            self.assertEqual(result.reasons, ["oi_flat_atr_compressed_force_chop_balanced"])

    def test_force_chop_balanced_false(self) -> None:
        snapshot = _make_snapshot()
        with (
            patch("regime_engine.veto.rules.oi_is_flat", return_value=False),
            patch("regime_engine.veto.rules.atr_is_compressed", return_value=False),
        ):
            results = rules.rule_oi_flat_atr_compressed_force_chop_balanced(snapshot, [])

        self.assertEqual(results, [])

    def test_rule_registry_order(self) -> None:
        expected = (
            rules.rule_acceptance_high_no_liquidation,
            rules.rule_acceptance_high_no_chop,
            rules.rule_oi_contracting_atr_expanding_no_trend_build_up,
            rules.rule_oi_contracting_atr_expanding_no_trend_build_down,
            rules.rule_oi_flat_atr_compressed_force_chop_balanced,
        )
        self.assertEqual(rules.rule_registry(), expected)


if __name__ == "__main__":
    unittest.main()
