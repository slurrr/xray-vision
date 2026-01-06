import unittest
from collections.abc import Mapping

from consumers.analysis_engine import (
    AnalysisEngine,
    AnalysisEngineConfig,
    ArtifactEmittedPayload,
    ArtifactSchema,
    ModuleRegistry,
    ModuleResult,
    Observability,
    SignalModule,
    build_module_definition,
)
from consumers.analysis_engine.contracts import RunContext
from consumers.state_gate.contracts import (
    EVENT_TYPE_GATE_EVALUATED,
    GATE_STATUS_OPEN,
    GateEvaluatedPayload,
    StateGateEvent,
)


class FakeLogger:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None:
        self.calls.append({"level": level, "message": message, "fields": dict(fields)})


class FakeMetrics:
    def __init__(self) -> None:
        self.increments: list[tuple[str, int, Mapping[str, str] | None]] = []

    def increment(
        self, name: str, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None:
        self.increments.append((name, value, tags))

    def observe(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None:
        return None

    def gauge(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None:
        return None


class _Signal(SignalModule):
    def __init__(self, module_id: str):
        definition = build_module_definition(
            module_id=module_id,
            module_kind="signal",
            module_version="1",
            artifact_schemas=[
                ArtifactSchema(
                    artifact_name="value",
                    artifact_schema=f"schema.{module_id}.value",
                    artifact_schema_version="1",
                )
            ],
            dependencies=[],
            config_schema_id=f"config.{module_id}",
            config_schema_version="1",
        )
        super().__init__(definition=definition)

    def execute(self, *, context: RunContext, dependencies, state=None):
        return ModuleResult(
            artifacts=[
                ArtifactEmittedPayload(
                    artifact_kind="signal",
                    module_id=self.definition.module_id,
                    artifact_name="value",
                    artifact_schema=f"schema.{self.definition.module_id}.value",
                    artifact_schema_version="1",
                    payload={},
                )
            ]
        )


def _gate_event(run_id: str = "run-1") -> StateGateEvent:
    return StateGateEvent(
        schema="state_gate_event",
        schema_version="1",
        event_type=EVENT_TYPE_GATE_EVALUATED,
        symbol="TEST",
        engine_timestamp_ms=100,
        run_id=run_id,
        state_status="READY",
        gate_status=GATE_STATUS_OPEN,
        reasons=["ok"],
        payload=GateEvaluatedPayload(regime_output=None, hysteresis_decision=None),
        input_event_type="EngineRunCompleted",
        engine_mode="truth",
    )


class TestObservability(unittest.TestCase):
    def test_logs_and_metrics_recorded(self) -> None:
        logger = FakeLogger()
        metrics = FakeMetrics()
        obs = Observability(logger=logger, metrics=metrics)
        registry = ModuleRegistry([_Signal("signal.a")])
        engine = AnalysisEngine(
            registry=registry,
            config=AnalysisEngineConfig(enabled_modules=["signal.a"], module_configs=[]),
            observability=obs,
        )
        engine.consume(_gate_event())
        self.assertTrue(logger.calls)
        run_status_metrics = [
            name for name, _, _ in metrics.increments if name == "analysis_engine.run_status"
        ]
        self.assertTrue(run_status_metrics)
        artifact_metrics = [
            name for name, _, _ in metrics.increments if name == "analysis_engine.artifacts"
        ]
        self.assertTrue(artifact_metrics)

    def test_idempotency_skip_metric(self) -> None:
        logger = FakeLogger()
        metrics = FakeMetrics()
        obs = Observability(logger=logger, metrics=metrics)
        registry = ModuleRegistry([_Signal("signal.a")])
        engine = AnalysisEngine(
            registry=registry,
            config=AnalysisEngineConfig(enabled_modules=["signal.a"], module_configs=[]),
            observability=obs,
        )
        event = _gate_event(run_id="dup")
        engine.consume(event)
        engine.consume(event)
        skip_metrics = [
            name
            for name, _, tags in metrics.increments
            if name == "analysis_engine.idempotency_skips"
        ]
        self.assertTrue(skip_metrics)

    def test_health_reflects_halt(self) -> None:
        obs = Observability(logger=FakeLogger(), metrics=FakeMetrics())
        registry = ModuleRegistry([])
        engine = AnalysisEngine(
            registry=registry,
            config=AnalysisEngineConfig(enabled_modules=[], module_configs=[]),
            observability=obs,
        )
        health = engine.health_status()
        self.assertTrue(health.ready)
        engine.consume(
            StateGateEvent(
                schema="state_gate_event",
                schema_version="1",
                event_type="StateGateHalted",  # type: ignore[arg-type]
                symbol="TEST",
                engine_timestamp_ms=100,
                run_id="halt",
                state_status="HALTED",
                gate_status="CLOSED",
                reasons=["halted"],
                payload=None,
                input_event_type=None,
                engine_mode=None,
            )
        )
        self.assertFalse(engine.health_status().ready)


if __name__ == "__main__":
    unittest.main()
