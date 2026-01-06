from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

from market_data.contracts import RawMarketEvent
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.hysteresis.decision import HysteresisDecision

SCHEMA_NAME = "orchestrator_event"
SCHEMA_VERSION = "1"

ENGINE_MODE_TRUTH = "truth"
ENGINE_MODE_HYSTERESIS = "hysteresis"
EngineMode = Literal["truth", "hysteresis"]

CutKind = Literal["timer", "boundary"]

EngineRunStatus = Literal["started", "completed", "failed"]

EventType = Literal[
    "EngineRunStarted",
    "EngineRunCompleted",
    "EngineRunFailed",
    "HysteresisDecisionPublished",
]

EVENT_TYPES: Sequence[str] = (
    "EngineRunStarted",
    "EngineRunCompleted",
    "EngineRunFailed",
    "HysteresisDecisionPublished",
)


@dataclass(frozen=True)
class EngineRunFailedPayload:
    error_kind: str
    error_detail: str


@dataclass(frozen=True)
class EngineRunCompletedPayload:
    regime_output: RegimeOutput


@dataclass(frozen=True)
class HysteresisDecisionPayload:
    hysteresis_decision: HysteresisDecision


@dataclass(frozen=True)
class OrchestratorEvent:
    schema: str
    schema_version: str
    event_type: EventType
    run_id: str
    symbol: str
    engine_timestamp_ms: int
    cut_start_ingest_seq: int
    cut_end_ingest_seq: int
    cut_kind: CutKind
    engine_mode: EngineMode | None = None
    attempt: int | None = None
    published_ts_ms: int | None = None
    counts_by_event_type: Mapping[str, int] | None = None
    payload: object | None = None


@dataclass(frozen=True)
class RawInputBufferRecord:
    ingest_seq: int
    ingest_ts_ms: int
    event: RawMarketEvent


@dataclass(frozen=True)
class EngineRunRecord:
    run_id: str
    symbol: str
    engine_timestamp_ms: int
    engine_mode: EngineMode
    cut_kind: CutKind
    cut_start_ingest_seq: int
    cut_end_ingest_seq: int
    planned_ts_ms: int
    started_ts_ms: int | None
    completed_ts_ms: int | None
    status: EngineRunStatus
    attempts: int
    error_kind: str | None = None
    error_detail: str | None = None
