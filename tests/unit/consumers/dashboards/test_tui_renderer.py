import unittest
from io import StringIO

from consumers.analysis_engine.contracts import SCHEMA_NAME as ANALYSIS_ENGINE_SCHEMA
from consumers.analysis_engine.contracts import SCHEMA_VERSION as ANALYSIS_ENGINE_SCHEMA_VERSION
from consumers.analysis_engine.contracts import (
    AnalysisEngineEvent,
    AnalysisRunStatusPayload,
    ArtifactEmittedPayload,
)
from consumers.dashboards import (
    DashboardBuilder,
    DashboardViewModel,
    GateSnapshot,
    SymbolSnapshot,
    SystemComponentStatus,
    SystemSection,
    TelemetryIngest,
    TelemetrySection,
    TelemetryStaleness,
    TuiRenderer,
)
from consumers.state_gate.contracts import SCHEMA_NAME as STATE_GATE_SCHEMA
from consumers.state_gate.contracts import SCHEMA_VERSION as STATE_GATE_SCHEMA_VERSION
from consumers.state_gate.contracts import GateEvaluatedPayload, StateGateEvent
from orchestrator.contracts import SCHEMA_NAME as ORCHESTRATOR_SCHEMA
from orchestrator.contracts import SCHEMA_VERSION as ORCHESTRATOR_SCHEMA_VERSION
from orchestrator.contracts import (
    EngineRunCompletedPayload,
    HysteresisStatePayload,
    OrchestratorEvent,
)
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.state import SCHEMA_NAME, SCHEMA_VERSION, HysteresisState


def _regime_output(symbol: str, timestamp: int, regime: Regime) -> RegimeOutput:
    return RegimeOutput(
        symbol=symbol,
        timestamp=timestamp,
        regime=regime,
        confidence=1.0,
        drivers=["d1"],
        invalidations=["i1"],
        permissions=["p1"],
    )


def _hysteresis_state(symbol: str, timestamp: int) -> HysteresisState:
    return HysteresisState(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=symbol,
        engine_timestamp_ms=timestamp,
        anchor_regime=Regime.CHOP_BALANCED,
        candidate_regime=Regime.SQUEEZE_UP,
        progress_current=2,
        progress_required=2,
        last_commit_timestamp_ms=None,
        reason_codes=("COMMIT_SWITCH:CHOP_BALANCED->SQUEEZE_UP",),
        debug=None,
    )


