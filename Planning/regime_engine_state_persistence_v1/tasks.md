# regime_engine_state_persistence_v1 — tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order; do not begin later phases until earlier phases are complete and reviewed.

This plan is constrained by:

- `Planning/regime_engine_state_persistence_v1/spec.md`
- Regime Engine API stability constraints (`src/regime_engine/AGENTS.md`)
- Existing orchestrator config contract (`src/orchestrator/config.py`) for `engine.hysteresis_state_path`

## Phase 0 — Freeze Persistence Contract (Docs + Interfaces)

1. Freeze the persisted record schema exactly as specified:
   - `schema="hysteresis_store_record"`, `schema_version="1"`
   - required fields and type rules
2. Freeze restore semantics:
   - latest-by-`engine_timestamp_ms` per symbol, tie-break by file order
   - fatal vs non-fatal corruption rules
3. Freeze durability semantics:
   - append-only JSONL
   - stable JSON encoding (`sort_keys`, compact separators)
   - persistence failure halts scheduling in hysteresis mode

## Phase 1 — Persistence Primitives (Engine-Owned Schema, No Engine Behavior Changes)

4. Implement a serializer/deserializer for the persisted record format:
   - mapping `HysteresisState` → record dict
   - mapping record dict → restored `HysteresisState` (with derived `progress_required`, empty `reason_codes`, `debug=None`)
   - strict validation per the spec (including regime value validation)
5. Implement file I/O helpers for:
   - append-durable (write + flush + fsync)
   - restore (scan JSONL deterministically, selecting the latest valid record per symbol)

Notes:

- Prefer keeping these helpers out of `regime_engine.engine` to avoid API churn; the stable API remains unchanged.
- If orchestrator needs to call helpers across subsystem boundaries, expose them via a minimal, explicit entrypoint (only if strictly required).

## Phase 2 — Runtime Wiring (Orchestrator Integration)

6. On orchestrator startup in hysteresis mode:
   - require `engine.hysteresis_state_path`
   - restore the `HysteresisStore` from that path
   - refuse to start hysteresis scheduling if restore fails per spec (fatal conditions)
7. After each successful `run_with_hysteresis(...)`:
   - append the new state record durably before publishing downstream events
   - on persist failure: halt/pause scheduling (do not proceed)

## Phase 3 — Replay Compatibility

8. Ensure orchestrator replay can seed the hysteresis store deterministically:
   - either from persisted hysteresis records (mid-stream resume), or
   - from an empty store when replaying from the beginning (full replay)

## Phase 4 — Tests (Minimal, Deterministic)

9. Add unit tests for persistence primitives:
   - record validation rejects malformed entries deterministically
   - restore selects latest record per symbol correctly (including tie-breaks)
   - restored `HysteresisState` fields match spec mapping
10. Add integration-level tests (orchestrator hysteresis mode):
   - restored store affects subsequent hysteresis decisions (progress/anchor continuity)
   - persist failure halts scheduling deterministically (no silent fallback)

## Phase 5 — Cleanup

11. Remove or replace in-memory-only hysteresis state wrappers that become redundant (e.g., `HysteresisStateLog`) in favor of the persisted store.

