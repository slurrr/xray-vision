# orchestrator — tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order; do not begin later phases until earlier phases are complete and reviewed.

## Phase 0 — Contracts (Freeze First)

1. Define the `orchestrator_event` v1 schema exactly as specified in `Planning/orchestrator/spec.md`.
2. Define the `RawInputBufferRecord` v1 persistence contract and retention/capacity configuration inputs.
3. Define the `EngineRunRecord` v1 persistence contract and replay rules.
4. Define the orchestrator runtime configuration contract:
   - scheduling mode (`timer` | `boundary`) and parameters
   - `engine_mode` (`truth` | `hysteresis`) and hysteresis state persistence requirements
   - retry/backoff bounds for each failure domain
   - backpressure/capacity limits for input buffer and output publishing
5. Define deterministic `run_id` derivation rules and document what fields are included.
6. Freeze contracts and document the additive-only evolution rules.

## Phase 1 — Data-plane: Input Subscription + Buffering

7. Implement input subscription to the `RawMarketEvent` stream (broker/interface choice is internal).
8. Implement append-only buffering with:
   - strictly increasing `ingest_seq`
   - persistence of the full `RawMarketEvent` unchanged
   - capacity/retention enforcement via explicit backpressure (no silent drop)
9. Implement buffer read APIs sufficient to support deterministic cut selection and per-symbol slicing.

## Phase 2 — Control-plane: Lifecycle + Scheduling

10. Implement orchestrator lifecycle state management (init/running/drained/stopped/degraded).
11. Implement the scheduler with exactly two modes (timer-driven and boundary-driven) and deterministic tick generation.
12. Persist an `EngineRunRecord` entry for each planned run (including `planned_ts_ms`) before attempting execution.
13. Implement per-symbol run sequencing rules (no overlap per symbol; monotonic timestamps).

## Phase 3 — Data-plane: Cut Selection + Engine Invocation

14. Implement deterministic cut selection producing `(cut_start_ingest_seq, cut_end_ingest_seq, cut_kind)` per `(symbol, engine_timestamp_ms)`.
15. Implement snapshot sourcing from `SnapshotInputs` events only (per `Planning/orchestrator/spec.md`), including the deterministic selection rule.
16. Implement snapshot construction coordination using Regime Engine public APIs only (no derived feature computation in orchestrator).
17. Implement engine invocation for `truth` mode and (optionally) `hysteresis` mode, including persistence of hysteresis state transitions required for replay.

## Phase 4 — Data-plane: Output Publishing (Fan-out)

18. Implement output publishing of `orchestrator_event` v1 events to a consumer-facing stream:
   - `EngineRunStarted`
   - `EngineRunCompleted` (with `RegimeOutput`)
   - `EngineRunFailed`
   - `HysteresisDecisionPublished` (when enabled)
19. Ensure per-symbol ordering of published outputs by `engine_timestamp_ms` with at-least-once delivery semantics.

## Phase 5 — Failure Handling + Backpressure (Domain-Explicit)

20. Implement bounded, deterministic retry/backoff per failure domain (ingest/buffer/engine/publish).
21. Implement explicit behavior on persistent failures:
   - buffer append failure → fail-fast to degraded/not-ready
   - engine run failure after retries → publish `EngineRunFailed` and continue
   - publish failure after retries → halt/pause scheduling (no silent drop)
22. Implement backpressure propagation rules:
   - output backpressure pauses scheduling
   - buffer capacity stops ingestion (propagates upstream via input mechanism)

## Phase 6 — Control-plane: Observability (Contract Enforcement)

23. Implement structured logging with the minimum required fields for ingestion, runs, and failures.
24. Implement the minimum metrics set from `Planning/orchestrator/spec.md`.
25. Implement health/readiness signals that reflect the current lifecycle and failure domains.

## Phase 7 — Determinism & Replay Validation (Layer-Local)

26. Add contract-level tests that validate:
   - stable `run_id` derivation
   - deterministic cut selection from a fixed buffered input log
   - per-symbol ordering guarantees for published outputs
27. Add replay tests that run the orchestrator against persisted `RawInputBufferRecord` + `EngineRunRecord` logs and confirm identical output event sequences (excluding explicitly non-authoritative operational timestamps if present).

## Phase 8 — Readiness Gate

28. Produce a “contract freeze” note stating:
   - finalized `orchestrator_event` v1 schema and event_type list
   - configuration keys required to run a single symbol end-to-end
   - explicit non-goals compliance confirmation
