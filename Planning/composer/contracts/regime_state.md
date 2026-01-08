# Contract — `RegimeState` v1 (Additive, Engine-Owned)

## Purpose

`RegimeState` is the single authoritative, memory-bearing belief state over regimes.

It is:

- a probability distribution over regimes
- updated by the Regime Engine belief updater (stateful, hysteretic)
- the sole source from which regime labels are projected (e.g., anchor regime)

`composer` does not create, update, or persist `RegimeState`. This contract is included only because it is required by the Composer & Belief architecture plan.

---

## Schema

- `schema`: string, fixed value `regime_state`
- `schema_version`: string, fixed value `1`

---

## Required Fields (Minimal v1)

- `symbol`: string (canonical instrument identifier)
- `engine_timestamp_ms`: int (timestamp of the belief state after an update at this engine timestep)
- `belief_by_regime`: mapping `string -> number`
  - Keys are stable regime identifiers as defined by the Regime Engine’s regime set.
  - Values are probabilities in `[0.0, 1.0]`.
  - Invariant: probabilities sum to `1.0` within a small numerical tolerance.
- `anchor_regime`: string
  - The projected regime label derived from belief (e.g., `argmax(belief_by_regime)`).

All numeric values must be finite (no `NaN`, no infinities).

---

## Determinism Requirements

- For a fixed input stream, fixed composer evidence outputs, and fixed engine configuration, `RegimeState` evolution must be deterministic and replayable.

---

## Additive Evolution Rules

Additive changes allowed within v1:

- add optional fields to represent transition/hysteresis metadata and explainability
- add new regimes only via explicit Regime Engine versioning rules (engine-owned)

Breaking changes require `schema_version` increment and explicit downstream review.

