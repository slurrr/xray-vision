import unittest

from market_data.contracts import RawMarketEvent
from orchestrator.failure_handling import BackpressureState
from orchestrator.lifecycle import Lifecycle, OrchestratorState
from orchestrator.observability import Observability, compute_health


class RecordingLogger:
    def __init__(self) -> None:
        self.entries = []

    def log(self, level, message, fields) -> None:
        self.entries.append((level, message, dict(fields)))


class RecordingMetrics:
    def __init__(self) -> None:
        self.increments = []
        self.observations = []
        self.gauges = []

    def increment(self, name, value=1, tags=None) -> None:
        self.increments.append((name, value, dict(tags or {})))

    def observe(self, name, value, tags=None) -> None:
        self.observations.append((name, value, dict(tags or {})))

    def gauge(self, name, value, tags=None) -> None:
        self.gauges.append((name, value, dict(tags or {})))


class TestObservability(unittest.TestCase):
    def test_ingest_logging_fields(self) -> None:
        logger = RecordingLogger()
        metrics = RecordingMetrics()
        obs = Observability(logger=logger, metrics=metrics)

        event = RawMarketEvent(
            schema="raw_market_event",
            schema_version="1",
            event_type="TradeTick",
            source_id="source",
            symbol="TEST",
            exchange_ts_ms=1,
            recv_ts_ms=2,
            raw_payload=b"{}",
            normalized={"price": 1.0, "quantity": 1.0, "side": None},
        )

        obs.log_ingest(event, ingest_seq=10)
        fields = logger.entries[0][2]
        self.assertEqual(fields["source_id"], "source")
        self.assertEqual(fields["symbol"], "TEST")
        self.assertEqual(fields["ingest_seq"], 10)

    def test_health_reflects_backpressure(self) -> None:
        lifecycle = Lifecycle()
        lifecycle.start()
        backpressure = BackpressureState(ingestion_paused=True, scheduling_paused=False)
        health = compute_health(lifecycle, backpressure)
        self.assertFalse(health.ready)
        self.assertEqual(health.state, OrchestratorState.RUNNING.value)


if __name__ == "__main__":
    unittest.main()
