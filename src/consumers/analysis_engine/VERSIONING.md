# analysis_engine versioning rules

## analysis_engine_event v1 immutability

- `schema` is fixed to `analysis_engine_event`.
- `schema_version` is fixed to `1`.
- Envelope fields `event_type`, `symbol`, `run_id`, and `engine_timestamp_ms` are required.
- Common metadata fields `engine_mode` and `source_gate_reasons` are optional and additive only.
- Event types are fixed for v1:
  - `AnalysisRunStarted`
  - `AnalysisRunSkipped`
  - `ArtifactEmitted`
  - `ModuleFailed`
  - `AnalysisRunCompleted`
  - `AnalysisRunFailed`
- Artifact envelope fields for `ArtifactEmitted` are required:
  - `artifact_kind`, `module_id`, `artifact_name`, `artifact_schema`, `artifact_schema_version`, `payload`.
- Module failure payload fields are required (`module_id`, `module_kind`, `error_kind`, `error_detail`).
- Run status payload fields are required (`status`, `module_failures`).

## Registry contract stability

- Module metadata is immutable once registered (`module_id`, `module_kind`, `module_version`).
- Dependencies are expressed as `(module_id, artifact_name)` pairs and are immutable without a new module version.
- Module-owned schema identifiers (`artifact_schema`, `artifact_schema_version`, `config_schema_id`, `config_schema_version`, and optional state schemas) are module-owned and versioned independently; changes require version bumps.

## State persistence contract

- `AnalysisModuleStateRecord` v1 is append-only with required fields:
  - `symbol`, `module_id`, `run_id`, `engine_timestamp_ms`
  - `state_schema_id`, `state_schema_version`, `state_payload`
- Additive fields are allowed; removals are breaking.

## Idempotency contract

- Idempotency is keyed strictly by `run_id`.
- Idempotency key format must not change without a version bump.

## Backward-compatible changes (additive only)

- Add optional envelope/metadata fields.
- Add new event types or artifact kinds only with spec updates and downstream review.
- Add optional registry metadata fields that do not change existing semantics.

## Breaking changes

- Any removal or reinterpretation of existing fields is breaking.
- Breaking changes require a `schema_version` increment and downstream review before merge.
