import unittest
from dataclasses import FrozenInstanceError

from consumers.analysis_engine import (
    ANALYSIS_EVENT_TYPES,
    ARTIFACT_KINDS,
    MODULE_KINDS,
    RUN_STATUSES,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    AnalysisEngineEvent,
    AnalysisModuleStateRecord,
    AnalysisRunStatusPayload,
    ArtifactEmittedPayload,
    ArtifactSchema,
    ModuleDefinition,
    ModuleDependency,
    ModuleFailedPayload,
    RunContext,
    build_idempotency_key,
)
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.state import SCHEMA_NAME as HYSTERESIS_SCHEMA
from regime_engine.hysteresis.state import SCHEMA_VERSION as HYSTERESIS_SCHEMA_VERSION
from regime_engine.hysteresis.state import HysteresisState


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


def _hysteresis_state(symbol: str, timestamp: int) -> HysteresisState:
    return HysteresisState(
        schema=HYSTERESIS_SCHEMA,
        schema_version=HYSTERESIS_SCHEMA_VERSION,
        symbol=symbol,
        engine_timestamp_ms=timestamp,
        anchor_regime=Regime.CHOP_BALANCED,
        candidate_regime=None,
        progress_current=0,
        progress_required=3,
        last_commit_timestamp_ms=None,
        reason_codes=(),
        debug=None,
    )


class TestAnalysisEngineContracts(unittest.TestCase):
    def test_analysis_engine_event_is_frozen(self) -> None:
        payload = AnalysisRunStatusPayload(status="SUCCESS", module_failures=[])
        event = AnalysisEngineEvent(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            event_type="AnalysisRunCompleted",
            symbol="TEST",
            run_id="run-1",
            engine_timestamp_ms=123,
            payload=payload,
            engine_mode="truth",
            source_gate_reasons=["ok"],
        )
        with self.assertRaises(FrozenInstanceError):
            event.symbol = "OTHER"  # type: ignore[misc]

    def test_payloads_and_records_are_frozen(self) -> None:
        artifact = ArtifactEmittedPayload(
            artifact_kind="signal",
            module_id="mod",
            artifact_name="value",
            artifact_schema="schema",
            artifact_schema_version="1",
            payload={"x": 1},
        )
        with self.assertRaises(FrozenInstanceError):
            artifact.artifact_name = "other"  # type: ignore[misc]

        module_failed = ModuleFailedPayload(
            module_id="mod",
            module_kind="signal",
            error_kind="exception",
            error_detail="boom",
        )
        with self.assertRaises(FrozenInstanceError):
            module_failed.error_kind = "other"  # type: ignore[misc]

        run_status = AnalysisRunStatusPayload(status="PARTIAL", module_failures=["mod"])
        with self.assertRaises(FrozenInstanceError):
            run_status.status = "SUCCESS"  # type: ignore[misc]

        state_record = AnalysisModuleStateRecord(
            symbol="TEST",
            module_id="mod",
            run_id="run-1",
            engine_timestamp_ms=123,
            state_schema_id="state",
            state_schema_version="1",
            state_payload={"a": 1},
        )
        with self.assertRaises(FrozenInstanceError):
            state_record.state_schema_id = "other"  # type: ignore[misc]

    def test_registry_contract_fields(self) -> None:
        dependency = ModuleDependency(module_id="signal.a", artifact_name="value")
        artifact_schema = ArtifactSchema(
            artifact_name="value",
            artifact_schema="schema.signal.value",
            artifact_schema_version="1",
        )
        module = ModuleDefinition(
            module_id="signal.a",
            module_kind="signal",
            module_version="1",
            dependencies=[dependency],
            artifact_schemas=[artifact_schema],
            config_schema_id="config.signal.a",
            config_schema_version="1",
            enabled_by_default=False,
            state_schema_id=None,
            state_schema_version=None,
        )
        with self.assertRaises(FrozenInstanceError):
            module.module_version = "2"  # type: ignore[misc]

    def test_run_context_is_limited_to_gate_payloads(self) -> None:
        context = RunContext(
            symbol="TEST",
            run_id="run-1",
            engine_timestamp_ms=123,
            engine_mode="truth",
            gate_status="OPEN",
            gate_reasons=["ok"],
            regime_output=_regime_output("TEST", 123),
            hysteresis_state=None,
        )
        with self.assertRaises(FrozenInstanceError):
            context.gate_status = "CLOSED"  # type: ignore[misc]

    def test_constants_and_idempotency_key(self) -> None:
        self.assertEqual(SCHEMA_NAME, "analysis_engine_event")
        self.assertEqual(SCHEMA_VERSION, "1")
        self.assertEqual(ANALYSIS_EVENT_TYPES[0], "AnalysisRunStarted")
        self.assertIn("signal", ARTIFACT_KINDS)
        self.assertIn("detector", MODULE_KINDS)
        self.assertEqual(RUN_STATUSES, ("SUCCESS", "PARTIAL", "FAILED"))
        self.assertEqual(build_idempotency_key("run-1"), "run-1")


if __name__ == "__main__":
    unittest.main()
