# Evidence × Regime Matrix — Phase 3 Implementation Plan (Primary + Legacy Retirement)

## Purpose

Make the **MatrixInterpreter** the **primary and default** source of belief-driving input, and retire legacy regime-opinion routing paths in a controlled, observable, rollback-safe manner while preserving:

- belief semantics (deterministic update + invariants),
- hysteresis semantics (state evolution + persistence),
- frozen contracts and public APIs,
- system runnability, observability, and inspectability throughout.

Phase 3 end state: belief input is matrix-derived by default; legacy paths are removed or isolated behind explicit emergency-only gates; the system remains stable and maintainable.

---

## Phase 3 Scope (Binding)

### In scope
- Flip default pipeline behavior so **matrix-derived belief input** is used for all eligible runs.
- Controlled retirement of legacy bypass paths that route regime-directed opinions directly into belief update.
- Maintain “rollback safety” during transition with per-run fallback and high-fidelity observability.
- Stabilize the post-transition codepath: simplified routing logic, clear module boundaries, documented operational controls.

### Out of scope (must not occur)
- Any frozen contract changes (`src/**/contracts/`), including payload schemas and public dataclasses.
- Any change to belief update semantics (`update_belief` selection rule, invariants) or hysteresis semantics/persistence schema.
- Any change to public engine APIs (`src/regime_engine/engine.py`) or orchestrator/state_gate event schemas.
- Any redesign of the matrix semantics itself.

---

## Phase 3 Assumptions (from Phase 2 system)

Phase 2 introduced:
- `MatrixInterpreter` producing `RegimeInfluenceSet`.
- A bridge converting matrix output into the existing belief-driving carrier (`EvidenceSnapshot`) without contract changes.
- A gated selector in `run_pipeline_with_state` supporting:
  - legacy-only,
  - dual-run (legacy-selected),
  - matrix-enabled (matrix-selected with fail-closed fallback to legacy).
- Full observability for mode selection, diffs, bridge output, and fallbacks.

Phase 3 builds on that, changing defaults and retiring legacy routing.

---

## Controlled Retirement Model (Phase 3)

Phase 3 transitions the system through three operational stages, with rollback safety preserved until final stabilization:

1. **Primary Matrix (default-on, rollback-active)**  
   Matrix-derived belief input is the default for all eligible runs; legacy is still computed (or selectively computed) for comparison and fallback.

2. **Legacy Disabled (rollback still available, explicit emergency gate)**  
   Legacy belief routing is no longer executed in steady state; it remains available only behind an explicit “emergency legacy enable” control for rollback.

3. **Legacy Retired (codepath removal/containment)**  
   Remove or quarantine legacy routing code so the primary belief path is matrix-only, with stable observability and maintainability.

---

## Implementation Steps (Phase 3)

### 1) Flip the default: matrix-derived belief input becomes primary

Update the internal gating defaults (introduced in Phase 2) so:
- default mode becomes matrix-primary (equivalent to Phase 2’s `matrix_enabled`), and
- legacy-only becomes an explicit opt-in rollback mode.

Constraints:
- “Default-on” must remain deterministic and local (no network, no wall-clock dependence).
- Failure containment remains: if matrix path hard-fails for a run, fail-closed fallback to legacy is permitted during Stage 1.

### 2) Narrow and formalize legacy coexistence (temporary)

During Stage 1, keep coexistence but controlled:
- Keep dual execution only to the extent needed for:
  - mismatch/diff observability,
  - per-run fallback safety.
- Ensure the legacy path used for fallback remains identical to pre-Phase-2 behavior for the same input.

Constraints:
- Legacy execution must not become a new steady-state dependency; its role is rollback and verification only.

### 3) Promote matrix observability to “primary truth” diagnostics

Elevate matrix-oriented observability as the primary inspection surface:
- Log the matrix-derived selected regime/opinion summary that actually drove belief update.
- Preserve per-run provenance:
  - input evidence summary,
  - matrix interpretation summary,
  - bridged belief-driving evidence summary,
  - final belief aggregation (existing belief aggregation log remains).

Maintain legacy comparison logs (Stage 1 only):
- log legacy-selected vs matrix-selected deltas,
- log whether fallback occurred and why.

