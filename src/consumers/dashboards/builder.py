from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import cast

from consumers.analysis_engine.contracts import (
    ANALYSIS_EVENT_TYPES,
    AnalysisEngineEvent,
    AnalysisRunStatusPayload,
    ArtifactEmittedPayload,
    ModuleFailedPayload,
)
from consumers.analysis_engine.contracts import (
    SCHEMA_NAME as ANALYSIS_ENGINE_SCHEMA,
)
from consumers.analysis_engine.contracts import (
    SCHEMA_VERSION as ANALYSIS_ENGINE_SCHEMA_VERSION,
)
from consumers.state_gate.contracts import (
    SCHEMA_NAME as STATE_GATE_SCHEMA,
)
from consumers.state_gate.contracts import (
    SCHEMA_VERSION as STATE_GATE_SCHEMA_VERSION,
)
from consumers.state_gate.contracts import (
    GateEvaluatedPayload,
    StateGateEvent,
)
from orchestrator.contracts import (
    SCHEMA_NAME as ORCHESTRATOR_SCHEMA,
)
from orchestrator.contracts import (
    SCHEMA_VERSION as ORCHESTRATOR_SCHEMA_VERSION,
)
from orchestrator.contracts import (
    EngineRunCompletedPayload,
    HysteresisStatePayload,
    OrchestratorEvent,
)
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.state import HysteresisState

from .contracts import (
    BELIEF_TREND_FALLING,
    BELIEF_TREND_FLAT,
    BELIEF_TREND_RISING,
    BELIEF_TREND_UNKNOWN,
    CONFIDENCE_TREND_FALLING,
    CONFIDENCE_TREND_FLAT,
    CONFIDENCE_TREND_RISING,
    DVM_SCHEMA,
    DVM_SCHEMA_VERSION,
    PHASE_FLIPPED,
    PHASE_RESET,
    PHASE_STABLE,
    PHASE_TRANSITIONING,
    AnalysisArtifactSummary,
    AnalysisSection,
    BeliefDistributionEntry,
    BeliefSnapshot,
    BeliefTrend,
    BeliefTrendStatus,
    ComponentStatus,
    ConfidenceTrend,
    DashboardViewModel,
    GateSnapshot,
    HysteresisPhase,
    HysteresisProgress,
    HysteresisSnapshot,
    HysteresisSummary,
    HysteresisTransition,
    MetricsSnapshot,
    RegimeEffectiveSnapshot,
    RegimeSource,
    RegimeTruthSnapshot,
    SymbolSnapshot,
    SystemComponentStatus,
    SystemSection,
    TelemetryIngest,
    TelemetrySection,
    TelemetryStaleness,
)
from .observability import NullLogger, NullMetrics, Observability

TimeFn = Callable[[], int]

_NO_EVENTS_DETAIL = "no events ingested"


@dataclass
class _TelemetryState:
    last_orchestrator_event_ts_ms: int | None = None
    last_state_gate_event_ts_ms: int | None = None
    last_analysis_engine_event_ts_ms: int | None = None

    def has_any_events(self) -> bool:
        return any(
            ts is not None
            for ts in (
                self.last_orchestrator_event_ts_ms,
                self.last_state_gate_event_ts_ms,
                self.last_analysis_engine_event_ts_ms,
            )
        )


@dataclass
class _AnalysisState:
    run_id: str | None = None
    engine_timestamp_ms: int | None = None
    highlights: set[str] = field(default_factory=set)
    artifacts: dict[tuple[str, str], AnalysisArtifactSummary] = field(default_factory=dict)
    status_hint: str | None = None

    def reset_for_run(self, run_id: str | None, engine_timestamp_ms: int) -> None:
        self.run_id = run_id
        self.engine_timestamp_ms = engine_timestamp_ms
        self.highlights = set()
        self.artifacts = {}
        self.status_hint = None


