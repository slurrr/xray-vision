import unittest

from consumers.state_gate import StateGateProcessor
from consumers.state_gate.config import OperationLimits, StateGateConfig
from orchestrator.contracts import EngineRunCompletedPayload, EngineRunFailedPayload, OrchestratorEvent, SCHEMA_NAME, SCHEMA_VERSION
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime


def _config(max_gap_ms: int = 1) -> StateGateConfig:
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
        payload=EngineRunCompletedPayload(regime_output=_regime_output(symbol, engine_timestamp_ms)),
    )


def _failed_event(run_id: str, *, symbol: str, engine_timestamp_ms: int) -> OrchestratorEvent:
    return OrchestratorEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type="EngineRunFailed",
        run_id=run_id,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        cut_start_ingest_seq=1,
        cut_end_ingest_seq=1,
        cut_kind="timer",
        engine_mode="truth",
        payload=EngineRunFailedPayload(error_kind="engine_error", error_detail="timeout"),
    )


class TestDeterminism(unittest.TestCase):
    def test_duplicate_inputs_and_replay_are_idempotent(self) -> None:
        events = [
            _completed_event("run-1", symbol="TEST", engine_timestamp_ms=100),
            _completed_event("run-1", symbol="TEST", engine_timestamp_ms=100),  # duplicate
            _completed_event("run-2", symbol="TEST", engine_timestamp_ms=105),
            _completed_event("run-2", symbol="TEST", engine_timestamp_ms=105),  # duplicate
            _failed_event("run-3", symbol="TEST", engine_timestamp_ms=106),
        ]
        processor = StateGateProcessor(config=_config())
        outputs_first = [output for event in events for output in processor.consume(event)]

        replay_processor = StateGateProcessor(config=_config())
        outputs_second = [output for event in events for output in replay_processor.consume(event)]

        summary_first = [(e.run_id, e.event_type, e.gate_status, e.state_status, tuple(e.reasons)) for e in outputs_first]
        summary_second = [(e.run_id, e.event_type, e.gate_status, e.state_status, tuple(e.reasons)) for e in outputs_second]
        self.assertEqual(summary_first, summary_second)
        gate_evaluated_runs = [e.run_id for e in outputs_first if e.event_type == "GateEvaluated"]
        self.assertEqual(gate_evaluated_runs, ["run-1", "run-2", "run-3"])
        self.assertEqual(outputs_first[-1].gate_status, "CLOSED")


if __name__ == "__main__":
    unittest.main()
