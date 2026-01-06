from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

DVM_SCHEMA = "dashboard_view_model"
DVM_SCHEMA_VERSION = "1"

SystemStatus = Literal["OK", "DEGRADED", "UNKNOWN"]
ComponentId = Literal["orchestrator", "state_gate", "analysis_engine", "dashboards"]
ComponentStatus = Literal["OK", "DEGRADED", "UNKNOWN"]

GateStatus = Literal["OPEN", "CLOSED", "UNKNOWN"]

AnalysisStatus = Literal["EMPTY", "PARTIAL", "PRESENT"]

RegimeSource = Literal["truth", "hysteresis"]

CONFIDENCE_TREND_RISING = "RISING"
CONFIDENCE_TREND_FALLING = "FALLING"
CONFIDENCE_TREND_FLAT = "FLAT"
ConfidenceTrend = Literal["RISING", "FALLING", "FLAT"]

PHASE_STABLE = "STABLE"
PHASE_TRANSITIONING = "TRANSITIONING"
PHASE_FLIPPED = "FLIPPED"
PHASE_RESET = "RESET"
HysteresisPhase = Literal["STABLE", "TRANSITIONING", "FLIPPED", "RESET"]

DVM_VERSIONING_POLICY = (
    "DVM schema version 1 is additive-only. New optional fields or sections may be added; "
    "breaking changes require a dvm_schema_version bump and renderer review."
)


@dataclass(frozen=True)
class SystemComponentStatus:
    component_id: ComponentId
    status: ComponentStatus
    details: Sequence[str]
    last_update_ts_ms: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", tuple(self.details))


@dataclass(frozen=True)
class SystemSection:
    status: SystemStatus
    components: Sequence[SystemComponentStatus]

    def __post_init__(self) -> None:
        sorted_components = tuple(
            sorted(self.components, key=lambda component: component.component_id)
        )
        object.__setattr__(self, "components", sorted_components)


@dataclass(frozen=True)
class GateSnapshot:
    status: GateStatus
    reasons: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(self.reasons))


@dataclass(frozen=True)
class RegimeTruthSnapshot:
    regime_name: str
    confidence: float
    drivers: Sequence[str]
    invalidations: Sequence[str]
    permissions: Sequence[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "drivers", tuple(self.drivers))
        object.__setattr__(self, "invalidations", tuple(self.invalidations))
        object.__setattr__(self, "permissions", tuple(self.permissions))


@dataclass(frozen=True)
class HysteresisTransition:
    stable_regime: str | None
    candidate_regime: str | None
    candidate_count: int
    transition_active: bool
    flipped: bool
    reset_due_to_gap: bool


@dataclass(frozen=True)
class HysteresisProgress:
    current: int
    required: int


@dataclass(frozen=True)
class HysteresisSummary:
    phase: HysteresisPhase
    anchor_regime: str | None
    candidate_regime: str | None
    progress: HysteresisProgress
    confidence_trend: ConfidenceTrend
    notes: Sequence[str] = ()

    def __post_init__(self) -> None:
        ordered_notes = tuple(sorted(self.notes))
        object.__setattr__(self, "notes", ordered_notes)


@dataclass(frozen=True)
class HysteresisSnapshot:
    effective_confidence: float
    transition: HysteresisTransition
    summary: HysteresisSummary | None = None


@dataclass(frozen=True)
class RegimeEffectiveSnapshot:
    regime_name: str
    confidence: float
    drivers: Sequence[str]
    invalidations: Sequence[str]
    permissions: Sequence[str]
    source: RegimeSource

    def __post_init__(self) -> None:
        object.__setattr__(self, "drivers", tuple(self.drivers))
        object.__setattr__(self, "invalidations", tuple(self.invalidations))
        object.__setattr__(self, "permissions", tuple(self.permissions))


@dataclass(frozen=True)
class AnalysisArtifactSummary:
    artifact_kind: str
    module_id: str
    artifact_name: str
    artifact_schema: str
    artifact_schema_version: str
    summary: str


@dataclass(frozen=True)
class AnalysisSection:
    status: AnalysisStatus
    highlights: Sequence[str]
    artifacts: Sequence[AnalysisArtifactSummary] = ()

    def __post_init__(self) -> None:
        ordered_highlights = tuple(sorted(self.highlights))
        ordered_artifacts = tuple(
            sorted(
                self.artifacts,
                key=lambda artifact: (
                    artifact.artifact_kind,
                    artifact.module_id,
                    artifact.artifact_name,
                ),
            )
        )
        object.__setattr__(self, "highlights", ordered_highlights)
        object.__setattr__(self, "artifacts", ordered_artifacts)


@dataclass(frozen=True)
class MetricsSnapshot:
    atr_pct: float | None = None
    atr_rank: float | None = None
    range_24h_pct: float | None = None
    range_session_pct: float | None = None
    volume_24h: float | None = None
    volume_rank: float | None = None
    relative_volume: float | None = None
    relative_strength: float | None = None


@dataclass(frozen=True)
class SymbolSnapshot:
    symbol: str
    last_run_id: str | None
    last_engine_timestamp_ms: int | None
    gate: GateSnapshot
    regime_truth: RegimeTruthSnapshot | None = None
    hysteresis: HysteresisSnapshot | None = None
    regime_effective: RegimeEffectiveSnapshot | None = None
    analysis: AnalysisSection | None = None
    metrics: MetricsSnapshot | None = None


@dataclass(frozen=True)
class TelemetryIngest:
    last_orchestrator_event_ts_ms: int | None
    last_state_gate_event_ts_ms: int | None
    last_analysis_engine_event_ts_ms: int | None


@dataclass(frozen=True)
class TelemetryStaleness:
    is_stale: bool
    stale_reasons: Sequence[str]

    def __post_init__(self) -> None:
        ordered_reasons = tuple(sorted(self.stale_reasons))
        object.__setattr__(self, "stale_reasons", ordered_reasons)


@dataclass(frozen=True)
class TelemetrySection:
    ingest: TelemetryIngest
    staleness: TelemetryStaleness


@dataclass(frozen=True)
class DashboardViewModel:
    dvm_schema: str
    dvm_schema_version: str
    as_of_ts_ms: int
    source_run_id: str | None
    source_engine_timestamp_ms: int | None
    system: SystemSection
    symbols: Sequence[SymbolSnapshot]
    telemetry: TelemetrySection

    def __post_init__(self) -> None:
        if self.dvm_schema != DVM_SCHEMA:
            raise ValueError(f"Invalid dvm_schema: {self.dvm_schema}")
        if self.dvm_schema_version != DVM_SCHEMA_VERSION:
            raise ValueError(f"Invalid dvm_schema_version: {self.dvm_schema_version}")

        ordered_symbols = tuple(sorted(self.symbols, key=lambda symbol: symbol.symbol))
        object.__setattr__(self, "symbols", ordered_symbols)
