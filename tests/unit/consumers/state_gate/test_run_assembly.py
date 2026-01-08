import unittest

from consumers.state_gate import RunAssembler
from orchestrator.contracts import (
    SCHEMA_NAME as ORCHESTRATOR_SCHEMA,
)
from orchestrator.contracts import (
    SCHEMA_VERSION as ORCHESTRATOR_SCHEMA_VERSION,
)
from orchestrator.contracts import (
    EngineMode,
    EngineRunCompletedPayload,
    EngineRunFailedPayload,
    HysteresisStatePayload,
    OrchestratorEvent,
)
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.state import SCHEMA_NAME, SCHEMA_VERSION, HysteresisState


def _make_regime_output(symbol: str, timestamp: int) -> RegimeOutput:
    return RegimeOutput(
        symbol=symbol,
        timestamp=timestamp,
        regime=Regime.CHOP_BALANCED,
        confidence=1.0,
        drivers=[],
        invalidations=[],
        permissions=[],
    )


def _make_completed_event(
    run_id: str, *, symbol: str, engine_timestamp_ms: int, engine_mode: EngineMode
) -> OrchestratorEvent:
    return OrchestratorEvent(
        schema=ORCHESTRATOR_SCHEMA,
        schema_version=ORCHESTRATOR_SCHEMA_VERSION,
        event_type="EngineRunCompleted",
        run_id=run_id,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        cut_start_ingest_seq=1,
        cut_end_ingest_seq=1,
        cut_kind="timer",
        engine_mode=engine_mode,
        payload=EngineRunCompletedPayload(
            regime_output=_make_regime_output(symbol=symbol, timestamp=engine_timestamp_ms),
        ),
    )


def _make_failed_event(
    run_id: str, *, symbol: str, engine_timestamp_ms: int, engine_mode: EngineMode
) -> OrchestratorEvent:
    return OrchestratorEvent(
        schema=ORCHESTRATOR_SCHEMA,
        schema_version=ORCHESTRATOR_SCHEMA_VERSION,
        event_type="EngineRunFailed",
        run_id=run_id,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        cut_start_ingest_seq=1,
        cut_end_ingest_seq=1,
        cut_kind="timer",
        engine_mode=engine_mode,
        payload=EngineRunFailedPayload(error_kind="internal_error", error_detail="timeout"),
    )


def _make_hysteresis_event(
    run_id: str, *, symbol: str, engine_timestamp_ms: int
) -> OrchestratorEvent:
    state = HysteresisState(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        anchor_regime=Regime.CHOP_BALANCED,
        candidate_regime=Regime.SQUEEZE_UP,
        progress_current=1,
        progress_required=3,
        last_commit_timestamp_ms=None,
        reason_codes=("PROGRESS_RESET",),
        debug=None,
    )
    return OrchestratorEvent(
        schema=ORCHESTRATOR_SCHEMA,
        schema_version=ORCHESTRATOR_SCHEMA_VERSION,
        event_type="HysteresisStatePublished",
        run_id=run_id,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        cut_start_ingest_seq=1,
        cut_end_ingest_seq=1,
        cut_kind="timer",
        engine_mode="hysteresis",
        payload=HysteresisStatePayload(hysteresis_state=state),
    )


class TestRunAssembly(unittest.TestCase):
    def test_completed_run_emits_once_and_dedupes(self) -> None:
        assembler = RunAssembler()
        event = _make_completed_event(
            "run-1", symbol="TEST", engine_timestamp_ms=100, engine_mode="truth"
        )

        assembled = assembler.ingest(event)
        self.assertIsNotNone(assembled)
        assert assembled is not None  # for mypy type narrowing
        self.assertEqual(assembled.input_event_type, "EngineRunCompleted")
        self.assertEqual(assembled.run_id, "run-1")
        assert assembled.regime_output is not None
        self.assertEqual(assembled.regime_output.timestamp, 100)

        duplicate = assembler.ingest(event)
        self.assertIsNone(duplicate)

    def test_hysteresis_overrides_completed_in_hysteresis_mode(self) -> None:
        assembler = RunAssembler()
        completed = _make_completed_event(
            "run-2", symbol="TEST", engine_timestamp_ms=200, engine_mode="hysteresis"
        )
        hysteresis = _make_hysteresis_event("run-2", symbol="TEST", engine_timestamp_ms=200)

        first = assembler.ingest(completed)
        self.assertIsNone(first)

        assembled = assembler.ingest(hysteresis)
        self.assertIsNotNone(assembled)
        assert assembled is not None
        self.assertEqual(assembled.input_event_type, "HysteresisStatePublished")
        self.assertIsNone(assembler.ingest(hysteresis))

    def test_run_failed_is_ready_immediately(self) -> None:
        assembler = RunAssembler()
        failed = _make_failed_event(
            "run-3", symbol="TEST", engine_timestamp_ms=300, engine_mode="truth"
        )
        assembled = assembler.ingest(failed)
        self.assertIsNotNone(assembled)
        assert assembled is not None
        self.assertEqual(assembled.input_event_type, "EngineRunFailed")
        self.assertIsNone(assembled.regime_output)

    def test_out_of_order_runs_are_ignored(self) -> None:
        assembler = RunAssembler()
        newest = _make_completed_event(
            "run-4", symbol="TEST", engine_timestamp_ms=400, engine_mode="truth"
        )
        older = _make_completed_event(
            "run-5", symbol="TEST", engine_timestamp_ms=399, engine_mode="truth"
        )

        assembled_new = assembler.ingest(newest)
        self.assertIsNotNone(assembled_new)
        self.assertIsNone(assembler.ingest(older))
        self.assertIn("run-5", assembler.processed_run_ids())


if __name__ == "__main__":
    unittest.main()
