# Contract — `EvidenceSnapshot` v1

## Purpose

`EvidenceSnapshot` is the sparse list of advisory evidence opinions emitted by `composer` for a single `(symbol, engine_timestamp_ms)` invocation.

Only `EvidenceSnapshot` is consumed by the belief updater (Regime Engine). `composer` does not perform inference and does not update belief.

---

## Schema

- `schema`: string, fixed value `evidence_snapshot`
- `schema_version`: string, fixed value `1`

---

## Required Fields

- `symbol`: string (canonical instrument identifier)
- `engine_timestamp_ms`: int (the engine-time timestamp for which evidence is constructed)
- `opinions`: sequence of `EvidenceOpinion` v1
  - See: `Planning/composer/contracts/evidence_opinion.md`

`opinions` may be empty.

---

## Deterministic Ordering & Replay

To guarantee replay-safe serialization:

- The `opinions` list must be deterministically ordered.
- Canonical ordering rule (v1):
  1. `type` (ascending lexicographic)
  2. `source` (ascending lexicographic)
  3. `direction` (ascending lexicographic)
  4. `strength` (descending numeric)
  5. `confidence` (descending numeric)

If two opinions still tie under the above keys, their relative order must be stable (no hash/random ordering).

The snapshot must be a pure function of:

- the provided raw event cut
- `symbol`
- `engine_timestamp_ms`
- composer configuration (when introduced)

---

## Additive Evolution Rules

Additive changes allowed within v1:

- add new opinion types and sources
- add optional fields

Breaking changes require `schema_version` increment and explicit downstream review.

