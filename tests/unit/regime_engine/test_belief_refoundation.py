import unittest

from regime_engine.confidence import synthesize_confidence
from regime_engine.contracts.regimes import Regime
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.engine import run
from regime_engine.explainability import build_regime_output
from regime_engine.resolution import resolve_regime
from regime_engine.scoring import score_all
from regime_engine.state.evidence import EvidenceOpinion, EvidenceSnapshot
from regime_engine.state.update import initialize_state, update_belief


def _make_snapshot() -> RegimeInputSnapshot:
    return RegimeInputSnapshot(
        symbol="TEST",
        timestamp=180_000,
        market=MarketSnapshot(
            price=1.0,
            vwap=1.0,
            atr=1.0,
            atr_z=0.0,
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


class TestBeliefRefoundation(unittest.TestCase):
    def test_belief_normalization(self) -> None:
        initial = initialize_state(symbol="TEST", engine_timestamp_ms=100)
        evidence = EvidenceSnapshot(
            symbol="TEST",
            engine_timestamp_ms=101,
            opinions=(
                EvidenceOpinion(
                    regime=Regime.TREND_BUILD_UP,
                    strength=1.0,
                    confidence=0.5,
                    source="test",
                ),
            ),
        )
        updated = update_belief(initial, evidence)
        total = sum(updated.belief_by_regime.values())
        self.assertAlmostEqual(total, 1.0)
        for value in updated.belief_by_regime.values():
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)
        self.assertEqual(updated.anchor_regime, Regime.TREND_BUILD_UP)

    def test_output_equivalence(self) -> None:
        snapshot = _make_snapshot()
        scores = score_all(snapshot)
        resolution = resolve_regime(scores, snapshot, weights={})
        confidence = synthesize_confidence(
            resolution,
            spread_transform=lambda spread: 0.5 * max(min(spread, 1.0), 0.0),
            agreement_transform=lambda overlap: 0.5 * max(min(overlap, 1.0), 0.0),
            veto_penalty_transform=lambda _veto_present: 1.0,
        )
        expected = build_regime_output(snapshot.symbol, snapshot.timestamp, resolution, confidence)
        actual = run(snapshot)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
