# orchestrator — spec

## Purpose & Scope

`orchestrator` is the coordination layer that turns an unbounded stream of raw market receipts into a **deterministic, replayable sequence of engine invocations and outputs** for downstream subscribers.

It exists to solve systemic problems that should not be handled by adapters or consumers:

- **Cadence control**: choose *when* to invoke the Regime Engine (timer- or boundary-driven) without interpreting market meaning.
- **Buffering & replay**: persist an append-only record of inputs and run metadata so outputs can be reproduced from raw logs.
- **Isolation**: prevent consumer slowness/failure from directly destabilizing ingestion and engine cadence (within configured limits).
- **Fan-out**: publish engine outputs to an arbitrary set of downstream consumers without special-casing any consumer.

`orchestrator` must never:

- Compute indicators, features, or “fix” data.
- Perform timestamp alignment of market meaning (bucketing, completeness inference, gap filling).
- Embed regime, pattern, trading, or consumer-specific logic.
- Depend on consumer internals or change behavior based on consumer outcomes (no feedback loops).

---

## Core Responsibilities

### Data-plane (routing + execution)

- Consume `RawMarketEvent` events produced by `market_data` (contract-only dependency).
- Append all observed raw events into an internal **RawInputBuffer** (append-only, replayable, no in-place mutation).
- Maintain a deterministic **ingest sequence** (`ingest_seq`) for each buffered event.
- Define deterministic **snapshot cuts** (input slices) for each engine invocation.
- Invoke the Regime Engine via public API only:
  - `regime_engine.engine.run(snapshot) -> RegimeOutput`
  - `regime_engine.engine.run_with_hysteresis(snapshot, state, config) -> HysteresisDecision`
- Publish engine outputs and minimal run metadata to a downstream output stream for consumers.

### Control-plane (lifecycle + configuration)

- Load and validate runtime configuration at startup (sources, symbols, cadence mode, retry/backpressure limits).
- Provide start/stop lifecycle control for:
  - ingestion (subscription to raw events)
  - buffering
  - scheduling
  - engine execution
  - output publishing
- Expose health/ready state and operational telemetry (see Observability).

---

## Inputs & Outputs (Contracts)

### Inputs: `RawMarketEvent` (from `market_data`)

`orchestrator` consumes the `RawMarketEvent` v1 schema as defined in `Planning/market_data/spec.md`.

Contract expectations:

- Input delivery is at-least-once; duplicates may be present.
- New upstream `event_type` values and additive fields must not break ingestion.
- `orchestrator` must treat `raw_payload` as opaque; only the envelope and `normalized` keys defined by the schema may be used.

### Internal persistence contract: `RawInputBufferRecord` (v1)

For replay safety, `orchestrator` must persist each consumed `RawMarketEvent` as an append-only record with:

- `ingest_seq`: int, strictly increasing (global within the buffer)
- `ingest_ts_ms`: int, local timestamp of buffering
- `event`: the full `RawMarketEvent` v1 (unaltered)

The buffer is not a validator. It stores receipts.

### Internal persistence contract: `EngineRunRecord` (v1)

To make scheduling and cut selection replayable, `orchestrator` must persist an append-only run record for every attempted run with:

- `run_id`, `symbol`, `engine_timestamp_ms`, `engine_mode`, `cut_kind`
- `cut_start_ingest_seq`, `cut_end_ingest_seq`
- `planned_ts_ms`: int (the scheduler’s intended wall-clock time for the run)
- `started_ts_ms` / `completed_ts_ms`: int (operational timestamps)
- `status`: string (`started` | `completed` | `failed`)
- `attempts`: int (total attempts made)
- For failures: `error_kind`, `error_detail` (non-sensitive)

`EngineRunRecord` is authoritative replay metadata; replays must use it rather than re-deriving schedules from wall clock.

### Outputs to consumers: `OrchestratorEvent` (v1)

All consumer-facing outputs are emitted as versioned, append-only events.

**Envelope (required)**

- `schema`: string, fixed value `orchestrator_event`
- `schema_version`: string, fixed value `1`
- `event_type`: string, one of the types below
- `run_id`: string, deterministic identifier for the engine invocation
- `symbol`: string
- `engine_timestamp_ms`: int (the timestamp passed into the engine snapshot)

