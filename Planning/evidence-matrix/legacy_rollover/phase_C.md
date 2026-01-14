# Evidence Matrix Legacy Rollover — Phase C Implementation Plan

## Purpose
Enable a controlled, gated cutover where **matrix-derived regime-labelled evidence** (computed from regime-neutral inputs) becomes the belief-driving input, while preserving belief math, hysteresis semantics, and full rollback safety. The legacy regime-labelled path remains runnable throughout the transition.

This phase corresponds to “Phase C — Controlled Cutover: Matrix Feeds Belief (Gated, Reversible)” in `Planning/evidence-matrix/legacy_rollover/regime_agnostic_evidence_migration_rfc.md`.

---

## Scope (Binding)

### In scope
- Add routing that, when enabled for a deterministic scope, uses matrix-derived evidence to feed belief update.
- Maintain coexistence with legacy evidence:
  - legacy remains available for rollback and for comparison/diff observability
- Define strict, bounded fallback behavior (“fail closed”) to ensure runnability.

### Out of scope
- Any change to belief update semantics (selection ordering, one-hot assignment, invariants).
- Any change to hysteresis semantics or persistence formats.
- Any removal of legacy routing in this phase (retirement is a later phase).

---

## Contracts and Schemas (Phase C)

### Contract changes
- None (no breaking changes).

### Data sources for matrix path
- Primary input for matrix: regime-neutral embedded payload (Phase A key).
- Legacy evidence input remains: `composer_evidence_snapshot_v1` (regime-labelled).

---

## Cutover Model (Phase C)

Per-run behavior is controlled by a deterministic routing mode (configurable) with three modes:
- `legacy_only`: legacy evidence feeds belief (matrix may compute for observability but has no effect).
- `dual_run`: legacy evidence feeds belief; matrix evidence computed and diffed.
- `matrix_enabled`: matrix evidence feeds belief when available and valid; otherwise fail closed to legacy for that run.

The legacy path must remain runnable in all modes.

---

## Implementation Steps (Phase C)

### 1) Define the belief-driving input selection rule (routing only)
Maintain the invariant:
- `update_belief` always receives a `regime_engine.state.evidence.EvidenceSnapshot` (regime-labelled).

In `matrix_enabled`:
- belief-driving evidence is sourced from the matrix path (Phase B output bridged to `EvidenceSnapshot`), *if and only if* it is present and valid for the run.

### 2) Fail-closed fallback behavior (per run)
Define explicit per-run fallback triggers, including:
- regime-neutral payload missing or invalid
- interpreter failure
- matrix definition failure/invalidity
- bridge failure or bounds/invariant violations in bridged evidence

Fallback behavior:
- For the affected run, use legacy evidence for belief update.
- Emit a deterministic, correlated fallback observability event.
- Do not partially mutate or persist new state formats.

### 3) Coexistence observability (required)
In `matrix_enabled`, compute legacy evidence in parallel for:
- selected-regime diff
- mismatch/fallback attribution

Ensure:
- logs are additive only
- logs are bounded and deterministic
- correlation uses `(symbol, engine_timestamp_ms)`

### 4) Rollback mechanism (operational)
Provide deterministic, bounded scope controls to revert to:
- `dual_run` (legacy-driven belief) or
- `legacy_only`
without requiring any persistence reset or migration.

---

## Validation Gates (Phase C)

### Legacy mode equivalence (required)
For `legacy_only` and `dual_run`:
- Replay diffs must remain `{"status":"ok"}` compared to pre-Phase-C for the same captured inputs.

### Matrix-enabled safety (required)
For `matrix_enabled` in a small scope:
- Belief invariants must always hold.
- Hysteresis semantics and persistence behavior must remain unchanged (aside from being driven by whichever belief-driving evidence is selected for that run).
- Any matrix-path failure must result in a run-local fail-closed fallback with explicit observability.

---

## Rollback / Reversibility (Phase C)
- Reverting scope/mode back to legacy-driven belief must:
  - not require clearing hysteresis persistence
  - not require schema migrations
  - keep the system runnable with legacy embedded evidence only

---

## Hard Constraints / Red Lines
- Do not change belief math or `update_belief` selection rules.
- Do not change hysteresis math/progression/persistence formats.
- Do not remove the legacy regime-labelled embedded evidence path in Phase C.
- Composer/contracts evidence and regime_engine/state evidence remain distinct; the only belief-driving carrier remains the regime_engine/state evidence species.