@dataclass
class _SymbolState:
    symbol: str
    gate: GateSnapshot = field(default_factory=lambda: GateSnapshot(status="UNKNOWN", reasons=()))
    gate_updated_at: int | None = None
    regime_truth: RegimeTruthSnapshot | None = None
    regime_truth_ts: int | None = None
    hysteresis: HysteresisSnapshot | None = None
    hysteresis_ts: int | None = None
    belief: BeliefSnapshot | None = None
    belief_ts: int | None = None
    regime_effective: RegimeEffectiveSnapshot | None = None
    regime_effective_ts: int | None = None
    analysis: _AnalysisState = field(default_factory=_AnalysisState)
    metrics: MetricsSnapshot | None = None
    last_run_id: str | None = None
    last_engine_timestamp_ms: int | None = None
    hysteresis_progress_required: int | None = None
    previous_progress_required: int | None = None
    previous_effective_confidence: float | None = None
    previous_belief_by_regime: dict[str, float] | None = None

    def track_run(self, run_id: str, engine_timestamp_ms: int) -> None:
        if (
            self.last_engine_timestamp_ms is None
            or engine_timestamp_ms >= self.last_engine_timestamp_ms
        ):
            self.last_run_id = run_id
            self.last_engine_timestamp_ms = engine_timestamp_ms


