import unittest

from market_data.config import BackpressureConfig
from market_data.decoder import decode_and_ingest
from market_data.observability import NullLogger, NullMetrics, Observability
from market_data.pipeline import IngestionPipeline


class RecordingSink:
    def __init__(self) -> None:
        self.events = []

    def write(self, event, *, block: bool, timeout_ms: int | None) -> None:
        self.events.append(event)


class TestDecoder(unittest.TestCase):
    def _pipeline(self) -> IngestionPipeline:
        return IngestionPipeline(
            sink=RecordingSink(),
            backpressure=BackpressureConfig(policy="block", max_pending=1, max_block_ms=50),
            observability=Observability(logger=NullLogger(), metrics=NullMetrics()),
            clock_ms=lambda: 100,
        )

    def test_trade_tick_decodes_and_maps(self) -> None:
        pipeline = self._pipeline()
        event = decode_and_ingest(
            pipeline=pipeline,
            event_type="TradeTick",
            source_id="test",
            symbol="TEST",
            exchange_ts_ms=1,
            raw_payload=b"{\"price\": \"1.2\", \"quantity\": \"3\", \"side\": \"BUY\"}",
            payload_content_type="application/json",
        )

        self.assertEqual(event.event_type, "TradeTick")
        self.assertEqual(event.normalized["price"], 1.2)
        self.assertEqual(event.normalized["quantity"], 3.0)
        self.assertEqual(event.normalized["side"], "buy")

    def test_missing_required_field_emits_decode_failure(self) -> None:
        pipeline = self._pipeline()
        event = decode_and_ingest(
            pipeline=pipeline,
            event_type="TradeTick",
            source_id="test",
            symbol="TEST",
            exchange_ts_ms=1,
            raw_payload=b"{\"price\": 1.2}",
            payload_content_type="application/json",
        )

        self.assertEqual(event.event_type, "DecodeFailure")
        self.assertEqual(event.normalized["error_kind"], "missing_required_field")

    def test_parse_failure_emits_decode_failure(self) -> None:
        pipeline = self._pipeline()
        event = decode_and_ingest(
            pipeline=pipeline,
            event_type="TradeTick",
            source_id="test",
            symbol="TEST",
            exchange_ts_ms=1,
            raw_payload=b"{\"price\": \"bad\", \"quantity\": 1}",
            payload_content_type="application/json",
        )

        self.assertEqual(event.event_type, "DecodeFailure")
        self.assertEqual(event.normalized["error_kind"], "parse_error")

    def test_decode_error_emits_decode_failure(self) -> None:
        pipeline = self._pipeline()
        event = decode_and_ingest(
            pipeline=pipeline,
            event_type="TradeTick",
            source_id="test",
            symbol="TEST",
            exchange_ts_ms=1,
            raw_payload=b"{bad-json}",
            payload_content_type="application/json",
        )

        self.assertEqual(event.event_type, "DecodeFailure")
        self.assertEqual(event.normalized["error_kind"], "decode_error")


if __name__ == "__main__":
    unittest.main()
