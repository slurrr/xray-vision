from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from orchestrator.contracts import EngineMode
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.hysteresis.decision import HysteresisDecision

SCHEMA_NAME = "state_gate_event"
SCHEMA_VERSION = "1"

GATE_STATUS_OPEN = "OPEN"
GATE_STATUS_CLOSED = "CLOSED"
GateStatus = Literal["OPEN", "CLOSED"]

STATE_STATUS_BOOTSTRAP = "BOOTSTRAP"
STATE_STATUS_READY = "READY"
STATE_STATUS_HOLD = "HOLD"
STATE_STATUS_DEGRADED = "DEGRADED"
STATE_STATUS_HALTED = "HALTED"
StateStatus = Literal["BOOTSTRAP", "READY", "HOLD", "DEGRADED", "HALTED"]

EVENT_TYPE_GATE_EVALUATED = "GateEvaluated"
EVENT_TYPE_STATE_RESET = "StateReset"
EVENT_TYPE_STATE_GATE_HALTED = "StateGateHalted"
EventType = Literal["GateEvaluated", "StateReset", "StateGateHalted"]
EVENT_TYPES: Sequence[str] = (
    EVENT_TYPE_GATE_EVALUATED,
    EVENT_TYPE_STATE_RESET,
    EVENT_TYPE_STATE_GATE_HALTED,
)

INPUT_EVENT_TYPES: Sequence[str] = (
    "EngineRunCompleted",
    "EngineRunFailed",
    "HysteresisDecisionPublished",
)
InputEventType = Literal["EngineRunCompleted", "EngineRunFailed", "HysteresisDecisionPublished"]

RESET_REASON_TIMESTAMP_GAP = "reset_timestamp_gap"
RESET_REASON_ENGINE_GAP = "reset_engine_gap"
ResetReason = Literal["reset_timestamp_gap", "reset_engine_gap"]

REASON_CODE_RUN_FAILED = "run_failed"
REASON_PREFIX_DENYLISTED_INVALIDATION = "denylisted_invalidation:"
REASON_CODE_TRANSITION_ACTIVE = "transition_active"
REASON_CODE_INTERNAL_FAILURE = "internal_failure"
REASON_CODES: Sequence[str] = (
    REASON_CODE_RUN_FAILED,
    REASON_PREFIX_DENYLISTED_INVALIDATION,
    REASON_CODE_TRANSITION_ACTIVE,
    RESET_REASON_TIMESTAMP_GAP,
    RESET_REASON_ENGINE_GAP,
    REASON_CODE_INTERNAL_FAILURE,
)


@dataclass(frozen=True)
class GateEvaluatedPayload:
    regime_output: RegimeOutput | None = None
    hysteresis_decision: HysteresisDecision | None = None


@dataclass(frozen=True)
class StateResetPayload:
    reset_reason: ResetReason


@dataclass(frozen=True)
class StateGateHaltedPayload:
    error_kind: str
    error_detail: str


StateGatePayload = GateEvaluatedPayload | StateResetPayload | StateGateHaltedPayload


@dataclass(frozen=True)
class StateGateEvent:
    schema: str
    schema_version: str
    event_type: EventType
    symbol: str
    engine_timestamp_ms: int
    run_id: str
    state_status: StateStatus
    gate_status: GateStatus
    reasons: Sequence[str]
    payload: StateGatePayload | None = None
    input_event_type: InputEventType | None = None
    engine_mode: EngineMode | None = None


@dataclass(frozen=True)
class StateGateStateRecord:
    symbol: str
    engine_timestamp_ms: int
    run_id: str
    state_status: StateStatus
    gate_status: GateStatus
    reasons: Sequence[str]
    engine_mode: EngineMode | None
    source_event_type: InputEventType | None
    regime_output: RegimeOutput | None = None
    hysteresis_decision: HysteresisDecision | None = None
    reset_reason: ResetReason | None = None
    error_kind: str | None = None
    error_detail: str | None = None


@dataclass(frozen=True)
class StateGateSnapshot:
    symbol: str
    last_run_id: str | None
    last_engine_timestamp_ms: int | None
    state_status: StateStatus
    gate_status: GateStatus
    reasons: Sequence[str]
    engine_mode: EngineMode | None
    source_event_type: InputEventType | None


INPUT_IDEMPOTENCY_FIELDS: Sequence[str] = ("run_id", "input_event_type")
OUTPUT_IDEMPOTENCY_FIELDS: Sequence[str] = ("run_id", "event_type")
OUTPUT_EVENT_TYPES: Sequence[str] = EVENT_TYPES


def input_idempotency_key(run_id: str, event_type: InputEventType) -> str:
    return f"{run_id}:{event_type}"


def output_idempotency_key(run_id: str, event_type: EventType) -> str:
    return f"{run_id}:{event_type}"
