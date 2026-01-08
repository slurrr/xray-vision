# Contract — `FeatureSnapshot` v1

## Purpose

`FeatureSnapshot` is the dense, deterministic numeric feature output produced by `composer` for a single `(symbol, engine_timestamp_ms)` invocation.

It is:

- deterministic
- replayable from the raw input cut + composer configuration
- used as the input to evidence observers

It is **not** an inference output and must not encode regime truth.

---

## Schema

- `schema`: string, fixed value `feature_snapshot`
- `schema_version`: string, fixed value `1`

---

## Required Fields

- `symbol`: string (canonical instrument identifier)
- `engine_timestamp_ms`: int (the engine-time timestamp for which features are computed)
- `features`: mapping `string -> number | null`

### `features` semantics

- Keys are stable, deterministic feature identifiers (e.g., `cvd`, `atr_z`, `range_expansion`).
- Values are numeric, descriptive measurements only.
- Missingness is explicit (`null`) and must not be silently imputed.
- Values must be finite numbers (no `NaN`, no infinities).

---

## Deterministic Ordering & Replay

To guarantee replay-safe serialization:

- Feature keys must be emitted/serialized in deterministic order (lexicographic by key).
- The snapshot must be a pure function of:
  - the provided raw event cut
  - `symbol`
  - `engine_timestamp_ms`
  - composer configuration (when introduced)

---

## Additive Evolution Rules

Additive changes allowed within v1:

- add new feature keys
- add optional top-level fields

Breaking changes require `schema_version` increment and explicit downstream review.