class DashboardBuilder:
    def __init__(
        self,
        *,
        time_fn: TimeFn | None = None,
        observability: Observability | None = None,
        default_time_window_ms: int = 0,
    ) -> None:
        self._symbols: dict[str, _SymbolState] = {}
        self._telemetry = _TelemetryState()
        self._latest_source: tuple[int, str] | None = None
        self._last_logged_source: tuple[int, str] | None = None
        self._time_fn = time_fn or (lambda: int(time.time() * 1000))
        self._observability = observability or Observability(
            logger=NullLogger(), metrics=NullMetrics()
        )
        self._ingest_failure_codes: set[str] = set()
        self._default_time_window_ms = default_time_window_ms

    def ingest_orchestrator_event(self, event: OrchestratorEvent) -> None:
        if not self._validate_or_record(
            event.schema,
            event.schema_version,
            ORCHESTRATOR_SCHEMA,
            ORCHESTRATOR_SCHEMA_VERSION,
            event.event_type,
        ):
            return

        try:
            self._telemetry.last_orchestrator_event_ts_ms = event.engine_timestamp_ms
            symbol_state = self._symbol_state(event.symbol)
            if event.event_type == "EngineRunCompleted":
                self._track_source(event.run_id, event.engine_timestamp_ms)
            symbol_state.track_run(event.run_id, event.engine_timestamp_ms)

            if event.event_type == "EngineRunCompleted" and isinstance(
                event.payload, EngineRunCompletedPayload
            ):
                if (
                    symbol_state.regime_truth_ts is None
                    or event.engine_timestamp_ms >= symbol_state.regime_truth_ts
                ):
                    symbol_state.regime_truth = _regime_truth_from_output(
                        event.payload.regime_output
                    )
                    symbol_state.regime_truth_ts = event.engine_timestamp_ms

            if event.event_type == "HysteresisStatePublished" and isinstance(
                event.payload, HysteresisStatePayload
            ):
                if (
                    symbol_state.hysteresis_ts is None
                    or event.engine_timestamp_ms >= symbol_state.hysteresis_ts
                ):
                    symbol_state.hysteresis = _hysteresis_snapshot_from_state(
                        event.payload.hysteresis_state,
                        effective_confidence=None,
                    )
                    symbol_state.hysteresis_ts = event.engine_timestamp_ms
                    symbol_state.hysteresis_progress_required = (
                        event.payload.hysteresis_state.progress_required
                    )
                belief_snapshot = _belief_snapshot_from_state(
                    event.payload.hysteresis_state,
                    previous_belief=symbol_state.previous_belief_by_regime,
                )
                if belief_snapshot is not None and (
                    symbol_state.belief_ts is None
                    or event.engine_timestamp_ms >= symbol_state.belief_ts
                ):
                    symbol_state.belief = belief_snapshot
                    symbol_state.belief_ts = event.engine_timestamp_ms
        except Exception as exc:  # pragma: no cover - defensive guard
            self._record_ingest_failure(
                input_schema=event.schema,
                input_event_type=event.event_type,
                error_kind="ingest_error",
                error_detail=str(exc),
            )

    def ingest_state_gate_event(self, event: StateGateEvent) -> None:
        if not self._validate_or_record(
            event.schema,
            event.schema_version,
            STATE_GATE_SCHEMA,
            STATE_GATE_SCHEMA_VERSION,
            event.event_type,
        ):
            return

        try:
            self._telemetry.last_state_gate_event_ts_ms = event.engine_timestamp_ms
            symbol_state = self._symbol_state(event.symbol)
            self._track_source(event.run_id, event.engine_timestamp_ms)
            symbol_state.track_run(event.run_id, event.engine_timestamp_ms)

            if (
                symbol_state.gate_updated_at is None
                or event.engine_timestamp_ms >= symbol_state.gate_updated_at
            ):
                symbol_state.gate = GateSnapshot(
                    status=event.gate_status, reasons=tuple(event.reasons)
                )
                symbol_state.gate_updated_at = event.engine_timestamp_ms

            if isinstance(event.payload, GateEvaluatedPayload):
                effective = _regime_effective_from_payload(
                    payload=event.payload,
                    engine_mode=event.engine_mode,
                )
                if effective is not None and (
                    symbol_state.regime_effective_ts is None
                    or event.engine_timestamp_ms >= symbol_state.regime_effective_ts
                ):
                    symbol_state.regime_effective = effective
                    symbol_state.regime_effective_ts = event.engine_timestamp_ms

                if event.payload.hysteresis_state is not None:
                    effective_confidence = None
                    if event.payload.regime_output is not None:
                        effective_confidence = event.payload.regime_output.confidence
                    hysteresis_snapshot = _hysteresis_snapshot_from_state(
                        event.payload.hysteresis_state,
                        effective_confidence=effective_confidence,
                    )
                    if (
                        symbol_state.hysteresis_ts is None
                        or event.engine_timestamp_ms >= symbol_state.hysteresis_ts
                    ):
                        symbol_state.hysteresis = hysteresis_snapshot
                        symbol_state.hysteresis_ts = event.engine_timestamp_ms
                        symbol_state.hysteresis_progress_required = (
                            event.payload.hysteresis_state.progress_required
                        )
                    belief_snapshot = _belief_snapshot_from_state(
                        event.payload.hysteresis_state,
                        previous_belief=symbol_state.previous_belief_by_regime,
                    )
                    if belief_snapshot is not None and (
                        symbol_state.belief_ts is None
                        or event.engine_timestamp_ms >= symbol_state.belief_ts
                    ):
                        symbol_state.belief = belief_snapshot
                        symbol_state.belief_ts = event.engine_timestamp_ms
        except Exception as exc:  # pragma: no cover - defensive guard
            self._record_ingest_failure(
                input_schema=event.schema,
                input_event_type=event.event_type,
                error_kind="ingest_error",
                error_detail=str(exc),
            )

    def ingest_analysis_engine_event(self, event: AnalysisEngineEvent) -> None:
        if not self._validate_or_record(
            event.schema,
            event.schema_version,
            ANALYSIS_ENGINE_SCHEMA,
            ANALYSIS_ENGINE_SCHEMA_VERSION,
            event.event_type,
        ):
            return
        if event.event_type not in ANALYSIS_EVENT_TYPES:
            self._record_ingest_failure(
                input_schema=event.schema,
                input_event_type=event.event_type,
                error_kind="invalid_event_type",
                error_detail="analysis_engine_event type not supported",
            )
            return

        try:
            self._telemetry.last_analysis_engine_event_ts_ms = event.engine_timestamp_ms
            symbol_state = self._symbol_state(event.symbol)
            self._track_source(event.run_id, event.engine_timestamp_ms)
            symbol_state.track_run(event.run_id, event.engine_timestamp_ms)

            analysis_state = symbol_state.analysis
            if (
                analysis_state.engine_timestamp_ms is None
                or event.engine_timestamp_ms > analysis_state.engine_timestamp_ms
            ):
                analysis_state.reset_for_run(event.run_id, event.engine_timestamp_ms)
            elif event.engine_timestamp_ms < analysis_state.engine_timestamp_ms:
                return
            elif (
                analysis_state.run_id is not None
                and event.run_id is not None
                and event.run_id != analysis_state.run_id
            ):
                if event.run_id < analysis_state.run_id:
                    return
                analysis_state.reset_for_run(event.run_id, event.engine_timestamp_ms)

            if event.event_type == "ArtifactEmitted" and isinstance(
                event.payload, ArtifactEmittedPayload
            ):
                summary = AnalysisArtifactSummary(
                    artifact_kind=event.payload.artifact_kind,
                    module_id=event.payload.module_id,
                    artifact_name=event.payload.artifact_name,
                    artifact_schema=event.payload.artifact_schema,
                    artifact_schema_version=event.payload.artifact_schema_version,
                    summary=f"{event.payload.module_id}:{event.payload.artifact_name}",
                )
                analysis_state.artifacts[(event.payload.module_id, event.payload.artifact_name)] = (
                    summary
                )
                analysis_state.highlights.add(
                    f"artifact:{event.payload.module_id}:{event.payload.artifact_name}"
                )

            if event.event_type == "ModuleFailed" and isinstance(
                event.payload, ModuleFailedPayload
            ):
                analysis_state.highlights.add(f"module_failed:{event.payload.module_id}")

            if event.event_type == "AnalysisRunCompleted" and isinstance(
                event.payload, AnalysisRunStatusPayload
            ):
                analysis_state.highlights.add(f"run_completed:{event.payload.status.lower()}")
                for module_id in event.payload.module_failures:
                    analysis_state.highlights.add(f"module_failure:{module_id}")
                analysis_state.status_hint = event.payload.status

            if event.event_type == "AnalysisRunSkipped":
                analysis_state.highlights.add("run_skipped")
                analysis_state.status_hint = "SKIPPED"

            if event.event_type == "AnalysisRunFailed":
                analysis_state.highlights.add("run_failed")
                analysis_state.status_hint = "FAILED"

            if event.event_type == "AnalysisRunStarted":
                analysis_state.highlights.add("run_started")
        except Exception as exc:  # pragma: no cover - defensive guard
            self._record_ingest_failure(
                input_schema=event.schema,
                input_event_type=event.event_type,
                error_kind="ingest_error",
                error_detail=str(exc),
            )

    def build_snapshot(self, *, as_of_ts_ms: int | None = None) -> DashboardViewModel:
        start_time = self._time_fn()
        as_of = as_of_ts_ms if as_of_ts_ms is not None else self._time_fn()
        telemetry = self._build_telemetry(as_of_ts_ms=as_of)
        system = self._build_system_section(as_of_ts_ms=as_of, telemetry=telemetry)
        symbols = tuple(self._build_symbol_snapshot(state) for state in self._symbols.values())
        source_engine_timestamp_ms, source_run_id = (
            self._latest_source if self._latest_source else (None, None)
        )
        snapshot = DashboardViewModel(
            dvm_schema=DVM_SCHEMA,
            dvm_schema_version=DVM_SCHEMA_VERSION,
            as_of_ts_ms=as_of,
            source_run_id=source_run_id,
            source_engine_timestamp_ms=source_engine_timestamp_ms,
            system=system,
            symbols=symbols,
            telemetry=telemetry,
        )
        latency_ms = max(0, self._time_fn() - start_time)
        builder_lag_ms = _builder_lag(as_of_ts_ms=as_of, telemetry=telemetry)
        if source_engine_timestamp_ms is None or source_run_id is None:
            self._observability.log_snapshot(snapshot, latency_ms=latency_ms)
            self._observability.record_snapshot_metrics(
                latency_ms=latency_ms, builder_lag_ms=builder_lag_ms
            )
            return snapshot

        if source_engine_timestamp_ms is not None and source_run_id is not None:
            current_source = (source_engine_timestamp_ms, source_run_id)
            should_log = (
                self._last_logged_source is None
                or current_source != self._last_logged_source
            )
            if should_log:
                self._observability.log_snapshot(snapshot, latency_ms=latency_ms)
                self._observability.record_snapshot_metrics(
                    latency_ms=latency_ms, builder_lag_ms=builder_lag_ms
                )
                self._last_logged_source = current_source
        return snapshot

    def _build_symbol_snapshot(self, symbol_state: _SymbolState) -> SymbolSnapshot:
        hysteresis_snapshot = symbol_state.hysteresis
        summary = (
            self._build_hysteresis_summary(symbol_state)
            if hysteresis_snapshot is not None
            else None
        )
        if hysteresis_snapshot is not None:
            hysteresis_snapshot = HysteresisSnapshot(
                effective_confidence=hysteresis_snapshot.effective_confidence,
                transition=hysteresis_snapshot.transition,
                summary=summary,
            )

        analysis_section = self._build_analysis_section(symbol_state.analysis)

        snapshot = SymbolSnapshot(
            symbol=symbol_state.symbol,
            last_run_id=symbol_state.last_run_id,
            last_engine_timestamp_ms=symbol_state.last_engine_timestamp_ms,
            gate=symbol_state.gate,
            regime_truth=symbol_state.regime_truth,
            hysteresis=hysteresis_snapshot,
            regime_effective=symbol_state.regime_effective,
            analysis=analysis_section,
            metrics=symbol_state.metrics,
            belief=symbol_state.belief,
        )

        self._update_previous_hysteresis_state(symbol_state, hysteresis_snapshot)
        self._update_previous_belief_state(symbol_state, symbol_state.belief)
        return snapshot

    def _build_hysteresis_summary(self, symbol_state: _SymbolState) -> HysteresisSummary | None:
        if symbol_state.hysteresis is None:
            return None

        transition = symbol_state.hysteresis.transition
        progress_required = symbol_state.hysteresis_progress_required
        if progress_required is None:
            return None

        confidence_trend = self._confidence_trend(
            previous=symbol_state.previous_effective_confidence,
            current=symbol_state.hysteresis.effective_confidence,
        )
        phase = _hysteresis_phase(transition)
        notes: Sequence[str] = ()
        if transition.reset_due_to_gap:
            notes = (*notes, "reset_due_to_gap")
        if transition.flipped:
            notes = (*notes, "flipped")

        return HysteresisSummary(
            phase=phase,
            anchor_regime=transition.stable_regime,
            candidate_regime=transition.candidate_regime,
            progress=HysteresisProgress(
                current=transition.candidate_count, required=progress_required
            ),
            confidence_trend=confidence_trend,
            notes=notes,
        )

    def _confidence_trend(self, previous: float | None, current: float) -> ConfidenceTrend:
        if previous is None:
            return CONFIDENCE_TREND_FLAT
        if current > previous:
            return CONFIDENCE_TREND_RISING
        if current < previous:
            return CONFIDENCE_TREND_FALLING
        return CONFIDENCE_TREND_FLAT

    def _update_previous_belief_state(
        self,
        symbol_state: _SymbolState,
        belief_snapshot: BeliefSnapshot | None,
    ) -> None:
        if belief_snapshot is None:
            symbol_state.previous_belief_by_regime = None
            return
        symbol_state.previous_belief_by_regime = {
            entry.regime_name: entry.mass
            for entry in belief_snapshot.distribution
        }

    def _build_analysis_section(self, analysis_state: _AnalysisState) -> AnalysisSection | None:
        if not analysis_state.highlights and not analysis_state.artifacts:
            return None

        status = "EMPTY"
        if analysis_state.artifacts:
            status = "PRESENT"
        elif analysis_state.highlights:
            status = "PARTIAL"

        artifacts = tuple(analysis_state.artifacts.values())
        return AnalysisSection(
            status=status, highlights=tuple(analysis_state.highlights), artifacts=artifacts
        )

    def _build_telemetry(self, *, as_of_ts_ms: int) -> TelemetrySection:
        stale_reasons = []
        if self._telemetry.last_orchestrator_event_ts_ms is None:
            stale_reasons.append("missing_orchestrator_events")
        if self._telemetry.last_state_gate_event_ts_ms is None:
            stale_reasons.append("missing_state_gate_events")
        if self._telemetry.last_analysis_engine_event_ts_ms is None:
            stale_reasons.append("missing_analysis_engine_events")
        if not self._symbols:
            stale_reasons.append("no_symbols_observed")
        if self._ingest_failure_codes:
            stale_reasons.extend(sorted(self._ingest_failure_codes))

        staleness = TelemetryStaleness(
            is_stale=bool(stale_reasons), stale_reasons=tuple(stale_reasons)
        )
        ingest = TelemetryIngest(
            last_orchestrator_event_ts_ms=self._telemetry.last_orchestrator_event_ts_ms,
            last_state_gate_event_ts_ms=self._telemetry.last_state_gate_event_ts_ms,
            last_analysis_engine_event_ts_ms=self._telemetry.last_analysis_engine_event_ts_ms,
        )
        if self._default_time_window_ms > 0:
            latest_seen = max(
                (
                    ts
                    for ts in (
                        ingest.last_orchestrator_event_ts_ms,
                        ingest.last_state_gate_event_ts_ms,
                        ingest.last_analysis_engine_event_ts_ms,
                    )
                    if ts is not None
                ),
                default=None,
            )
            if latest_seen is not None:
                lag_ms = max(0, as_of_ts_ms - latest_seen)
                if lag_ms > self._default_time_window_ms:
                    stale_reasons.append("stale_over_window")
                    staleness = TelemetryStaleness(
                        is_stale=bool(stale_reasons),
                        stale_reasons=tuple(stale_reasons),
                    )
        return TelemetrySection(ingest=ingest, staleness=staleness)

    def _build_system_section(
        self, *, as_of_ts_ms: int, telemetry: TelemetrySection
    ) -> SystemSection:
        components = [
            SystemComponentStatus(
                component_id="analysis_engine",
                status=_component_status(
                    telemetry.ingest.last_analysis_engine_event_ts_ms, telemetry.staleness
                ),
                details=_component_details(telemetry.ingest.last_analysis_engine_event_ts_ms),
                last_update_ts_ms=telemetry.ingest.last_analysis_engine_event_ts_ms,
            ),
            SystemComponentStatus(
                component_id="dashboards",
                status=cast(
                    ComponentStatus,
                    "DEGRADED" if telemetry.staleness.is_stale else "OK",
                ),
                details=tuple(telemetry.staleness.stale_reasons)
                if telemetry.staleness.is_stale
                else (),
                last_update_ts_ms=as_of_ts_ms,
            ),
            SystemComponentStatus(
                component_id="orchestrator",
                status=_component_status(
                    telemetry.ingest.last_orchestrator_event_ts_ms, telemetry.staleness
                ),
                details=_component_details(telemetry.ingest.last_orchestrator_event_ts_ms),
                last_update_ts_ms=telemetry.ingest.last_orchestrator_event_ts_ms,
            ),
            SystemComponentStatus(
                component_id="state_gate",
                status=_component_status(
                    telemetry.ingest.last_state_gate_event_ts_ms, telemetry.staleness
                ),
                details=_component_details(telemetry.ingest.last_state_gate_event_ts_ms),
                last_update_ts_ms=telemetry.ingest.last_state_gate_event_ts_ms,
            ),
        ]

        if (
            not telemetry.ingest.last_orchestrator_event_ts_ms
            and not telemetry.ingest.last_state_gate_event_ts_ms
            and not telemetry.ingest.last_analysis_engine_event_ts_ms
        ):
            system_status = "UNKNOWN"
        elif telemetry.staleness.is_stale:
            system_status = "DEGRADED"
        else:
            system_status = "OK"
        return SystemSection(status=system_status, components=components)

    def _update_previous_hysteresis_state(
        self, symbol_state: _SymbolState, hysteresis_snapshot: HysteresisSnapshot | None
    ) -> None:
        symbol_state.previous_effective_confidence = (
            hysteresis_snapshot.effective_confidence if hysteresis_snapshot is not None else None
        )

    def _symbol_state(self, symbol: str) -> _SymbolState:
        if symbol not in self._symbols:
            self._symbols[symbol] = _SymbolState(symbol=symbol)
        return self._symbols[symbol]

    def _track_source(self, run_id: str, engine_timestamp_ms: int) -> None:
        if self._latest_source is None or engine_timestamp_ms > self._latest_source[0]:
            self._latest_source = (engine_timestamp_ms, run_id)
        elif engine_timestamp_ms == self._latest_source[0] and run_id > self._latest_source[1]:
            self._latest_source = (engine_timestamp_ms, run_id)

    def _validate_or_record(
        self,
        event_schema: str,
        event_schema_version: str,
        expected_schema: str,
        expected_schema_version: str,
        input_event_type: str,
    ) -> bool:
        try:
            _validate_schema(
                event_schema,
                event_schema_version,
                expected_schema,
                expected_schema_version,
            )
            return True
        except ValueError as exc:
            self._record_ingest_failure(
                input_schema=event_schema,
                input_event_type=input_event_type,
                error_kind="invalid_schema",
                error_detail=str(exc),
            )
            return False

    def _record_ingest_failure(
        self,
        *,
        input_schema: str,
        input_event_type: str | None,
        error_kind: str,
        error_detail: str,
    ) -> None:
        self._ingest_failure_codes.add("ingest_failure")
        self._observability.log_ingest_failure(
            input_schema=input_schema,
            input_event_type=input_event_type,
            error_kind=error_kind,
            error_detail=error_detail,
        )


