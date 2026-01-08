import unittest

from consumers.analysis_engine.contracts import (
    SCHEMA_NAME as ANALYSIS_ENGINE_SCHEMA,
)
from consumers.analysis_engine.contracts import (
    SCHEMA_VERSION as ANALYSIS_ENGINE_SCHEMA_VERSION,
)
from consumers.analysis_engine.contracts import (
    AnalysisEngineEvent,
    AnalysisEnginePayload,
    AnalysisEventType,
    AnalysisRunStatusPayload,
    ArtifactEmittedPayload,
)
from consumers.dashboards import DashboardBuilder
from consumers.state_gate.contracts import (
    SCHEMA_NAME as STATE_GATE_SCHEMA,
)
from consumers.state_gate.contracts import (
    SCHEMA_VERSION as STATE_GATE_SCHEMA_VERSION,
)
from consumers.state_gate.contracts import (
    GateEvaluatedPayload,
    GateStatus,
    StateGateEvent,
    StateGatePayload,
)
from orchestrator.contracts import (
    SCHEMA_NAME as ORCHESTRATOR_SCHEMA,
)
from orchestrator.contracts import (
    SCHEMA_VERSION as ORCHESTRATOR_SCHEMA_VERSION,
)
from orchestrator.contracts import (
    EngineMode,
    EngineRunCompletedPayload,
    EventType,
    HysteresisStatePayload,
    OrchestratorEvent,
)
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.state import SCHEMA_NAME, SCHEMA_VERSION, HysteresisState


def _regime_output(*, symbol: str, timestamp: int, regime: Regime) -> RegimeOutput:
    return RegimeOutput(
        symbol=symbol,
        timestamp=timestamp,
        regime=regime,
        confidence=0.8,
        drivers=["driver-1"],
        invalidations=["invalid-1"],
        permissions=["perm-1"],
    )


def _hysteresis_state(
    *,
    symbol: str,
    engine_timestamp_ms: int,
    anchor_regime: Regime,
    candidate_regime: Regime | None,
    progress_current: int,
    progress_required: int,
    reason_codes: tuple[str, ...],
) -> HysteresisState:
    return HysteresisState(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        anchor_regime=anchor_regime,
        candidate_regime=candidate_regime,
        progress_current=progress_current,
        progress_required=progress_required,
        last_commit_timestamp_ms=None,
        reason_codes=reason_codes,
        debug=None,
    )


def _orchestrator_event(
    *,
    event_type: EventType,
    run_id: str,
    symbol: str,
    engine_timestamp_ms: int,
    payload: object | None = None,
    engine_mode: EngineMode | None = None,
) -> OrchestratorEvent:
    return OrchestratorEvent(
        schema=ORCHESTRATOR_SCHEMA,
        schema_version=ORCHESTRATOR_SCHEMA_VERSION,
        event_type=event_type,  # type: ignore[arg-type]
        run_id=run_id,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        cut_start_ingest_seq=1,
        cut_end_ingest_seq=1,
        cut_kind="timer",
        engine_mode=engine_mode,
        payload=payload,
    )


def _state_gate_event(
    *,
    run_id: str,
    symbol: str,
    engine_timestamp_ms: int,
    gate_status: GateStatus,
    reasons: tuple[str, ...],
    payload: StateGatePayload | None = None,
    engine_mode: EngineMode | None = None,
) -> StateGateEvent:
    return StateGateEvent(
        schema=STATE_GATE_SCHEMA,
        schema_version=STATE_GATE_SCHEMA_VERSION,
        event_type="GateEvaluated",
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        run_id=run_id,
        state_status="READY",
        gate_status=gate_status,  # type: ignore[arg-type]
        reasons=reasons,
        payload=payload,
        input_event_type="EngineRunCompleted",
        engine_mode=engine_mode,
    )


