# composer — Evidence Observers v1 tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order.

This plan is constrained by:

- `Planning/composer/evidence_observers_v1/spec.md`
- `Planning/composer/spec.md`

Hard boundary notes:

- Do not change Regime Engine behavior in this work.
- Do not add new contracts or change frozen contract schemas.
- Do not emit empty embedded evidence; omit the reserved key when zero opinions.

## Phase 0 — Freeze (Spec Compliance Gate)

1. Confirm the observer set is exactly:
   - `classical_regime_v1`
   - `flow_pressure_v1`
   - `volatility_context_v1`
2. Confirm each observer’s:
   - allowed regimes
   - emission cardinality (exactly-one vs zero-or-one)
   - deterministic regime assignment rules
   - deterministic strength/confidence rules
   - fixed `source` id
3. Confirm embedding rules:
   - reserved carrier key is `snapshot.market.structure_levels["composer_evidence_snapshot_v1"]`
   - embedded payload conforms to `regime_engine.state.evidence.EvidenceSnapshot` / `EvidenceOpinion`
   - omit the reserved key when zero opinions are emitted

## Phase 1 — Implement Observers (Engine Evidence Emission)

4. Implement `classical_regime_v1` to emit exactly one `EvidenceOpinion` with `source="composer:classical_regime_v1"`.
5. Implement `flow_pressure_v1` to emit zero-or-one `EvidenceOpinion` with `source="composer:flow_pressure_v1"`.
6. Implement `volatility_context_v1` to emit zero-or-one `EvidenceOpinion` with `source="composer:volatility_context_v1"`.
7. Ensure all emitted opinions satisfy:
   - `regime` is one of the allowed regimes for that observer
   - `strength` and `confidence` are finite and within `[0.0, 1.0]`
   - no wall-clock reads, randomness, or cross-run state

## Phase 2 — Adaptation + Embedding

8. If composer-local opinion shapes exist, add/confirm the adapter that produces engine evidence by assigning `EvidenceOpinion.regime` (no engine-side mapping).
9. Embed the engine evidence snapshot under the reserved carrier key only when at least one opinion is emitted:
   - do not embed an empty snapshot
10. Confirm the embedded payload is JSON-serializable and matches the engine evidence contract fields exactly.

## Phase 3 — Determinism & Contract Tests

11. Add deterministic unit tests per observer for:
   - regime selection / assignment for representative inputs
   - strength/confidence bounds and finiteness
   - zero-opinion emission conditions (where applicable)
12. Add embedding tests that validate:
   - reserved key present only when opinions exist
   - reserved key omitted when zero opinions exist
   - embedded payload conforms to engine evidence contracts
13. Add determinism tests that validate:
   - identical inputs produce identical opinions and ordering
   - no hash-order dependence in any emitted sequences