def _component_status(timestamp_ms: int | None, staleness: TelemetryStaleness) -> ComponentStatus:
    if timestamp_ms is None:
        return "UNKNOWN"
    if staleness.is_stale:
        return "DEGRADED"
    return "OK"


def _component_details(timestamp_ms: int | None) -> Sequence[str]:
    if timestamp_ms is None:
        return (_NO_EVENTS_DETAIL,)
    return ()


def _regime_truth_from_output(regime_output: RegimeOutput) -> RegimeTruthSnapshot:
    regime_name = cast(str, _regime_value(regime_output.regime))
    return RegimeTruthSnapshot(
        regime_name=regime_name,
        confidence=regime_output.confidence,
        drivers=tuple(regime_output.drivers),
        invalidations=tuple(regime_output.invalidations),
        permissions=tuple(regime_output.permissions),
    )


def _regime_effective_from_payload(
    *, payload: GateEvaluatedPayload, engine_mode: str | None
) -> RegimeEffectiveSnapshot | None:
    if engine_mode == "truth" and payload.regime_output is not None:
        return _regime_effective_from_output(payload.regime_output, source="truth")
    if (
        engine_mode == "hysteresis"
        and payload.hysteresis_state is not None
        and payload.regime_output is not None
    ):
        return _regime_effective_from_output(
            payload.regime_output,
            source="hysteresis",
        )
    return None


