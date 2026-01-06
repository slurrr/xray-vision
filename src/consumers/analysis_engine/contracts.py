from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.hysteresis.decision import HysteresisDecision

SCHEMA_NAME = "analysis_engine_event"
SCHEMA_VERSION = "1"

ANALYSIS_EVENT_TYPES: Sequence[str] = (
    "AnalysisRunStarted",
    "AnalysisRunSkipped",
    "ArtifactEmitted",
    "ModuleFailed",
    "AnalysisRunCompleted",
    "AnalysisRunFailed",
)
AnalysisEventType = Literal[
    "AnalysisRunStarted",
    "AnalysisRunSkipped",
    "ArtifactEmitted",
    "ModuleFailed",
    "AnalysisRunCompleted",
    "AnalysisRunFailed",
]

ARTIFACT_KINDS: Sequence[str] = ("signal", "detection", "evaluation", "output")
ArtifactKind = Literal["signal", "detection", "evaluation", "output"]

MODULE_KINDS: Sequence[str] = ("signal", "detector", "rule", "output")
ModuleKind = Literal["signal", "detector", "rule", "output"]

RUN_STATUSES: Sequence[str] = ("SUCCESS", "PARTIAL", "FAILED")
RunStatus = Literal["SUCCESS", "PARTIAL", "FAILED"]


@dataclass(frozen=True)
class ArtifactSchema:
    artifact_name: str
    artifact_schema: str
    artifact_schema_version: str


@dataclass(frozen=True)
class ModuleDependency:
    module_id: str
    artifact_name: str


@dataclass(frozen=True)
class ModuleDefinition:
    module_id: str
    module_kind: ModuleKind
    module_version: str
    dependencies: Sequence[ModuleDependency]
    artifact_schemas: Sequence[ArtifactSchema]
    config_schema_id: str
    config_schema_version: str
    enabled_by_default: bool = False
    state_schema_id: str | None = None
    state_schema_version: str | None = None


@dataclass(frozen=True)
class ArtifactEmittedPayload:
    artifact_kind: ArtifactKind
    module_id: str
    artifact_name: str
    artifact_schema: str
    artifact_schema_version: str
    payload: object


@dataclass(frozen=True)
class ModuleFailedPayload:
    module_id: str
    module_kind: ModuleKind
    error_kind: str
    error_detail: str


@dataclass(frozen=True)
class AnalysisRunStatusPayload:
    status: RunStatus
    module_failures: Sequence[str]


AnalysisEnginePayload = ArtifactEmittedPayload | ModuleFailedPayload | AnalysisRunStatusPayload


@dataclass(frozen=True)
class AnalysisEngineEvent:
    schema: str
    schema_version: str
    event_type: AnalysisEventType
    symbol: str
    run_id: str
    engine_timestamp_ms: int
    payload: AnalysisEnginePayload | None = None
    engine_mode: str | None = None
    source_gate_reasons: Sequence[str] | None = None


@dataclass(frozen=True)
class RunContext:
    symbol: str
    run_id: str
    engine_timestamp_ms: int
    engine_mode: str | None
    gate_status: str
    gate_reasons: Sequence[str]
    regime_output: RegimeOutput | None
    hysteresis_decision: HysteresisDecision | None


@dataclass(frozen=True)
class AnalysisModuleStateRecord:
    symbol: str
    module_id: str
    run_id: str
    engine_timestamp_ms: int
    state_schema_id: str
    state_schema_version: str
    state_payload: object


IdempotencyKey = str


def build_idempotency_key(run_id: str) -> IdempotencyKey:
    return run_id