**Run cut metadata (required)**

- `cut_start_ingest_seq`: int (inclusive)
- `cut_end_ingest_seq`: int (inclusive)
- `cut_kind`: string (`timer` | `boundary`)

**Optional metadata (additive only)**

- `engine_mode`: string (`truth` | `hysteresis`)
- `attempt`: int (1-based retry attempt for the run)
- `published_ts_ms`: int (local publish timestamp)
- `counts_by_event_type`: object mapping raw `event_type` → count within the cut (informational only)

**Event types**

- `EngineRunStarted`
  - no additional payload required beyond metadata
- `EngineRunCompleted`
  - `payload.regime_output`: the engine’s `RegimeOutput` (as an immutable payload)
- `EngineRunFailed`
  - `payload.error_kind`: string (non-sensitive, stable category)
  - `payload.error_detail`: string (brief, non-sensitive)
- `HysteresisDecisionPublished` (only when `engine_mode == hysteresis`)
  - `payload.hysteresis_decision`: the engine’s `HysteresisDecision`

Delivery semantics:

- Outputs are at-least-once; duplicates may occur.
- Per-symbol output ordering is preserved by `engine_timestamp_ms` (monotonic, non-decreasing).
- Consumers must not assume global ordering across symbols.

### Contract stability & versioning

- `orchestrator_event` v1 changes are additive only (new optional fields or new `event_type` values).
- Breaking changes require `schema_version` increment and explicit downstream review.
- `orchestrator` must tolerate additive evolution of `RawMarketEvent` without requiring changes.

---

## Execution & Ordering Model

### Unit of work

The atomic execution unit is an **engine run** identified by:

- `symbol`
- `engine_timestamp_ms` (must satisfy Regime Engine alignment requirements)
- `cut_end_ingest_seq` (the cut boundary)
- `engine_mode` (`truth` or `hysteresis`)

`run_id` must be deterministically derived from these fields so a replay produces identical identifiers.

### Scheduling modes

`orchestrator` supports exactly two scheduling modes:

- **Timer-driven**: invoke runs every configured interval (`T`) using wall-clock time.
- **Boundary-driven**: invoke runs on configured time boundaries (e.g., 3m close) with a fixed delay, without interpreting data completeness.

In both modes:

- `orchestrator` is responsible for choosing invocation timestamps and cuts deterministically.
- `orchestrator` must not perform market-meaning alignment; it only defines mechanical cut boundaries.

### Cut definition (deterministic)

For each `(symbol, engine_timestamp_ms)` run, a cut is defined as a contiguous range of `ingest_seq` values:

- `cut_end_ingest_seq` is the highest sequence included for that run.
- `cut_start_ingest_seq` is the first sequence after the prior cut for that symbol (or the first available sequence for the first run).

The mapping from scheduler tick/boundary → `cut_end_ingest_seq` must be deterministic and replayable from persisted ingestion records.

### Snapshot sourcing (no derived computation)

For v1, `orchestrator` sources engine snapshot inputs only from upstream `RawMarketEvent` items with:

- `event_type == SnapshotInputs`
- `normalized.timestamp_ms == engine_timestamp_ms`

Selection rule:

- For a given run cut, select the **single** `SnapshotInputs` event with the highest `ingest_seq` within `[cut_start_ingest_seq, cut_end_ingest_seq]`.

If no such `SnapshotInputs` event exists within the cut, `orchestrator` must:

- emit `EngineRunFailed` with `error_kind == missing_snapshot_inputs`, and
- not invoke the Regime Engine for that run.

If the selected `SnapshotInputs` event omits any sub-object or field, `orchestrator` must pass the omission through as an explicit missing value per the frozen Regime Engine input contract; it must not fabricate or compute replacements.

### Concurrency

- Per `symbol`, runs execute sequentially in increasing `engine_timestamp_ms`.
- Across symbols, runs may execute concurrently, but concurrency must not change per-symbol ordering or `run_id` determinism.

### Replay semantics

Given:

