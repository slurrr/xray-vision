# Evidence × Regime Matrix — Phase 2 Implementation Plan (Controlled Cutover)

## Purpose

Route **MatrixInterpreter** output into the belief update path in a **controlled, gated, reversible** manner while keeping the system runnable throughout the transition and preserving:

- belief semantics (selection, invariants, determinism),
- hysteresis semantics (state progression/commit/persistence),
- frozen contracts and public APIs,
- downstream observability and gating behavior.

Phase 2 target behavior: belief update may (when enabled) consume **RegimeInfluenceSet** derived by the matrix, while legacy regime-opinion paths remain available during coexistence.

---

## Phase 2 Scope (Binding)

### In scope
- Add controlled routing from `EvidenceSnapshot → MatrixInterpreter → RegimeInfluenceSet → (bridge) → belief update`.
- Maintain temporary coexistence with legacy evidence/opinion paths:
  - embedded evidence ingestion (composer payload),
  - classical fallback evidence generation.
- Add explicit gating controls (default-off) that can be toggled without contract changes.
- Add comprehensive observability for:
  - which path was used,
  - equivalence/mismatch diagnostics vs legacy,
  - rollback actions taken.
- Ensure reversibility at every step (per-run and operationally) and keep engine runnable.

### Out of scope (must not occur)
- Any change to frozen contract dataclasses or schema constants under `src/**/contracts/`.
- Any change to public engine API surface (`src/regime_engine/engine.py`) or orchestrator event schemas.
- Any redesign of hysteresis or belief semantics (selection rules, invariants, persistence).
- Any attempt to “improve” or refactor unrelated code paths.

---

## Ground Truth Dependencies (from audit)

- Belief update today consumes `EvidenceSnapshot` and deterministically selects a single opinion (`strength desc`, `confidence desc`, `Regime enum order`) to become belief mass (`src/regime_engine/state/update.py:51`).
- Evidence selection today occurs in `src/regime_engine/pipeline.py:69` (embedded evidence when present; else classical evidence).
- Hysteresis consumes `RegimeState.belief_by_regime` and persists `HysteresisState` records; dashboards derive belief display from `HysteresisState.debug["belief_by_regime"]`.

Phase 2 must not change these semantics or invariants; Phase 2 only changes *where the same effective belief-driving signal is sourced from* when explicitly gated on.

---

## Controlled Cutover Model (Phase 2)

Phase 2 introduces **three execution modes** inside the Regime Engine pipeline (internal-only; no contract changes):

1. **Legacy-only (default)**: current behavior; matrix may run for observability but does not influence belief.
2. **Dual-run (comparison mode)**: compute both legacy belief-driving input and matrix-derived belief-driving input; use legacy for actual belief; emit diff observability.
3. **Matrix-enabled (gated)**: compute matrix-derived belief-driving input and use it for actual belief update; compute legacy in parallel for diff observability and rollback safety.

Reversibility requirement: switching from (3) back to (1) or (2) must be possible without data migration and without breaking persistence.

---

## Implementation Steps (Phase 2)

### 1) Define the bridge: `RegimeInfluenceSet → belief-driving input`

Create an internal bridge module that converts matrix output into the *existing* belief update input shape without changing belief update semantics:

- `src/regime_engine/matrix/bridge.py`
  - `influences_to_evidence_snapshot(...) -> EvidenceSnapshot` (internal-only)

Constraints:
- The produced `EvidenceSnapshot` must be deterministic and schema-free (matches current `regime_engine.state.evidence.EvidenceSnapshot`).
- It must preserve:
  - symbol match,
  - `engine_timestamp_ms`,
  - bounded `strength`/`confidence` in `[0, 1]`,
  - deterministic opinion ordering (compatible with `update_belief` selection rule).
- This bridge must not introduce new inference thresholds; it only expresses the matrix output in the existing evidence/opinion carrier format.

### 2) Add gating configuration (internal-only, default-off)

Introduce a Regime Engine internal configuration mechanism that does not change public API:

- e.g., environment-based config, or a local config object reachable from inside the engine pipeline.

Required controls:
- `mode`: `legacy_only | dual_run | matrix_enabled`
- `enablement_scope`: allow limiting to a deterministic subset (e.g., by symbol allowlist, or stable hashing of `symbol` for percentage rollout)
- `fail_closed`: if matrix path fails, fall back to legacy (must be the default behavior during Phase 2)

Constraints:
- Default must be `legacy_only`.
- Controls must be readable without network calls and without wall-clock dependence.
- Controls must not be serialized into contracts or outputs; all visibility is via logs.

### 3) Execute both paths in the pipeline with explicit selection

Modify `src/regime_engine/pipeline.py:run_pipeline_with_state` to:

