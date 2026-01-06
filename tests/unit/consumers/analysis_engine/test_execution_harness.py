import unittest
from typing import cast

from consumers.analysis_engine import (
    AnalysisEngine,
    AnalysisEngineConfig,
    ArtifactEmittedPayload,
    ArtifactSchema,
    ModuleDependency,
    ModuleRegistry,
    ModuleResult,
    SignalModule,
    build_module_definition,
)
from consumers.analysis_engine.contracts import (
    AnalysisRunStatusPayload,
    ModuleFailedPayload,
    RunContext,
)
from consumers.state_gate.contracts import (
    EVENT_TYPE_GATE_EVALUATED,
    GATE_STATUS_OPEN,
    GateEvaluatedPayload,
    StateGateEvent,
)


class _Signal(SignalModule):
    def __init__(
        self,
        module_id: str,
        *,
        should_fail: bool = False,
        stateful: bool = False,
        dependencies: list[ModuleDependency] | None = None,
    ):
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
            dependencies=dependencies or [],
            config_schema_id=f"config.{module_id}",
            config_schema_version="1",
            state_schema_id="state.schema" if stateful else None,
            state_schema_version="1" if stateful else None,
        )
        super().__init__(definition=definition)
        self._should_fail = should_fail
        self._stateful = stateful

    def execute(self, *, context: RunContext, dependencies, state=None):
        if self._should_fail:
            raise RuntimeError("boom")
        artifacts = [
            ArtifactEmittedPayload(
                artifact_kind="signal",
                module_id=self.definition.module_id,
                artifact_name="value",
                artifact_schema=f"schema.{self.definition.module_id}.value",
                artifact_schema_version="1",
                payload={"symbol": context.symbol},
            )
        ]
        state_payload = (
            {"count": cast(dict[str, int], state or {}).get("count", 0) + 1}
            if self._stateful
            else None
        )
        return ModuleResult(artifacts=artifacts, state_payload=state_payload)


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


class TestExecutionHarness(unittest.TestCase):
    def test_successful_run_emits_artifacts_and_completion(self) -> None:
        signal = _Signal("signal.a")
        registry = ModuleRegistry([signal])
        engine = AnalysisEngine(
            registry=registry,
            config=AnalysisEngineConfig(enabled_modules=["signal.a"], module_configs=[]),
        )
        outputs = engine.consume(_gate_event())
        event_types = [event.event_type for event in outputs]
        self.assertEqual(
            event_types, ["AnalysisRunStarted", "ArtifactEmitted", "AnalysisRunCompleted"]
        )
        completed = outputs[-1]
        assert isinstance(completed.payload, AnalysisRunStatusPayload)
        self.assertEqual(completed.payload.status, "SUCCESS")

    def test_module_failure_isolated_and_marks_partial(self) -> None:
        failing = _Signal("signal.fail", should_fail=True)
        registry = ModuleRegistry([failing])
        engine = AnalysisEngine(
            registry=registry,
            config=AnalysisEngineConfig(enabled_modules=["signal.fail"], module_configs=[]),
        )
        outputs = engine.consume(_gate_event(run_id="run-fail"))
        event_types = [event.event_type for event in outputs]
        self.assertIn("ModuleFailed", event_types)
        completed = outputs[-1]
        assert isinstance(completed.payload, AnalysisRunStatusPayload)
        self.assertEqual(completed.payload.status, "PARTIAL")

    def test_missing_dependency_marks_dependent_failed(self) -> None:
        parent = _Signal("signal.parent", should_fail=True)
        child = _Signal(
            "signal.child",
            dependencies=[ModuleDependency(module_id="signal.parent", artifact_name="value")],
        )
        registry = ModuleRegistry([parent, child])
        engine = AnalysisEngine(
            registry=registry,
            config=AnalysisEngineConfig(
                enabled_modules=["signal.parent", "signal.child"], module_configs=[]
            ),
        )
        outputs = engine.consume(_gate_event(run_id="run-missing"))
        module_failed_payloads = [
            event.payload for event in outputs if isinstance(event.payload, ModuleFailedPayload)
        ]
        self.assertGreaterEqual(len(module_failed_payloads), 1)
        completed = outputs[-1]
        assert isinstance(completed.payload, AnalysisRunStatusPayload)
        self.assertEqual(completed.payload.status, "PARTIAL")

    def test_state_persisted_only_on_success(self) -> None:
        stateful = _Signal("signal.stateful", stateful=True)
        registry = ModuleRegistry([stateful])
        engine = AnalysisEngine(
            registry=registry,
            config=AnalysisEngineConfig(enabled_modules=["signal.stateful"], module_configs=[]),
        )
        engine.consume(_gate_event(run_id="run-state-1"))
        records = engine.module_state_store.all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].state_payload, {"count": 1})

    def test_state_not_persisted_on_failure(self) -> None:
        failing_stateful = _Signal("signal.stateful.fail", stateful=True, should_fail=True)
        registry = ModuleRegistry([failing_stateful])
        engine = AnalysisEngine(
            registry=registry,
            config=AnalysisEngineConfig(
                enabled_modules=["signal.stateful.fail"], module_configs=[]
            ),
        )
        engine.consume(_gate_event(run_id="run-state-fail"))
        self.assertEqual(len(engine.module_state_store.all()), 0)


if __name__ == "__main__":
    unittest.main()
