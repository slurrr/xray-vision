# composer — tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order; do not begin later phases until earlier phases are complete and reviewed.

This plan is constrained by:

- `Planning/composer/spec.md`
- `Planning/composer/composer_belief_planning_doc.md`

Hard boundary notes:

- Do not refactor or reinterpret the Regime Engine.
- Do not wire `composer` into `orchestrator` yet.
- Do not introduce inference, belief updates, hysteresis, or gating into `composer`.

---

## Phase 0 — Contracts (Freeze First)

1. Freeze `FeatureSnapshot` v1 as specified in `Planning/composer/contracts/feature_snapshot.md`.
2. Freeze `EvidenceOpinion` v1 as specified in `Planning/composer/contracts/evidence_opinion.md`.
3. Freeze `EvidenceSnapshot` v1 as specified in `Planning/composer/contracts/evidence_snapshot.md`.
4. Freeze deterministic ordering rules:
   - feature key ordering in `FeatureSnapshot.features`
   - opinion ordering in `EvidenceSnapshot.opinions`
5. Freeze the public composition entrypoint interface semantics:
   - `compose(raw_events, symbol, engine_timestamp_ms) -> (FeatureSnapshot, EvidenceSnapshot)`
   - no wall-clock reads, randomness, or cross-run state
6. Freeze the v1 **feature set** as a named, finite list of feature identifiers:
   - numeric only; explicit missingness semantics
7. Freeze the v1 **evidence observer set** as a named, finite list of observer identifiers:
   - each observer emits `EvidenceOpinion` entries deterministically and statelessly from `FeatureSnapshot`
8. Document `RegimeState` v1 (engine-owned) as an additive cross-layer contract in `Planning/composer/contracts/regime_state.md` without implementing or changing Regime Engine code in this phase.

## Phase 1 — Package Scaffolding (No Wiring)

9. Create the composer package structure per the architecture plan:
   - `src/composer/contracts/`
   - `src/composer/features/`
   - `src/composer/evidence/`
   - `src/composer/tests/`
10. Provide a minimal module boundary note in `src/composer/__init__.py` (public entrypoints only) without importing orchestrator or consumers.
11. Ensure stable serialization strategy for snapshots (if serialized) is deterministic (no hash-order dependence).

## Phase 2 — Feature Computation Scaffolding (Numeric Only)

12. Implement the v1 feature set computation:
   - features are computed only from the provided `raw_events` cut and `(symbol, engine_timestamp_ms)`
   - features are numeric and descriptive only
   - missingness is explicit (no silent defaults)
13. Assemble and return a `FeatureSnapshot` v1:
   - deterministic key ordering
   - finite numeric outputs only
14. Add unit tests for:
   - deterministic `FeatureSnapshot` from fixed inputs
   - explicit missingness behavior
   - ordering stability

## Phase 3 — Evidence Construction Scaffolding (Stateless Only)

15. Define the evidence observer interface (stateless) that consumes `FeatureSnapshot` and emits `EvidenceOpinion` entries.
16. Implement the v1 evidence observer set:
   - deterministic outputs for fixed feature inputs
   - no cross-run memory; no wall-clock reads
17. Assemble and return an `EvidenceSnapshot` v1:
   - deterministic opinion ordering per contract
18. Add unit tests for:
   - deterministic `EvidenceSnapshot` from fixed inputs
   - ordering stability
   - observer statelessness (no retained internal state between calls)

## Phase 4 — Determinism & Replay Safety (Layer-Local)

19. Add replay equivalence tests:
   - same raw cut + config (when introduced) → identical snapshots
20. Add guard tests that fail if:
   - composer reads wall-clock time
   - composer uses randomness
   - composer imports forbidden downstream packages (`orchestrator`, `consumers/*`)
21. Confirm that `composer` does not invoke the Regime Engine and does not depend on its internals.

## Phase 5 — Readiness Gate

22. Produce a short “contract freeze” note stating:
   - finalized `FeatureSnapshot` v1 and `EvidenceSnapshot` v1 schemas
   - frozen v1 feature set and evidence observer set identifiers
   - explicit non-goals compliance confirmation
