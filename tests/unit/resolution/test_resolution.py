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
from regime_engine.veto.types import VetoResult


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


class TestResolution(unittest.TestCase):
    def test_vetoed_regimes_excluded(self) -> None:
        snapshot = _make_snapshot()
        candidates = [
            RegimeScore(regime=Regime.CHOP_BALANCED, score=1.0, contributors=[]),
            RegimeScore(regime=Regime.SQUEEZE_UP, score=3.0, contributors=[]),
        ]

        def rule(_snapshot: RegimeInputSnapshot, _scores: list[RegimeScore]) -> list[VetoResult]:
            return [VetoResult(regime=Regime.SQUEEZE_UP, vetoed=True, reasons=["veto_x"]) ]

        original_registry = veto_rules.rule_registry
        veto_rules.rule_registry = lambda: (rule,)
        try:
            result = resolve_regime(candidates, snapshot, weights={})
        finally:
            veto_rules.rule_registry = original_registry

        self.assertEqual([score.regime for score in result.ranked], [Regime.CHOP_BALANCED])
        self.assertEqual(result.winner.regime if result.winner else None, Regime.CHOP_BALANCED)
        self.assertEqual([v.regime for v in result.vetoes], [Regime.SQUEEZE_UP])


if __name__ == "__main__":
    unittest.main()
