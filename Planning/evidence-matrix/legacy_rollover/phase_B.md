# Evidence Matrix Legacy Rollover — Phase B Implementation Plan

## Purpose
Make the matrix interpreter consume the **regime-neutral evidence payload** introduced in Phase A and produce **regime-labelled influences** derived solely from the matrix definition, while remaining non-interfering to belief by operating in **dual-run**.

This phase corresponds to “Phase B — Matrix Interprets Regime-Neutral Evidence (Dual-Run, Non-Interfering)” in `Planning/evidence-matrix/legacy_rollover/regime_agnostic_evidence_migration_rfc.md`.

---

## Scope (Binding)

### In scope
- Define a matrix definition whose inputs are **composer/contracts evidence opinion fields** (`type`, `direction`, `strength`, `confidence`, `source`) and whose outputs are **RegimeInfluenceSet** (regime-labelled).
- Update the matrix interpreter to:
  - read regime-neutral evidence for a run
  - apply the matrix definition
  - output regime-labelled influences deterministically
- Bridge matrix output to a *belief-compatible carrier* (`regime_engine.state.evidence.EvidenceSnapshot`) for logging/diffing only.

### Out of scope
- Routing matrix output into belief (must remain legacy-driven in Phase B).
- Any change to `update_belief` selection rules or invariants.
- Any change to hysteresis rules/persistence.
- Removal or disabling of the legacy regime-labelled evidence path.

---

## Contracts and Schemas (Phase B)

### Contract changes
- None (no breaking changes).

### Internal interfaces (allowed to evolve)
- The matrix layer may introduce an internal “regime-neutral evidence” representation for the interpreter input.
  - This representation must not import composer modules if that creates cross-layer coupling; it is a Regime Engine internal view of the embedded payload.
- The bridge output remains the existing Regime Engine evidence species:
  - `src/regime_engine/state/evidence.py:EvidenceSnapshot` with `EvidenceOpinion(regime=...)`

---

## Required Precondition (Phase A complete)
- The regime-neutral embedded payload exists on `RegimeInputSnapshot` for in-scope runs and is parseable/aligned.

---

## Data Flow (Phase B, Conceptual)

### Legacy path (unchanged)
`embedded regime-labelled evidence (composer_evidence_snapshot_v1)` → `update_belief` → hysteresis

### Matrix dual-run path (new, non-interfering)
`embedded regime-neutral evidence (Phase A key)` → `MatrixInterpreter` → `RegimeInfluenceSet` → `(bridge)` → belief-compatible `EvidenceSnapshot` → diff/log only

Belief uses legacy evidence only in this phase.

---

## Implementation Steps (Phase B)

### 1) Define the matrix input space (composer evidence species)
Treat each composer/contracts opinion as an input signal defined by:
- `type` (string)
- `direction` (`UP|DOWN|NEUTRAL`)
- `strength` (bounded)
- `confidence` (bounded)
- `source` (string)

No regime labels are present in this input space.

### 2) Define the matrix output space (Regime Engine regimes)
Matrix output is:
- `RegimeInfluenceSet(symbol, engine_timestamp_ms, influences[])`
- Each influence is:
  - `regime: Regime`
  - `strength` and `confidence` bounded in `[0, 1]`
  - `source` (string) for observability provenance

### 3) Author the v1 matrix definition (data-only)
Introduce a matrix definition format keyed by regime-neutral signal identity:
- at minimum: `(source, type, direction)` → `(regime, strength/confidence transforms)`

Constraints:
- Deterministic evaluation order.
- No wall-clock reads, randomness, or non-deterministic container ordering.
- Bounded outputs enforced by definition validation and/or interpreter clamping.

### 4) Implement interpreter evaluation (dual-run only)
Interpreter responsibilities for Phase B:
- Consume the regime-neutral evidence payload for the run.
- Apply the matrix definition to produce regime-labelled influences.
- Ensure the influence set is deterministic:
  - stable sorting
  - stable tie-breaking

Phase B rule:
- The interpreter may emit multiple influences per run; however, it must not “leak” belief selection logic (no approximating `update_belief`’s winner selection).
  - Selection comparisons are performed downstream via the existing bridge + `select_opinion` diffing.

### 5) Bridge for comparability and diffing (non-authoritative)
Bridge matrix influence output into a Regime Engine evidence snapshot (regime-labelled) solely for:
- logging summaries
- diffing selected opinion vs legacy-selected opinion

Belief must still consume legacy evidence in Phase B.

### 6) Gating: enforce dual-run semantics
Ensure configuration/routing is set such that:
- matrix interpreter executes for the chosen scope, and
- belief update remains driven exclusively by legacy evidence.

---

## Validation Gates (Phase B)

### Non-interference (required)
- Deterministic replay diffs must still be `{"status":"ok"}` between:
  - a build with Phase B enabled in `dual_run` and
  - a build with Phase B disabled (or with matrix disabled),
  for the same captured inputs.

### Interpretability (required)
- Matrix-derived influence summaries must be observable per run and correlated by `(symbol, engine_timestamp_ms)`.
- If the matrix definition is intentionally incomplete, that incompleteness must be observable as “no influences” rather than silent inference.

---

## Rollback / Reversibility (Phase B)
- Phase B can be rolled back by:
  - disabling matrix dual-run execution for the scope
  - leaving Phase A regime-neutral payload embedding intact or disabling it independently
- Legacy belief/hysteresis path remains the operational source of truth throughout Phase B.

---

## Hard Constraints / Red Lines
- Matrix must not feed belief in Phase B.
- Matrix must not require changes to belief/hysteresis contracts or semantics.
- Composer/contracts evidence and regime_engine/state evidence must remain distinct species; any bridge must be explicit and one-directional for logging/diff only.

