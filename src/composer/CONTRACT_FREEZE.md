# Composer Contract Freeze (v1)

This note freezes the v1 Composer contracts and identifiers.

## Schemas

- FeatureSnapshot v1
  - schema: feature_snapshot
  - schema_version: 1
- EvidenceSnapshot v1
  - schema: evidence_snapshot
  - schema_version: 1
- EvidenceOpinion v1 (entries within EvidenceSnapshot)

## Frozen Feature Set (v1)

Ordered identifiers:

- price
- vwap
- atr
- atr_z
- cvd
- open_interest

## Frozen Evidence Observer Set (v1)

Ordered identifiers:

1. classical_regime_v1
   - source: composer.classical
   - may_emit: REGIME_OPINION
2. flow_pressure_v1
   - source: composer.flow
   - may_emit: FLOW_PRESSURE_OPINION
3. volatility_context_v1
   - source: composer.volatility
   - may_emit: VOLATILITY_REGIME_OPINION

## Non-Goals Compliance

- No inference, belief updates, hysteresis, or gating in composer
- No Regime Engine invocation or downstream coupling
- Deterministic, replay-safe snapshot assembly only