def _regime_effective_from_output(
    regime_output: RegimeOutput, *, source: RegimeSource, effective_confidence: float | None = None
) -> RegimeEffectiveSnapshot:
    regime_name = cast(str, _regime_value(regime_output.regime))
    confidence = (
        effective_confidence if effective_confidence is not None else regime_output.confidence
    )
    return RegimeEffectiveSnapshot(
        regime_name=regime_name,
        confidence=confidence,
        drivers=tuple(regime_output.drivers),
        invalidations=tuple(regime_output.invalidations),
        permissions=tuple(regime_output.permissions),
        source=source,
    )


def _hysteresis_snapshot_from_state(
    state: HysteresisState, *, effective_confidence: float | None
) -> HysteresisSnapshot:
    transition_active = state.progress_current > 0
    flipped = any(code.startswith("COMMIT_SWITCH:") for code in state.reason_codes)
    confidence = effective_confidence if effective_confidence is not None else 0.0
    return HysteresisSnapshot(
        effective_confidence=confidence,
        transition=HysteresisTransition(
            stable_regime=_regime_value(state.anchor_regime),
            candidate_regime=_regime_value(state.candidate_regime),
            candidate_count=state.progress_current,
            transition_active=transition_active,
            flipped=flipped,
            reset_due_to_gap=False,
        ),
    )


