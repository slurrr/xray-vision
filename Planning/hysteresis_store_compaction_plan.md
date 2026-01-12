## Plan — Periodic Hysteresis Store Compaction (Atomic Rewrite/Replace)

### Goal
Implement **orchestrator-owned retention/rotation** for hysteresis persistence so `engine.hysteresis_state_path` does not grow without bound, while keeping only the **minimal persisted data** required for hysteresis restore (per `Planning/regime_engine_state_persistence_v1/spec.md`, including the explicit note that compaction is permitted).

Compaction must preserve restore semantics:
- Effective state per symbol remains “latest valid record by `engine_timestamp_ms`, tie-break by last occurrence”.
- Compaction output retains exactly one record per symbol representing that effective state.

### Scope / Placement (matches the spec’s ownership boundary)
- Implement compaction **inside the orchestrator’s hysteresis persistence wrapper**, because the storage medium and retention policy are orchestrator-owned:
  - `src/orchestrator/engine_runner.py:HysteresisStatePersistence`
- Reuse the engine-owned record schema/encoding routines (already used by orchestrator today):
  - `src/regime_engine/hysteresis/persistence.py:build_record`
  - `src/regime_engine/hysteresis/persistence.py:encode_record`
- No changes to record schemas, engine contracts, or orchestrator event contracts.

### Inputs
- Required:
  - `--path`: the JSONL file path currently configured as `engine.hysteresis_state_path` (e.g., `logs/hysteresis/hysteresis_store.jsonl`).
  - (In-process) `engine.hysteresis_state_path` (same value already required for hysteresis mode by orchestrator config validation).

### Trigger (what “periodic” means here)
Periodic compaction is implemented as a **bounded, deterministic cadence within the single writer**:
- Run compaction after successful persistence appends on a fixed cadence, e.g. “every N successful appends”, tracked in-memory per process.
- This cadence is mechanical (append count), not market-meaning “window semantics”.

The minimal semantic requirement (prevent unbounded growth) is satisfied even if cadence is set to “every append”; cadence selection is an operational/performance tuning detail.

### Deterministic Compaction Algorithm (authoritative for in-process compaction)
Compaction writes the effective, already-restored in-memory store back to disk as one record per symbol.

Rationale: the in-memory `HysteresisStore` is already the authoritative “latest per symbol” view that restore semantics define; writing it back is the minimal retention target.

1. Acquire a persistence mutex that also covers `append_record` calls (single-writer guarantee within the process).
2. Snapshot the in-memory store state:
   - source: `src/orchestrator/engine_runner.py:HysteresisStatePersistence.store.states`
3. For each `symbol` in deterministic order (`sorted(store.states)`):
   - Convert `HysteresisState` → record using the engine-owned mapping:
     - `src/regime_engine/hysteresis/persistence.py:build_record`
   - Encode JSON deterministically:
     - `src/regime_engine/hysteresis/persistence.py:encode_record` (stable JSON per spec)
4. Write output to a temp file in the same directory as `engine.hysteresis_state_path`:
   - One record per line, trailing newline.
5. Durability + atomic replace:
   - `fsync()` the temp file descriptor after writing.
   - `os.replace(temp_path, path)` to atomically install the compacted file.
   - `fsync()` the directory containing `path` to make the rename durable.

Stop condition:
- If the in-memory store is empty, **do not compact** (leave file as-is).
  - This avoids turning a valid non-empty file into an empty file (which would be fatal for hysteresis mode restore per `src/regime_engine/hysteresis/persistence.py:restore_store`).

### Operational Safety Constraints
- **Single-writer requirement**: compaction must not interleave with appends within the same process.
  - Enforce via a mutex in `src/orchestrator/engine_runner.py:HysteresisStatePersistence` covering both:
    - `append_record(...)`
    - compaction rewrite/replace
- Multi-process writers are out of scope; operationally, only one orchestrator instance should own a given `engine.hysteresis_state_path`.
- Compaction must not change restore semantics or schema validation rules (must reuse the engine-owned encoding).
- Compaction must not introduce non-determinism (no timestamps, randomness, or map-iteration order dependence).

### Implementation Steps (minimal, orchestrator-local)
1. Add internal compaction capability to `src/orchestrator/engine_runner.py:HysteresisStatePersistence`:
   - Add a lock and an append counter (in-memory only).
   - Implement a `compact_atomic()` method that rewrites to a temp file and `os.replace(...)`’s it into place (with `fsync` steps).
2. Invoke compaction on a fixed cadence from `HysteresisStatePersistence.append(...)` after a successful durable append:
   - Ensure compaction happens after the append completes and while holding the same lock.
3. Keep the cadence implementation entirely internal (no new config contract fields).

### Output / Reporting
- No changes required to consumer-facing logs/events.
- If any local logging is added for compaction, it must be additive and must not reorder existing events (bounded and deterministic).

### Validation Plan (additive tests only)
1. Unit tests for `HysteresisStatePersistence.compact_atomic()`:
   - Given a store with N symbols → file after compaction contains exactly N records.
   - Output order is deterministic (sorted by symbol).
   - Atomic replace behavior: temp file is used; target path ends with compacted contents.
2. Integration check:
   - Starting from a file with multiple records per symbol:
     - restore → compact → restore again produces identical in-memory `HysteresisStore` (latest per symbol).

### Hard Constraints / Red Lines
- No changes to:
  - `hysteresis_store_record` schema or serialization (`encode_record` must remain the canonical encoding).
  - Regime Engine behavior, hysteresis rules, or orchestrator scheduling behavior.
  - Orchestrator/engine configuration contracts (no new config keys required for minimal compaction).
- No partial writes: compaction must be “write temp → fsync → atomic replace”.
