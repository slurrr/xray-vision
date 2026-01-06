# dashboards contract freeze

## DVM v1 schema

Envelope (required):
- dvm_schema: dashboard_view_model
- dvm_schema_version: 1
- as_of_ts_ms: int
- source_run_id: string | null
- source_engine_timestamp_ms: int | null

Required sections:
- system.status: OK | DEGRADED | UNKNOWN
- system.components: component_id (orchestrator | state_gate | analysis_engine | dashboards), status (OK | DEGRADED | UNKNOWN), details [], last_update_ts_ms
- symbols: ordered by `symbol` ascending
- telemetry.ingest: last_orchestrator_event_ts_ms | last_state_gate_event_ts_ms | last_analysis_engine_event_ts_ms
- telemetry.staleness: is_stale bool, stale_reasons (lexicographic)

Optional per-symbol sections (additive only):
- gate: status (OPEN | CLOSED | UNKNOWN), reasons
- regime_truth: regime_name, confidence, drivers, invalidations, permissions
- hysteresis: effective_confidence, transition (stable_regime, candidate_regime, candidate_count, transition_active, flipped, reset_due_to_gap), optional summary (phase, anchor_regime, candidate_regime, progress.current/progress.required, confidence_trend, notes)
- regime_effective: regime_name, confidence, drivers, invalidations, permissions, source (truth | hysteresis)
- analysis: status (EMPTY | PARTIAL | PRESENT), highlights (lexicographic), artifacts (ordered by artifact_kind, module_id, artifact_name)
- metrics: atr_pct, atr_rank, range_24h_pct, range_session_pct, volume_24h, volume_rank, relative_volume, relative_strength

Deterministic ordering:
- symbols by symbol
- system.components by component_id
- analysis.highlights lexicographic
- analysis.artifacts by (artifact_kind, module_id, artifact_name)
- hysteresis.summary.notes lexicographic
- telemetry.staleness.stale_reasons lexicographic

## Builder inputs (schema identifiers only)

- orchestrator_event v1
- state_gate_event v1
- analysis_engine_event v1

## Non-goals compliance

- Dashboards are read-only observers (no upstream writes or feedback).
- DVM is the only renderer input; renderers depend only on DVM fields and ignore unknown/optional sections.
- Additive-only evolution within dvm_schema_version 1; breaking changes require a version bump and renderer review.
