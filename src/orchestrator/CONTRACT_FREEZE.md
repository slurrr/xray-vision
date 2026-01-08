# orchestrator contract freeze

## OrchestratorEvent v1 schema

Envelope (required):
- schema: orchestrator_event
- schema_version: 1
- event_type: one of the supported v1 event types
- run_id: string
- symbol: string
- engine_timestamp_ms: int

Run cut metadata (required):
- cut_start_ingest_seq: int
- cut_end_ingest_seq: int
- cut_kind: timer|boundary

Optional metadata (additive only):
- engine_mode: truth|hysteresis
- attempt: int
- published_ts_ms: int
- counts_by_event_type: object

Payload (per event type):
- EngineRunCompleted: payload.regime_output (RegimeOutput)
- EngineRunFailed: payload.error_kind, payload.error_detail
- HysteresisStatePublished: payload.hysteresis_state

## Supported v1 event_type list

- EngineRunStarted
- EngineRunCompleted
- EngineRunFailed
- HysteresisStatePublished

## Minimal config (single symbol end-to-end)

OrchestratorConfig
- sources: list of SourceConfig entries
- scheduler:
  - mode: timer|boundary
  - timer_interval_ms (timer)
  - boundary_interval_ms + boundary_delay_ms (boundary)
- engine:
  - engine_mode: truth|hysteresis
  - hysteresis_state_path (required when hysteresis)
- ingestion_retry
- buffer_retry
- engine_retry
- publish_retry
- buffer_retention:
  - max_records
  - max_age_ms (optional)
- output_publish:
  - max_pending
  - max_block_ms (optional)

## Non-goals compliance

- No indicator, feature, regime, pattern, signal, or confidence computation.
- No timestamp alignment, completeness inference, or gap filling.
- No consumer-specific logic or feedback loops.
- No downstream imports.
- No silent drops; failures are explicit events.
- Inputs are buffered unaltered (append-only).
