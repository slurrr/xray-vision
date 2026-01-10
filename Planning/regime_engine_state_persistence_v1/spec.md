# regime_engine_state_persistence_v1 — spec

## Purpose & Scope

This spec defines the **minimal persistent state** required so Regime Engine hysteresis works correctly across process restarts, without changing any engine behavior.

This work is strictly about **persistence and restore mechanics** for hysteresis state. It does not introduce new regime semantics or belief math.

Locked context:

- Regime Engine belief + hysteresis logic is complete and correct.
- Snapshots and embedded evidence flow end-to-end.
- Hysteresis currently operates only in-memory (`HysteresisStore.states`).

## Hard Constraints (Binding)

- No new belief math.
- No changes to hysteresis rules or thresholds.
- No composer or `market_data` changes.
- Persistence is transparent to callers: existing engine invocation remains:
  - `regime_engine.engine.run(snapshot) -> RegimeOutput`
  - `regime_engine.engine.run_with_hysteresis(snapshot, state, config) -> HysteresisState`
- No new public APIs unless strictly required.
- Persist only what hysteresis cannot deterministically recompute.

## What Must Persist (Minimal, Engine-Owned)

Hysteresis behavior depends on cross-run memory that is not recoverable from a single snapshot:

From `regime_engine.hysteresis.state.HysteresisState`, only these fields are required to continue hysteresis correctly:

- `symbol` (partition key)
- `anchor_regime` (stable selection carried across runs)
- `candidate_regime` (in-progress transition target, if any)
- `progress_current` (window progress counter)
- `last_commit_timestamp_ms` (observability/diagnostics; retain for continuity; see semantics below)
- `engine_timestamp_ms` (last processed timestamp for restore ordering and sanity checks)

Everything else is either:

- derived deterministically from config (`progress_required` == `HysteresisConfig.window_updates`), or
- debug/telemetry (`reason_codes`, `debug`) and not required to resume hysteresis correctly.

## Explicit Non-Goals (Not Persisted)

This v1 persistence plan does **not** persist:

- `RegimeState` belief distributions (`belief_by_regime`) or any “prior belief”
- any evidence/opinion inputs or feature values
- any Regime Engine internal pipeline state
- any cross-run diagnostics (deltas/trends)
- any snapshot inputs or raw market events

Belief remains stateless per run; hysteresis is the only cross-run memory in scope.

## Persistence Boundary (Engine-Owned State, Orchestrator-Owned Storage)

Persistence is defined in terms of engine-owned state and schema. Storage is an orchestrator/runtime responsibility.

Authoritative persisted record: **Hysteresis Store Record v1** (defined below).

- The record is **engine-owned** (fields/meaning frozen by this spec).
- The storage medium (file path, retention, rotation) is **orchestrator-owned** and configured via existing orchestrator configuration (`engine.hysteresis_state_path`).
- No layer may invent or compute additional state for persistence beyond what the engine emits.

### Multi-Symbol Atomicity (Authoritative)

- Persistence and restore are **per-symbol**.
- No atomicity or transactional guarantees exist across multiple symbols.
- Partial persistence across symbols is valid and expected.

## Persisted Record Format (Hysteresis Store Record v1)

Storage uses an append-only JSON Lines file (JSONL). Each line is one record.

### Schema

- `schema`: string, fixed value `hysteresis_store_record`
- `schema_version`: string, fixed value `1`

### Required Fields

- `symbol`: string
- `engine_timestamp_ms`: int
- `anchor_regime`: string (`Regime.value`)
- `candidate_regime`: string (`Regime.value`) or `null`
- `progress_current`: int (>= 0)
- `last_commit_timestamp_ms`: int or `null`

### `last_commit_timestamp_ms` Semantics (Authoritative)

- `last_commit_timestamp_ms` is the **wall-clock commit time** (ms since epoch) at which hysteresis last committed an anchor switch for the symbol.
- It may be `null` before the first commit.
- It is **observability/diagnostics only**.
- It must not be used for ordering, restore precedence, replay gating, or hysteresis logic.

### Deterministic Serialization Requirements

- JSON encoding must be stable:
  - `sort_keys=true`
  - `separators=(",", ":")`
- One record per line; no pretty-printing.
- Records are append-only; no in-place mutation.

### Ordering + Dedup Semantics (Restore)

On restore, the effective store state for each `symbol` is the **latest valid record** by:

1. highest `engine_timestamp_ms`, then
2. file order (last occurrence wins on timestamp ties).

## Restore-on-Startup Semantics (Authoritative)