Constraints:
- All logs remain bounded and correlate using `(symbol, engine_timestamp_ms)`.
- No output schema changes; all inspection is via logs and existing debug fields (e.g., `HysteresisState.debug`).

### 4) Make rollback explicit and safe during matrix-primary operation

Define and enforce rollback rules (Stage 1 and Stage 2):
- Default behavior remains fail-closed:
  - matrix interpreter error → fallback to legacy for that run,
  - bridge error or invalid/boundedness violation → fallback to legacy,
  - invariant violation pre-update → fallback to legacy (and emit hard error telemetry).
- Provide an explicit, operator-controlled mode switch to force legacy-only for a bounded scope if needed.

Constraints:
- Rollback must never require modifying persistence formats or clearing hysteresis state.
- Rollback must not alter orchestrator/state_gate event contracts or event ordering.

### 5) Disable legacy in steady state, keep emergency-only gate

Move to Stage 2:
- Disable routine legacy execution (no dual-run) to reduce surface area and risk.
- Keep an explicit “emergency legacy enable” mode that:
  - reactivates the legacy routing path for a bounded scope,
  - restores Phase 2-style diff/fallback logging while active.

Constraints:
- Emergency mode must be opt-in and explicit; default remains matrix-primary.
- The system must remain runnable even if emergency mode is never used again.

### 6) Retire legacy routing paths in a controlled code change window

Move to Stage 3 with a controlled removal/containment plan:
- Remove or quarantine the legacy bypass logic that routes regime opinions directly into belief update.
- Keep only:
  - matrix interpretation,
  - bridge to belief-driving `EvidenceSnapshot`,
  - existing belief update function and invariants (unchanged),
  - existing hysteresis behavior/persistence (unchanged).

Legacy retirement boundaries (descriptive):
- The “legacy-selected belief evidence” path is removed as a runtime option.
- Any remaining legacy evidence generation that exists solely to feed belief (not for output explainability) is removed or made inert.
- Any legacy-related observability remains only as historical/archival support, not as an executed path.

Constraints:
- Retirement must not remove required explainability validation for outputs.
- Retirement must not break runs where embedded evidence is absent; matrix must still have a defined input behavior (including the possibility of an empty influence set producing “no-opinion” belief behavior).

### 7) Post-transition stability and maintainability hardening

Leave the system stable and inspectable:
- Document the final steady-state modes:
  - matrix-primary (default),
  - emergency legacy (if retained), with explicit deprecation timeline or removal criteria.
- Consolidate configuration and observability into stable internal modules (no public API changes).
- Ensure test coverage:
  - matrix-primary path is exercised for both embedded-evidence-present and embedded-evidence-absent scenarios,
  - belief invariants and hysteresis persistence remain valid,
  - output and event schemas remain unchanged.

Constraints:
- No speculative refactors; only what is necessary to retire legacy routing safely and keep the codebase maintainable.

---

## Runbook-Style Transition Stages (Operational Sequence)

1. **Stage 1 — Matrix primary, rollback active**
   - Default mode is matrix-primary.
   - Legacy executes in parallel only as needed for diff + fallback.
   - Monitor:
     - fallback rate,
     - mismatch rate (legacy vs matrix selected),
     - invariant violations (must be zero),
     - downstream stability (state_gate gating, dashboards).

2. **Stage 2 — Legacy disabled, emergency gate available**
   - Turn off dual-run and routine legacy execution.
   - Keep emergency legacy mode available for bounded scope only.
   - Monitor:
     - matrix interpreter error rate,
     - bridge error rate,
     - belief/hysteresis invariants (must remain zero violations).

3. **Stage 3 — Legacy retired**
   - Remove/quarantine legacy bypass routing.
   - Retain only matrix-primary behavior + observability.
   - Confirm:
     - system remains runnable and stable,
     - inspection surfaces remain sufficient (logs + existing debug fields),
     - no dependency on legacy routing remains.

---

## Hard Constraints / Red Lines (Phase 3)

Must remain unchanged:
- Frozen contracts and schemas across orchestrator/state_gate/regime_engine outputs and events.
- Belief update semantics and invariants (`update_belief` selection + `assert_belief_invariants`).
- Hysteresis semantics and persistence schema/version.
- Embedded evidence key name and validation rules.
- Downstream dependencies on existing output fields and hysteresis debug format.

