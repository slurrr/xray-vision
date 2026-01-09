# composer_orchestrator_snapshot_flow_v1 — spec (transport-only)

## Purpose & Scope

This spec defines the **end-to-end snapshot transport flow** across:

- `orchestrator` (cut selection + engine invocation)
- `composer` (snapshot assembly + embedded evidence)
- `regime_engine` (consumes legacy `RegimeInputSnapshot` + embedded evidence)

Goal: make snapshots behave correctly end-to-end so runs are:

- deterministic and replayable
- consistently delivered to the engine
- correctly carry embedded composer evidence
- observable via orchestrator outputs and dashboards

This spec is **transport-only**. It does not define market semantics and must not introduce new belief math or engine behavior.

Authoritative references:

- `ARCHITECTURE_NEXT_LAYERS.md`
- `Planning/composer/spec.md`
- `Planning/composer_to_regime_engine/spec.md` (carrier + embedding rules)
- `Planning/composer/evidence_observers_v1/spec.md` (engine-addressed evidence rules)
- `Planning/orchestrator/spec.md` (scheduling/cuts/run records; snapshot sourcing updated to match this spec)

## Locked Context (Given)

- Market data is flowing (Binance adapters are live).
- Composer produces:
  - `FeatureSnapshot` v1
  - embedded engine evidence under `snapshot.market.structure_levels["composer_evidence_snapshot_v1"]`
- Regime Engine consumes:
  - legacy `RegimeInputSnapshot` as a **transport shell**, not semantic truth
  - embedded composer evidence when present (presence-based selection)
- Classical regime exists only as evidence (engine projections are belief-derived).

## Current Wiring Audit (Gaps / Misplacements)

This is the minimal gap list required to complete the transport path.

1. **Engine runs are currently gated on `SnapshotInputs` events**
   - `src/runtime/wiring.py` triggers runs only when `RawMarketEvent.event_type == "SnapshotInputs"`.
   - Binance adapters emit trades (and now other channels), not `SnapshotInputs`, so the engine path is inert under live market ingestion.

2. **Orchestrator snapshot sourcing is hard-wired to `SnapshotInputs`**
   - `src/orchestrator/snapshots.py` and `src/orchestrator/replay.py` both require `SnapshotInputs` in-cut and fail otherwise.
   - This conflicts with the locked architecture where Composer is the snapshot builder during migration.

3. **Composer snapshot assembly + engine evidence embedding exist but are unused**
   - `src/composer/legacy_snapshot/builder.py` builds a legacy `RegimeInputSnapshot` and embeds engine evidence.
   - `src/composer/engine_evidence/*` computes engine-addressed evidence.
   - No orchestration path calls these, so embedded evidence never reaches the engine.

4. **Duplicate snapshot shell construction logic**
   - `src/orchestrator/snapshots.py` and `src/composer/legacy_snapshot/builder.py` both implement SnapshotInputs pass-through with `MISSING` fill.
   - Only one should exist; prefer keeping snapshot assembly in Composer and deleting the duplicate in Orchestrator.

5. **Replay path cannot reproduce composer-evidence runs**
   - `src/orchestrator/replay.py` reconstructs snapshots only via `SnapshotInputs`, so it cannot replay the composer evidence path from raw logs.

## Intended End-to-End Flow (Authoritative)

### 1) Ingestion → Buffer (Orchestrator)

- Orchestrator consumes `RawMarketEvent` v1 (at-least-once).
- Orchestrator appends each event into an append-only buffer (`RawInputBufferRecord`) with strictly increasing `ingest_seq`.

No snapshot building happens here.

### 2) Scheduling → Cut Selection (Orchestrator)

For each `(symbol, engine_timestamp_ms)` run:

- Orchestrator determines `engine_timestamp_ms` from the scheduler (timer or boundary).
  - `engine_timestamp_ms` must satisfy Regime Engine alignment requirements (3m-aligned when using 180000ms cadence).
