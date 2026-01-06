import unittest
from collections.abc import Mapping
from typing import cast

from consumers.state_gate import StateGateProcessor
from consumers.state_gate.config import OperationLimits, StateGateConfig
from consumers.state_gate.observability import HealthStatus, Observability
from orchestrator.contracts import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    EngineRunCompletedPayload,
    OrchestratorEvent,
)
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime


class FakeLogger:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None:
        self.calls.append({"level": level, "message": message, "fields": dict(fields)})


class FakeMetrics:
    def __init__(self) -> None:
        self.increments: list[tuple[str, int, Mapping[str, str] | None]] = []
        self.observations: list[tuple[str, float, Mapping[str, str] | None]] = []

    def increment(
        self, name: str, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None:
        self.increments.append((name, value, tags))

    def observe(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None:
        self.observations.append((name, value, tags))

    def gauge(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None:
        return None


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


class TestObservability(unittest.TestCase):
    def test_logs_gate_events_with_required_fields(self) -> None:
        logger = FakeLogger()
        metrics = FakeMetrics()
        processor = StateGateProcessor(
            config=_config(),
            observability=Observability(logger=logger, metrics=metrics),
        )
        processor.consume(_completed_event("run-1", symbol="TEST", engine_timestamp_ms=100))

        self.assertEqual(len(logger.calls), 1)
        fields = cast(dict[str, object], logger.calls[0]["fields"])
        self.assertEqual(fields["symbol"], "TEST")
        self.assertEqual(fields["run_id"], "run-1")
        self.assertEqual(fields["input_event_type"], "EngineRunCompleted")
        self.assertEqual(fields["state_status"], "READY")
        self.assertEqual(fields["gate_status"], "OPEN")
        self.assertIn("reasons", fields)

    def test_records_metrics_for_decisions_and_resets(self) -> None:
        logger = FakeLogger()
        metrics = FakeMetrics()
        processor = StateGateProcessor(
            config=_config(max_gap_ms=1),
            observability=Observability(logger=logger, metrics=metrics),
        )
        processor.consume(_completed_event("run-2", symbol="TEST", engine_timestamp_ms=100))
        processor.consume(_completed_event("run-3", symbol="TEST", engine_timestamp_ms=105))

        gate_decisions = [
            entry for entry in metrics.increments if entry[0] == "state_gate.gate_decisions"
        ]
        self.assertGreaterEqual(len(gate_decisions), 2)
        reset_metrics = [
            entry for entry in metrics.increments if entry[0] == "state_gate.resets"
        ]
        self.assertEqual(len(reset_metrics), 1)
        self.assertEqual(reset_metrics[0][2], {"reset_reason": "reset_timestamp_gap"})
        processing_lag = [
            obs for obs in metrics.observations if obs[0] == "state_gate.processing_lag_ms"
        ]
        self.assertEqual(len(processing_lag), 1)
        self.assertEqual(processing_lag[0][1], 5.0)

    def test_health_status_defaults_ready(self) -> None:
        processor = StateGateProcessor(config=_config())
        health = processor.health_status()
        self.assertIsInstance(health, HealthStatus)
        self.assertTrue(health.ready)
        self.assertFalse(health.halted)


if __name__ == "__main__":
    unittest.main()
