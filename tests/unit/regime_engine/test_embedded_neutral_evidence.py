from __future__ import annotations

import unittest

from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.state.embedded_neutral_evidence import (
    EMBEDDED_NEUTRAL_EVIDENCE_KEY,
    INVALIDATION_SYMBOL_MISMATCH,
    extract_embedded_neutral_evidence,
)


def _snapshot(structure_levels: dict[str, object]) -> RegimeInputSnapshot:
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


class TestEmbeddedNeutralEvidence(unittest.TestCase):
    def test_parse_valid_payload(self) -> None:
        payload = {
            "schema": "evidence_snapshot",
            "schema_version": "1",
            "symbol": "TEST",
            "engine_timestamp_ms": 180_000,
            "opinions": [
                {
                    "type": "momentum",
                    "direction": "UP",
                    "strength": 0.4,
                    "confidence": 0.6,
                    "source": "composer:test",
                },
                {
                    "type": "momentum",
                    "direction": "DOWN",
                    "strength": 0.7,
                    "confidence": 0.2,
                    "source": "composer:test",
                },
            ],
        }
        snapshot = _snapshot({EMBEDDED_NEUTRAL_EVIDENCE_KEY: payload})

        result = extract_embedded_neutral_evidence(snapshot)

        assert result is not None
        self.assertEqual(result.evidence.symbol, "TEST")
        self.assertEqual(result.evidence.engine_timestamp_ms, 180_000)
        self.assertEqual(len(result.evidence.opinions), 2)
        ordered = result.evidence.opinions
        self.assertEqual([op.direction for op in ordered], ["DOWN", "UP"])

    def test_invalid_symbol_records_invalidation(self) -> None:
        payload = {
            "schema": "evidence_snapshot",
            "schema_version": "1",
            "symbol": "OTHER",
            "engine_timestamp_ms": 180_000,
            "opinions": [],
        }
        snapshot = _snapshot({EMBEDDED_NEUTRAL_EVIDENCE_KEY: payload})

        result = extract_embedded_neutral_evidence(snapshot)

        assert result is not None
        self.assertIn(INVALIDATION_SYMBOL_MISMATCH, result.invalidations)


if __name__ == "__main__":
    unittest.main()