- **Boundary mode (v1 default):** `engine_timestamp_ms` is the boundary timestamp (aligned), while the scheduler’s wall-clock trigger time is `planned_ts_ms = engine_timestamp_ms + boundary_delay_ms`.
- Orchestrator selects a deterministic cut:
  - `cut_end_ingest_seq`: the chosen ingestion boundary for the run (recorded in `EngineRunRecord`)
  - `cut_start_ingest_seq`: first seq after the previous cut for that symbol
- Orchestrator materializes the run input slice as `raw_events`:
  - all buffered events for `symbol` in `[cut_start_ingest_seq, cut_end_ingest_seq]`

### 3) Snapshot Assembly + Evidence Embedding (Composer)

Given `(raw_events, symbol, engine_timestamp_ms)`, Composer deterministically produces the engine input snapshot:

1. Compute `FeatureSnapshot` v1 from `raw_events` (composer-internal).
2. Compute **engine-addressed** evidence per `Planning/composer/evidence_observers_v1/spec.md`.
3. Build the legacy `RegimeInputSnapshot` **transport shell** via:
   - **Pass-through path (migration-only):** if the cut contains a `RawMarketEvent` with `event_type == "SnapshotInputs"` and `normalized.timestamp_ms == engine_timestamp_ms`, use it as the base shell, filling omitted fields with `MISSING`.
   - **Fallback path:** otherwise synthesize a minimal shell from `FeatureSnapshot` values, using `MISSING` for any unavailable fields.
4. Embed engine evidence under:
   - `snapshot.market.structure_levels["composer_evidence_snapshot_v1"]`
   - Omit the key entirely when zero opinions are emitted (per `Planning/composer/evidence_observers_v1/spec.md`).

Composer does not invoke the engine.

### 4) Engine Invocation (Orchestrator)

- Orchestrator invokes the engine via public API only:
  - `regime_engine.engine.run(snapshot) -> RegimeOutput`
  - `run_with_hysteresis(...) -> HysteresisState` (when enabled)
- Evidence source selection is presence-based inside the engine:
  - embedded evidence present → use it (after validation + deterministic ordering)
  - embedded evidence absent → legacy internal evidence construction path

### 5) Publishing + Observability (Orchestrator + Dashboards)

Orchestrator publishes `OrchestratorEvent` v1 outputs:

- `EngineRunStarted`
- `EngineRunCompleted` (payload: `RegimeOutput`)
- `EngineRunFailed`
- `HysteresisStatePublished` (if enabled)

Transport observability requirements:

- Include `counts_by_event_type` (optional field already present in `OrchestratorEvent` v1) computed from the run’s `raw_events` slice.
- Rely on Regime Engine outputs for evidence visibility:
  - `RegimeOutput.drivers` should show composer sources when embedded evidence is selected.
  - `RegimeOutput.invalidations` should expose deterministic embedded evidence validation failures when present.

## Determinism & Replay Requirements (Transport)

The pipeline is replay-safe iff:

- The same persisted `RawInputBufferRecord` log and `EngineRunRecord` log produce identical run inputs (`raw_events`) per run.
- Composer snapshot assembly is a pure function of `(raw_events, symbol, engine_timestamp_ms)` and config.
- Embedded evidence payloads are deterministic and JSON-serializable.
- Engine invocation uses only the snapshot + frozen engine dependency.

Replay must not require `SnapshotInputs` events to exist. SnapshotInputs are an optional pass-through override only.

## Deletions Preferred (Instead of Fixing)

If implementing this spec, the following are deletion candidates (not exhaustive):

- `src/runtime/stub_feed.py` (plumbing-only SnapshotInputs emitter; superseded by live market ingestion + scheduler)
- `src/runtime/wiring.py:OrchestratorRuntime` SnapshotInputs-triggered run path (inert under live feeds)
- `src/orchestrator/snapshots.py` (duplicate snapshot shell construction; superseded by composer legacy snapshot builder)
- SnapshotInputs-only replay and tests that assume SnapshotInputs are mandatory (`tests/unit/orchestrator/test_snapshots.py`, `tests/unit/orchestrator/test_replay.py`)
