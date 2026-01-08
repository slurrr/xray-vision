import unittest

from composer.composer import compose
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


class TestCompose(unittest.TestCase):
    def test_compose_replay_equivalence(self) -> None:
        raw_events = (
            _make_event(normalized={"price": 1.0, "vwap": 2.0}),
            _make_event(normalized={"price": 3.0, "cvd": 4.0}),
        )
        first_features, first_evidence = compose(
            raw_events,
            symbol="TEST",
            engine_timestamp_ms=100,
        )
        second_features, second_evidence = compose(
            raw_events,
            symbol="TEST",
            engine_timestamp_ms=100,
        )
        self.assertEqual(first_features, second_features)
        self.assertEqual(first_evidence, second_evidence)


if __name__ == "__main__":
    unittest.main()
