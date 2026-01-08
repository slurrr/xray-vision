import unittest

from composer.contracts.feature_snapshot import FEATURE_KEYS_V1
from composer.features.compute import compute_feature_snapshot
from market_data.contracts import SCHEMA_NAME, SCHEMA_VERSION, RawMarketEvent


def _make_event(*, normalized: dict[str, object], symbol: str = "TEST") -> RawMarketEvent:
    return RawMarketEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type="TradeTick",
        source_id="source",
        symbol=symbol,
        exchange_ts_ms=None,
        recv_ts_ms=1,
        raw_payload=b"{}",
        normalized=normalized,
    )


class TestFeatureSnapshot(unittest.TestCase):
    def test_feature_snapshot_is_deterministic(self) -> None:
        raw_events = (
            _make_event(normalized={"price": 1.0, "vwap": 2.0}),
            _make_event(normalized={"price": 3.0, "cvd": 4.0}),
        )
        first = compute_feature_snapshot(raw_events, symbol="TEST", engine_timestamp_ms=100)
        second = compute_feature_snapshot(raw_events, symbol="TEST", engine_timestamp_ms=100)
        self.assertEqual(first, second)
        self.assertEqual(first.features["price"], 3.0)
        self.assertEqual(first.features["cvd"], 4.0)

    def test_feature_snapshot_explicit_missingness(self) -> None:
        snapshot = compute_feature_snapshot((), symbol="TEST", engine_timestamp_ms=100)
        for key in FEATURE_KEYS_V1:
            self.assertIsNone(snapshot.features[key])

    def test_feature_snapshot_ordering(self) -> None:
        raw_events = (_make_event(normalized={"vwap": 1.0, "price": 2.0}),)
        snapshot = compute_feature_snapshot(raw_events, symbol="TEST", engine_timestamp_ms=100)
        self.assertEqual(list(snapshot.features.keys()), sorted(snapshot.features.keys()))


if __name__ == "__main__":
    unittest.main()
