# composer_orchestrator_snapshot_flow_v1 — tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order; do not begin later phases until earlier phases are complete and reviewed.

This plan is constrained by:

- `Planning/composer_orchestrator_snapshot_flow_v1/spec.md`
- `Planning/composer_to_regime_engine/spec.md`
- `Planning/composer/evidence_observers_v1/spec.md`
- `Planning/orchestrator/spec.md` (update required; see Phase 0)

Non-goals (binding):

- No new belief math.
- No redesign of Regime Engine internals or semantics.
- No market_data changes.
- No new public APIs unless unavoidable.

## Phase 0 — Freeze Transport Contract (Docs First)

1. Update `Planning/orchestrator/spec.md` to make Composer the snapshot builder:
   - snapshot sourcing is from Composer output, not mandatory `SnapshotInputs`
   - `SnapshotInputs` are optional pass-through only (composer concern)
   - allow dependency on `composer` for snapshot assembly
2. Update `Planning/orchestrator/tasks.md` to remove SnapshotInputs-only sourcing and replace it with composer-delegated snapshot assembly.
3. Confirm the reserved carrier key remains frozen:
   - `snapshot.market.structure_levels["composer_evidence_snapshot_v1"]`

## Phase 1 — Orchestrator Control-Plane: Runs Without SnapshotInputs

4. Implement a run trigger that does not depend on `RawMarketEvent.event_type == "SnapshotInputs"`:
   - use scheduler ticks (timer/boundary) to plan runs
   - persist `EngineRunRecord` before attempting execution
5. For each run, materialize the per-symbol raw cut slice deterministically:
   - `[cut_start_ingest_seq, cut_end_ingest_seq]` with per-symbol filtering

## Phase 2 — Snapshot Assembly via Composer (Transport Shell + Evidence)

6. Add an orchestrator-owned snapshot assembly step that delegates to Composer:
   - compute `FeatureSnapshot` from cut raw events
   - compute engine evidence opinions (v1 observers)
   - build legacy `RegimeInputSnapshot` (pass-through SnapshotInputs if present; else fallback)
   - embed engine evidence when opinion count > 0; omit key when zero opinions
7. Ensure symbol/timestamp alignment across:
   - orchestrator run record `(symbol, engine_timestamp_ms)`
   - composer evidence payload `(symbol, engine_timestamp_ms)`
   - `RegimeInputSnapshot(symbol, timestamp)`

## Phase 3 — Engine Invocation + Publishing

8. Invoke `regime_engine.engine.run(snapshot)` (and hysteresis mode when enabled) using the composer-built snapshot.
9. Publish `OrchestratorEvent` outputs with:
   - `counts_by_event_type` filled from the cut slice (existing optional field)
   - no new schemas required

## Phase 4 — Replay Path (Composer Evidence-Compatible)

10. Update orchestrator replay to reconstruct snapshots via Composer from:
    - persisted `RawInputBufferRecord` slices
    - persisted `EngineRunRecord` cuts
    Replay must not fail due to missing `SnapshotInputs` events.

## Phase 5 — Tests (Delete/Replace SnapshotInputs Assumptions)

11. Delete or rewrite SnapshotInputs-mandatory tests:
    - `tests/unit/orchestrator/test_snapshots.py`
    - `tests/unit/orchestrator/test_replay.py`
12. Add transport-level tests for the new flow:
    - Orchestrator run executes with a cut that contains no `SnapshotInputs`
    - The engine sees `embedded_evidence_present == True` (observable via `RegimeOutput.drivers` containing `composer:*` sources)
    - Replay determinism: same buffer + run records → same output event sequence