When running in hysteresis mode:

1. Load the JSONL file at `engine.hysteresis_state_path` if it exists.
2. Parse records line-by-line; ignore empty lines.
3. A record is valid iff:
   - `schema == "hysteresis_store_record"` and `schema_version == "1"`
   - `symbol` is a non-empty string
   - `engine_timestamp_ms` is a non-negative int
   - `anchor_regime` is a known `Regime.value`
   - `candidate_regime` is `null` or a known `Regime.value`
   - `progress_current` is an int >= 0
   - `last_commit_timestamp_ms` is `null` or a non-negative int
4. Build an in-memory `HysteresisStore` as:
   - `store.states[symbol] = restored_state(symbol)` for each symbol’s latest valid record.

### Restored `HysteresisState` Construction

To seed the engine’s existing `HysteresisStore`, each persisted record is mapped into a `HysteresisState` with:

- `schema = "hysteresis_state"` and `schema_version = "1"`
- `symbol` / `engine_timestamp_ms` / `anchor_regime` / `candidate_regime` / `progress_current` / `last_commit_timestamp_ms` from the record
- `progress_required = active_config.window_updates` (derived; not persisted)
- `reason_codes = ()` (not persisted)
- `debug = None` (not persisted)

If config changes between restarts (e.g., `window_updates`), the mapping above is authoritative. Hysteresis rules remain unchanged; only the derived `progress_required` reflects the active config.

### HysteresisState Schema Compatibility Check (Authoritative)

Restore must enforce that the engine’s expected hysteresis state schema matches the restored mapping:

- expected `HysteresisState.schema == "hysteresis_state"`
- expected `HysteresisState.schema_version == "1"`

If the engine expects a different hysteresis state schema or schema_version, restore must **fail for hysteresis mode** (operator action required). No silent downgrade/upgrade is permitted.

## Runtime Safety Invariants (Authoritative)

### Restore-Time Monotonicity Guard (Per Symbol)

For each symbol in hysteresis mode:

- Let `restored_ts_ms` be the restored `HysteresisState.engine_timestamp_ms` (if any).
- For any subsequent snapshot processed for that symbol, if:
  - `snapshot.engine_timestamp_ms < restored_ts_ms`

Then hysteresis must **not** continue normally.

Authoritative behavior:

- **Hard-fail hysteresis mode for that symbol** (operator action required).

This guard prevents time-travel, mis-ordered feeds, partial replay corruption, or clock skew from silently breaking hysteresis continuity.

## Failure Behavior (Authoritative)

### Missing State File

- If the state file does not exist: start with an empty `HysteresisStore` (bootstrap).

### Unreadable / Corrupt State File

To avoid silent hysteresis resets:

- If the file exists but cannot be read (I/O error) → treat as **fatal** for hysteresis mode and refuse to start scheduling engine runs until the operator fixes or removes the file.
- If the file can be read but contains invalid records:
  - invalid records are ignored deterministically
  - if at least one valid record exists for a symbol, restore from the latest valid record
  - if **no valid record exists for any symbol**, treat as **fatal** for hysteresis mode (equivalent to corrupt file)

### Persist Failure During Runtime

Persistence must be treated as a first-class durability requirement:

- If the engine successfully produces a new `HysteresisState` but the state record cannot be appended durably:
  - treat as a persistence failure
  - halt/pause scheduling (do not continue advancing runs without durable state)
  - do not publish downstream events that would imply hysteresis continuity

This ensures “hysteresis across runs” is never silently broken.

## Deterministic Replay Compatibility

This persistence design is replay-compatible:

- The persisted record stream is append-only and can be used to reconstruct the exact starting `HysteresisStore` for a restart-at-time replay.
- Full-history replay from the beginning may start from an empty store and recompute states deterministically by processing runs in order; persistence is not required for full replay, only for mid-stream resume.

## Non-Normative Note: Store Compaction (Optional)

Implementations MAY periodically compact the JSONL store by retaining only the latest valid record per symbol.

Compaction must not change restore semantics (latest-by-`engine_timestamp_ms` per symbol; tie-break by file order for equal timestamps).

## Out of Scope (Reaffirmed)

This revision does not introduce:

- belief persistence
- prior carryover
- evidence replay
- hysteresis rule/threshold/math changes
- new Regime Engine behavior

## Deletion Candidates (Prefer Deletion Over Reconstruction)

Once persistence is implemented and wired:

- `src/orchestrator/engine_runner.py:HysteresisStateLog` (in-memory-only store wrapper) becomes redundant and should be removed or replaced by the persisted store.
