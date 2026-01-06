import unittest
from dataclasses import FrozenInstanceError

from market_data.contracts import RawMarketEvent
from orchestrator.config import (
    BufferRetentionConfig,
    EngineConfig,
    OrchestratorConfig,
    OutputPublishConfig,
    RetryPolicy,
    SchedulerConfig,
    SourceConfig,
    validate_config,
)
from orchestrator.contracts import (
    EVENT_TYPES,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    EngineRunRecord,
    OrchestratorEvent,
    RawInputBufferRecord,
)
from orchestrator.run_id import derive_run_id


class TestOrchestratorContracts(unittest.TestCase):
    def test_orchestrator_event_is_frozen(self) -> None:
        event = OrchestratorEvent(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            event_type="EngineRunStarted",
            run_id="run",
            symbol="TEST",
            engine_timestamp_ms=100,
            cut_start_ingest_seq=1,
            cut_end_ingest_seq=10,
            cut_kind="timer",
        )
        with self.assertRaises(FrozenInstanceError):
            event.symbol = "OTHER"  # type: ignore[misc]

    def test_buffer_and_run_records_are_frozen(self) -> None:
        raw_event = RawMarketEvent(
            schema="raw_market_event",
            schema_version="1",
            event_type="TradeTick",
            source_id="source",
            symbol="TEST",
            exchange_ts_ms=None,
            recv_ts_ms=1,
            raw_payload=b"{}",
            normalized={"price": 1.0, "quantity": 1.0, "side": None},
        )
        buffer_record = RawInputBufferRecord(ingest_seq=1, ingest_ts_ms=2, event=raw_event)
        with self.assertRaises(FrozenInstanceError):
            buffer_record.ingest_seq = 2  # type: ignore[misc]

        run_record = EngineRunRecord(
            run_id="run",
            symbol="TEST",
            engine_timestamp_ms=100,
            engine_mode="truth",
            cut_kind="timer",
            cut_start_ingest_seq=1,
            cut_end_ingest_seq=10,
            planned_ts_ms=99,
            started_ts_ms=None,
            completed_ts_ms=None,
            status="started",
            attempts=1,
        )
        with self.assertRaises(FrozenInstanceError):
            run_record.status = "failed"  # type: ignore[misc]

    def test_run_id_is_deterministic(self) -> None:
        run_id = derive_run_id(
            symbol="TEST",
            engine_timestamp_ms=100,
            cut_end_ingest_seq=10,
            engine_mode="truth",
        )
        self.assertEqual(
            run_id,
            derive_run_id(
                symbol="TEST",
                engine_timestamp_ms=100,
                cut_end_ingest_seq=10,
                engine_mode="truth",
            ),
        )

    def test_event_type_list_is_non_empty(self) -> None:
        self.assertTrue(len(EVENT_TYPES) > 0)

    def test_config_validation_accepts_minimal_config(self) -> None:
        config = OrchestratorConfig(
            sources=[SourceConfig(source_id="source", symbols=["TEST"])],
            scheduler=SchedulerConfig(mode="timer", timer_interval_ms=1000),
            engine=EngineConfig(engine_mode="truth"),
            ingestion_retry=RetryPolicy(min_delay_ms=1, max_delay_ms=2, max_attempts=1),
            buffer_retry=RetryPolicy(min_delay_ms=1, max_delay_ms=2, max_attempts=1),
            engine_retry=RetryPolicy(min_delay_ms=1, max_delay_ms=2, max_attempts=1),
            publish_retry=RetryPolicy(min_delay_ms=1, max_delay_ms=2, max_attempts=1),
            buffer_retention=BufferRetentionConfig(max_records=10),
            output_publish=OutputPublishConfig(max_pending=10),
        )
        validate_config(config)


if __name__ == "__main__":
    unittest.main()
