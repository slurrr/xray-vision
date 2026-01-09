# regime_engine — tasks (Phase 1 only)

This task list is Phase 1 only. Do not plan or implement beyond Phase 1 in this document.

## Phase 1 — Evidence Canonicalization + Belief-Derived Confidence (Internal Only)

1. Freeze Phase 1 terminology: document `RegimeInputSnapshot` as legacy ingress and `EvidenceSnapshot` as canonical evidence input to belief update.
2. Specify evidence canonicalization rules: define how all evidence sources are normalized into engine-owned `EvidenceSnapshot` with deterministic ordering/tie-break rules.
3. Specify belief update constraints: restate Phase 1 statelessness requirements and invariants for `update_belief(prior_state, evidence_snapshot)`.
4. Define belief-derived confidence diagnostics: choose the allowed current-run-only metrics and explicitly forbid cross-run trends/deltas/comparisons.
5. Add internal diagnostics container contract (internal-only): specify where belief-derived confidence lives inside the pipeline without affecting `RegimeOutput` or hysteresis logic.
6. Identify prior-belief insertion point: document the explicit (inactive) hook location for prior-belief-as-evidence augmentation and define the persistence activation boundary condition.
7. Define Phase 1 non-regression checks: specify verification requirements that outputs (`RegimeOutput`, `HysteresisState`) remain unchanged for identical inputs and that diagnostics are current-run only.
