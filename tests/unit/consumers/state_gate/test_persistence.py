import unittest

from consumers.state_gate import StateGateProcessor, StateGateStateStore
from consumers.state_gate.config import OperationLimits, StateGateConfig
from orchestrator.contracts import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    EngineRunCompletedPayload,
    OrchestratorEvent,
)
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime


def _config(max_gap_ms: int = 1000) -> StateGateConfig:
    limits = OperationLimits(max_pending=10, max_block_ms=100, max_failures=3)
    return StateGateConfig(
        max_gap_ms=max_gap_ms,
        denylisted_invalidations=[],
        block_during_transition=False,
        input_limits=limits,
        persistence_limits=limits,
        publish_limits=limits,
    )


def _regime_output(symbol: str, timestamp: int) -> RegimeOutput:
    return RegimeOutput(
        symbol=symbol,
        timestamp=timestamp,
        regime=Regime.CHOP_BALANCED,
        confidence=1.0,
        drivers=[],
        invalidations=[],
        permissions=[],
    )


def _completed_event(run_id: str, *, symbol: str, engine_timestamp_ms: int) -> OrchestratorEvent:
    return OrchestratorEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type="EngineRunCompleted",
        run_id=run_id,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        cut_start_ingest_seq=1,
        cut_end_ingest_seq=1,
        cut_kind="timer",
        engine_mode="truth",
        payload=EngineRunCompletedPayload(
            regime_output=_regime_output(symbol, engine_timestamp_ms)
        ),
    )


class TestPersistence(unittest.TestCase):
    def test_persists_state_records_before_output(self) -> None:
        processor = StateGateProcessor(config=_config())
        events = processor.consume(
            _completed_event("run-1", symbol="TEST", engine_timestamp_ms=100)
        )
        self.assertEqual(len(events), 1)
        records = processor.records()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.state_status, "READY")
        self.assertEqual(record.gate_status, "OPEN")
        snapshot = processor.snapshot_for("TEST")
        self.assertEqual(snapshot.state_status, "READY")

    def test_restart_skips_processed_runs(self) -> None:
        processor = StateGateProcessor(config=_config())
        event = _completed_event("run-2", symbol="TEST", engine_timestamp_ms=100)
        first = processor.consume(event)
        self.assertEqual(len(first), 1)

        store = StateGateStateStore(records=processor.records())
        restarted = StateGateProcessor(config=_config(), store=store)
        duplicate = restarted.consume(event)
        self.assertEqual(duplicate, [])
        snapshot = restarted.snapshot_for("TEST")
        self.assertEqual(snapshot.state_status, "READY")
        self.assertEqual(snapshot.last_run_id, "run-2")

    def test_replay_is_deterministic(self) -> None:
        config = _config(max_gap_ms=1)
        processor = StateGateProcessor(config=config)
        events = [
            _completed_event("run-3", symbol="TEST", engine_timestamp_ms=100),
            _completed_event("run-4", symbol="TEST", engine_timestamp_ms=105),
        ]
        first_outputs = [output for event in events for output in processor.consume(event)]

        replay_processor = StateGateProcessor(config=config)
        replay_outputs = [output for event in events for output in replay_processor.consume(event)]

        self.assertEqual(
            [e.event_type for e in first_outputs],
            [e.event_type for e in replay_outputs],
        )
        self.assertEqual(
            [e.reasons for e in first_outputs], [e.reasons for e in replay_outputs]
        )


if __name__ == "__main__":
    unittest.main()
