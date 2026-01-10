# composer_analysis_logic_v1 — spec (FeatureSnapshot + EvidenceSnapshot)

## Purpose & Scope

This spec defines the deterministic **analysis logic** inside `composer` required to produce:

- `FeatureSnapshot` v1 (dense numeric features)
- regime-addressed engine evidence (embedded `composer_evidence_snapshot_v1`)

so the Regime Engine’s belief update is explainable via evidence alone.

This is composer-owned computation only:

- feature computation is numeric and descriptive
- evidence construction interprets features into regime-addressed opinions

This spec does not change the Regime Engine and does not introduce persistence or upstream changes.

Authoritative references:

- `Planning/composer/spec.md`
- `Planning/composer/contracts/feature_snapshot.md`
- `Planning/composer/evidence_observers_v1/spec.md` (engine-addressed observer set v1)
- `Planning/composer_to_regime_engine/spec.md` (carrier key + embedding rules)
- `Planning/market_data/spec.md` (canonical raw event types)

## Hard Constraints (Binding)

- No engine changes.
- No persistence changes.
- No `market_data` changes.
- No downstream feedback/control loops.
- Evidence must be regime-addressed and deterministic.
- Features do not directly influence belief; only evidence does.
- Avoid duplication of math across features vs evidence:
  - compute numeric measurements once in features
  - evidence observers should not recompute base measurements already present as features

## Outputs (Authoritative)

### 1) `FeatureSnapshot` v1 (composer-local)

`FeatureSnapshot` is the dense numeric feature output for a single `(symbol, engine_timestamp_ms)`.

Missingness:

- Missing values MUST be represented as `null` (Python `None`), never silently defaulted.
- Values MUST be finite numbers when present (no NaN/inf).

### 2) Engine Evidence Snapshot (embedded)

Composer produces **engine-addressed evidence** conforming to:

- `regime_engine.state.evidence.EvidenceSnapshot(symbol, engine_timestamp_ms, opinions)`
- `regime_engine.state.evidence.EvidenceOpinion(regime, strength, confidence, source)`

Embedding:

- Embed evidence under the reserved key:
  - `snapshot.market.structure_levels["composer_evidence_snapshot_v1"]`
- Omit the key when zero opinions are emitted.

## Inputs (Authoritative)

Composer consumes a deterministic raw event cut:

- `raw_events`: ordered sequence of `market_data.contracts.RawMarketEvent`
- `symbol`: canonical instrument id
- `engine_timestamp_ms`: engine cadence timestamp for the run

Ordering:

- `raw_events` must be provided in deterministic cut order (ingest order).
- When internal selection requires a “latest” item, ties are resolved deterministically by input order.

## Supported Market Data Inputs (v1)

This spec supports the following canonical raw event types when present in the cut stream for the symbol:

- `TradeTick` (for `price`, `vwap_3m`, `cvd_3m`, `aggressive_volume_ratio_3m`)
- `OpenInterest` (for `open_interest_latest`)

Optional analysis-only input:

- `Candle` with `interval_ms == 180000` (for volatility features only: `atr_14`, `atr_z_50`)

All other inputs are optional.

Authoritative constraint:

- Candles are **analysis-only inputs**, never engine requirements.
- Absence of candles must not block runs, emit failures, or degrade engine state. Missing candle-derived features are the normal path (`null` features; zero volatility opinions).

## Feature Computation (Authoritative)

Composer computes features in two layers:

1. **Base features** (direct measurements from raw events; windowed)
2. **Derived features** (pure transforms of base features; no additional raw reads)

### Canonical Feature Keys (v1)

The v1 feature key set is the following stable mapping.

**Market**

- `price_last`
- `vwap_3m`
- `atr_14`
- `atr_z_50`

**Flow**

- `cvd_3m`
- `aggressive_volume_ratio_3m`

**Derivatives**

- `open_interest_latest`

Notes:

- This key set is additive-only within v1.
- Existing keys in `src/composer/contracts/feature_snapshot.py` may be retained as aliases during implementation, but this spec’s keys are authoritative for v1 completeness.

### Window Definitions (v1, locked)

All time windows are defined relative to `engine_timestamp_ms` using `exchange_ts_ms` when available.

#### Window: `W_3m`

- `start_ms = engine_timestamp_ms - 180000`
- `end_ms = engine_timestamp_ms`
- Include raw events with `exchange_ts_ms` in `[start_ms, end_ms]`.
- If `exchange_ts_ms` is missing, the event is excluded from windowed computations.

#### Candle selection for volatility features

For volatility features, use only:

- `event_type == "Candle"`
- `normalized.interval_ms == 180000`
- `normalized.is_final == True`
- `exchange_ts_ms <= engine_timestamp_ms` (bar close time)
- When multiple eligible candles share the same `exchange_ts_ms`, select by deterministic tie-break: **last-in-input-order wins**.

### Base Feature Definitions (v1)

#### `price_last`

Latest observed price for the symbol.

Selection order:

1. Latest `TradeTick.normalized.price` among trades with `exchange_ts_ms <= engine_timestamp_ms`
2. If none: `null`

#### `vwap_3m`

Volume-weighted average price over `W_3m` using `TradeTick` events:

- `vwap_3m = sum(price * quantity) / sum(quantity)`
- Include only trades where:
  - `normalized.price` is finite
  - `normalized.quantity` is finite and `> 0`
- If `sum(quantity) == 0` or no eligible trades: `null`

#### `cvd_3m`

Cumulative volume delta over `W_3m`:

