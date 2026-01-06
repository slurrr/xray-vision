import unittest

from market_data.config import BackpressureConfig
from market_data.observability import NullLogger, NullMetrics, Observability
from market_data.pipeline import IngestionPipeline
from market_data.sink import BackpressureError


class RecordingSink:
    def __init__(self, *, fail_on_write: bool = False) -> None:
        self.fail_on_write = fail_on_write
        self.events = []
        self.last_block = None
        self.last_timeout_ms = None

    def write(self, event, *, block: bool, timeout_ms: int | None) -> None:
        self.last_block = block
        self.last_timeout_ms = timeout_ms
        if self.fail_on_write:
            raise BackpressureError("sink saturated")
        self.events.append(event)


class TestIngestionPipeline(unittest.TestCase):
    def test_ingest_assigns_recv_ts_ms_and_emits(self) -> None:
        sink = RecordingSink()
        pipeline = IngestionPipeline(
            sink=sink,
            backpressure=BackpressureConfig(policy="block", max_pending=1, max_block_ms=50),
            observability=Observability(logger=NullLogger(), metrics=NullMetrics()),
            clock_ms=lambda: 123,
        )

        event = pipeline.ingest(
            event_type="TradeTick",
            source_id="test-source",
            symbol="TEST",
            exchange_ts_ms=100,
            raw_payload=b"payload",
            normalized={"price": 1.0, "quantity": 2.0, "side": None},
        )

        self.assertEqual(event.recv_ts_ms, 123)
        self.assertEqual(len(sink.events), 1)
        self.assertIs(sink.events[0], event)
        self.assertEqual(sink.last_block, True)
        self.assertEqual(sink.last_timeout_ms, 50)

    def test_ingest_validates_required_keys(self) -> None:
        sink = RecordingSink()
        pipeline = IngestionPipeline(
            sink=sink,
            backpressure=BackpressureConfig(policy="fail", max_pending=1),
            observability=Observability(logger=NullLogger(), metrics=NullMetrics()),
            clock_ms=lambda: 123,
        )

        with self.assertRaises(ValueError):
            pipeline.ingest(
                event_type="TradeTick",
                source_id="test-source",
                symbol="TEST",
                exchange_ts_ms=100,
                raw_payload=b"payload",
                normalized={"price": 1.0},
            )

    def test_backpressure_policy_fail_is_passed_to_sink(self) -> None:
        sink = RecordingSink(fail_on_write=True)
        pipeline = IngestionPipeline(
            sink=sink,
            backpressure=BackpressureConfig(policy="fail", max_pending=1),
            observability=Observability(logger=NullLogger(), metrics=NullMetrics()),
            clock_ms=lambda: 123,
        )

        with self.assertRaises(BackpressureError):
            pipeline.ingest(
                event_type="TradeTick",
                source_id="test-source",
                symbol="TEST",
                exchange_ts_ms=100,
                raw_payload=b"payload",
                normalized={"price": 1.0, "quantity": 2.0, "side": None},
            )

        self.assertEqual(sink.last_block, False)
        self.assertEqual(sink.last_timeout_ms, 0)


if __name__ == "__main__":
    unittest.main()
