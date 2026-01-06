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


class FailingStore(StateGateStateStore):
    def append_event(self, event):  # type: ignore[override]
        raise RuntimeError("persistence_down")


def _config(*, max_gap_ms: int = 1000, publish_max_pending: int = 2) -> StateGateConfig:
    limits = OperationLimits(max_pending=10, max_block_ms=100, max_failures=3)
    publish_limits = OperationLimits(
        max_pending=publish_max_pending, max_block_ms=100, max_failures=3
    )
    return StateGateConfig(
        max_gap_ms=max_gap_ms,
        denylisted_invalidations=[],
        block_during_transition=False,
        input_limits=limits,
        persistence_limits=limits,
        publish_limits=publish_limits,
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


class TestFailureIsolation(unittest.TestCase):
    def test_persistence_failure_halts_and_closes_gate(self) -> None:
        processor = StateGateProcessor(config=_config(), store=FailingStore())
        events = processor.consume(
            _completed_event("run-1", symbol="TEST", engine_timestamp_ms=100)
        )
        self.assertEqual(len(events), 1)
        halted = events[0]
        self.assertEqual(halted.event_type, "StateGateHalted")
        self.assertEqual(halted.gate_status, "CLOSED")
        health = processor.health_status()
        self.assertFalse(health.ready)
        self.assertFalse(health.persistence_healthy)

    def test_publish_backpressure_halts_and_no_gate_outputs(self) -> None:
        processor = StateGateProcessor(config=_config(max_gap_ms=1, publish_max_pending=1))
        processor.consume(_completed_event("run-2", symbol="TEST", engine_timestamp_ms=100))
        events = processor.consume(
            _completed_event("run-3", symbol="TEST", engine_timestamp_ms=105)
        )

        self.assertEqual([event.event_type for event in events], ["StateGateHalted"])
        records = processor.records()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[-1].state_status, "HALTED")
        self.assertEqual(records[-1].gate_status, "CLOSED")
        self.assertEqual(
            processor.consume(
                _completed_event("run-4", symbol="TEST", engine_timestamp_ms=200)
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