- For each `TradeTick`:
  - if `normalized.side == "buy"`: contribution `+quantity`
  - if `normalized.side == "sell"`: contribution `-quantity`
  - if `normalized.side is null`: ignore (contribution `0`)
- `cvd_3m = sum(contributions)`
- If no eligible trades with side: `null` (not `0.0`)

#### `aggressive_volume_ratio_3m`

Aggressive buy volume ratio over `W_3m`:

- `buy_qty = sum(quantity for TradeTick where side=="buy")`
- `sell_qty = sum(quantity for TradeTick where side=="sell")`
- `total = buy_qty + sell_qty`
- `ratio = buy_qty / total` when `total > 0`, else `null`

#### `atr_14`

ATR over the last 14 final 3m candles.

Define the eligible candle sequence as:

- `candles =` all eligible final 3m candle events with `exchange_ts_ms <= engine_timestamp_ms`, ordered by `(exchange_ts_ms asc, input_order asc)`.

For each candle `i` in chronological order (by the ordering above):

- `high = normalized.high`
- `low = normalized.low`
- `prev_close` = previous candle’s `normalized.close` when `i>0`
- `true_range_i` definition (off-by-one clarified):
  - if `i==0`: `true_range_i = high - low`
  - else: `true_range_i = max(high-low, abs(high-prev_close), abs(low-prev_close))`

Then:

- `atr_14 = mean(true_range_i over the last 14 eligible candles)`
- If fewer than 14 eligible candles: `null` (non-fatal)

#### `atr_z_50`

Z-score of `atr_14` against a rolling distribution of ATR values computed over eligible candles.

Procedure:

1. Compute a time series `atr_14_series` over `candles`:
   - for each candle index `j` (chronological), define `atr_14_series[j]` as `atr_14` computed over the last 14 candles ending at `j` (inclusive)
   - `atr_14_series[j]` is defined only when `j >= 13` (i.e., 14 candles available)
2. Let `atr_14_current` be the last defined value in `atr_14_series` (i.e., for the latest eligible candle close `<= engine_timestamp_ms`).
3. Use the last 50 defined ATR values ending at `atr_14_current` (chronological) to compute:
   - `mean_atr`, `std_atr` (population std)
4. `atr_z_50 = (atr_14_current - mean_atr) / std_atr`

Missingness:

- If `atr_14_current` is `null`, or fewer than 50 defined ATR values are available, or `std_atr <= 0`: `null` (non-fatal)

#### `open_interest_latest`

Latest observed open interest value:

- Select the latest `OpenInterest.normalized.open_interest` by `exchange_ts_ms` when present, else by input order.
- If no eligible values: `null`

### Derived Feature Definitions (v1)

Derived features are computed from base features only (no additional raw reads).

These derived values are defined only to eliminate duplicate math across evidence observers:

- `flow_ratio = cvd_3m / open_interest_latest` when:
  - both present and `open_interest_latest > 0`, else `null`
- `trend_sign = sign(price_last - vwap_3m)` when both present, else `null`

Derived values are not required to be emitted as separate keys; they may be computed internally. If emitted, keys must be additive-only and named deterministically.

## Evidence Interpretation (Authoritative)

Composer must emit **regime-addressed engine evidence** using the frozen Evidence Observers v1 set:

- `classical_regime_v1`
- `flow_pressure_v1`
- `volatility_context_v1`

The observer rules, strengths, and confidence definitions are frozen by:

- `Planning/composer/evidence_observers_v1/spec.md`

### Evidence Inputs (Mapping)

Evidence observers consume the following feature values (by semantic meaning):

- `price_last` → `price`
- `vwap_3m` → `vwap`
- `atr_z_50` → `atr_z`
- `cvd_3m` → `cvd`
- `open_interest_latest` → `open_interest`

Implementation may expose these under the exact key names the observer code expects, or provide a deterministic adapter layer. The semantic mapping above is authoritative.

### Missingness Semantics (Evidence)

- Observers compute `confidence` as an availability ratio over their required inputs (as specified).
- Observers must never emit opinions with non-finite `strength`/`confidence`.
- If an observer’s preconditions are unmet (e.g., undefined `flow_ratio`), it emits zero opinions.

### Volatility Evidence Gating (Authoritative)

`volatility_context_v1` is candle/ATR-gated:

- It may emit an opinion only when its required volatility input (`atr_z`) is present and finite.
- If candles are missing (or insufficient to compute ATR/ATR z), the corresponding volatility features are `null`, and `volatility_context_v1` emits **zero opinions** (normal path).

Candles do not gate engine execution; they only influence whether volatility evidence exists.

## RegimeInputSnapshot Fields (Transport Shell Only)

`RegimeInputSnapshot` is a temporary transport shell and does not define semantic truth.

Composer must maintain the following:

- Always embed engine evidence into `snapshot.market.structure_levels` under the reserved key when opinions exist.
- When `SnapshotInputs` exists in-cut for the `(symbol, engine_timestamp_ms)`, pass it through as the base shell (with explicit `MISSING` fill).
- Otherwise synthesize a minimal shell from features and set all other fields to explicit missing (`MISSING`), per `Planning/composer_to_regime_engine/spec.md`.

This spec does not introduce new snapshot semantics or require filling additional snapshot fields beyond what is deterministically available from the raw cut.

## Determinism Requirements (Mandatory)

- For identical inputs `(raw_events, symbol, engine_timestamp_ms)` and identical config, composer outputs must be identical.
- No wall-clock reads or randomness.
- All iteration over event sequences must be order-stable (input order or explicitly sorted deterministically).
