import math
import unittest

from composer.features.compute import compute_feature_snapshot
from market_data.contracts import SCHEMA_NAME, SCHEMA_VERSION, RawMarketEvent


def _trade(
    *,
    price: float,
    quantity: float,
    side: str | None,
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


def _candle(
    *,
    high: float,
    low: float,
    close: float,
    exchange_ts_ms: int,
    interval_ms: int = 180_000,
    is_final: bool = True,
    symbol: str = "TEST",
) -> RawMarketEvent:
    return RawMarketEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type="Candle",
        source_id="source",
        symbol=symbol,
        exchange_ts_ms=exchange_ts_ms,
        recv_ts_ms=exchange_ts_ms + 1,
        raw_payload=b"{}",
        normalized={
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1.0,
            "interval_ms": interval_ms,
            "is_final": is_final,
        },
    )


def _open_interest(*, value: float, exchange_ts_ms: int, symbol: str = "TEST") -> RawMarketEvent:
    return RawMarketEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type="OpenInterest",
        source_id="source",
        symbol=symbol,
        exchange_ts_ms=exchange_ts_ms,
        recv_ts_ms=exchange_ts_ms + 1,
        raw_payload=b"{}",
        normalized={"open_interest": value},
    )


class TestFeatureSnapshotV1(unittest.TestCase):
    def test_feature_snapshot_emits_canonical_only(self) -> None:
        events = (_trade(price=1.0, quantity=1.0, side="buy", exchange_ts_ms=10),)
        snapshot = compute_feature_snapshot(events, symbol="TEST", engine_timestamp_ms=180_000)
        self.assertIn("price_last", snapshot.features)
        self.assertNotIn("price", snapshot.features)

    def test_price_last_respects_engine_timestamp(self) -> None:
        events = (
            _trade(price=1.0, quantity=1.0, side="buy", exchange_ts_ms=90),
            _trade(price=2.0, quantity=1.0, side="buy", exchange_ts_ms=110),
        )
        snapshot = compute_feature_snapshot(events, symbol="TEST", engine_timestamp_ms=100)
        self.assertEqual(snapshot.features["price_last"], 1.0)

    def test_vwap_3m_window(self) -> None:
        events = (
            _trade(price=1.0, quantity=1.0, side="buy", exchange_ts_ms=10),
            _trade(price=3.0, quantity=3.0, side="sell", exchange_ts_ms=179_000),
            _trade(price=5.0, quantity=5.0, side="buy", exchange_ts_ms=181_000),
        )
        snapshot = compute_feature_snapshot(events, symbol="TEST", engine_timestamp_ms=180_000)
        value = snapshot.features["vwap_3m"]
        self.assertIsNotNone(value)
        assert value is not None
        self.assertAlmostEqual(value, (1.0 * 1.0 + 3.0 * 3.0) / 4.0)

    def test_cvd_3m_requires_side(self) -> None:
        events = (_trade(price=1.0, quantity=1.0, side=None, exchange_ts_ms=50),)
        snapshot = compute_feature_snapshot(events, symbol="TEST", engine_timestamp_ms=180_000)
        self.assertIsNone(snapshot.features["cvd_3m"])

    def test_aggressive_volume_ratio_null_on_zero(self) -> None:
        events = (
            _trade(price=1.0, quantity=1.0, side=None, exchange_ts_ms=50),
            _trade(price=1.0, quantity=1.0, side=None, exchange_ts_ms=60),
        )
        snapshot = compute_feature_snapshot(events, symbol="TEST", engine_timestamp_ms=180_000)
        self.assertIsNone(snapshot.features["aggressive_volume_ratio_3m"])

    def test_atr_14_requires_min_candles(self) -> None:
        events = tuple(
            _candle(high=10.0, low=5.0, close=7.0, exchange_ts_ms=idx * 180_000)
            for idx in range(10)
        )
        snapshot = compute_feature_snapshot(events, symbol="TEST", engine_timestamp_ms=2_000_000)
        self.assertIsNone(snapshot.features["atr_14"])

    def test_atr_14_computes_mean_true_range(self) -> None:
        events = tuple(
            _candle(high=10.0, low=5.0, close=7.0, exchange_ts_ms=idx * 180_000)
            for idx in range(14)
        )
        snapshot = compute_feature_snapshot(events, symbol="TEST", engine_timestamp_ms=2_000_000)
        self.assertEqual(snapshot.features["atr_14"], 5.0)

    def test_atr_z_50_requires_history(self) -> None:
        events = tuple(
            _candle(high=10.0, low=5.0, close=7.0, exchange_ts_ms=idx * 180_000)
            for idx in range(20)
        )
        snapshot = compute_feature_snapshot(events, symbol="TEST", engine_timestamp_ms=4_000_000)
        self.assertIsNone(snapshot.features["atr_z_50"])

    def test_atr_z_50_is_finite_when_available(self) -> None:
        events = tuple(
            _candle(
                high=10.0 + idx,
                low=5.0,
                close=7.0 + idx,
                exchange_ts_ms=idx * 180_000,
            )
            for idx in range(63)
        )
        snapshot = compute_feature_snapshot(events, symbol="TEST", engine_timestamp_ms=20_000_000)
        value = snapshot.features["atr_z_50"]
        self.assertIsNotNone(value)
        assert value is not None
        self.assertTrue(math.isfinite(value))

    def test_open_interest_latest_prefers_exchange_ts(self) -> None:
        events = (
            _open_interest(value=1.0, exchange_ts_ms=10),
            _open_interest(value=3.0, exchange_ts_ms=20),
        )
        snapshot = compute_feature_snapshot(events, symbol="TEST", engine_timestamp_ms=100)
        self.assertEqual(snapshot.features["open_interest_latest"], 3.0)


if __name__ == "__main__":
    unittest.main()
