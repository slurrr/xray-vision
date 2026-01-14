import unittest

from composer.engine_evidence.compute import compute_engine_evidence_snapshot
from composer.evidence.compute import compute_evidence_snapshot
from composer.features.compute import compute_feature_snapshot
from composer.legacy_snapshot.builder import build_legacy_snapshot
from market_data.contracts import SCHEMA_NAME, SCHEMA_VERSION, RawMarketEvent


def _trade(
    *,
    price: float,
    quantity: float,
    side: str,
    exchange_ts_ms: int,
    symbol: str = "TEST",
) -> RawMarketEvent:
    return RawMarketEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type="TradeTick",
        source_id="source",
        symbol=symbol,
        exchange_ts_ms=exchange_ts_ms,
        recv_ts_ms=exchange_ts_ms + 1,
        raw_payload=b"{}",
        normalized={"price": price, "quantity": quantity, "side": side},
    )


class TestComposeEngineEvidence(unittest.TestCase):
    def test_replay_equivalence(self) -> None:
        raw_events = (
            _trade(price=1.0, quantity=1.0, side="buy", exchange_ts_ms=10),
            _trade(price=2.0, quantity=2.0, side="sell", exchange_ts_ms=20),
        )
        first_features = compute_feature_snapshot(
            raw_events, symbol="TEST", engine_timestamp_ms=180_000
        )
        first_evidence = compute_engine_evidence_snapshot(first_features)
        second_features = compute_feature_snapshot(
            raw_events, symbol="TEST", engine_timestamp_ms=180_000
        )
        second_evidence = compute_engine_evidence_snapshot(second_features)
        self.assertEqual(first_features, second_features)
        self.assertEqual(first_evidence, second_evidence)

    def test_no_eligible_data_embeds_classical_opinion(self) -> None:
        feature_snapshot = compute_feature_snapshot((), symbol="TEST", engine_timestamp_ms=180_000)
        evidence_snapshot = compute_engine_evidence_snapshot(feature_snapshot)
        neutral_evidence_snapshot = compute_evidence_snapshot(feature_snapshot)
        legacy_snapshot = build_legacy_snapshot(
            (),
            symbol="TEST",
            engine_timestamp_ms=180_000,
            feature_snapshot=feature_snapshot,
            evidence_snapshot=evidence_snapshot,
            neutral_evidence_snapshot=neutral_evidence_snapshot,
        )
        self.assertIsNotNone(evidence_snapshot.opinions)
        self.assertIn(
            "composer_evidence_snapshot_v1", legacy_snapshot.market.structure_levels
        )


if __name__ == "__main__":
    unittest.main()