- the persisted `RawInputBufferRecord` log
- the persisted `EngineRunRecord` log
- orchestrator configuration (including scheduling parameters)
- the same frozen Regime Engine dependency
- (when using hysteresis) the persisted hysteresis state stream

then a replay must reproduce the same sequence of `OrchestratorEvent` v1 outputs (allowing only for explicitly non-deterministic operational timestamps like `published_ts_ms` if present and defined as non-authoritative).

---

## Dependency Boundaries

### Allowed dependencies

- `market_data` contract types (input schema only).
- Regime Engine public API (`regime_engine.engine.*`) and its frozen contract payloads (`RegimeOutput`, `HysteresisDecision`).
- Storage primitives for append-only logs (file, local DB, or equivalent) as an implementation detail.
- Messaging primitives for input subscription and output publish (broker choice is an implementation detail).

### Forbidden coupling

- No dependency on consumer package code or consumer-specific schemas.
- No consumer-aware routing rules (no “if consumer X then…” behavior).
- No interpretation of `raw_payload` vendor formats; only the `RawMarketEvent` contract is supported.
- No regime/pattern/market logic or any derived feature computation.
- No behavior changes based on consumer acknowledgement beyond generic backpressure handling (no feedback loops).

---

## Failure & Backpressure Semantics

### Failure isolation domains

`orchestrator` treats these as separate failure domains with explicit handling:

1. **Input ingestion** (subscribing to `RawMarketEvent`)
2. **Buffer append** (persisting `RawInputBufferRecord`)
3. **Engine execution** (snapshot build + engine call)
4. **Output publish** (emitting `OrchestratorEvent` to consumers)

### Retry rules (bounded, deterministic)

- Ingestion reconnect/retry: bounded backoff per configuration.
- Buffer append failure: fail-fast and transition to “not ready” (do not silently drop).
- Engine run failure: retry up to a configured bound; if still failing, emit `EngineRunFailed` and proceed to subsequent timestamps (no hidden halts).
- Output publish failure: retry up to a configured bound; if still failing, transition to a halted/degraded state (do not drop completed outputs silently).

All retry bounds and backoff schedules are configuration inputs and must be deterministic.

### Backpressure behavior

- If output publishing is blocked beyond configured limits, `orchestrator` must pause engine scheduling rather than dropping outputs.
- If the input buffer reaches configured capacity, `orchestrator` must stop ingesting further inputs (propagating backpressure upstream via the input mechanism) rather than silently dropping raw events.

---

## Operational Behavior

### Lifecycle

- **Init**: validate config; initialize input subscription, buffer, scheduler, engine mode, and output publisher.
- **Run**: ingest → buffer → schedule → run engine → publish outputs.
- **Shutdown**: stop scheduling new runs, finish in-flight run publish or mark explicit failure, and close resources.

### Observability (contractual)

**Structured logs (minimum fields)**

- For ingestion: `source_id`, `symbol`, `ingest_seq`, `recv_ts_ms`, `exchange_ts_ms` (when present)
- For runs: `run_id`, `symbol`, `engine_timestamp_ms`, `cut_start_ingest_seq`, `cut_end_ingest_seq`, `engine_mode`, `attempt`
- For failures: `error_kind`, `error_detail` (non-sensitive), and the failure domain (ingest/buffer/engine/publish)

**Metrics (minimum set)**

- Ingest rate: events/sec by `source_id` and `event_type`
- Buffer: current depth/age; append failures
- Scheduler: run ticks; lag vs intended cadence
- Engine: run count, duration, success/failure count
- Publish: output count by `event_type`; publish latency; blocked/backpressure time

### Control-plane vs data-plane

- **Control-plane** owns configuration validation, lifecycle transitions, readiness/health, and telemetry.
- **Data-plane** owns ingestion, buffering, deterministic cut selection, engine invocation, and output publishing.

---

## Non-Goals

- No consumer coordination beyond generic fan-out (no dependency graphs, no consumer-specific retries).
- No data quality scoring, completeness inference, alignment, or gap filling.
- No “business meaning” interpretation of raw events.
- No strategy, execution, alerting, or dashboard logic.
- No redesign or modification of the Regime Engine (public API only).
