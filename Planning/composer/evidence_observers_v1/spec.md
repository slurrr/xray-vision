# composer — Evidence Observers v1 (Regime-Addressed Engine Evidence)

## Purpose & Scope

This document defines **Evidence Observers v1** for `composer` and is authoritative for how `composer` assigns `Regime` targets when emitting **engine-addressed evidence**.

This spec exists to support the migration wiring defined in:

- `Planning/composer_to_regime_engine/spec.md`

In particular, the Regime Engine will not map any `(type, direction)` or other local opinion fields into `Regime`. **All regime addressing is a composer responsibility.**

## General Rules (Frozen)

### 1) Composer emits regime-addressed engine evidence only (for embedding)

When embedding evidence for the Regime Engine, Composer MUST emit the Regime Engine’s evidence contract types:

- `regime_engine.state.evidence.EvidenceSnapshot(symbol, engine_timestamp_ms, opinions)`
- `regime_engine.state.evidence.EvidenceOpinion(regime, strength, confidence, source)`

No other evidence schema is introduced by this spec.

### 2) Composer-local opinions are internal-only

Any composer-local evidence shapes (e.g., opinions with `(type, direction, ...)`) are internal implementation details. If they exist, they MUST be adapted to engine evidence by assigning a concrete `Regime` value in the emitted `EvidenceOpinion.regime`.

The engine will not interpret or map composer-local opinion fields.

### 3) Omit embedded evidence when zero opinions

If an observer set emits **zero** engine evidence opinions for a snapshot, Composer MUST omit:

- `snapshot.market.structure_levels["composer_evidence_snapshot_v1"]`

Composer must not embed an empty evidence snapshot.

### 4) Determinism (mandatory)

For fixed inputs, observers must emit identical evidence:

- No wall-clock reads
- No randomness
- No cross-run memory

### 5) Non-goals (explicit)

This spec does NOT:

- define belief math
- define Regime Engine behavior
- define dashboard semantics
- introduce new contracts or change contract schemas

## Evidence Observer Set (v1)

All observers below are stateless and deterministic.

Each observer emits **engine evidence opinions** with:

- `regime`: one of its allowed regimes
- `strength`: finite float in `[0.0, 1.0]`
- `confidence`: finite float in `[0.0, 1.0]`
- `source`: fixed per observer as specified below

### Shared Helpers (Normative)

Define the following helper functions for deterministic calculations.

**Clamp**

- `clamp01(x) = min(1.0, max(0.0, x))`

**Availability Confidence**

Observers compute `confidence` as an availability ratio over required inputs:

- `confidence = available_count / required_count`
- `available_count`: number of required inputs present and finite
- `required_count`: number of required inputs
- If `required_count == 0`, `confidence = 0.0`

“Present and finite” means the value is not missing/null and is a finite number (not NaN/inf).

**Flow Ratio**

When both `cvd` and `open_interest` are present and `open_interest > 0`:

- `flow_ratio = cvd / open_interest`

If `open_interest <= 0` or any input missing/non-finite, `flow_ratio` is undefined.

**Trend Sign**

When both `price` and `vwap` are present and finite:

- `trend_sign = sign(price - vwap)` where sign is `+1` if `> 0`, `-1` if `< 0`, else `0`.

If any input missing/non-finite, `trend_sign` is undefined.

## Observer 1 — `classical_regime_v1`

### Identity

- Observer id: `classical_regime_v1`
- Source id (engine evidence): `composer:classical_regime_v1`

### Allowed Regimes (v1, frozen)

- `CHOP_BALANCED`
- `CHOP_STOPHUNT`
- `LIQUIDATION_UP`
- `LIQUIDATION_DOWN`
- `SQUEEZE_UP`
- `SQUEEZE_DOWN`
- `TREND_BUILD_UP`
- `TREND_BUILD_DOWN`
- `TREND_EXHAUSTION`

### Emission Cardinality

- Emits **exactly one** engine evidence opinion per snapshot.

### Required Inputs

For regime selection, the observer uses these feature inputs (if available):

- `price`, `vwap`, `atr`, `atr_z`, `cvd`, `open_interest`

Confidence required inputs (for availability ratio):

- `price`, `vwap`, `atr_z`, `cvd`, `open_interest`

### Regime Assignment Rule (Deterministic)

The observer computes a deterministic score for each allowed regime and selects the winner:

- Winner selection: `argmax(score_by_regime)` with deterministic tie-break by `Regime` enum order.

If an input required for a component score is missing/undefined, that component contributes `0.0`.

Definitions:

- `vol = atr_z` when present, else undefined.
- `fr = flow_ratio` when defined, else undefined.
- `ts = trend_sign` when defined, else undefined.
- `abs_fr = abs(fr)` when defined, else `0.0`.
- `abs_ts = abs(ts)` when defined, else `0.0` (so `0` when unknown or equal).
- `vol_level = clamp01((vol + 1.0) / 3.0)` when vol defined, else `0.0`
- `high_vol = clamp01((vol - 1.0) / 2.0)` when vol defined, else `0.0`
- `low_flow = clamp01(1.0 - (abs_fr / 0.01))`
- `med_flow = clamp01(abs_fr / 0.02)`
- `high_flow = clamp01(abs_fr / 0.05)`

Scores:

