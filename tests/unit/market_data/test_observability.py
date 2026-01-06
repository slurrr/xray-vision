import unittest

from market_data.adapter import StreamKey
from market_data.contracts import RawMarketEvent, SCHEMA_NAME, SCHEMA_VERSION
from market_data.observability import Observability


class RecordingLogger:
    def __init__(self) -> None:
        self.entries = []

    def log(self, level: int, message: str, fields) -> None:
        self.entries.append((level, message, dict(fields)))


class RecordingMetrics:
    def __init__(self) -> None:
        self.increments = []
        self.observations = []
        self.gauges = []

    def increment(self, name: str, value: int = 1, tags=None) -> None:
        self.increments.append((name, value, dict(tags or {})))

    def observe(self, name: str, value: float, tags=None) -> None:
        self.observations.append((name, value, dict(tags or {})))

    def gauge(self, name: str, value: float, tags=None) -> None:
        self.gauges.append((name, value, dict(tags or {})))


class TestObservability(unittest.TestCase):
    def test_event_logging_includes_required_fields(self) -> None:
        logger = RecordingLogger()
        metrics = RecordingMetrics()
        obs = Observability(logger=logger, metrics=metrics)

        event = RawMarketEvent(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            event_type="TradeTick",
            source_id="test-source",
            symbol="TEST",
            exchange_ts_ms=1,
            recv_ts_ms=2,
            raw_payload=b"payload",
            normalized={"price": 1.0, "quantity": 2.0, "side": None},
        )

        obs.record_event(event)
        self.assertEqual(logger.entries[0][1], "market_data.event")
        fields = logger.entries[0][2]
        self.assertEqual(fields["source_id"], "test-source")
        self.assertEqual(fields["symbol"], "TEST")
        self.assertEqual(fields["event_type"], "TradeTick")
        self.assertEqual(fields["exchange_ts_ms"], 1)
        self.assertEqual(fields["recv_ts_ms"], 2)

    def test_decode_failure_logging_includes_error_fields(self) -> None:
        logger = RecordingLogger()
        metrics = RecordingMetrics()
        obs = Observability(logger=logger, metrics=metrics)

        event = RawMarketEvent(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            event_type="DecodeFailure",
            source_id="test-source",
            symbol="TEST",
            exchange_ts_ms=None,
            recv_ts_ms=2,
            raw_payload=b"payload",
            normalized={"error_kind": "decode_error", "error_detail": "bad"},
        )

        obs.record_event(event)
        self.assertEqual(logger.entries[0][1], "market_data.decode_failure")
        fields = logger.entries[0][2]
        self.assertEqual(fields["error_kind"], "decode_error")
        self.assertEqual(fields["error_detail"], "bad")

    def test_transport_state_logging_and_metrics(self) -> None:
        logger = RecordingLogger()
        metrics = RecordingMetrics()
        obs = Observability(logger=logger, metrics=metrics)
        stream_key = StreamKey(source_id="test-source", channel="trades", symbol="TEST")

        obs.log_transport_state(stream_key=stream_key, state="connected", reconnect_count=3)
        obs.record_connection_state(stream_key=stream_key, state="connected", reconnect_count=3)

        fields = logger.entries[0][2]
        self.assertEqual(fields["source_id"], "test-source")
        self.assertEqual(fields["channel"], "trades")
        self.assertEqual(fields["symbol"], "TEST")
        self.assertEqual(fields["state"], "connected")
        self.assertEqual(fields["reconnect_count"], 3)
        self.assertEqual(metrics.increments[0][0], "market_data.transport.reconnects")
        self.assertEqual(metrics.gauges[0][0], "market_data.transport.state")


if __name__ == "__main__":
    unittest.main()
