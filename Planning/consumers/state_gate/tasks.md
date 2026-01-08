# consumers/state_gate — tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order; do not begin later phases until earlier phases are complete and reviewed.

## Phase 0 — Contracts (Freeze First)

1. Define the `state_gate_event` v1 schema exactly as specified in `Planning/consumers/state_gate/spec.md`.
2. Define the `StateGateStateRecord` v1 persistence contract (append-only transition log) and snapshot cache contract.
3. Define the `state_gate` configuration contract, including:
   - `max_gap_ms`
   - `denylisted_invalidations` (exact string matches)
   - `block_during_transition` (hysteresis mode behavior)
   - failure/backpressure limits for input consumption, persistence, and output publishing
4. Define idempotency keys and deduplication expectations for both inputs and outputs.
5. Freeze contracts and document additive-only evolution rules.

## Phase 1 — Input Consumption & Run Assembly

6. Implement consumption of the `orchestrator_event` v1 stream with at-least-once semantics.
7. Implement per-run assembly keyed by `run_id` to support deterministic input selection:
   - recognize `EngineRunCompleted`, `EngineRunFailed`, `HysteresisStatePublished`
   - ensure duplicate inputs do not produce duplicate decisions
8. Implement per-symbol ordering safeguards (strictly increasing `engine_timestamp_ms` for state mutation; ignore older runs as replay).

## Phase 2 — State Machine (Model + Transitions)

9. Implement the per-symbol state model and allowed states exactly as specified (`BOOTSTRAP`, `READY`, `HOLD`, `DEGRADED`, `HALTED`).
10. Implement deterministic promotion/demotion rules driven by `GateEvaluated` outcomes.
11. Implement deterministic reset detection and `StateReset` emission:
    - timestamp-gap reset using `max_gap_ms`
    - hysteresis reset using `reset_due_to_gap` when applicable
    - populate `payload.reset_reason` deterministically (`reset_timestamp_gap` | `reset_engine_gap`)

## Phase 3 — Gating Evaluation (No Business Logic)

12. Implement the v1 gating rule evaluation in the specified order:
    - run failure closes gate → `DEGRADED`
    - denylisted invalidations close gate → `HOLD`
    - hysteresis transition hold (if configured) → `HOLD`
    - otherwise open → `READY`
13. Implement deterministic `reasons` generation (stable codes; deterministic ordering).
14. Emit `GateEvaluated` exactly once per `run_id` once sufficient input is available.

## Phase 4 — Persistence & Replay Safety

15. Persist every state transition as a `StateGateStateRecord` append-only entry before publishing downstream outputs.
16. Maintain a current-state snapshot cache derived from the append-only log for restart performance.
17. Implement restart behavior:
    - load snapshot cache
    - resume consumption without emitting duplicate `GateEvaluated` for already-processed `run_id`s
18. Implement replay behavior that reproduces the same `state_gate_event` sequence from the persisted orchestrator inputs and configuration.

## Phase 5 — Observability & Health (Contract Enforcement)

19. Implement structured logging with the minimum required fields for decisions, resets, and internal failures.
20. Implement the minimum metrics set from `Planning/consumers/state_gate/spec.md`.
21. Implement health/readiness signals that reflect:
    - input consumption health
    - persistence availability
    - output publish health
    - halted status

## Phase 6 — Failure Isolation & Backpressure

22. Implement explicit behavior when persistence fails: transition to `HALTED` and do not emit `OPEN` gates.
23. Implement explicit behavior when output publishing is blocked beyond limits: transition to `HALTED` and stop producing new gating decisions.
24. Ensure no downstream consumer acknowledgement or behavior is required for correctness (observer-only).

## Phase 7 — Determinism Tests (Layer-Local)

25. Add contract-level tests that validate:
    - idempotent handling of duplicated input events
    - exactly-once `GateEvaluated` per `run_id`
    - correct state transitions for promotion/demotion/reset
26. Add replay tests that validate identical outputs from a fixed input log + configuration.

## Phase 8 — Readiness Gate

27. Produce a “contract freeze” note stating:
    - finalized `state_gate_event` v1 schema and event_type list
    - configuration keys required to run for a single symbol
    - explicit non-goals compliance confirmation
