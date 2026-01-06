# state_gate contract freeze

## state_gate_event v1 schema

Envelope (required):
- schema: state_gate_event
- schema_version: 1
- event_type: GateEvaluated | StateReset | StateGateHalted
- symbol: string
- engine_timestamp_ms: int
- run_id: string
- state_status: BOOTSTRAP | READY | HOLD | DEGRADED | HALTED
- gate_status: OPEN | CLOSED
- reasons: array of stable reason codes

Payload (per event type):
- GateEvaluated: payload.regime_output (RegimeOutput) or payload.hysteresis_decision (HysteresisDecision) when present
- StateReset: payload.reset_reason (reset_timestamp_gap | reset_engine_gap)
- StateGateHalted: payload.error_kind, payload.error_detail (non-sensitive categories)

Optional metadata (additive only):
- input_event_type: EngineRunCompleted | EngineRunFailed | HysteresisDecisionPublished
- engine_mode: truth | hysteresis

## Supported v1 event_type list

- GateEvaluated
- StateReset
- StateGateHalted

## Minimal config (single symbol)

- max_gap_ms
- denylisted_invalidations (list of strings)
- block_during_transition (bool)
- input_limits: OperationLimits (max_pending, optional max_block_ms, optional max_failures)
- persistence_limits: OperationLimits (max_pending, optional max_block_ms, optional max_failures)
- publish_limits: OperationLimits (max_pending, optional max_block_ms, optional max_failures)

## Non-goals compliance

- No feature, indicator, regime, pattern, or signal computation.
- No downstream consumer coupling or feedback.
- No wall-clock gating or upstream inference.
- Additive-only evolution; schema_version bump required for breaking changes.