class TestTuiRenderer(unittest.TestCase):
    def test_tui_handles_missing_optional_sections(self) -> None:
        system = SystemSection(
            status="UNKNOWN",
            components=[
                SystemComponentStatus(
                    component_id="orchestrator",
                    status="UNKNOWN",
                    details=("missing",),
                    last_update_ts_ms=None,
                ),
                SystemComponentStatus(
                    component_id="state_gate",
                    status="UNKNOWN",
                    details=("missing",),
                    last_update_ts_ms=None,
                ),
                SystemComponentStatus(
                    component_id="analysis_engine",
                    status="UNKNOWN",
                    details=("missing",),
                    last_update_ts_ms=None,
                ),
                SystemComponentStatus(
                    component_id="dashboards",
                    status="DEGRADED",
                    details=("stale",),
                    last_update_ts_ms=10,
                ),
            ],
        )
        telemetry = TelemetrySection(
            ingest=TelemetryIngest(
                last_orchestrator_event_ts_ms=None,
                last_state_gate_event_ts_ms=None,
                last_analysis_engine_event_ts_ms=None,
            ),
            staleness=TelemetryStaleness(is_stale=True, stale_reasons=("stale",)),
        )
        snapshot = DashboardViewModel(
            dvm_schema="dashboard_view_model",
            dvm_schema_version="1",
            as_of_ts_ms=10,
            source_run_id=None,
            source_engine_timestamp_ms=None,
            system=system,
            symbols=(
                SymbolSnapshot(
                    symbol="MISSING",
                    last_run_id=None,
                    last_engine_timestamp_ms=None,
                    gate=GateSnapshot(status="UNKNOWN", reasons=()),
                ),
            ),
            telemetry=telemetry,
        )
        object.__setattr__(snapshot, "future_section", {"note": "new"})
        object.__setattr__(snapshot.symbols[0], "future_field", "value")

        writer = StringIO()
        renderer = TuiRenderer(writer=writer)
        renderer.start()
        renderer.render(snapshot)
        renderer.stop()

        output = writer.getvalue()
        self.assertIn("stale=True", output)
        self.assertIn("gate=UNKNOWN", output)
        self.assertIn("system_status=UNKNOWN", output)

    def test_tui_renders_optional_sections(self) -> None:
        symbol = "SYM"
        builder = DashboardBuilder(time_fn=lambda: 300)
        truth_output = _regime_output(symbol, 100, Regime.CHOP_BALANCED)
        hysteresis_state = _hysteresis_state(symbol, 150)

        builder.ingest_orchestrator_event(
            OrchestratorEvent(
                schema=ORCHESTRATOR_SCHEMA,
                schema_version=ORCHESTRATOR_SCHEMA_VERSION,
                event_type="EngineRunCompleted",
                run_id="run-1",
                symbol=symbol,
                engine_timestamp_ms=100,
                cut_start_ingest_seq=1,
                cut_end_ingest_seq=1,
                cut_kind="timer",
                engine_mode="truth",
                payload=EngineRunCompletedPayload(regime_output=truth_output),
            )
        )
        builder.ingest_orchestrator_event(
            OrchestratorEvent(
                schema=ORCHESTRATOR_SCHEMA,
                schema_version=ORCHESTRATOR_SCHEMA_VERSION,
                event_type="HysteresisStatePublished",
                run_id="run-2",
                symbol=symbol,
                engine_timestamp_ms=150,
                cut_start_ingest_seq=1,
                cut_end_ingest_seq=1,
                cut_kind="timer",
                engine_mode="hysteresis",
                payload=HysteresisStatePayload(hysteresis_state=hysteresis_state),
            )
        )
        builder.ingest_state_gate_event(
            StateGateEvent(
                schema=STATE_GATE_SCHEMA,
                schema_version=STATE_GATE_SCHEMA_VERSION,
                event_type="GateEvaluated",
                symbol=symbol,
                engine_timestamp_ms=200,
                run_id="run-2",
                state_status="READY",
                gate_status="OPEN",
                reasons=("ready",),
                payload=GateEvaluatedPayload(
                    regime_output=truth_output, hysteresis_state=hysteresis_state
                ),
                input_event_type="HysteresisStatePublished",
                engine_mode="hysteresis",
            )
        )
        builder.ingest_analysis_engine_event(
            AnalysisEngineEvent(
                schema=ANALYSIS_ENGINE_SCHEMA,
                schema_version=ANALYSIS_ENGINE_SCHEMA_VERSION,
                event_type="ArtifactEmitted",
                symbol=symbol,
                run_id="run-2",
                engine_timestamp_ms=200,
                payload=ArtifactEmittedPayload(
                    artifact_kind="output",
                    module_id="m1",
                    artifact_name="a1",
                    artifact_schema="schema",
                    artifact_schema_version="1",
                    payload={"v": 1},
                ),
                engine_mode="hysteresis",
                source_gate_reasons=("ready",),
            )
        )
        builder.ingest_analysis_engine_event(
            AnalysisEngineEvent(
                schema=ANALYSIS_ENGINE_SCHEMA,
                schema_version=ANALYSIS_ENGINE_SCHEMA_VERSION,
                event_type="AnalysisRunCompleted",
                symbol=symbol,
                run_id="run-2",
                engine_timestamp_ms=200,
                payload=AnalysisRunStatusPayload(status="SUCCESS", module_failures=()),
                engine_mode="hysteresis",
                source_gate_reasons=("ready",),
            )
        )

        snapshot = builder.build_snapshot(as_of_ts_ms=250)
        writer = StringIO()
        renderer = TuiRenderer(writer=writer)
        renderer.start()
        renderer.render(snapshot)
        renderer.stop()

        output = writer.getvalue()
        self.assertIn("regime_effective", output)
        self.assertIn("regime_truth", output)
        self.assertIn("hysteresis_confidence", output)
        self.assertIn("analysis_status=PRESENT", output)
        self.assertIn("artifact=m1:a1", output)


if __name__ == "__main__":
    unittest.main()