- Determine the legacy evidence (as today) and build the legacy belief-driving `EvidenceSnapshot`.
- Compute matrix output from the same selected evidence input (same `EvidenceSnapshot` used for legacy belief), producing `RegimeInfluenceSet`.
- Convert `RegimeInfluenceSet` to a matrix-derived `EvidenceSnapshot` via the bridge.
- Select which `EvidenceSnapshot` is used for the *actual* `update_belief` call based on gating mode:
  - legacy-only: use legacy
  - dual-run: use legacy
  - matrix-enabled: use matrix-derived (but still compute legacy for diff + rollback observability)

Constraints:
- `update_belief` implementation and selection rules remain unchanged.
- `initialize_state` and belief invariants remain unchanged.
- Downstream output building and explainability validation must remain unchanged for a given belief outcome.
- Hysteresis path must remain unchanged (still runs over the resulting `RegimeState`).

### 4) Make coexistence explicit: preserve legacy ingress and fallback

During Phase 2 coexistence:
- Embedded evidence ingestion (composer payload) remains the primary evidence source when present.
- Classical fallback evidence generation remains active when embedded evidence is absent.

Matrix routing must work for both cases:
- Embedded case: matrix consumes the extracted `EvidenceSnapshot` (post-validation) and produces influences.
- Classical case: matrix consumes the classical `EvidenceSnapshot` produced by `build_classical_evidence`.

Constraints:
- The presence/absence of embedded evidence must not change as a result of matrix routing.
- The engine must remain runnable even if embedded evidence is malformed (existing invalidation behavior preserved).

### 5) Observability: full-path, diff, and decision logs

Extend `src/regime_engine/observability.py` with Phase 2 log events (additive):

Minimum required log events:
- `regime_engine.matrix.mode`: emits the selected mode and scope decision for `(symbol, engine_timestamp_ms)`.
- `regime_engine.matrix.bridge`: emits a bounded summary of `RegimeInfluenceSet` and the resulting bridged `EvidenceSnapshot` summary.
- `regime_engine.matrix.diff`: emits a deterministic diff between legacy-selected opinion and matrix-selected opinion:
  - selected `regime`, `strength`, `confidence`, `source` (or `None`),
  - whether belief-driving selection matches,
  - any invariant/validation failures in the matrix path.
- `regime_engine.matrix.fallback`: emitted when matrix-enabled mode fails closed and the engine falls back to legacy.

Constraints:
- Logs must not rely on wall-clock time; correlate with `(symbol, engine_timestamp_ms)`.
- Payload sizes must be bounded and deterministic (caps + counts).
- Observability must not change output schemas or event payloads.

### 6) Controlled rollback behavior (reversible at every step)

Define explicit rollback rules in the implementation (internal-only):

- In `matrix_enabled` mode:
  - If MatrixInterpreter fails, bridge fails, or produced evidence violates bounds/invariants → fall back to legacy for that run and emit `matrix.fallback`.
  - If mismatch between legacy-selected and matrix-selected opinion is detected and a strict safety setting is enabled → fall back to legacy (optional safety gate, default to fail-closed only on hard errors).

Constraints:
- Rollback must not persist any new state formats.
- Rollback must not require clearing hysteresis store; hysteresis continues from prior state using the selected belief outcome.

### 7) Verification gates (Phase 2 non-regression + controlled change)

Add verification that supports controlled activation without breaking runnability:

Non-regression in legacy-only and dual-run modes:
- `RegimeOutput` and `HysteresisState` must be identical to pre-Phase-2 for identical inputs.

Controlled-change validation in matrix-enabled mode:
- Belief invariants must always hold.
- Hysteresis invariants and persistence must remain valid.
- System must remain observable: matrix logs present and correlated for every run in scope.
- Reversibility must be demonstrable: switching mode back to legacy-only yields stable operation without requiring persistence resets.

Test strategy constraints:
- Prefer deterministic unit tests that run the pipeline on fixed snapshots and compare outputs.
- Ensure tests cover both embedded-evidence-present and classical-fallback cases.

---

## Runbook-Style Transition Stages (Operational Sequence)

1. **Stage A — Dual-run everywhere, legacy-selected**
   - Enable `dual_run` globally.
   - Observe diffs and failure rates without any behavioral change.

2. **Stage B — Matrix-enabled on a narrow scope**
   - Enable `matrix_enabled` for a small deterministic scope (e.g., symbol allowlist).
   - Keep `fail_closed` active; compute legacy in parallel for diff.
   - Validate outputs remain within expected invariants and downstream systems remain stable.

3. **Stage C — Expand scope**
   - Expand enablement scope gradually (still deterministic).
   - Maintain rollback at run granularity.

4. **Stage D — Coexistence end condition (not executed in Phase 2)**
   - Phase 2 ends with both paths still present; removal of legacy paths is a separate phase.

---

## Hard Constraints / Red Lines (Phase 2)

Must remain unchanged throughout Phase 2:
- Frozen contracts and public APIs.
- Evidence embedding key and payload validation rules.
- Belief update selection semantics and invariants.
- Hysteresis semantics and persistence schema/version.
- Downstream gating behavior (e.g., state_gate denylist over `RegimeOutput.invalidations`) and dashboards’ belief display dependency on `HysteresisState.debug["belief_by_regime"]`.

