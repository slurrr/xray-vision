import unittest

from composer.contracts.feature_snapshot import (
    FEATURE_KEYS_V1,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    FeatureSnapshot,
)
from composer.legacy_snapshot.builder import build_legacy_snapshot
from market_data.contracts import SCHEMA_NAME as RAW_SCHEMA_NAME
from market_data.contracts import SCHEMA_VERSION as RAW_SCHEMA_VERSION
from market_data.contracts import RawMarketEvent
from regime_engine.contracts.regimes import Regime
from regime_engine.contracts.snapshots import MISSING, RegimeInputSnapshot
from regime_engine.state.evidence import EvidenceOpinion, EvidenceSnapshot


def _feature_snapshot(values: dict[str, float | None]) -> FeatureSnapshot:
    features = {key: values.get(key) for key in FEATURE_KEYS_V1}
    return FeatureSnapshot(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol="TEST",
        engine_timestamp_ms=180_000,
        features=features,
    )


def _raw_event(*, event_type: str, normalized: dict[str, object]) -> RawMarketEvent:
    return RawMarketEvent(
        schema=RAW_SCHEMA_NAME,
        schema_version=RAW_SCHEMA_VERSION,
        event_type=event_type,
        source_id="source",
        symbol="TEST",
        exchange_ts_ms=None,
        recv_ts_ms=1,
        raw_payload=b"{}",
        normalized=normalized,
    )


class TestLegacySnapshotBuilder(unittest.TestCase):
    def test_snapshot_inputs_pass_through(self) -> None:
        snapshot_event = _raw_event(
            event_type="SnapshotInputs",
            normalized={
                "timestamp_ms": 180_000,
                "market": {"price": 2.0},
                "derivatives": {"open_interest": 5.0},
                "flow": {"cvd": 3.0},
                "context": {"rs_vs_btc": 1.0},
            },
        )
        feature_snapshot = _feature_snapshot({"price": 1.0})
        evidence = EvidenceSnapshot(
            symbol="TEST",
            engine_timestamp_ms=180_000,
            opinions=(
                EvidenceOpinion(
                    regime=Regime.CHOP_BALANCED,
                    strength=0.5,
                    confidence=0.5,
                    source="composer:test",
                ),
            ),
        )
        legacy = build_legacy_snapshot(
            (snapshot_event,),
            symbol="TEST",
            engine_timestamp_ms=180_000,
            feature_snapshot=feature_snapshot,
            evidence_snapshot=evidence,
        )
        self.assertIsInstance(legacy, RegimeInputSnapshot)
        self.assertEqual(legacy.market.price, 2.0)
        self.assertEqual(legacy.derivatives.open_interest, 5.0)
        self.assertEqual(legacy.flow.cvd, 3.0)
        self.assertEqual(legacy.context.rs_vs_btc, 1.0)
        self.assertIn("composer_evidence_snapshot_v1", legacy.market.structure_levels)

    def test_fallback_from_features(self) -> None:
        feature_snapshot = _feature_snapshot(
            {
                "price": 1.2,
                "vwap": 1.0,
                "atr": 0.5,
                "atr_z": 0.2,
                "cvd": 10.0,
                "open_interest": 20.0,
            }
        )
        evidence = EvidenceSnapshot(
            symbol="TEST",
            engine_timestamp_ms=180_000,
            opinions=(),
        )
        legacy = build_legacy_snapshot(
            (),
            symbol="TEST",
            engine_timestamp_ms=180_000,
            feature_snapshot=feature_snapshot,
            evidence_snapshot=evidence,
        )
        self.assertEqual(legacy.market.price, 1.2)
        self.assertEqual(legacy.market.vwap, 1.0)
        self.assertEqual(legacy.market.atr, 0.5)
        self.assertEqual(legacy.market.atr_z, 0.2)
        self.assertEqual(legacy.derivatives.open_interest, 20.0)
        self.assertEqual(legacy.flow.cvd, 10.0)
        self.assertEqual(legacy.market.range_expansion, MISSING)
        self.assertEqual(legacy.flow.cvd_slope, MISSING)
        self.assertNotIn("composer_evidence_snapshot_v1", legacy.market.structure_levels)


if __name__ == "__main__":
    unittest.main()
