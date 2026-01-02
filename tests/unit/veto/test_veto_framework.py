import unittest

from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.scoring.types import UnweightedScores
from regime_engine.veto import apply_vetoes
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


def _make_scores() -> UnweightedScores:
    return UnweightedScores(
        scores=[
            RegimeScore(regime=Regime.CHOP_BALANCED, score=0.0, contributors=["a"]),
            RegimeScore(regime=Regime.SQUEEZE_UP, score=0.0, contributors=["b"]),
        ]
    )


class TestVetoFramework(unittest.TestCase):
    def test_apply_vetoes_uses_registry_order(self) -> None:
        snapshot = _make_snapshot()
        scores = _make_scores()

        def rule_one(_snapshot: RegimeInputSnapshot, _scores: list[RegimeScore]) -> list[VetoResult]:
            return [
                VetoResult(regime=Regime.CHOP_BALANCED, vetoed=True, reasons=["rule_one"])
            ]

        def rule_two(_snapshot: RegimeInputSnapshot, _scores: list[RegimeScore]) -> list[VetoResult]:
            return [VetoResult(regime=Regime.SQUEEZE_UP, vetoed=False, reasons=["rule_two"])]

        original_registry = veto_rules.rule_registry
        veto_rules.rule_registry = lambda: (rule_one, rule_two)
        try:
            vetoed = apply_vetoes(scores, snapshot)
        finally:
            veto_rules.rule_registry = original_registry

        self.assertEqual([v.regime for v in vetoed.vetoes], [Regime.CHOP_BALANCED, Regime.SQUEEZE_UP])
        self.assertEqual([v.reasons for v in vetoed.vetoes], [["rule_one"], ["rule_two"]])
        self.assertEqual(vetoed.scores, scores.scores)


if __name__ == "__main__":
    unittest.main()
