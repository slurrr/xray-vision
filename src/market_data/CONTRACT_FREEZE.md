# market_data contract freeze

## RawMarketEvent v1 schema

Envelope (required):
- schema: raw_market_event
- schema_version: 1
- event_type: one of the supported v1 event types
- source_id: string
- symbol: string
- exchange_ts_ms: int or null (source-provided)
- recv_ts_ms: int
- raw_payload: bytes or string (unchanged)

Receipt metadata (optional):
- source_event_id: string or null
- source_seq: int or null
- channel: string or null
- payload_content_type: string or null
- payload_hash: string or null

Normalized (required):
- normalized: object with required keys per event_type (direct mappings only)

## Supported v1 event_type list

- TradeTick
- BookTop
- BookDelta
- Candle
- FundingRate
- OpenInterest
- MarkPrice
- IndexPrice
- LiquidationPrint
- SnapshotInputs
- DecodeFailure

## Minimal config (single source, single symbol)

MarketDataConfig
- sources: list of SourceConfig entries

SourceConfig (minimal fields)
- source_id
- symbol_map: {source_symbol: canonical_symbol}
- channels: ["trades"] (or other source channel)
- limits:
  - connect_timeout_ms
  - read_timeout_ms
  - retry:
    - min_delay_ms
    - max_delay_ms
    - max_attempts
  - backpressure:
    - policy: block|fail
    - max_pending
    - max_block_ms (optional)