- `CHOP_BALANCED`: `clamp01((1.0 - vol_level) * low_flow)`
- `CHOP_STOPHUNT`: `clamp01(vol_level * low_flow)`
- `LIQUIDATION_UP`: `clamp01(high_vol * high_flow * (1.0 if fr > 0 else 0.0))`
- `LIQUIDATION_DOWN`: `clamp01(high_vol * high_flow * (1.0 if fr < 0 else 0.0))`
- `SQUEEZE_UP`: `clamp01(high_vol * med_flow * (1.0 if ts > 0 else 0.0))`
- `SQUEEZE_DOWN`: `clamp01(high_vol * med_flow * (1.0 if ts < 0 else 0.0))`
- `TREND_BUILD_UP`: `clamp01(vol_level * med_flow * (1.0 if ts > 0 else 0.0))`
- `TREND_BUILD_DOWN`: `clamp01(vol_level * med_flow * (1.0 if ts < 0 else 0.0))`
- `TREND_EXHAUSTION`: `clamp01(high_vol * low_flow)`

### Strength / Confidence (Deterministic)

- `confidence`: availability ratio over required inputs (`price`, `vwap`, `atr_z`, `cvd`, `open_interest`)
- `strength`: the selected winner’s score, clamped to `[0.0, 1.0]`

## Observer 2 — `flow_pressure_v1`

### Identity

- Observer id: `flow_pressure_v1`
- Source id (engine evidence): `composer:flow_pressure_v1`

### Allowed Regimes (v1, frozen)

- `TREND_BUILD_UP`
- `TREND_BUILD_DOWN`
- `LIQUIDATION_UP`
- `LIQUIDATION_DOWN`
- `SQUEEZE_UP`
- `SQUEEZE_DOWN`

### Emission Cardinality

- May emit **zero or one** engine evidence opinion per snapshot.

### Required Inputs

For emission and assignment:

- `cvd`, `open_interest`

Optional modifier inputs:

- `atr_z`, `price`, `vwap`

Confidence required inputs (for availability ratio):

- `cvd`, `open_interest`

### Emission Rule (Deterministic)

If `flow_ratio` is undefined, emit zero opinions.

Otherwise:

- If `abs(flow_ratio) < 0.002`, emit zero opinions.

### Regime Assignment Rule (Deterministic)

When emitting an opinion:

- Let `fr = flow_ratio`
- Let `dir` be `UP` if `fr > 0`, else `DOWN` if `fr < 0`, else no opinion (already excluded by threshold).
- Let `vol = atr_z` if present.
- Let `ts = trend_sign` if present.

Select regime by the following deterministic precedence:

1. If `vol` is present and `vol >= 1.5` and `abs(fr) >= 0.02`:
   - `LIQUIDATION_UP` if `dir == UP`, else `LIQUIDATION_DOWN`
2. Else if `vol` is present and `vol >= 1.0`:
   - `SQUEEZE_UP` if `dir == UP`, else `SQUEEZE_DOWN`
3. Else:
   - `TREND_BUILD_UP` if `dir == UP`, else `TREND_BUILD_DOWN`

### Strength / Confidence (Deterministic)

- `confidence`: availability ratio over required inputs (`cvd`, `open_interest`)
- `strength`: `clamp01(abs(flow_ratio) / 0.02)`

## Observer 3 — `volatility_context_v1`

### Identity

- Observer id: `volatility_context_v1`
- Source id (engine evidence): `composer:volatility_context_v1`

### Allowed Regimes (v1, frozen)

- `CHOP_BALANCED`
- `CHOP_STOPHUNT`
- `TREND_EXHAUSTION`
- `SQUEEZE_UP`
- `SQUEEZE_DOWN`

### Emission Cardinality

- May emit **zero or one** engine evidence opinion per snapshot.

### Required Inputs

For emission and assignment:

- `atr_z`

Optional modifier inputs:

- `price`, `vwap`

Confidence required inputs (for availability ratio):

- `atr_z`

### Emission Rule (Deterministic)

If `atr_z` is missing/non-finite, emit zero opinions.

### Regime Assignment Rule (Deterministic)

When emitting an opinion, let `vol = atr_z`:

1. If `vol <= 0.2`:
   - `CHOP_BALANCED`
2. Else if `vol <= 0.8`:
   - `CHOP_STOPHUNT`
3. Else if `vol >= 1.8`:
   - `TREND_EXHAUSTION`
4. Else:
   - If `trend_sign` is defined and `trend_sign > 0`: `SQUEEZE_UP`
   - If `trend_sign` is defined and `trend_sign < 0`: `SQUEEZE_DOWN`
   - If `trend_sign` is undefined or `0`: emit zero opinions

### Strength / Confidence (Deterministic)

- `confidence`: availability ratio over required inputs (`atr_z`)
- `strength`: `clamp01((atr_z - 0.2) / 2.0)`

## Embedded Evidence Output Rules (Frozen)

When Composer embeds engine evidence for a snapshot:

- It must use the reserved carrier key:
  - `snapshot.market.structure_levels["composer_evidence_snapshot_v1"]`
- The embedded payload MUST conform to `regime_engine.state.evidence.EvidenceSnapshot` / `EvidenceOpinion`.
- If the combined observer set emits zero opinions, Composer MUST omit the reserved key entirely.

No other `structure_levels` keys are interpreted by the engine.
