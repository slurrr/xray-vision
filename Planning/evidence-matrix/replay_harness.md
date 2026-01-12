# Deterministic Replay Harness — Phase 1 (Non-Interference) — Minimal Plan

This document is gated by Phase A findings in this session:

- `SnapshotInputs` are supported as a `RawMarketEvent.event_type` but are **not serialized to disk** by the current runtime/orchestrator implementation.
- In the default live runtime wiring, `SnapshotInputs` are also **not produced** by Binance adapters; they are only produced by the optional stub feed (`src/runtime/stub_feed.py`) or by any external source that directly emits `SnapshotInputs`.

Accordingly, this plan uses **new additive capture artifacts** (proposal only) as the smallest replay input source. No changes are required to engine, composer, or orchestrator modules.

---

## 1) Harness Location and Scope

- Add a new harness under `tools/evidence_matrix_replay/` (or `tools/replay/`), consisting of:
  - a **capture** entrypoint (records required artifacts from a running runtime),
  - a **replay** entrypoint (runs deterministic replay from artifacts),
  - a **diff** entrypoint (compares outputs between two runs/binaries).

Scope constraints:
- Additive-only: new files under `tools/` only.
- No modifications to `src/runtime/*`, `src/orchestrator/*`, `src/composer/*`, or `src/regime_engine/*`.

---

## 2) Required Inputs

Because SnapshotInputs are not persisted, deterministic replay requires capturing the closest sufficient inputs:

### A) Raw input stream (required)

- Artifact: `raw_market_events.jsonl`
- Content: one JSON object per ingested `RawMarketEvent` in arrival order (the order observed by the runtime bus).
- Source object: `market_data.contracts.RawMarketEvent` (`src/market_data/contracts.py:51`).
- Capture point: subscribe to `RawMarketEvent` on `runtime.bus.EventBus` (`src/runtime/bus.py:10`), same event stream used by `OrchestratorRuntime.handle_raw_event` (`src/runtime/wiring.py:131`).

Notes for determinism:
- `recv_ts_ms` is produced from wall clock at ingest (`src/market_data/pipeline.py:38`) and must be treated as non-deterministic metadata; replay should not require it for computation.
- Replay must preserve **event ordering** and **exchange_ts_ms / normalized / raw_payload** as recorded.

### B) Run plan (required)

- Artifact: `orchestrator_events.jsonl`
- Content: one JSON object per `orchestrator.contracts.OrchestratorEvent` (`src/orchestrator/contracts.py:54`).
- Source object: `OrchestratorEvent` emitted by `OrchestratorRuntime` via `OrchestratorEventPublisher` (`src/runtime/wiring.py:188` → `src/orchestrator/publisher.py:*`).
- Capture point: subscribe to `OrchestratorEvent` on `EventBus` (see `src/runtime/wiring.py:396`).

Replay uses these events to reconstruct the minimum run metadata:
- `EngineRunStarted`: `run_id`, `symbol`, `engine_timestamp_ms`, `cut_start_ingest_seq`, `cut_end_ingest_seq`, `cut_kind`, `engine_mode`
  (`src/orchestrator/publisher.py:28`).
- If replay equivalence needs to include failed runs: capture `EngineRunFailed` and map to `EngineRunRecord.status == "failed"`.

### C) Hysteresis initial state (optional / mode-dependent)

If replaying hysteresis mode equivalence:
- Input: a hysteresis store file path compatible with `regime_engine.hysteresis.persistence.restore_store`
  (`src/regime_engine/hysteresis/persistence.py:91`).

If no such persisted file exists, replay can start from an empty store.

---

## 3) Replay Loop Structure (Conceptual)

### Build replay inputs
1. Load `raw_market_events.jsonl` into an in-memory sequence.
2. Assign a deterministic `ingest_seq` starting at 1 in capture order (mirrors `RawInputBuffer._next_seq` in `src/orchestrator/buffer.py:19`).
3. Populate an in-memory `orchestrator.buffer.RawInputBuffer` with events in that order (`src/orchestrator/buffer.py:23`).
4. Load `orchestrator_events.jsonl` and reconstruct an ordered list of `orchestrator.contracts.EngineRunRecord` using:
   - the fields from `EngineRunStarted` as the minimal run plan,
   - status inferred from the presence/absence of `EngineRunFailed` / `EngineRunCompleted` for a given `(run_id, symbol, engine_timestamp_ms)`.

### Execute deterministic replay
5. Call `orchestrator.replay.replay_events(...)` (`src/orchestrator/replay.py:22`) with:
   - `buffer=<reconstructed RawInputBuffer>`,
   - `run_records=<reconstructed EngineRunRecord list>`,
   - `engine_runner=<callable>`:
     - truth mode: `regime_engine.engine.run` wrapped to match the callable type, or an `EngineRunner` in truth mode,
     - hysteresis mode: `orchestrator.engine_runner.EngineRunner(..., engine_mode="hysteresis")` (`src/orchestrator/engine_runner.py:50`).

---

## 4) Exact Outputs to Capture

Capture outputs from the replay run (per run_id or per `(symbol, engine_timestamp_ms)`):

1. `RegimeOutput` (required)
   - Source: `EngineRunCompletedPayload.regime_output` (`src/orchestrator/contracts.py:35`).

2. `HysteresisState` (required in hysteresis mode)
   - Source: `HysteresisStatePublished.payload.hysteresis_state` (`src/orchestrator/contracts.py:40`).

3. Persistence append count (required in hysteresis mode)
   - Measure the number of times hysteresis persistence appends would occur.
   - Current write point is `HysteresisStatePersistence.append` → `regime_engine.hysteresis.persistence.append_record`
     (`src/orchestrator/engine_runner.py:37`, `src/regime_engine/hysteresis/persistence.py:106`).
   - Harness must capture:
     - total append calls,
     - and (optionally) per-symbol append calls.

---

## 5) Diff Strategy

The replay harness is intended to compare **baseline** vs **Phase 1** runs using the *same captured inputs*.

### Equality definitions
- `RegimeOutput`: exact structural equality (all fields).
- `HysteresisState`: equality with an explicit rule for `last_commit_timestamp_ms`:
  - `last_commit_timestamp_ms` is derived from wall clock (`time.time()`) in hysteresis rules (`src/regime_engine/hysteresis/rules.py:153`), so cross-run equality may require either:
    - comparing all fields except `last_commit_timestamp_ms`, or
    - comparing `last_commit_timestamp_ms` only for `None` vs non-`None` transitions.
- Persistence append count:
  - total count must match across baseline vs Phase 1 for the same inputs and same replay ordering.

### Ignored fields (explicit)
- Any ingest-time metadata derived from wall clock (e.g., `RawMarketEvent.recv_ts_ms`) is not used for engine computations and must not be used for equivalence.

---

## Ambiguities / Preconditions (must be resolved by the harness run)

- The runtime bus does not expose the orchestrator-assigned `ingest_seq`; the harness must reconstruct it from capture order and validate that captured ordering is consistent with `cut_start_ingest_seq` / `cut_end_ingest_seq` values observed in `EngineRunStarted` events.
- If the capture misses events (dropped subscriber, process crash), run cuts may not be reconstructable; the harness must treat this as invalid input for replay.

