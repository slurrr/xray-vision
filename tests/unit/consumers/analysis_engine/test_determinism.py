import unittest

from consumers.analysis_engine import (
    AnalysisEngine,
    AnalysisEngineConfig,
    ArtifactEmittedPayload,
    ArtifactSchema,
    ModuleRegistry,
    ModuleResult,
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
                    payload={"symbol": context.symbol},
                )
            ]
        )


def _gate_event(run_id: str) -> StateGateEvent:
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


class TestDeterminism(unittest.TestCase):
    def test_replay_produces_identical_outputs(self) -> None:
        registry = ModuleRegistry([_Signal("signal.a")])
        config = AnalysisEngineConfig(enabled_modules=["signal.a"], module_configs=[])
        events = [_gate_event("run-1"), _gate_event("run-2")]

        engine_one = AnalysisEngine(registry=registry, config=config)
        outputs_one = [out for event in events for out in engine_one.consume(event)]

        engine_two = AnalysisEngine(registry=registry, config=config)
        outputs_two = [out for event in events for out in engine_two.consume(event)]

        def summarize(output):
            payload = output.payload
            payload_summary = None
            if isinstance(payload, ArtifactEmittedPayload):
                payload_summary = (payload.module_id, payload.artifact_name, payload.artifact_kind)
            return (output.event_type, payload_summary)

        self.assertEqual([summarize(o) for o in outputs_one], [summarize(o) for o in outputs_two])


if __name__ == "__main__":
    unittest.main()