def _analysis_event(
    *,
    event_type: AnalysisEventType,
    symbol: str,
    run_id: str,
    engine_timestamp_ms: int,
    payload: AnalysisEnginePayload | None = None,
) -> AnalysisEngineEvent:
    return AnalysisEngineEvent(
        schema=ANALYSIS_ENGINE_SCHEMA,
        schema_version=ANALYSIS_ENGINE_SCHEMA_VERSION,
        event_type=event_type,  # type: ignore[arg-type]
        symbol=symbol,
        run_id=run_id,
        engine_timestamp_ms=engine_timestamp_ms,
        payload=payload,
        engine_mode=None,
        source_gate_reasons=None,
    )


def _ingest(builder: DashboardBuilder, kind: str, event: object) -> None:
    if kind == "orchestrator":
        builder.ingest_orchestrator_event(event)  # type: ignore[arg-type]
    elif kind == "state_gate":
        builder.ingest_state_gate_event(event)  # type: ignore[arg-type]
    elif kind == "analysis":
        builder.ingest_analysis_engine_event(event)  # type: ignore[arg-type]


class TestDashboardBuilder(unittest.TestCase):
    def test_builder_constructs_snapshot_from_events(self) -> None:
        builder = DashboardBuilder(time_fn=lambda: 999)
        symbol = "TEST"
        truth_output = _regime_output(symbol=symbol, timestamp=100, regime=Regime.CHOP_BALANCED)
        hysteresis_state = _hysteresis_state(
            symbol=symbol,
            engine_timestamp_ms=150,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=Regime.SQUEEZE_UP,
            progress_current=2,
            progress_required=2,
            reason_codes=("COMMIT_SWITCH:CHOP_BALANCED->SQUEEZE_UP", "PROGRESS_INC"),
        )

        builder.ingest_orchestrator_event(
            _orchestrator_event(
                event_type="EngineRunCompleted",
                run_id="run-1",
                symbol=symbol,
                engine_timestamp_ms=100,
                payload=EngineRunCompletedPayload(regime_output=truth_output),
                engine_mode="truth",
            )
        )
        builder.ingest_orchestrator_event(
            _orchestrator_event(
                event_type="HysteresisStatePublished",
                run_id="run-2",
                symbol=symbol,
                engine_timestamp_ms=150,
                payload=HysteresisStatePayload(hysteresis_state=hysteresis_state),
                engine_mode="hysteresis",
            )
        )

        gate_payload = GateEvaluatedPayload(
            regime_output=truth_output, hysteresis_state=hysteresis_state
        )
        builder.ingest_state_gate_event(
            _state_gate_event(
                run_id="run-2",
                symbol=symbol,
                engine_timestamp_ms=200,
                gate_status="OPEN",
                reasons=("ok",),
                payload=gate_payload,
                engine_mode="hysteresis",
            )
        )

        artifact_payload = ArtifactEmittedPayload(
            artifact_kind="output",
            module_id="module",
            artifact_name="artifact",
            artifact_schema="artifact-schema",
            artifact_schema_version="1",
            payload={"value": 1},
        )
        builder.ingest_analysis_engine_event(
            _analysis_event(
                event_type="ArtifactEmitted",
                symbol=symbol,
                run_id="run-2",
                engine_timestamp_ms=200,
                payload=artifact_payload,
            )
        )
        builder.ingest_analysis_engine_event(
            _analysis_event(
                event_type="AnalysisRunCompleted",
                symbol=symbol,
                run_id="run-2",
                engine_timestamp_ms=200,
                payload=AnalysisRunStatusPayload(status="SUCCESS", module_failures=()),
            )
        )

        snapshot = builder.build_snapshot(as_of_ts_ms=250)
        self.assertEqual(snapshot.dvm_schema, "dashboard_view_model")
        self.assertFalse(snapshot.telemetry.staleness.is_stale)
        self.assertEqual(snapshot.system.status, "OK")
        self.assertEqual(snapshot.source_run_id, "run-2")
        self.assertEqual(snapshot.source_engine_timestamp_ms, 200)

        self.assertEqual(len(snapshot.symbols), 1)
        symbol_snapshot = snapshot.symbols[0]
        self.assertEqual(symbol_snapshot.gate.status, "OPEN")
        assert symbol_snapshot.regime_truth is not None
        self.assertEqual(symbol_snapshot.regime_truth.regime_name, Regime.CHOP_BALANCED.value)
        assert symbol_snapshot.regime_effective is not None
        self.assertEqual(symbol_snapshot.regime_effective.source, "hysteresis")
        self.assertIsNotNone(symbol_snapshot.hysteresis)
        assert symbol_snapshot.hysteresis is not None  # narrow type for mypy/pyright
        assert symbol_snapshot.hysteresis.summary is not None
        self.assertEqual(symbol_snapshot.hysteresis.summary.phase, "FLIPPED")
        self.assertEqual(symbol_snapshot.hysteresis.summary.progress.required, 2)
        self.assertEqual(symbol_snapshot.hysteresis.summary.confidence_trend, "FLAT")
        assert symbol_snapshot.analysis is not None
        self.assertEqual(symbol_snapshot.analysis.status, "PRESENT")
        self.assertEqual(
            (
                symbol_snapshot.analysis.artifacts[0].module_id,
                symbol_snapshot.analysis.artifacts[0].artifact_name,
            ),
            ("module", "artifact"),
        )

    def test_builder_handles_out_of_order_events(self) -> None:
        builder = DashboardBuilder(time_fn=lambda: 111)
        symbol = "AAA"
        recent_gate = _state_gate_event(
            run_id="run-new",
            symbol=symbol,
            engine_timestamp_ms=200,
            gate_status="OPEN",
            reasons=("new",),
        )
        older_gate = _state_gate_event(
            run_id="run-old",
            symbol=symbol,
            engine_timestamp_ms=100,
            gate_status="CLOSED",
            reasons=("old",),
        )

        builder.ingest_state_gate_event(recent_gate)
        builder.ingest_state_gate_event(older_gate)
        builder.ingest_state_gate_event(recent_gate)

        snapshot = builder.build_snapshot(as_of_ts_ms=210)
        symbol_snapshot = snapshot.symbols[0]
        self.assertEqual(symbol_snapshot.gate.status, "OPEN")
        self.assertEqual(symbol_snapshot.gate.reasons, ("new",))
        self.assertEqual(snapshot.source_run_id, "run-new")
        self.assertEqual(snapshot.source_engine_timestamp_ms, 200)

    def test_hysteresis_summary_carries_progress_and_trend(self) -> None:
        builder = DashboardBuilder(time_fn=lambda: 222)
        symbol = "BBB"
        first_state = _hysteresis_state(
            symbol=symbol,
            engine_timestamp_ms=10,
            anchor_regime=Regime.TREND_BUILD_UP,
            candidate_regime=Regime.TREND_BUILD_DOWN,
            progress_current=1,
            progress_required=3,
            reason_codes=("PROGRESS_RESET",),
        )
        second_state = _hysteresis_state(
            symbol=symbol,
            engine_timestamp_ms=20,
            anchor_regime=Regime.TREND_BUILD_UP,
            candidate_regime=Regime.TREND_BUILD_DOWN,
            progress_current=3,
            progress_required=3,
            reason_codes=("PROGRESS_INC",),
        )
        third_state = _hysteresis_state(
            symbol=symbol,
            engine_timestamp_ms=30,
            anchor_regime=Regime.TREND_BUILD_DOWN,
            candidate_regime=None,
            progress_current=0,
            progress_required=3,
            reason_codes=("CANDIDATE_SAME_AS_ANCHOR",),
        )

        builder.ingest_orchestrator_event(
            _orchestrator_event(
                event_type="HysteresisStatePublished",
                run_id="run-1",
                symbol=symbol,
                engine_timestamp_ms=100,
                payload=HysteresisStatePayload(hysteresis_state=first_state),
                engine_mode="hysteresis",
            )
        )
        first_snapshot = builder.build_snapshot(as_of_ts_ms=101)
        assert first_snapshot.symbols[0].hysteresis is not None
        self.assertIsNotNone(first_snapshot.symbols[0].hysteresis.summary)

        builder.ingest_orchestrator_event(
            _orchestrator_event(
                event_type="HysteresisStatePublished",
                run_id="run-2",
                symbol=symbol,
                engine_timestamp_ms=200,
                payload=HysteresisStatePayload(hysteresis_state=second_state),
                engine_mode="hysteresis",
            )
        )
        second_snapshot = builder.build_snapshot(as_of_ts_ms=201)
        assert second_snapshot.symbols[0].hysteresis is not None
        summary = second_snapshot.symbols[0].hysteresis.summary
        assert summary is not None
        self.assertEqual(summary.progress.required, 3)
        self.assertEqual(summary.progress.current, 3)
        self.assertEqual(summary.confidence_trend, "FLAT")

        builder.ingest_orchestrator_event(
            _orchestrator_event(
                event_type="HysteresisStatePublished",
                run_id="run-3",
                symbol=symbol,
                engine_timestamp_ms=300,
                payload=HysteresisStatePayload(hysteresis_state=third_state),
                engine_mode="hysteresis",
            )
        )
        third_snapshot = builder.build_snapshot(as_of_ts_ms=301)
        assert third_snapshot.symbols[0].hysteresis is not None
        summary = third_snapshot.symbols[0].hysteresis.summary
        assert summary is not None
        self.assertEqual(summary.progress.required, 3)
        self.assertEqual(summary.progress.current, 0)
        self.assertEqual(summary.confidence_trend, "FLAT")

    def test_staleness_signals_missing_inputs(self) -> None:
        builder = DashboardBuilder(time_fn=lambda: 333)
        snapshot = builder.build_snapshot(as_of_ts_ms=333)
        self.assertTrue(snapshot.telemetry.staleness.is_stale)
        self.assertIn("missing_orchestrator_events", snapshot.telemetry.staleness.stale_reasons)
        self.assertEqual(snapshot.system.status, "UNKNOWN")

    def test_builder_is_deterministic_for_same_event_log(self) -> None:
        symbol = "DET"
        truth_output = _regime_output(symbol=symbol, timestamp=1, regime=Regime.CHOP_BALANCED)
        hysteresis_state = _hysteresis_state(
            symbol=symbol,
            engine_timestamp_ms=2,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=Regime.SQUEEZE_UP,
            progress_current=1,
            progress_required=3,
            reason_codes=("PROGRESS_RESET",),
        )

        orchestrator_completed = _orchestrator_event(
            event_type="EngineRunCompleted",
            run_id="run-1",
            symbol=symbol,
            engine_timestamp_ms=10,
            payload=EngineRunCompletedPayload(regime_output=truth_output),
            engine_mode="truth",
        )
        state_gate_event = _state_gate_event(
            run_id="run-1",
            symbol=symbol,
            engine_timestamp_ms=11,
            gate_status="OPEN",
            reasons=("go",),
            payload=GateEvaluatedPayload(
                regime_output=truth_output, hysteresis_state=hysteresis_state
            ),
            engine_mode="hysteresis",
        )
        analysis_event = _analysis_event(
            event_type="AnalysisRunCompleted",
            symbol=symbol,
            run_id="run-1",
            engine_timestamp_ms=11,
            payload=AnalysisRunStatusPayload(status="SUCCESS", module_failures=()),
        )

        event_log = (
            ("orchestrator", orchestrator_completed),
            ("state_gate", state_gate_event),
            ("analysis", analysis_event),
        )

        builder_a = DashboardBuilder(time_fn=lambda: 500)
        for kind, event in event_log:
            _ingest(builder_a, kind, event)
        snapshot_a = builder_a.build_snapshot(as_of_ts_ms=600)

        builder_b = DashboardBuilder(time_fn=lambda: 500)
        for kind, event in reversed(event_log):
            _ingest(builder_b, kind, event)
        snapshot_b = builder_b.build_snapshot(as_of_ts_ms=600)

        self.assertEqual(snapshot_a, snapshot_b)


if __name__ == "__main__":
    unittest.main()
