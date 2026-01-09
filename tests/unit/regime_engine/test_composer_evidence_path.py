import unittest

from regime_engine.contracts.regimes import Regime
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.engine import run
from regime_engine.state.embedded_evidence import (
    EMBEDDED_EVIDENCE_KEY,
    INVALIDATION_INVALID_BOUNDS,
    INVALIDATION_SYMBOL_MISMATCH,
    INVALIDATION_TIMESTAMP_MISMATCH,
    INVALIDATION_UNKNOWN_REGIME,
    extract_embedded_evidence,
)


def _make_snapshot(structure_levels: dict[str, object]) -> RegimeInputSnapshot:
    return RegimeInputSnapshot(
        symbol="TEST",
        timestamp=180_000,
        market=MarketSnapshot(
            price=1.0,
            vwap=1.0,
            atr=1.0,
            atr_z=0.0,
            range_expansion=0.0,
            structure_levels=structure_levels,
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


class TestComposerEvidencePath(unittest.TestCase):
    def test_invalid_opinions_are_dropped(self) -> None:
        payload = {
            "symbol": "TEST",
            "engine_timestamp_ms": 180_000,
            "opinions": [
                {
                    "regime": "UNKNOWN_REGIME",
                    "strength": 0.5,
                    "confidence": 0.5,
                    "source": "composer:bad",
                },
                {
                    "regime": Regime.CHOP_BALANCED.value,
                    "strength": 2.0,
                    "confidence": 0.5,
                    "source": "composer:bad2",
                },
            ],
        }
        snapshot = _make_snapshot({EMBEDDED_EVIDENCE_KEY: payload})
        result = extract_embedded_evidence(snapshot)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.evidence.opinions, ())
        self.assertIn(INVALIDATION_UNKNOWN_REGIME, result.invalidations)
        self.assertIn(INVALIDATION_INVALID_BOUNDS, result.invalidations)

    def test_ordering_is_deterministic(self) -> None:
        payload = {
            "symbol": "TEST",
            "engine_timestamp_ms": 180_000,
            "opinions": [
                {
                    "regime": Regime.TREND_BUILD_UP.value,
                    "strength": 0.1,
                    "confidence": 0.2,
                    "source": "b",
                },
                {
                    "regime": Regime.CHOP_BALANCED.value,
                    "strength": 0.9,
                    "confidence": 0.3,
                    "source": "a",
                },
                {
                    "regime": Regime.CHOP_BALANCED.value,
                    "strength": 0.4,
                    "confidence": 0.5,
                    "source": "a",
                },
            ],
        }
        snapshot = _make_snapshot({EMBEDDED_EVIDENCE_KEY: payload})
        result = extract_embedded_evidence(snapshot)
        self.assertIsNotNone(result)
        assert result is not None
        ordered = result.evidence.opinions
        self.assertEqual(ordered[0].regime, Regime.CHOP_BALANCED)
        self.assertEqual(ordered[0].confidence, 0.5)
        self.assertEqual(ordered[1].regime, Regime.CHOP_BALANCED)
        self.assertEqual(ordered[1].confidence, 0.3)
        self.assertEqual(ordered[2].regime, Regime.TREND_BUILD_UP)

    def test_zero_opinions_yields_uniform_projection(self) -> None:
        payload = {
            "symbol": "OTHER",
            "engine_timestamp_ms": 42,
            "opinions": [
                {
                    "regime": Regime.TREND_BUILD_UP.value,
                    "strength": 0.5,
                    "confidence": 0.5,
                    "source": "composer:test",
                }
            ],
        }
        snapshot = _make_snapshot({EMBEDDED_EVIDENCE_KEY: payload})
        output = run(snapshot)
        self.assertEqual(output.regime, Regime.CHOP_BALANCED)
        self.assertIn("DRIVER_NO_CANONICAL_EVIDENCE", output.drivers)
        self.assertIn(INVALIDATION_SYMBOL_MISMATCH, output.invalidations)
        self.assertIn(INVALIDATION_TIMESTAMP_MISMATCH, output.invalidations)


if __name__ == "__main__":
    unittest.main()
