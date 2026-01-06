import unittest
from dataclasses import FrozenInstanceError

from market_data.config import (
    BackpressureConfig,
    MarketDataConfig,
    OperationalLimits,
    RetryPolicy,
    SourceConfig,
    validate_config,
)
from market_data.contracts import (
    EVENT_TYPE_REQUIRED_NORMALIZED_KEYS,
    EVENT_TYPES,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    RawMarketEvent,
)


class TestMarketDataContracts(unittest.TestCase):
    def test_event_type_registry_is_authoritative(self) -> None:
        self.assertEqual(set(EVENT_TYPES), set(EVENT_TYPE_REQUIRED_NORMALIZED_KEYS.keys()))

    def test_raw_market_event_is_frozen(self) -> None:
        event = RawMarketEvent(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            event_type="TradeTick",
            source_id="test-source",
            symbol="TEST",
            exchange_ts_ms=None,
            recv_ts_ms=123,
            raw_payload=b"{}",
            normalized={"price": 1.0, "quantity": 1.0, "side": None},
        )
        with self.assertRaises(FrozenInstanceError):
            event.symbol = "OTHER"  # type: ignore[misc]

    def test_config_validation_rejects_empty_sources(self) -> None:
        with self.assertRaises(ValueError):
            validate_config(MarketDataConfig(sources=[]))

    def test_config_validation_accepts_minimal_source(self) -> None:
        config = MarketDataConfig(
            sources=[
                SourceConfig(
                    source_id="test-source",
                    symbol_map={"X": "X"},
                    channels=["trades"],
                    limits=OperationalLimits(
                        connect_timeout_ms=1,
                        read_timeout_ms=1,
                        retry=RetryPolicy(min_delay_ms=1, max_delay_ms=1, max_attempts=1),
                        backpressure=BackpressureConfig(policy="block", max_pending=1),
                    ),
                )
            ]
        )
        validate_config(config)


if __name__ == "__main__":
    unittest.main()