def _belief_snapshot_from_state(
    state: HysteresisState,
    *,
    previous_belief: dict[str, float] | None,
) -> BeliefSnapshot | None:
    debug = state.debug
    if debug is None or not isinstance(debug, dict):
        return None
    belief_payload = debug.get("belief_by_regime")
    if not isinstance(belief_payload, dict):
        return None

    distribution: list[BeliefDistributionEntry] = []
    for regime in Regime:
        value = belief_payload.get(regime.value)
        if isinstance(value, (int, float)):
            distribution.append(
                BeliefDistributionEntry(regime_name=regime.value, mass=float(value))
            )
    if not distribution:
        return None

    anchor_regime = _anchor_from_distribution(distribution)
    trend = _belief_trend(
        anchor_regime=anchor_regime,
        distribution=distribution,
        previous_belief=previous_belief,
    )
    return BeliefSnapshot(
        anchor_regime=anchor_regime,
        distribution=tuple(distribution),
        trend=trend,
    )


def _anchor_from_distribution(distribution: Sequence[BeliefDistributionEntry]) -> str:
    masses = {entry.regime_name: entry.mass for entry in distribution}
    best_regime = Regime.CHOP_BALANCED.value
    best_mass = float("-inf")
    for regime in Regime:
        mass = masses.get(regime.value)
        if mass is None:
            continue
        if mass > best_mass:
            best_regime = regime.value
            best_mass = mass
    return best_regime


