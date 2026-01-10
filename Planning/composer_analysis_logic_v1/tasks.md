# composer_analysis_logic_v1 — tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order; do not begin later phases until earlier phases are complete and reviewed.

This plan is constrained by:

- `Planning/composer_analysis_logic_v1/spec.md`
- `Planning/composer/spec.md`
- `Planning/composer/evidence_observers_v1/spec.md`
- `Planning/composer_to_regime_engine/spec.md`
- `src/composer/AGENTS.md`

## Phase 0 — Freeze (Contract + Naming)

1. Freeze the v1 feature key set and window definitions exactly as specified.
2. Freeze the evidence observer set to Evidence Observers v1 (engine-addressed).
3. Freeze the semantic mapping from feature keys → observer inputs.
4. Confirm missingness and finiteness rules for features and evidence.

## Phase 1 — Feature Computation (Base Features)

5. Implement `price_last` from `TradeTick` events (bounded by `engine_timestamp_ms`).
6. Implement `vwap_3m` from `TradeTick` within `W_3m`.
7. Implement `cvd_3m` from `TradeTick.side` within `W_3m` with null-side handling.
8. Implement `aggressive_volume_ratio_3m` from `TradeTick` within `W_3m`.
9. Implement `atr_14` from final 3m `Candle` events (optional input; missingness is non-fatal).
10. Implement `atr_z_50` from the rolling ATR series with the required minimum history (optional input; missingness is non-fatal).
11. Implement `open_interest_latest` from `OpenInterest` events.

## Phase 2 — Evidence Interpretation (Engine Evidence)

12. Add/confirm the adapter that provides the observer inputs (`price/vwap/atr_z/cvd/open_interest`) from v1 features.
13. Emit engine-addressed evidence opinions using the frozen observer set and deterministic ordering rules.
14. Enforce omission of embedded evidence carrier when zero opinions are emitted.

## Phase 3 — Legacy Snapshot Shell Integration (Transport Only)

15. Ensure snapshot assembly follows `Planning/composer_to_regime_engine/spec.md`:
    - pass-through `SnapshotInputs` if present
    - else synthesize minimal shell from features and fill remaining fields with `MISSING`
16. Embed engine evidence under `snapshot.market.structure_levels["composer_evidence_snapshot_v1"]` only when opinions exist.

## Phase 4 — Tests (Determinism + Missingness)

17. Add deterministic unit tests for each feature:
    - correct window inclusion/exclusion
    - null behavior when insufficient data
    - no NaN/inf
18. Add evidence tests:
    - observer inputs map correctly from feature keys
    - confidence availability ratio is correct under missing inputs
    - deterministic ordering of emitted opinions
19. Add end-to-end composer tests for:
    - identical raw cut → identical `FeatureSnapshot` + embedded evidence payload
    - no eligible data ⇒ null features; derived observers emit zero opinions;
      classical_regime_v1 emits exactly one opinion with confidence = 0;
      embedding is present.
