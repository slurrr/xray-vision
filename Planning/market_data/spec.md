# market_data — spec

## Purpose & Scope

`market_data` exists to acquire **raw market observables** from external sources (venues, brokers, data vendors), perform **transport decoding** and **shape-level normalization**, and deliver those observations downstream as immutable, replayable events.

`market_data` does **not** compute indicators, align timestamps, bucket candles, infer missingness, or perform any regime / strategy / trading logic. It is a “dumb pipe with receipts”.

---

## Responsibilities

### Acquisition

- Connect to external data sources via supported transports (e.g., REST polling, WebSocket streaming).
- Subscribe/poll for a configured set of instruments and channels.
- Preserve source-provided identifiers, timestamps, and payloads.

### Normalization (Shape Only)

- Convert source payloads into canonical event *shapes* while preserving meaning-neutral fidelity:
  - Standardize timestamp units to `*_ts_ms` (milliseconds since epoch).
  - Standardize instrument identifiers to a configured canonical `symbol`.
  - Standardize numeric types (e.g., parseable strings → numbers) without correcting values.
  - Standardize enums/flags (e.g., side/bid-ask) by mapping only.
- Always retain `raw_payload` unchanged alongside normalized fields.

### Validation (Structural Only)

- Validate only what is required to **emit a well-formed event**:
  - The payload can be decoded (JSON/protobuf/etc.).
  - Required envelope fields are present.
  - Required normalized fields for the declared `event_type` are present and parseable.
- If decoding/structural validation fails, emit a `DecodeFailure` event (with the original `raw_payload`) rather than dropping silently.
- `market_data` must not decide whether an event is “late”, “bad”, “invalid”, “complete”, or “aligned” in the domain sense.

### Delivery

- Publish events to a downstream sink (the “Raw Event Bus”) using the contract defined below.
- Delivery is at-least-once; duplicates are allowed; no implicit de-duplication.

---

## Inputs & Outputs (Contracts)

### Inputs

`market_data` inputs are configuration and runtime environment only:

- **Sources**: a finite set of `source_id` values (venue/vendor identifiers) and per-source transport settings.
- **Universe**: mapping from source-native instruments to canonical `symbol` strings.
- **Channels**: which raw channels to ingest per source (e.g., trades, book, candles, funding, open interest).
- **Credentials**: source auth material provided out-of-band (e.g., env vars, secrets manager); not logged.
- **Operational limits**: connection limits, timeouts, backpressure thresholds.

No downstream dependencies are required to start producing well-formed events.

### Output: Canonical Raw Market Event (`RawMarketEvent`, v1)

Every emitted item is a single immutable event with:

**Envelope (required)**

- `schema`: string, fixed value `raw_market_event`
- `schema_version`: string, fixed value `1`
- `event_type`: string, one of the types listed below
- `source_id`: string, stable identifier of the upstream venue/vendor
- `symbol`: string, canonical instrument identifier (post-mapping)
- `exchange_ts_ms`: int, timestamp taken from the source payload when available; otherwise `null`
- `recv_ts_ms`: int, local receipt timestamp when the payload was received/decoded
- `raw_payload`: bytes/string, the untouched source payload (or transport frame) exactly as received

**Receipt metadata (optional, shape-only)**

- `source_event_id`: string, a source-provided unique id if present
- `source_seq`: int, a source-provided sequence number if present
- `channel`: string, source channel name if present (e.g., `trades`, `book`, `candle_3m`)
- `payload_content_type`: string, e.g., `application/json`, `application/x-protobuf`
- `payload_hash`: string, deterministic hash of `raw_payload` (if computed); used only as a receipt fingerprint

**Normalized fields (required)**

- `normalized`: object whose required keys depend on `event_type`; values are direct mappings only

#### Canonical `event_type` payloads (v1)

All numeric values are as-observed from the source after parsing; no correction or smoothing is performed.

**`TradeTick`**

- `normalized.price`: number
- `normalized.quantity`: number
- `normalized.side`: string (`buy` | `sell`) if available; otherwise `null`

**`BookTop`** (best bid/ask)

- `normalized.best_bid_price`: number
- `normalized.best_bid_quantity`: number
- `normalized.best_ask_price`: number
- `normalized.best_ask_quantity`: number

**`BookDelta`** (incremental depth update)

- `normalized.bids`: array of `[price:number, quantity:number]`
- `normalized.asks`: array of `[price:number, quantity:number]`

**`Candle`** (time-bucketed bar as provided by source)

- `normalized.open`: number
- `normalized.high`: number
- `normalized.low`: number
- `normalized.close`: number
- `normalized.volume`: number
- `normalized.interval_ms`: int (the bar interval as reported/selected; e.g., 180000 for 3m)
- `normalized.is_final`: bool if available; otherwise `null`

**`FundingRate`**

- `normalized.funding_rate`: number

**`OpenInterest`**

- `normalized.open_interest`: number

**`MarkPrice`**

- `normalized.mark_price`: number

**`IndexPrice`**

- `normalized.index_price`: number

**`LiquidationPrint`** (if source provides it)

- `normalized.price`: number
- `normalized.quantity`: number
- `normalized.side`: string (`buy` | `sell`) if available; otherwise `null`

