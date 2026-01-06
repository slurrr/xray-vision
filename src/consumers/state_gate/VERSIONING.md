# state_gate versioning rules

## state_gate_event v1 immutability

- `schema` is fixed to `state_gate_event`.
- `schema_version` is fixed to `1`.
- Envelope fields `event_type`, `symbol`, `engine_timestamp_ms`, and `run_id` are required.
- State payload fields `state_status`, `gate_status`, and `reasons` are required.
- `payload` attachment keys follow the event type contracts:
  - `GateEvaluated`: `regime_output` and/or `hysteresis_decision`
  - `StateReset`: `reset_reason`
  - `StateGateHalted`: `error_kind`, `error_detail`
- Optional metadata fields (`input_event_type`, `engine_mode`) are additive only.

## StateGateStateRecord v1 immutability

- Append-only transition log with required fields:
  - `symbol`, `engine_timestamp_ms`, `run_id`
  - `state_status`, `gate_status`, `reasons`
  - `engine_mode`, `source_event_type`
- Optional attachments mirror the event payloads (`regime_output`, `hysteresis_decision`, `reset_reason`, `error_kind`, `error_detail`).

## Snapshot cache contract

- Materialized view derived from the append-only log.
- Contains the current per-symbol state (`state_status`, `gate_status`, `reasons`) and the latest `run_id`/`engine_timestamp_ms`.
- Additive fields are allowed; removals are breaking.

## Idempotency contracts

- Inputs are deduped by `(run_id, input_event_type)`.
- Outputs are deduped by `(run_id, event_type)`.
- Idempotency keys are stable and must not change without a version bump.

## Backward-compatible changes (additive only)

- Add optional envelope/metadata fields.
- Add optional payload fields for existing event types.
- Add new `event_type` values with explicit spec updates.
- Add optional configuration keys (must not change semantics of existing keys).

## Breaking changes

- Any removal or reinterpretation of existing fields is breaking.
- Breaking changes require a `schema_version` increment and downstream review before merge.
