# dashboards versioning rules

## DVM v1 immutability

- `dvm_schema` is fixed to `dashboard_view_model`.
- `dvm_schema_version` is fixed to `1`.
- Envelope fields `as_of_ts_ms`, `source_run_id`, and `source_engine_timestamp_ms` are present on every snapshot.
- Required sections are fixed: `system`, `symbols`, `telemetry`.
- Deterministic ordering is fixed for:
  - `symbols` (lexicographic by `symbol`)
  - `system.components` (lexicographic by `component_id`)
  - `analysis.highlights` (lexicographic)
  - `analysis.artifacts` (by `artifact_kind`, `module_id`, `artifact_name`)
  - `hysteresis.summary.notes` (lexicographic)
  - `telemetry.staleness.stale_reasons` (lexicographic)

## Optional sections (additive only)

- Per-symbol optional sections may be present: `regime_truth`, `hysteresis`, `regime_effective`, `analysis`, `metrics`.
- Optional sections may add optional fields in a backward-compatible manner.
- Renderer compatibility rule: renderers must ignore unknown optional sections and unknown fields.

## Backward-compatible changes

- Adding optional fields or optional sections.
- Adding new component IDs or renderer-safe strings when accompanied by updated ordering rules.
- Adding new stable `stale_reasons` codes.

## Breaking changes

- Any removal or reinterpretation of required fields or sections.
- Any change that alters ordering semantics.
- Any change that makes previously optional fields required.
- Breaking changes require a `dvm_schema_version` increment and renderer review.
