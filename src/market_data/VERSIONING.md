# market_data versioning rules

## RawMarketEvent v1 immutability

- `schema` is fixed to `raw_market_event`.
- `schema_version` is fixed to `1`.
- Existing envelope fields and `normalized` keys are immutable.

## Backward-compatible changes (additive only)

- Add optional envelope fields.
- Add new optional keys within `normalized` for an existing `event_type`.
- Add new `event_type` values with explicit spec updates.

## Breaking changes

- Any removal or reinterpretation of existing fields is breaking.
- Breaking changes require:
  - a `schema_version` increment, and
  - explicit downstream review and approval before merge.