def _belief_trend(
    *,
    anchor_regime: str,
    distribution: Sequence[BeliefDistributionEntry],
    previous_belief: dict[str, float] | None,
) -> BeliefTrend:
    current_mass = next(
        (entry.mass for entry in distribution if entry.regime_name == anchor_regime),
        None,
    )
    if current_mass is None or previous_belief is None:
        return BeliefTrend(status=BELIEF_TREND_UNKNOWN, anchor_mass_delta=None)
    prior_mass = previous_belief.get(anchor_regime)
    if prior_mass is None:
        return BeliefTrend(status=BELIEF_TREND_UNKNOWN, anchor_mass_delta=None)

    delta = current_mass - prior_mass
    status: BeliefTrendStatus
    if delta > 0:
        status = BELIEF_TREND_RISING
    elif delta < 0:
        status = BELIEF_TREND_FALLING
    else:
        status = BELIEF_TREND_FLAT
    return BeliefTrend(status=status, anchor_mass_delta=delta)


def _regime_value(regime: Regime | None) -> str | None:
    if regime is None:
        return None
    if isinstance(regime, Regime):
        return regime.value
    return str(regime)


def _hysteresis_phase(transition: HysteresisTransition) -> HysteresisPhase:
    if transition.reset_due_to_gap:
        return PHASE_RESET
    if transition.flipped:
        return PHASE_FLIPPED
    if transition.transition_active:
        return PHASE_TRANSITIONING
    return PHASE_STABLE


def _validate_schema(
    event_schema: str,
    event_schema_version: str,
    expected_schema: str,
    expected_schema_version: str,
) -> None:
    if event_schema != expected_schema or event_schema_version != expected_schema_version:
        raise ValueError(
            f"unsupported schema: {event_schema} v{event_schema_version} "
            f"(expected {expected_schema} v{expected_schema_version})"
        )


def _builder_lag(*, as_of_ts_ms: int, telemetry: TelemetrySection) -> int | None:
    timestamps = [
        telemetry.ingest.last_orchestrator_event_ts_ms,
        telemetry.ingest.last_state_gate_event_ts_ms,
        telemetry.ingest.last_analysis_engine_event_ts_ms,
    ]
    latest_seen = max((ts for ts in timestamps if ts is not None), default=None)
    if latest_seen is None:
        return None
    return max(0, as_of_ts_ms - latest_seen)
