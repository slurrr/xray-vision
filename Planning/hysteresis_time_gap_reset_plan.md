## Plan — Hysteresis Time-Gap Reset (12 minutes or 4 missed updates)

### Goal
Introduce a deterministic “gap reset” for hysteresis memory so that, after a sufficiently large `engine_timestamp_ms` discontinuity, the next hysteresis update behaves as if there were no prior `HysteresisState` for that symbol.

Target reset trigger: **12 minutes** or **4 missed updates**.

### Scope / Placement (authoritative for this plan)
- **Reset decision + reset application** lives in the Regime Engine hysteresis layer so it is applied consistently for all callers:
  - `src/regime_engine/hysteresis/__init__.py:process_state`
  - (or, if kept purely rule-level, `src/regime_engine/hysteresis/rules.py:advance_hysteresis` with consistent handling for candidate selection/logging in `process_state`)
- **Wiring of any interval parameter** (if needed to define “missed updates”) lives in runtime wiring:
  - `src/runtime/wiring.py:build_runtime` (this already has access to `orchestrator_config.scheduler.boundary_interval_ms`).
- **Do not implement reset logic inside orchestrator** (`src/orchestrator/**`), to avoid introducing window/gap semantics into the orchestrator layer per `src/orchestrator/AGENTS.md`.

### Existing Facts (from current implementation)
- The prior hysteresis memory is retrieved in `src/regime_engine/hysteresis/__init__.py:process_state` via `store.state_for(regime_state.symbol)`.
- The timestamps needed for a gap check already exist:
  - current: `regime_state.engine_timestamp_ms` (`src/regime_engine/state/state.py:RegimeState.engine_timestamp_ms`)
  - prior: `prev_state.engine_timestamp_ms` (`src/regime_engine/hysteresis/state.py:HysteresisState.engine_timestamp_ms`)
- Hysteresis persistence stores `engine_timestamp_ms` per symbol and restores the latest record per symbol:
  - write: `src/regime_engine/hysteresis/persistence.py:append_record`
  - restore: `src/regime_engine/hysteresis/persistence.py:restore_store` → `_load_records` (latest-by-`engine_timestamp_ms`)
- Orchestrator enforces monotonicity (time-travel protection) before running hysteresis:
  - `src/orchestrator/engine_runner.py:EngineRunner._guard_monotonic`

### Required Semantics
When the reset trigger condition is met for `(symbol, current_engine_timestamp_ms, prev_engine_timestamp_ms)`:
1. Treat `prev_state` as absent for the purposes of hysteresis progression for **that one run**.
2. Ensure the in-memory store is updated to the newly computed state for that run (the existing `store.update(...)` path remains authoritative).
3. Persistence remains append-only and unchanged in format: the next computed state will be persisted via the existing append path.

### Reset Trigger Definition (needs one explicit choice)
The plan supports both triggers; one ambiguity must be resolved before coding:

1) **Absolute time-gap trigger (unambiguous)**
- `gap_ms = current_engine_timestamp_ms - prev_engine_timestamp_ms`
- reset iff `gap_ms >= 720_000` (12 minutes)

2) **“4 missed updates” trigger (requires defining an interval)**
- Define `expected_interval_ms` deterministically.
  - Option A (preferred if boundary mode): take `expected_interval_ms` from orchestrator scheduler config:
    - `orchestrator_config.scheduler.boundary_interval_ms` in `src/runtime/wiring.py:build_runtime`
  - Option B (fallback): if no boundary interval is available, omit this trigger (time-gap trigger remains).
- Define “missed updates” in terms of elapsed intervals:
  - `intervals_elapsed = gap_ms // expected_interval_ms`
  - reset iff `intervals_elapsed >= 4`

Note: If the system’s cadence is effectively fixed to 3 minutes (as suggested by `src/regime_engine/contracts/snapshots.py:RegimeInputSnapshot.timestamp  # ms, aligned to 3m close`), then the absolute gap trigger alone may already satisfy the intent; treat this as a requirement clarification point, not an implementation assumption.

