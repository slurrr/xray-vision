import unittest

from consumers.state_gate import GateEvaluator, StateGateConfig, StateGateProcessor
from consumers.state_gate.assembly import AssembledRunInput
from consumers.state_gate.config import OperationLimits
from orchestrator.contracts import (
    EngineRunCompletedPayload,
    OrchestratorEvent,
    SCHEMA_NAME as ORCHESTRATOR_SCHEMA,
    SCHEMA_VERSION as ORCHESTRATOR_SCHEMA_VERSION,
)
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.decision import HysteresisDecision, HysteresisTransition


def _config(**overrides) -> StateGateConfig:
    limits = OperationLimits(max_pending=10, max_block_ms=100, max_failures=3)
    return StateGateConfig(
        max_gap_ms=overrides.get("max_gap_ms", 1000),
        denylisted_invalidations=overrides.get("denylisted_invalidations", []),
        block_during_transition=overrides.get("block_during_transition", False),
        input_limits=limits,
        persistence_limits=limits,
        publish_limits=limits,
    )


def _regime_output(symbol: str, timestamp: int, invalidations: list[str] | None = None) -> RegimeOutput:
    return RegimeOutput(
        symbol=symbol,
        timestamp=timestamp,
        regime=Regime.CHOP_BALANCED,
        confidence=1.0,
        drivers=[],
        invalidations=invalidations or [],
        permissions=[],
    )


def _hysteresis_decision(
    symbol: str,
    timestamp: int,
    *,
    transition_active: bool,
) -> HysteresisDecision:
    return HysteresisDecision(
        selected_output=_regime_output(symbol, timestamp),
        effective_confidence=0.5,
        transition=HysteresisTransition(
            stable_regime=None,
            candidate_regime=Regime.CHOP_BALANCED,
            candidate_count=1,
            transition_active=transition_active,
            flipped=False,
            reset_due_to_gap=False,
        ),
    )


def _assembled_run(
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


def _completed_event(run_id: str, *, symbol: str, engine_timestamp_ms: int) -> OrchestratorEvent:
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
        engine_mode="truth",
        payload=EngineRunCompletedPayload(regime_output=_regime_output(symbol, engine_timestamp_ms)),
    )


class TestGateEvaluation(unittest.TestCase):
    def test_run_failure_closes_gate(self) -> None:
        evaluator = GateEvaluator(config=_config())
        run = _assembled_run(
            "run-1",
            symbol="TEST",
            engine_timestamp_ms=100,
            input_event_type="EngineRunFailed",
            engine_mode="truth",
        )
        evaluation = evaluator.evaluate(run)
        self.assertEqual(evaluation.gate_status, "CLOSED")
        self.assertEqual(evaluation.state_status, "DEGRADED")
        self.assertEqual(evaluation.reasons, ["run_failed"])

    def test_denylisted_invalidations_close_gate(self) -> None:
        evaluator = GateEvaluator(config=_config(denylisted_invalidations=["gap", "late"]))
        run = _assembled_run(
            "run-2",
            symbol="TEST",
            engine_timestamp_ms=100,
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=_regime_output("TEST", 100, invalidations=["late", "gap"]),
        )
        evaluation = evaluator.evaluate(run)
        self.assertEqual(evaluation.gate_status, "CLOSED")
        self.assertEqual(evaluation.state_status, "HOLD")
        self.assertEqual(
            evaluation.reasons,
            ["denylisted_invalidation:gap", "denylisted_invalidation:late"],
        )

    def test_transition_hold_blocks_when_configured(self) -> None:
        evaluator = GateEvaluator(config=_config(block_during_transition=True))
        decision = _hysteresis_decision("TEST", 100, transition_active=True)
        run = _assembled_run(
            "run-3",
            symbol="TEST",
            engine_timestamp_ms=100,
            input_event_type="HysteresisDecisionPublished",
            engine_mode="hysteresis",
            hysteresis_decision=decision,
        )
        evaluation = evaluator.evaluate(run)
        self.assertEqual(evaluation.gate_status, "CLOSED")
        self.assertEqual(evaluation.state_status, "HOLD")
        self.assertEqual(evaluation.reasons, ["transition_active"])
        self.assertIsNotNone(evaluation.hysteresis_decision)

    def test_open_gate_by_default(self) -> None:
        evaluator = GateEvaluator(config=_config())
        run = _assembled_run(
            "run-4",
            symbol="TEST",
            engine_timestamp_ms=100,
            input_event_type="EngineRunCompleted",
            engine_mode="truth",
            regime_output=_regime_output("TEST", 100),
        )
        evaluation = evaluator.evaluate(run)
        self.assertEqual(evaluation.gate_status, "OPEN")
        self.assertEqual(evaluation.state_status, "READY")
        self.assertEqual(evaluation.reasons, [])


class TestProcessorIntegration(unittest.TestCase):
    def test_processor_emits_single_gate_evaluated(self) -> None:
        processor = StateGateProcessor(config=_config())
        event = _completed_event("run-1", symbol="TEST", engine_timestamp_ms=100)

        first = processor.consume(event)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].event_type, "GateEvaluated")
        duplicate = processor.consume(event)
        self.assertEqual(duplicate, [])


if __name__ == "__main__":
    unittest.main()
