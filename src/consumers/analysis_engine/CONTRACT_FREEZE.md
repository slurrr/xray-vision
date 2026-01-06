# analysis_engine contract freeze

## analysis_engine_event v1 schema

Envelope (required):
- `schema`: analysis_engine_event
- `schema_version`: 1
- `event_type`: AnalysisRunStarted | AnalysisRunSkipped | ArtifactEmitted | ModuleFailed | AnalysisRunCompleted | AnalysisRunFailed
- `symbol`: string
- `run_id`: string
- `engine_timestamp_ms`: int

Common metadata (optional, additive only):
- `engine_mode`: truth | hysteresis
- `source_gate_reasons`: array of strings

Payloads:
- `ArtifactEmitted`: `artifact_kind` (signal|detection|evaluation|output), `module_id`, `artifact_name`, `artifact_schema`, `artifact_schema_version`, `payload`
- `ModuleFailed`: `module_id`, `module_kind`, `error_kind`, `error_detail`
- `AnalysisRunCompleted`/`AnalysisRunFailed`: `status` (SUCCESS|PARTIAL|FAILED), `module_failures` (array of module_id)
- `AnalysisRunStarted`/`AnalysisRunSkipped`: no payload

## Module registry contract

- Modules declare immutable metadata: `module_id`, `module_kind` (signal|detector|rule|output), `module_version`
- Dependencies expressed as `(module_id, artifact_name)` pairs
- Module-owned schemas are versioned: `artifact_schema` + `artifact_schema_version`; `config_schema_id` + `config_schema_version`; optional `state_schema_id` + `state_schema_version` for stateful modules
- Registry is deterministic; duplicate `module_id` is invalid; dependency cycles are invalid

## Execution plan contract

- Stage order is fixed: signals → detectors → rules → outputs
- Within a stage: dependency order then lexicographic `module_id`
- Artifact emission ordering: stage → module_id → artifact_name (lexicographic)

## Idempotency contract

- Idempotency is keyed strictly by `run_id`; duplicate run_id inputs are ignored
- Module state updates and artifacts are committed at most once per run_id

## State persistence

- `AnalysisModuleStateRecord` v1 is append-only with fields:
  - `symbol`, `module_id`, `run_id`, `engine_timestamp_ms`
  - `state_schema_id`, `state_schema_version`, `state_payload`

## Minimal config (single symbol)

- `enabled_modules`: list of module_id
- `module_configs`: list of per-module config blobs (validated as mappings)
- Optional `symbols`: per-symbol enabled_modules overrides

## Non-goals compliance

- No trading/execution/alerting logic
- No regime inference or gating decisions
- No upstream imports (e.g., market_data) or feedback coupling
- No wall-clock or random inputs in computation stages
- Additive-only evolution; breaking changes require a schema_version bump and downstream review
