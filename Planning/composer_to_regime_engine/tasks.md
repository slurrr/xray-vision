# composer_to_regime_engine — tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order; do not plan or implement beyond this subsystem’s phases.

Dashboards and belief persistence are out of scope for this phase.

## Phase 0 — Freeze Boundary + Carrier (Migration-Only)

1. Freeze the embedded evidence contract reference (no schema changes):
   - embedded payload conforms to `regime_engine.state.evidence.EvidenceSnapshot` / `EvidenceOpinion`.
2. Freeze migration-only dual-shape authorization:
   - composer may emit both legacy snapshot-shaped inputs and belief-first evidence for the same `(symbol, engine_timestamp_ms)`.
   - orchestrator remains pure router (no shaping, no inference).
   - engine selects execution path by presence of embedded evidence.
3. Freeze the legacy snapshot carrier for composer evidence (reserved key):
   - `snapshot.market.structure_levels["composer_evidence_snapshot_v1"]`
4. Freeze deterministic validation/drop rules (engine canonicalization is validation + ordering only):
   - invalid bounds or non-finite values for `strength`/`confidence`
   - unknown/invalid `regime` identifiers (not in the engine regime set)
   - symbol/timestamp mismatch between embedded evidence and the snapshot
5. Freeze deterministic opinion ordering (mandatory):
   - `(regime.value, source, -confidence, -strength)`
6. Freeze zero-opinion explainability requirement:
   - zero canonical opinions must not hard-fail
   - include sentinel driver `DRIVER_NO_CANONICAL_EVIDENCE`

## Phase 1 — Engine Consumption Behind `run(snapshot)`

7. Implement detection of embedded composer evidence at the frozen carrier location inside the engine pipeline called by `engine.run(snapshot)`.
8. Implement engine canonicalization as validation + deterministic ordering only (no regime interpretation/mapping logic).
9. Implement evidence source selection in `run(snapshot)`:
   - if embedded composer evidence is present, use it as canonical evidence input to belief update
   - if absent, use the legacy internal evidence construction path
10. Implement zero-opinion behavior for the composer evidence path:
   - zero canonical opinions must not hard-fail
   - belief remains uniform (stateless prior) for that run
11. Implement composer-evidence-path explainability without violating engine validation rules:
   - drivers/invalidations derived deterministically from evidence and validation outcomes
   - include `DRIVER_NO_CANONICAL_EVIDENCE` when zero canonical opinions
   - permissions derived deterministically from projected regime
12. Add non-regression guarantees:
   - legacy `run(snapshot)` behavior remains unchanged when embedded composer evidence is absent
   - composer evidence path is deterministic and replay-safe

## Phase 2 — Composer Evidence Compliance

13. Ensure Composer emits belief-first evidence conforming to the existing frozen evidence contracts (`EvidenceSnapshot` / `EvidenceOpinion`).
14. Ensure Composer emits a legacy snapshot-shaped output for the same `(symbol, engine_timestamp_ms)` and embeds evidence into `structure_levels["composer_evidence_snapshot_v1"]`.
15. Ensure Composer emits bounded `strength`/`confidence`, valid `regime` identifiers, and stable `source` identifiers.
16. Ensure deterministic opinion ordering at emission (no hash-order dependence).
17. Add contract-level tests for the composer→engine boundary:
   - deterministic dropping behavior for invalid opinions and invalid regimes
   - deterministic ordering invariants (including mandatory sort key)
   - zero-opinion behavior does not crash, yields uniform-belief projection behavior, and includes `DRIVER_NO_CANONICAL_EVIDENCE`

## Stop & Evaluate

18. Stop and select the next active subsystem, explicitly confirming dashboards/persistence remain out of scope for this completed phase.
