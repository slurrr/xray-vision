## Plan — Orchestrator Buffer Pruning by Consumed Cuts

### Goal
Prevent `RawInputBuffer` from reaching `buffer_retention.max_records` (and triggering `BufferFullError("input buffer capacity exceeded")`) by deterministically dropping buffered records that are already consumed by completed cuts.

### Current Failure Mode (observed)
- `src/orchestrator/buffer.py:RawInputBuffer.append` raises when `len(self.records) >= self.max_records`.
- Exceptions propagate through `src/runtime/bus.py:EventBus.publish` into market-data adapter threads, causing adapter disconnect/fail loops.

### Constraints / Invariants to Preserve
- Buffered raw events remain **unaltered**; only deletion of records that are no longer needed is allowed.
- `ingest_seq` remains strictly increasing for appended records; no renumbering.
- Cut selection remains deterministic; no market-meaning “gap fill” semantics.
- Runs remain replayable from persisted input/run logs (this change only affects in-memory buffering).
- No contract/schema changes.

### Placement
- Buffer pruning lives in orchestrator + runtime wiring:
  - Buffer deletion method in `src/orchestrator/buffer.py:RawInputBuffer`
  - Safe-drop calculation and invocation in `src/runtime/wiring.py:OrchestratorRuntime._run_due`
  - Safe-drop sequence derivation uses cut progression tracked by `src/orchestrator/cuts.py:CutSelector`

### Safe-to-Drop Sequence Definition
Compute a single global `safe_drop_seq` such that dropping all records with `ingest_seq <= safe_drop_seq` cannot remove any record that might be needed for a future cut.

Two allowable definitions (choose one; both are deterministic):
1. **Min-consumed across symbols (preferred for multi-symbol safety)**
   - Let `last_end_by_symbol` be the cut-selector’s internal map of the most recent `cut_end_ingest_seq` successfully assigned for each symbol.
   - Define `safe_drop_seq = min(last_end_by_symbol.values())`.
   - Rationale: if symbols can diverge in how far they have progressed, only drop what every symbol has already consumed.
2. **End of executed cut (only safe if consumption is globally synchronized)**
   - After a tick in which all symbols successfully advanced to the same `cut_end_ingest_seq`, define `safe_drop_seq = that cut_end_ingest_seq`.
   - This requires explicit proof in code that symbols cannot diverge.

This plan proceeds with (1) to match the “minimum of last end across symbols” option.

### Implementation Steps
1. **Expose deterministic consumed-cut watermark**
   - Add a method to `src/orchestrator/cuts.py:CutSelector` (internal, not a contract change):
     - `def min_consumed_ingest_seq(self) -> int | None`
     - Returns `None` if no symbols have consumed any cut yet; otherwise returns `min(self._last_end_by_symbol.values())`.

2. **Add buffer drop method**
   - Add a method to `src/orchestrator/buffer.py:RawInputBuffer`:
     - `def drop_through(self, *, end_seq: int) -> int`
   - Behavior:
     - Deterministically remove all records with `record.ingest_seq <= end_seq`.
     - Return count of records dropped.
     - No mutation of remaining record objects; no renumbering.

3. **Invoke pruning at a deterministic point**
   - In `src/runtime/wiring.py:OrchestratorRuntime._run_due`, after finishing the per-tick loop over `symbols` (and after any successful runs), call:
     - `safe_drop_seq = self._cut_selector.min_consumed_ingest_seq()`
     - If not `None`, call `self._buffer.drop_through(end_seq=safe_drop_seq)`.
   - This matches “after finishing the per-tick symbol loop”.

4. **Guardrails**
   - Ensure pruning is not invoked when:
     - the scheduler is about to halt due to hysteresis monotonicity/persistence failure (no additional side effects on the failure path).
   - Ensure pruning does not run before any symbol has a consumed cut (when `min_consumed_ingest_seq()` is `None`).

### Validation Plan
1. **Unit tests for buffer pruning**
   - Given a buffer with records `[seq=1..N]`, dropping through `end_seq=k` removes exactly those records and retains `seq>k`.
   - Dropping through `end_seq` below the first seq drops nothing.
2. **Integration-level sanity (orchestrator-local)**
   - Simulate two symbols with divergent cut progression and verify `safe_drop_seq` uses the minimum watermark.
   - Verify that after pruning, `CutSelector.next_cut` for each symbol continues to produce valid cuts without requiring any dropped records.

### Observability (optional, additive only)
- If needed for diagnosis, emit an orchestrator-local log event indicating `safe_drop_seq` and dropped record count.
- Must be additive only; do not change existing log event shapes or ordering.

