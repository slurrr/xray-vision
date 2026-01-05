# consumers/state_gate — spec

## Purpose & Scope

`consumers/state_gate` exists to transform orchestrator engine-run outputs into a **stable, replayable per-symbol state** and an explicit **gating decision** that downstream consumers must honor.

Role in decision flow:

- `orchestrator` publishes engine-run results (`RegimeOutput` and optionally `HysteresisDecision`) plus run metadata.
- `state_gate` interprets those results into a minimal **state machine** and emits **gate open/closed** decisions with reasons.
- Downstream consumers subscribe to `state_gate` outputs and must not act on engine outputs when the gate is closed.

`state_gate` explicitly does not:

- Generate market signals, pattern detections, alerts, or user-facing outputs.
- Compute any market features or reinterpret regime logic.
- Modify, override, or “correct” Regime Engine outputs.
- Implement consumer-specific behavior or routing.

---

## Inputs & Outputs (Contracts)

### Inputs: `OrchestratorEvent` v1

`state_gate` consumes `orchestrator_event` v1 as defined in `Planning/orchestrator/spec.md`.

Input event types relevant to `state_gate`:

- `EngineRunCompleted` (contains `payload.regime_output`)
- `EngineRunFailed`
- `HysteresisDecisionPublished` (contains `payload.hysteresis_decision`) when orchestrator is configured for hysteresis mode

Contract assumptions:

- Delivery is at-least-once (duplicates may occur).
- Per-symbol ordering by `engine_timestamp_ms` is preserved by the orchestrator output stream, but `state_gate` must be robust to duplicates and replay.

### Outputs: `StateGateEvent` v1

`state_gate` emits a single downstream stream of versioned, append-only events.

**Envelope (required)**

- `schema`: string, fixed value `state_gate_event`
- `schema_version`: string, fixed value `1`
- `event_type`: string, one of the types below
- `symbol`: string
- `engine_timestamp_ms`: int
- `run_id`: string (copied from input run)

**State payload (required)**

- `state_status`: string (see State Model)
- `gate_status`: string (`OPEN` | `CLOSED`)
- `reasons`: array of strings (stable reason codes; deterministic ordering)

**Authoritative engine payload (optional by type)**

- `payload.regime_output`: the `RegimeOutput` used for gating when available
- `payload.hysteresis_decision`: the `HysteresisDecision` used for gating when available
- `payload.reset_reason`: string (for `StateReset`)
- `payload.error_kind`: string (for `StateGateHalted`, non-sensitive, stable category)
- `payload.error_detail`: string (for `StateGateHalted`, brief, non-sensitive)

**Optional metadata (additive only)**

- `input_event_type`: string (`EngineRunCompleted` | `EngineRunFailed` | `HysteresisDecisionPublished`)
- `engine_mode`: string (`truth` | `hysteresis`)

**Event types**

- `GateEvaluated`
  - Emitted exactly once per input run (`run_id`) when `state_gate` has enough information to decide a gate status.
- `StateReset`
  - Emitted when the state machine resets due to a deterministic reset condition (see Gating Semantics).
- `StateGateHalted`
  - Emitted when `state_gate` enters a halted state due to internal failure that prevents safe gating.

Delivery semantics:

- At-least-once output; duplicates may occur.
- Downstream consumers must treat `(run_id, event_type)` as an idempotency key.

### Versioning & stability

- `state_gate_event` v1 changes are additive only (new optional fields or new `event_type` values).
- Breaking changes require `schema_version` increment and explicit downstream review.
- `state_gate` must remain compatible with additive evolution of `orchestrator_event` v1.

---

## State Model

### Definition of “state”

State in `state_gate` is a per-symbol, replayable summary of:

- the latest processed engine run (`run_id`, `engine_timestamp_ms`)
- whether downstream consumption is currently permitted (`gate_status`)
- why the gate is open/closed (`reasons`)

State is *derived only* from orchestrator outputs and `state_gate` configuration; it is not inferred from raw market data.

### Allowed states

For each symbol, `state_status` is exactly one of:

- `BOOTSTRAP`: no acceptable run has been observed since start/reset; gate is closed.
- `READY`: gate is open for downstream processing.
- `HOLD`: gate is closed due to a transient gating condition (not an internal failure).
- `DEGRADED`: gate is closed due to run failures.
- `HALTED`: `state_gate` cannot safely produce gating decisions due to its own internal failure; output may stop.

### Persistence & lifecycle expectations

`state_gate` must persist enough state to support deterministic restart and replay:

- An append-only `StateGateStateRecord` log (v1) capturing every state transition.
- A current-state snapshot store for fast restart (a materialized view derived from the log).

`StateGateStateRecord` must include at minimum:

- `symbol`, `engine_timestamp_ms`, `run_id`
- `state_status`, `gate_status`, `reasons`
- `engine_mode`
- `source_event_type`

The persisted state log is authoritative for replay; the snapshot store is a cache.

---

## Gating Semantics

### What gating means

Gating is a binary, explicit decision per run:

- `OPEN`: downstream consumers may process the associated authoritative engine payload.
- `CLOSED`: downstream consumers must not process the associated engine payload for any action-taking behavior.

`state_gate` does not decide *what action to take*; it only decides whether downstream may act.

### Input selection rules (deterministic)

For each `run_id`, `state_gate` must select the authoritative payload used for evaluation:

- If a `HysteresisDecisionPublished` event exists for `run_id`, use `payload.hysteresis_decision` and treat `engine_mode == hysteresis`.
- Else if an `EngineRunCompleted` event exists for `run_id`, use `payload.regime_output` and treat `engine_mode == truth`.
- Else if an `EngineRunFailed` event exists for `run_id`, evaluate as failure (no engine payload).

