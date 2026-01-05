# consumers/dashboards — tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order; do not begin later phases until earlier phases are complete and reviewed.

## Phase 0 — DVM Contract (Freeze First)

1. Define the Dashboard View Model (DVM) v1 schema exactly as specified in `Planning/consumers/dashboards/spec.md`.
2. Define deterministic ordering rules for all arrays in the DVM and document them as part of the contract.
3. Define DVM versioning rules and the “additive-only” change policy for v1.
4. Freeze the DVM contract and require renderer review for any breaking change (schema_version increment).

## Phase 1 — DVM Builder (Construction, Not Rendering)

5. Define the DVM builder’s input contract bindings:
   - which upstream schemas are consumed (`orchestrator_event`, `state_gate_event`, `analysis_engine_event`)
   - which fields are mapped into DVM sections (system/symbols/telemetry), including:
     - `regime_truth` (truth output)
     - `hysteresis` (decision state)
     - `regime_effective` (effective regime exposed downstream)
6. Implement a deterministic builder state model that can:
   - ingest at-least-once inputs (dedupe safely)
   - tolerate out-of-order inputs without crashing
   - maintain “last known” per-symbol summaries for gate/regime/analysis artifacts
   - maintain the minimal prior-snapshot hysteresis fields needed for `hysteresis.summary` derivations (carry-forward `progress.required`, compare `effective_confidence`)
7. Implement explicit staleness computation and mapping into `telemetry.staleness` and `system.status` without any upstream influence.
8. Implement snapshot production:
   - produce full DVM snapshots only (no partial/delta contract in v1)
   - include `as_of_ts_ms` and best-effort source run/timestamp pointers

## Phase 2 — Renderer Interface (DVM-Only)

9. Define a renderer input interface that accepts only DVM snapshots (no upstream schemas, no domain objects).
10. Define renderer lifecycle expectations:
    - start/stop independent of builder
    - render latest snapshot
    - local navigation only (no upstream writes)

## Phase 3 — TUI Renderer (v1 Minimal)

11. Implement a minimal TUI renderer that can render the required DVM sections:
    - system status
    - per-symbol gate + `regime_truth` / `hysteresis` / `regime_effective` summaries
    - analysis highlights and artifact summaries (best-effort)
    - staleness indicators
12. Ensure the TUI renderer tolerates missing/optional fields and unknown future fields (ignore unknowns).

## Phase 4 — Observability & Failure Isolation

13. Implement structured logs for:
    - DVM snapshot production
    - upstream ingest issues (builder)
    - renderer failures
14. Implement the minimum metrics set from `Planning/consumers/dashboards/spec.md`.
15. Implement failure isolation rules:
    - renderer failure does not stop DVM snapshot production
    - builder ingest failure yields degraded/stale DVM rather than upstream actions

## Phase 5 — Determinism & Compatibility Validation

16. Add contract-level tests that validate:
    - DVM schema compliance for required sections
    - deterministic ordering of arrays
    - stable DVM output from a fixed input event log + builder config
17. Add renderer compatibility tests that validate:
    - unknown optional fields do not break rendering
    - missing optional sections do not break rendering

## Phase 6 — Readiness Gate

18. Produce a “contract freeze” note stating:
    - finalized DVM v1 schema and ordering rules
    - what upstream inputs are consumed by the DVM builder (schema identifiers only)
    - explicit non-goals compliance confirmation
