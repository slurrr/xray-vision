import unittest

from composer.contracts.feature_snapshot import FEATURE_KEYS_V1
from composer.features.compute import compute_feature_snapshot
from market_data.contracts import SCHEMA_NAME, SCHEMA_VERSION, RawMarketEvent


def _make_event(
    *,
    normalized: dict[str, object],
    symbol: str = "TEST",
    exchange_ts_ms: int | None = None,
) -> RawMarketEvent:
    return RawMarketEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type="TradeTick",
        source_id="source",
        symbol=symbol,
        exchange_ts_ms=exchange_ts_ms,
        recv_ts_ms=1,
        raw_payload=b"{}",
        normalized=normalized,
    )


class TestFeatureSnapshot(unittest.TestCase):
    def test_feature_snapshot_is_deterministic(self) -> None:
        raw_events = (
            _make_event(
                normalized={"price": 1.0, "quantity": 1.0, "side": "buy"},
                exchange_ts_ms=90,
            ),
            _make_event(
                normalized={"price": 3.0, "quantity": 2.0, "side": "sell"},
                exchange_ts_ms=95,
            ),
        )
        first = compute_feature_snapshot(raw_events, symbol="TEST", engine_timestamp_ms=100)
        second = compute_feature_snapshot(raw_events, symbol="TEST", engine_timestamp_ms=100)
        self.assertEqual(first, second)
        self.assertEqual(first.features["price_last"], 3.0)
        self.assertEqual(first.features["cvd_3m"], -1.0)

    def test_feature_snapshot_explicit_missingness(self) -> None:
        snapshot = compute_feature_snapshot((), symbol="TEST", engine_timestamp_ms=100)
        for key in FEATURE_KEYS_V1:
            self.assertIsNone(snapshot.features[key])

    def test_feature_snapshot_ordering(self) -> None:
        raw_events = (
            _make_event(
                normalized={"price": 2.0, "quantity": 1.0, "side": "buy"},
                exchange_ts_ms=50,
            ),
        )
        snapshot = compute_feature_snapshot(raw_events, symbol="TEST", engine_timestamp_ms=100)
        self.assertEqual(list(snapshot.features.keys()), sorted(snapshot.features.keys()))

    def test_feature_snapshot_emits_canonical_only(self) -> None:
        raw_events = (
            _make_event(
                normalized={"price": 2.0, "quantity": 1.0, "side": "buy"},
                exchange_ts_ms=50,
            ),
        )
        snapshot = compute_feature_snapshot(raw_events, symbol="TEST", engine_timestamp_ms=100)
        self.assertNotIn("price", snapshot.features)
        self.assertIn("price_last", snapshot.features)


if __name__ == "__main__":
    unittest.main()
