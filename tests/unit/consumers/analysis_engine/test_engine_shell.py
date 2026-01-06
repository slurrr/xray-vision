import unittest

from consumers.analysis_engine import (
    AnalysisEngine,
    AnalysisEngineConfig,
    AnalysisRunStatusPayload,
    IdempotencyStore,
    ModuleRegistry,
    ModuleStateStore,
)
from consumers.state_gate.contracts import (
    EVENT_TYPE_GATE_EVALUATED,
    EVENT_TYPE_STATE_GATE_HALTED,
    GATE_STATUS_CLOSED,
    GATE_STATUS_OPEN,
    StateGateEvent,
)


def _gate_event(
    *,
    event_type: str = EVENT_TYPE_GATE_EVALUATED,
    gate_status: str = GATE_STATUS_OPEN,
    symbol: str = "TEST",
    run_id: str = "run-1",
    engine_timestamp_ms: int = 100,
) -> StateGateEvent:
    return StateGateEvent(
        schema="state_gate_event",
        schema_version="1",
        event_type=event_type,  # type: ignore[arg-type]
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        run_id=run_id,
        state_status="READY",
        gate_status=gate_status,  # type: ignore[arg-type]
        reasons=["ok"],
        payload=None,
        input_event_type="EngineRunCompleted",
        engine_mode="truth",
    )


class TestEngineShell(unittest.TestCase):
    def test_open_gate_emits_started_and_completed(self) -> None:
        engine = AnalysisEngine(
            registry=ModuleRegistry([]),
            config=AnalysisEngineConfig(enabled_modules=[], module_configs=[]),
        )
        outputs = engine.consume(_gate_event())
        self.assertEqual([event.event_type for event in outputs], ["AnalysisRunStarted", "AnalysisRunCompleted"])
        completed = outputs[-1]
        assert isinstance(completed.payload, AnalysisRunStatusPayload)
        self.assertEqual(completed.payload.status, "SUCCESS")
        self.assertEqual(completed.schema, "analysis_engine_event")

    def test_closed_gate_emits_skipped(self) -> None:
        engine = AnalysisEngine(
            registry=ModuleRegistry([]),
            config=AnalysisEngineConfig(enabled_modules=[], module_configs=[]),
        )
        outputs = engine.consume(_gate_event(gate_status=GATE_STATUS_CLOSED))
        self.assertEqual([event.event_type for event in outputs], ["AnalysisRunSkipped"])

    def test_duplicate_run_id_is_idempotent(self) -> None:
        engine = AnalysisEngine(
            registry=ModuleRegistry([]),
            config=AnalysisEngineConfig(enabled_modules=[], module_configs=[]),
            idempotency_store=IdempotencyStore(),
        )
        open_event = _gate_event(run_id="run-dup")
        first = engine.consume(open_event)
        second = engine.consume(open_event)
        self.assertEqual(len(first), 2)
        self.assertEqual(second, [])

    def test_halted_symbol_prevents_processing(self) -> None:
        engine = AnalysisEngine(
            registry=ModuleRegistry([]),
            config=AnalysisEngineConfig(enabled_modules=[], module_configs=[]),
        )
        halt_event = _gate_event(event_type=EVENT_TYPE_STATE_GATE_HALTED, run_id="run-halt")
        halt_outputs = engine.consume(halt_event)
        self.assertEqual([event.event_type for event in halt_outputs], ["AnalysisRunFailed"])
        self.assertEqual(engine.halted_symbols, {"TEST"})
        after = engine.consume(_gate_event(run_id="run-late"))
        self.assertEqual(after, [])


if __name__ == "__main__":
    unittest.main()
