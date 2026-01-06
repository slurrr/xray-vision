# orchestrator versioning rules

## orchestrator_event v1 immutability

- `schema` is fixed to `orchestrator_event`.
- `schema_version` is fixed to `1`.
- Existing envelope fields and required metadata are immutable.

## Backward-compatible changes (additive only)

- Add optional envelope/metadata fields.
- Add new optional keys to payloads for existing event types.
- Add new `event_type` values with explicit spec updates.

## Breaking changes

- Any removal or reinterpretation of existing fields is breaking.
- Breaking changes require:
  - a `schema_version` increment, and
  - explicit downstream review and approval before merge.