**`SnapshotInputs`** (optional: source-provided snapshot-level metrics)

This event type exists only to carry **source-provided** values that map directly into the frozen Regime Engine input contract; `market_data` must not compute these values locally.

- `normalized.timestamp_ms`: int (effective timestamp in ms, as provided by source)
- `normalized.market`: object with keys matching `regime_engine.contracts.snapshots.MarketSnapshot`
- `normalized.derivatives`: object with keys matching `regime_engine.contracts.snapshots.DerivativesSnapshot`
- `normalized.flow`: object with keys matching `regime_engine.contracts.snapshots.FlowSnapshot`
- `normalized.context`: object with keys matching `regime_engine.contracts.snapshots.ContextSnapshot`

If a source cannot provide a sub-object, it must be omitted from the event (do not fabricate values).

#### `DecodeFailure`

When a payload cannot be decoded or structurally validated, emit:

- `event_type`: `DecodeFailure`
- Envelope fields as above (use best-effort `source_id`, `symbol`, `recv_ts_ms`; `exchange_ts_ms` may be `null`)
- `normalized.error_kind`: string (e.g., `decode_error`, `schema_mismatch`, `missing_required_field`)
- `normalized.error_detail`: string (brief, non-sensitive)

### Delivery semantics

- **At-least-once**: events may be delivered more than once.
- **Ordering**: no global ordering guarantee. If ordering exists, it is best-effort per `(source_id, symbol, channel)` only.
- **Backpressure**: if downstream cannot accept events beyond configured limits, `market_data` must fail fast (stop the affected stream/adapter) rather than silently dropping events.
- **Immutability**: once emitted, an event’s `raw_payload` and `normalized` content must never be mutated.

### Versioning & backward compatibility

- The envelope `schema` and `schema_version` are immutable for `v1`.
- Backward-compatible changes are **additive only**:
  - Adding optional envelope fields is allowed.
  - Adding new `event_type` values is allowed.
  - Adding new optional keys within `normalized` for an existing `event_type` is allowed.
- Breaking changes require `schema_version` increment and explicit downstream review (no silent behavior changes).

---

## Dependency Boundaries

### Allowed dependencies (inside `market_data`)

- Transport clients for external sources (WS/REST libraries, vendor SDKs).
- Parsing/serialization libraries for decoding payloads.
- A minimal, local definition of the `RawMarketEvent` contract and sink interface.

### Downstream dependencies

- Downstream layers may depend on `market_data` **contracts only** (event schema + sink interface).
- Downstream layers must not rely on vendor-specific payload fields in `raw_payload`; only the canonical envelope and `normalized` fields are supported contracts.

### Forbidden coupling

- `market_data` must not import or depend on downstream layer packages.
- `market_data` must not contain regime logic, strategy logic, or any computation that attempts to recreate or approximate Regime Engine behavior.
- `market_data` must not hide state that affects which events are emitted based on downstream outcomes (no feedback loops).

---

## Invariants & Guarantees

- Every emitted event includes: `source_id`, `symbol`, `recv_ts_ms`, and `raw_payload`.
- If the source provides a timestamp, it is emitted as `exchange_ts_ms` unchanged (unit-normalized to ms only).
- Normalized fields are **direct mappings** from the source payload:
  - No derived indicators (e.g., ATR, z-scores, slopes) may be computed locally.
  - No aggregation/bucketing beyond using source-provided candle intervals.
- Errors are explicit:
  - Decode/schema failures must emit `DecodeFailure`; silent drops are forbidden.
  - Transport disconnects must be observable (see Operational Behavior).

---

## Operational Behavior

### Lifecycle

- **Start**: load configuration, initialize adapters per source, and begin ingestion.
- **Run**: adapters emit `RawMarketEvent` continuously until stopped.
- **Stop**: attempt clean shutdown (close connections). No requirement to flush beyond the sink contract.

### Retry / backoff

- On transient transport failures, adapters retry with a bounded, deterministic backoff schedule:
  - Minimum delay, maximum delay, and maximum attempts/time window are configuration inputs.
- On repeated failure beyond limits, the adapter transitions to a failed state and stops emitting for that stream.

### Observability (contractual)

**Structured logs (minimum fields)**

- `source_id`, `symbol` (when known), `event_type` (when known), `exchange_ts_ms`, `recv_ts_ms`
- For failures: `error_kind`, `error_detail` (non-sensitive), and a stable adapter/stream identifier

**Metrics (minimum set)**

- Events: count by `source_id` and `event_type`
- Decode failures: count by `source_id` and `error_kind`
- Transport: current connection state per adapter/stream; reconnect count
- Latency: distribution of `(recv_ts_ms - exchange_ts_ms)` when `exchange_ts_ms` is present
- Backpressure: count/time spent blocked on downstream sink writes

**Tracing (optional but supported)**

- A span per received payload and per publish attempt, correlated by a stable receipt identifier if available.

---

## Non-Goals

- No candle construction or rebucketing from trades.
- No timestamp alignment to engine cadence boundaries.
- No missing-data inference or gap-filling.
- No data correction, smoothing, filtering, or de-duplication beyond emitting receipts.
- No persistence/replay store (handled downstream).
- No regime/pattern/trading logic of any kind.
