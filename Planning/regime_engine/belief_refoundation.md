# Regime Engine — Belief Refoundation Plan

## Purpose

Refound the existing `regime_engine` so that **belief is the authoritative state** and regime labels are **derived projections**, without breaking public APIs or deleting existing logic.

This is a **refoundation**, not a rewrite.

---

## Architectural Shift (Authoritative)

FROM:

- Regime label as truth
- Hysteresis as a wrapper around labels

TO:

- `RegimeState` (belief) as truth
- Hysteresis as inertia on belief mass
- Regime labels as projections of belief

Public outputs remain stable.  
Internal authority changes.

---

## Scope

This plan governs:

- Introduction of `RegimeState`
- Belief update semantics
- Re-targeting hysteresis to belief
- Demotion of existing logic to evidence

Out of scope:

- Composer changes
- Orchestrator changes
- Analysis layer changes
- Feature math rewrites
- Strategy or edge work

---

## Core Concepts

### RegimeState

- Engine-owned, persistent belief state
- Probability distribution over regimes
- Carries memory required for hysteresis
- Sole authoritative state

### Evidence

- Opinions derived from existing engine logic
- Stateless
- Advisory only
- Used to update RegimeState

### Projection

- Deterministic mapping from RegimeState → effective regime label
- No authority, no memory

---

## Phased Plan

### Phase 0 — Declare Authority (planning only)

- Add this document
- Clarify in README:
  - RegimeState is authoritative
  - Regime labels are projections

No code changes.

---

### Phase 1 — Insert RegimeState (additive, inert)

- Add `regime_engine/state/`:
  - `state.py` (data only)
  - `invariants.py` (assertions only)
- No math
- No wiring
- Nothing consumes it yet

---

### Phase 2 — Wrap Existing Output as Evidence

- Identify current regime resolution point
- Treat its output as a **classical regime evidence opinion**
- Do not change its logic
- Do not remove scoring / ranking / veto code

Behavior remains identical.

---

### Phase 3 — Belief Update Core

- Add belief update function:

  **RegimeState × EvidenceSnapshot → RegimeState**

- Enforce invariants (normalization, bounds)
- No hysteresis yet

`engine.run()` internally:

- builds evidence
- updates belief
- projects belief → regime label

Public API unchanged.

---

### Phase 4 — Move Hysteresis to Belief

Re-target existing hysteresis logic:

- from regime labels
- to RegimeState belief mass
- Reuse decay, counters, thresholds
- Hysteresis stabilizes belief, not labels

---

### Phase 5 — Optional Demotion / Cleanup

- Scoring, ranking, resolution become evidence producers or projection helpers
- No deletions required
- Cleanup is optional and deferred

---

## Invariants (Must Always Hold)

- Single authoritative state: RegimeState
- No parallel truth sources
- Hysteresis operates on belief only
- Identical inputs → identical belief → identical outputs
- Labels have no memory or authority

---

## Success Criteria

- Engine outputs remain stable
- Belief exists as a first-class internal state
- Hysteresis no longer wraps labels
- Existing logic is preserved but demoted
- No downstream changes required

---

## Execution Guidance

- Changes must be additive and staged
- Stop if public APIs would change
- Do not optimize
- Do not redesign scoring logic yet
