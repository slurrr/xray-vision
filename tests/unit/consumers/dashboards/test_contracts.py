import unittest
from dataclasses import FrozenInstanceError

from consumers.dashboards import (
    CONFIDENCE_TREND_FLAT,
    CONFIDENCE_TREND_RISING,
    DVM_SCHEMA,
    DVM_SCHEMA_VERSION,
    DVM_VERSIONING_POLICY,
    PHASE_TRANSITIONING,
    AnalysisArtifactSummary,
    AnalysisSection,
    DashboardViewModel,
    GateSnapshot,
    HysteresisProgress,
    HysteresisSnapshot,
    HysteresisSummary,
    HysteresisTransition,
    MetricsSnapshot,
    RegimeEffectiveSnapshot,
    RegimeTruthSnapshot,
    SymbolSnapshot,
    SystemComponentStatus,
    SystemSection,
    TelemetryIngest,
    TelemetrySection,
    TelemetryStaleness,
)


class TestDashboardContracts(unittest.TestCase):
    def test_dvm_snapshot_is_frozen_and_validates_schema(self) -> None:
        symbol = SymbolSnapshot(
            symbol="BTC",
            last_run_id="run-1",
            last_engine_timestamp_ms=123,
            gate=GateSnapshot(status="OPEN", reasons=("reason-1",)),
        )
        dvm = DashboardViewModel(
            dvm_schema=DVM_SCHEMA,
            dvm_schema_version=DVM_SCHEMA_VERSION,
            as_of_ts_ms=999,
            source_run_id="run-1",
            source_engine_timestamp_ms=123,
            system=SystemSection(
                status="OK",
                components=(
                    SystemComponentStatus(
                        component_id="orchestrator",
                        status="OK",
                        details=(),
                        last_update_ts_ms=123,
                    ),
                ),
            ),
            symbols=(symbol,),
            telemetry=TelemetrySection(
                ingest=TelemetryIngest(
                    last_orchestrator_event_ts_ms=1,
                    last_state_gate_event_ts_ms=2,
                    last_analysis_engine_event_ts_ms=3,
                ),
                staleness=TelemetryStaleness(is_stale=False, stale_reasons=()),
            ),
        )

        with self.assertRaises(FrozenInstanceError):
            dvm.as_of_ts_ms = 1  # type: ignore[misc]

        with self.assertRaises(ValueError):
            DashboardViewModel(
                dvm_schema="other_schema",
                dvm_schema_version=DVM_SCHEMA_VERSION,
                as_of_ts_ms=1,
                source_run_id=None,
                source_engine_timestamp_ms=None,
                system=dvm.system,
                symbols=dvm.symbols,
                telemetry=dvm.telemetry,
            )

    def test_ordering_rules_are_enforced(self) -> None:
        unsorted_components = (
            SystemComponentStatus(
                component_id="state_gate",
                status="DEGRADED",
                details=("late",),
                last_update_ts_ms=20,
            ),
            SystemComponentStatus(
                component_id="analysis_engine",
                status="OK",
                details=(),
                last_update_ts_ms=10,
            ),
        )
        hysteresis_summary = HysteresisSummary(
            phase=PHASE_TRANSITIONING,
            anchor_regime="r1",
            candidate_regime="r2",
            progress=HysteresisProgress(current=2, required=3),
            confidence_trend=CONFIDENCE_TREND_RISING,
            notes=("reset_due_to_gap", "flipped"),
        )
        analysis_section = AnalysisSection(
            status="PRESENT",
            highlights=("beta", "alpha"),
            artifacts=(
                AnalysisArtifactSummary(
                    artifact_kind="output",
                    module_id="module-b",
                    artifact_name="artifact-b",
                    artifact_schema="schema",
                    artifact_schema_version="1",
                    summary="summary-b",
                ),
                AnalysisArtifactSummary(
                    artifact_kind="output",
                    module_id="module-a",
                    artifact_name="artifact-a",
                    artifact_schema="schema",
                    artifact_schema_version="1",
                    summary="summary-a",
                ),
            ),
        )
        unsorted_symbols = (
            SymbolSnapshot(
                symbol="BTC",
                last_run_id="run-2",
                last_engine_timestamp_ms=200,
                gate=GateSnapshot(status="OPEN", reasons=("b", "a")),
                regime_truth=RegimeTruthSnapshot(
                    regime_name="truth",
                    confidence=0.8,
                    drivers=("d2", "d1"),
                    invalidations=("i2", "i1"),
                    permissions=("p2", "p1"),
                ),
                hysteresis=HysteresisSnapshot(
                    effective_confidence=0.7,
                    transition=HysteresisTransition(
                        stable_regime="truth",
                        candidate_regime="hyst",
                        candidate_count=2,
                        transition_active=True,
                        flipped=False,
                        reset_due_to_gap=False,
                    ),
                    summary=hysteresis_summary,
                ),
                regime_effective=RegimeEffectiveSnapshot(
                    regime_name="hyst",
                    confidence=0.7,
                    drivers=("d2", "d1"),
                    invalidations=("i2", "i1"),
                    permissions=("p2", "p1"),
                    source="hysteresis",
                ),
                analysis=analysis_section,
                metrics=MetricsSnapshot(atr_rank=2),
            ),
            SymbolSnapshot(
                symbol="ADA",
                last_run_id="run-1",
                last_engine_timestamp_ms=100,
                gate=GateSnapshot(status="CLOSED", reasons=("c",)),
            ),
        )
        dvm = DashboardViewModel(
            dvm_schema=DVM_SCHEMA,
            dvm_schema_version=DVM_SCHEMA_VERSION,
            as_of_ts_ms=123,
            source_run_id="run-2",
            source_engine_timestamp_ms=200,
            system=SystemSection(status="DEGRADED", components=unsorted_components),
            symbols=unsorted_symbols,
            telemetry=TelemetrySection(
                ingest=TelemetryIngest(
                    last_orchestrator_event_ts_ms=10,
                    last_state_gate_event_ts_ms=11,
                    last_analysis_engine_event_ts_ms=12,
                ),
                staleness=TelemetryStaleness(
                    is_stale=True, stale_reasons=("engine_gap", "builder_halt")
                ),
            ),
        )

        self.assertEqual(
            tuple(component.component_id for component in dvm.system.components),
            ("analysis_engine", "state_gate"),
        )
        self.assertEqual(tuple(symbol.symbol for symbol in dvm.symbols), ("ADA", "BTC"))
        btc_symbol = dvm.symbols[1]
        assert btc_symbol.analysis is not None
        self.assertEqual(btc_symbol.analysis.highlights, ("alpha", "beta"))
        self.assertEqual(
            tuple(
                (artifact.module_id, artifact.artifact_name)
                for artifact in btc_symbol.analysis.artifacts
            ),
            (("module-a", "artifact-a"), ("module-b", "artifact-b")),
        )
        assert btc_symbol.hysteresis is not None
        assert btc_symbol.hysteresis.summary is not None
        self.assertEqual(btc_symbol.hysteresis.summary.notes, ("flipped", "reset_due_to_gap"))
        self.assertEqual(dvm.telemetry.staleness.stale_reasons, ("builder_halt", "engine_gap"))

    def test_versioning_policy_is_documented(self) -> None:
        self.assertEqual(DVM_SCHEMA, "dashboard_view_model")
        self.assertEqual(DVM_SCHEMA_VERSION, "1")
        self.assertIn("additive-only", DVM_VERSIONING_POLICY)
        self.assertIn("version", DVM_VERSIONING_POLICY)
        self.assertEqual(CONFIDENCE_TREND_FLAT, "FLAT")


if __name__ == "__main__":
    unittest.main()