If multiple relevant events exist for the same `run_id` due to duplication, `state_gate` must treat them as identical and produce a single `GateEvaluated` outcome.

### Gate decision rules (v1)

The v1 gate decision is determined by the following rules in order:

1. **Run failure closes the gate**
   - If input is `EngineRunFailed`, emit `GateEvaluated` with `gate_status == CLOSED` and set `state_status == DEGRADED`.
2. **Configured denylist closes the gate**
   - If the selected `RegimeOutput.invalidations` contains any configured `denylisted_invalidations` entry (exact string match), gate is `CLOSED` and `state_status == HOLD`.
3. **Configured transition hold (hysteresis mode only)**
   - If in hysteresis mode and `hysteresis_decision.transition.transition_active == true` and config `block_during_transition == true`, gate is `CLOSED` and `state_status == HOLD`.
4. **Otherwise open**
   - Gate is `OPEN` and `state_status == READY`.

`reasons` is a deterministic list of stable reason codes derived from the first matching rule and any additional configured matches (sorted lexicographically).

Reason code vocabulary (v1):

- `run_failed`
- `denylisted_invalidation:<invalidation_key>`
- `transition_active` (hysteresis mode only)
- `reset_timestamp_gap` (for `StateReset`)
- `reset_engine_gap` (for hysteresis `reset_due_to_gap`, for `StateReset`)
- `internal_failure` (for `StateGateHalted`)

No other gating rules exist in v1.

### Promotion, demotion, reset

**Promotion**

- `BOOTSTRAP → READY` occurs on the first `GateEvaluated` with `gate_status == OPEN`.

**Demotion**

- `READY → HOLD` occurs when a later run evaluates to `gate_status == CLOSED` due to a non-failure gating rule.
- `READY/HOLD/BOOTSTRAP → DEGRADED` occurs when a run evaluates as failed (`EngineRunFailed`).

**Reset**

`state_gate` must reset state to `BOOTSTRAP` (and emit `StateReset`) when either condition occurs:

- A configured engine timestamp gap is detected:
  - if `engine_timestamp_ms - last_engine_timestamp_ms > max_gap_ms` for that symbol, reset before evaluating the current run.
- In hysteresis mode, if `hysteresis_decision.transition.reset_due_to_gap == true`, reset before evaluating the current run.

Reset is mechanical; it does not require interpreting market meaning.

Reset event requirements:

- `StateReset.payload.reset_reason` must be:
  - `reset_timestamp_gap` for the configured timestamp gap condition
  - `reset_engine_gap` for `reset_due_to_gap == true`
- After emitting `StateReset`, `state_gate` must continue processing the current run and emit `GateEvaluated` for the same `run_id`.

### Determinism requirements

- For a fixed input stream of `orchestrator_event` items and fixed configuration, `state_gate` must emit the same `state_gate_event` sequence (modulo explicitly non-authoritative operational timestamps, if any are included).
- No wall-clock decisions are allowed in gating; only input fields and configuration.

---

## Dependency Boundaries

### Allowed dependencies

- `orchestrator_event` v1 contract (input schema only).
- Regime Engine output contracts as immutable payloads:
  - `RegimeOutput`
  - `HysteresisDecision`
- Local persistence primitives for the state transition log and snapshot cache.

### Forbidden coupling

- No dependency on downstream consumer code or schemas.
- No consumer-aware branching, filtering, or prioritization.
- No imports from `market_data` or any raw vendor payload interpretation.
- No regime logic: treat engine outputs as authoritative facts, not suggestions.

---

## Invariants & Guarantees

- **Idempotency**: processing the same input `(run_id, input_event_type)` multiple times must not change the final persisted state or produce multiple `GateEvaluated` events.
- **Per-symbol ordering safety**: out-of-order inputs for a symbol must not corrupt state; `state_gate` must either ignore older runs (replay) or process strictly increasing `engine_timestamp_ms` only.
- **Replay safety**: `StateGateEvent` outputs must be derivable from persisted input + configuration without hidden state.
- **Failure safety**: if persistence is unavailable or state cannot be updated safely, `state_gate` must transition to `HALTED` and must not emit `OPEN` gates.

---

## Operational Behavior

### Lifecycle

- **Start**: load configuration; load state snapshot; begin consuming `orchestrator_event` stream.
- **Run**: for each run, select authoritative payload, apply reset rules, evaluate gate, persist state transition, emit `StateGateEvent`.
- **Shutdown**: stop consumption, flush/persist any in-flight state transition, and close resources.

### Observability (contractual)

**Structured logs (minimum fields)**

- `symbol`, `run_id`, `engine_timestamp_ms`, `input_event_type`
- `state_status`, `gate_status`, `reasons`
- For resets: `reset_reason`
- For internal failures: `error_kind`, `error_detail` (non-sensitive)

**Metrics (minimum set)**

- Gate decisions: count by `gate_status` and `reason`
- State transitions: count by `state_status`
- Resets: count by reset reason
- Processing lag: distribution of (current input `engine_timestamp_ms` vs last processed) per symbol
- Internal failure counts and halted-state indicator

### Failure isolation expectations

`state_gate` must not require any behavior from downstream consumers to function. It is an observer+gating publisher only.

If downstream output publishing is blocked beyond configured limits, `state_gate` must stop producing new gating decisions (transition to `HALTED`) rather than dropping or continuing unsafely.

---

## Non-Goals

- No pattern detection, scanning, classification beyond the Regime Engine outputs.
- No alerting, notifications, or user-facing dashboards.
- No trade execution, strategy evaluation, or signal generation.
- No upstream feedback into market data or orchestrator behavior.