### Minimal Implementation Steps (no behavioral redesign beyond reset)
1. **Add configuration surface for the policy (engine-local)**
   - Extend `src/regime_engine/hysteresis/state.py:HysteresisConfig` with optional fields:
     - `reset_max_gap_ms: int | None` (default `None` to preserve current behavior until enabled)
     - `reset_max_intervals: int | None` (default `None`)
     - `reset_interval_ms: int | None` (default `None`; required if `reset_max_intervals` is set)
   - No existing fields’ meaning changes.

2. **Wire interval (runtime-only, if using missed-updates trigger)**
   - In `src/runtime/wiring.py:build_runtime`, construct and pass `hysteresis_config=HysteresisConfig(...)` into `OrchestratorRuntime(...)`.
   - If `orchestrator_config.scheduler.mode == "boundary"` and `boundary_interval_ms` is set, map it to `reset_interval_ms`.
   - Enable the policy by setting:
     - `reset_max_gap_ms = 720_000`
     - `reset_max_intervals = 4`
   - If the scheduler is not boundary-based or interval is unset, leave `reset_interval_ms` unset and rely only on `reset_max_gap_ms`.

3. **Apply reset deterministically inside hysteresis processing**
   - In `src/regime_engine/hysteresis/__init__.py:process_state`:
     - Retrieve `prev_state` as today.
     - Compute `gap_ms` if `prev_state` is present.
     - If the reset condition is met, set an `effective_prev_state = None` for:
       - candidate selection anchor (`anchor_for_candidate`)
       - `advance_hysteresis(...)`
       - prior-anchor comparison for “committed” logging
     - Proceed with existing `store.update(...)` and return the computed state.
   - The reset must not consult wall-clock time, randomness, or non-deterministic ordering.

4. **Observability (additive, local-only)**
   - Emit a dedicated hysteresis reset log event only if an existing observability surface supports adding a new event without changing existing event shapes.
   - Candidate location:
     - `src/regime_engine/observability.py` (via `get_observability()`)
   - Payload must include: `symbol`, `engine_timestamp_ms`, `prev_engine_timestamp_ms`, `gap_ms`, and which trigger fired.
   - If adding a new log event would violate an existing log contract, omit and rely on existing transition/decision logs (but this makes resets harder to diagnose).

### Invariants to Preserve (explicit checks)
- **Monotonicity guard unchanged**: `src/orchestrator/engine_runner.py:EngineRunner._guard_monotonic` remains authoritative; resets must not bypass it.
- **Persistence schema unchanged**: no changes to `src/regime_engine/hysteresis/persistence.py` record format or restore semantics.
- **Determinism**: reset decision uses only `(prev_state.engine_timestamp_ms, current engine_timestamp_ms, config values)`; no wall-clock reads.
- **Single hysteresis invocation per run**: reset is applied within the existing `run_with_hysteresis` call path; do not introduce extra runs.

### Validation Plan (deterministic, layer-local)
- Unit tests (engine-local):
  - Add tests around `process_state` to prove:
    - below-threshold gap → behavior matches current baseline for same inputs
    - above-threshold gap → `prev_state` is ignored and the new state matches the “fresh start” result
  - Ensure tests do not assert `last_commit_timestamp_ms` (it is wall-clock sourced in `src/regime_engine/hysteresis/rules.py:advance_hysteresis`).
- Replay harness validation (system-level, optional but aligned with existing tooling):
  - Use `tools/evidence_matrix_replay/` replay with two runs separated by an artificial timestamp gap in the orchestrator event stream to verify:
    - reset triggers deterministically
    - persistence append count remains exactly one per run (no extra writes)

### Open Ambiguities (must be resolved before implementation)
1. “4 missed updates” definition: does “missed” mean `gap_ms >= 4 * interval_ms` (intervals elapsed), or “4 scheduled updates not observed” (which would shift the threshold by one interval)?
2. Whether losing `last_commit_timestamp_ms` continuity on reset is acceptable (reset-as-fresh-start implies it is).

