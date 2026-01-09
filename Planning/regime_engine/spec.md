# regime_engine — spec (Phase 1 addendum only)

## Phase 1 — Evidence Canonicalization + Belief-Derived Confidence (Internal Only)

### Purpose

Phase 1 refines the Regime Engine’s internal architecture so that:

- `EvidenceSnapshot` is the **sole canonical evidence input** to belief update.
- Belief-derived confidence metrics exist **internally** as diagnostics and are **non-authoritative**.

This phase is additive and internal. It must not change public APIs or consumer-visible semantics.

### Scope (Phase 1 Only)

In scope:

- Clarify and formalize the canonical evidence model (`EvidenceSnapshot` + `EvidenceOpinion`).
- Define and compute belief-derived confidence diagnostics from the **current-run** `RegimeState` only.
- Define the future insertion point for “prior-belief-as-evidence” without activating it.

Out of scope:

- Any public API changes (`regime_engine.engine.*`).
- Any changes to frozen contract dataclasses under `regime_engine/contracts/`.
- Orchestrator changes, consumer changes, or wiring changes.
- Any persistence, state stores, cross-run memory, smoothing/decay, or trend computation.

### Non-Negotiable Guardrails

- **Belief is the only authority.** Labels are projections.
- **Composer never infers.** (Future integration uses evidence-only; this phase does not wire it.)
- **Hysteresis never touches labels.** (Already belief-targeted; must remain so.)
- **No downstream layer computes regime logic.**
- **No cross-run diagnostics in Phase 1:** no belief deltas, trends, rates, comparisons to prior runs, or stored baselines. Diagnostics are current-run only.

### Terminology (Phase 1)

- **Legacy ingress:** `RegimeInputSnapshot` (current engine input shape). It is an input used to *construct* evidence; it is **not** a canonical evidence interface.
- **Canonical evidence:** `EvidenceSnapshot` (engine-owned) containing `EvidenceOpinion` entries.
- **Belief state:** `RegimeState` (engine-owned probability distribution over `Regime`).
- **Belief update:** deterministic pure transform `RegimeState × EvidenceSnapshot → RegimeState`.
- **Projection:** deterministic mapping `RegimeState → Regime` (label has no authority).

### Evidence Canonicalization (Authoritative for Phase 1)

1. `EvidenceSnapshot` is the **sole canonical evidence input** to belief update.
2. `RegimeInputSnapshot` remains a **legacy ingress** and must be treated only as:
   - the source for scoring/resolution/veto/explainability (legacy internal mechanics), and/or
   - an intermediate input for producing canonical evidence.
3. All upstream evidence sources (including future Composer evidence) must be normalized into the engine’s canonical `EvidenceSnapshot` before belief update.

### Evidence Snapshot Semantics (Canonical Contract Within Engine)

`EvidenceSnapshot` represents a set of advisory opinions about regimes for a single `(symbol, engine_timestamp_ms)`.

- **Deterministic:** identical inputs → identical `EvidenceSnapshot`.
- **Stateless:** evidence construction has no memory.
- **Uniform:** all opinions are treated uniformly as evidence; no opinion is “truth”.

`EvidenceOpinion` semantics (engine-owned):

- `regime`: the candidate `Regime` targeted by the opinion.
- `strength ∈ [0, 1]`: weight/force of the opinion.
- `confidence ∈ [0, 1]`: observer self-quality; non-authoritative; must not be treated as belief.
- `source`: stable identifier for replay/debug (e.g., `classical_resolution_v1`).

### Deterministic Ordering & Selection Rules

- Any ordering or tie-break among opinions must be deterministic and specified (no hash-order dependence).
- If an update path selects a single “winning” opinion, its selection rule must be deterministic and documented (e.g., `strength desc`, then `confidence desc`, then stable regime order).

### Stateless Belief Update (Phase 1 Constraint)

Belief update is defined as:

- `updated_state = update_belief(prior_state, evidence_snapshot)`

Phase 1 constraints:

- `prior_state` must be **stateless** (e.g., initialized/uniform) and must not be loaded or derived from any cross-run memory.
- `update_belief` must be pure and deterministic and must enforce belief invariants (normalization, bounds, finite values).

### Belief-Derived Confidence (Internal Diagnostics Only)

Define internal, belief-derived diagnostic metrics computed **only from the current-run** `RegimeState.belief_by_regime`.

Requirements:

- Metrics are non-authoritative and must not affect:
  - projection,
  - `RegimeOutput.confidence`,
  - veto/resolve logic,
  - hysteresis progression/commit,
  - any downstream behavior.
- Metrics must not compare against any prior run (no trend/delta).

Examples of allowed current-run-only diagnostics (non-exhaustive):

- top belief mass
- margin between top and runner-up belief
- entropy-like dispersion summary

### Future Boundary: Persistence + Prior-Belief-as-Evidence (Not Activated in Phase 1)

Phase 1 must explicitly identify, but not activate, the future insertion point for prior belief:

- **Insertion point:** between canonical evidence construction and belief update.
- **Boundary activation condition:** the pipeline receives a non-`None` prior belief (`RegimeState`) from an explicit external interface.
- Before boundary activation:
  - no persistence, no cached priors, no cross-run comparisons, no smoothing.

### Phase 1 Exit Criteria

- Canonical evidence model is explicit: `EvidenceSnapshot` is the sole evidence input to belief update; `RegimeInputSnapshot` is documented as legacy ingress.
- Belief-derived confidence diagnostics exist internally and are current-run only, non-authoritative, and do not affect outputs.
- A named, explicit (inactive) insertion point exists for future prior-belief-as-evidence augmentation, with a clear activation boundary.
