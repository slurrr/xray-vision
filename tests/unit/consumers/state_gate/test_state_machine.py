import unittest

from consumers.state_gate import GateEvaluation, StateGateConfig, StateGateStateMachine
from consumers.state_gate.assembly import AssembledRunInput
from consumers.state_gate.config import OperationLimits
from orchestrator.contracts import ENGINE_MODE_HYSTERESIS
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.decision import HysteresisDecision, HysteresisTransition


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


def _hysteresis_decision(symbol: str, timestamp: int, *, reset_due_to_gap: bool) -> HysteresisDecision:
    return HysteresisDecision(
        selected_output=_regime_output(symbol=symbol, timestamp=timestamp),
        effective_confidence=0.5,
        transition=HysteresisTransition(
            stable_regime=None,
            candidate_regime=Regime.CHOP_BALANCED,
            candidate_count=1,
            transition_active=False,
            flipped=False,
            reset_due_to_gap=reset_due_to_gap,
        ),
    )


def _run_input(
    run_id: str,
    *,
    symbol: str,
    engine_timestamp_ms: int,
    input_event_type: str,
    engine_mode: str | None,
    regime_output: RegimeOutput | None = None,
    hysteresis_decision: HysteresisDecision | None = None,
) -> AssembledRunInput:
    return AssembledRunInput(
        run_id=run_id,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        engine_mode=engine_mode,
        input_event_type=input_event_type,  # type: ignore[arg-type]
        regime_output=regime_output,
        hysteresis_decision=hysteresis_decision,
    )


class TestStateMachine(unittest.TestCase):
    def test_bootstrap_promotes_to_ready_on_open_gate(self) -> None:
        machine = StateGateStateMachine(config=_config())
        run = _run_input(
            "run-1",
            symbol="TEST",
            engine_timestamp_ms=100,
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=_regime_output("TEST", 100),
        )
        evaluation = GateEvaluation(
            gate_status="OPEN",
            state_status="READY",
            reasons=[],
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=run.regime_output,
        )

        events = machine.process_run(run, evaluation)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.event_type, "GateEvaluated")
        self.assertEqual(event.state_status, "READY")
        self.assertEqual(event.gate_status, "OPEN")
        snapshot = machine.snapshot_for("TEST")
        self.assertEqual(snapshot.state_status, "READY")
        self.assertEqual(snapshot.gate_status, "OPEN")

    def test_closed_gate_demotes_to_hold(self) -> None:
        machine = StateGateStateMachine(config=_config())
        initial_run = _run_input(
            "run-1",
            symbol="TEST",
            engine_timestamp_ms=100,
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=_regime_output("TEST", 100),
        )
        open_eval = GateEvaluation(
            gate_status="OPEN",
            state_status="READY",
            reasons=[],
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=initial_run.regime_output,
        )
        machine.process_run(initial_run, open_eval)

        closed_run = _run_input(
            "run-2",
            symbol="TEST",
            engine_timestamp_ms=101,
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=_regime_output("TEST", 101),
        )
        closed_eval = GateEvaluation(
            gate_status="CLOSED",
            state_status="HOLD",
            reasons=["denylisted_invalidation:liquidations"],
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=closed_run.regime_output,
        )

        events = machine.process_run(closed_run, closed_eval)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].state_status, "HOLD")
        snapshot = machine.snapshot_for("TEST")
        self.assertEqual(snapshot.state_status, "HOLD")
        self.assertEqual(snapshot.gate_status, "CLOSED")

    def test_failure_moves_to_degraded(self) -> None:
        machine = StateGateStateMachine(config=_config())
        failed_run = _run_input(
            "run-3",
            symbol="TEST",
            engine_timestamp_ms=200,
            input_event_type="EngineRunFailed",
            engine_mode="truth",
        )
        failure_eval = GateEvaluation(
            gate_status="CLOSED",
            state_status="DEGRADED",
            reasons=["run_failed"],
            input_event_type="EngineRunFailed",
            engine_mode="truth",
        )
        events = machine.process_run(failed_run, failure_eval)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].state_status, "DEGRADED")
        snapshot = machine.snapshot_for("TEST")
        self.assertEqual(snapshot.state_status, "DEGRADED")
        self.assertEqual(snapshot.gate_status, "CLOSED")

    def test_timestamp_gap_reset_then_gate(self) -> None:
        machine = StateGateStateMachine(config=_config(max_gap_ms=1))
        first_run = _run_input(
            "run-4",
            symbol="TEST",
            engine_timestamp_ms=100,
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=_regime_output("TEST", 100),
        )
        open_eval = GateEvaluation(
            gate_status="OPEN",
            state_status="READY",
            reasons=[],
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=first_run.regime_output,
        )
        machine.process_run(first_run, open_eval)

        second_run = _run_input(
            "run-5",
            symbol="TEST",
            engine_timestamp_ms=105,
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=_regime_output("TEST", 105),
        )
        closed_eval = GateEvaluation(
            gate_status="OPEN",
            state_status="READY",
            reasons=[],
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=second_run.regime_output,
        )

        events = machine.process_run(second_run, closed_eval)
        self.assertEqual([event.event_type for event in events], ["StateReset", "GateEvaluated"])
        reset_event = events[0]
        self.assertEqual(reset_event.payload.reset_reason, "reset_timestamp_gap")
        gate_event = events[1]
        self.assertEqual(gate_event.state_status, "READY")
        snapshot = machine.snapshot_for("TEST")
        self.assertEqual(snapshot.last_run_id, "run-5")
        self.assertEqual(snapshot.state_status, "READY")

    def test_hysteresis_reset_due_to_gap(self) -> None:
        machine = StateGateStateMachine(config=_config(max_gap_ms=10))
        decision = _hysteresis_decision(symbol="TEST", timestamp=300, reset_due_to_gap=True)
        run = _run_input(
            "run-6",
            symbol="TEST",
            engine_timestamp_ms=300,
            input_event_type="HysteresisDecisionPublished",
            engine_mode=ENGINE_MODE_HYSTERESIS,
            hysteresis_decision=decision,
        )
        evaluation = GateEvaluation(
            gate_status="CLOSED",
            state_status="HOLD",
            reasons=["transition_active"],
            input_event_type="HysteresisDecisionPublished",
            engine_mode=ENGINE_MODE_HYSTERESIS,
            hysteresis_decision=decision,
        )

        events = machine.process_run(run, evaluation)
        self.assertEqual([event.event_type for event in events], ["StateReset", "GateEvaluated"])
        self.assertEqual(events[0].payload.reset_reason, "reset_engine_gap")
        self.assertEqual(events[1].state_status, "HOLD")


if __name__ == "__main__":
    unittest.main()
