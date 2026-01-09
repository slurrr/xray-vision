# market_data — Binance channel coverage v1 (planning-only)

## Purpose & Scope

This spec defines the **Binance public market data coverage** required for:

1. `composer` Evidence Observers v1 feature needs (`price`, `vwap`, `atr_z`, `cvd`, `open_interest`), and
2. future completeness toward the canonical `market_data` v1 `event_type` set in `Planning/market_data/spec.md`.

It is **planning-only** and does not change any contracts. It defines what Binance can provide via **public WS/REST**, which canonical `RawMarketEvent` types we will emit, and how the data must flow downstream.

This work must remain within `market_data` scope:

- shape-level normalization only
- preserve `raw_payload` byte-for-byte
- no aggregation/bucketing/alignment (beyond using source-provided kline buckets)
- no inference/validation of market meaning

## Locked Decisions (No Open Choices)

These decisions are **frozen for v1** and must not be revisited during implementation.

### Source (Locked)

- **Primary feed:** Binance **USD‑M Perpetual Futures**
  - WS base: `wss://fstream.binance.com/ws`
  - REST base: `https://fapi.binance.com`
- **Spot feeds:** optional/non-blocking and **out of scope** for v1.

### Symbol Universe (Locked)

- Target **USD‑M perpetual** symbols (examples: `BTCUSDT`, `ETHUSDT`).
- Symbol format:
  - uppercase ASCII with no separators (exact Binance symbol string)
  - `quoteAsset == "USDT"` only (USDT‑margined)
- Inclusion rule (authoritative for v1):
  - `contractType == "PERPETUAL"` and `status == "TRADING"` (as reported by Binance exchange metadata)
- Exclusions (out of scope for v1):
  - spot symbols
  - delivery futures / dated contracts
  - COIN‑M futures
  - options and other derivative products

### Candle Interval (Locked)

- Primary kline feed is **3m** only:
  - `interval_ms == 180000`
  - `channel == "candle_3m"`
- No additional candle intervals are permitted in v1.

### Open Interest (Locked)

- Source via REST only:
  - `GET /fapi/v1/openInterest?symbol=<SYMBOL>`
- Poll cadence is deterministic and fixed:
  - `poll_interval_ms == 10_000` (10s) (default for v1)
  - no jitter; schedule must be driven purely by config + a deterministic clock

### Trade Stream Choice (Locked)

- Use USD‑M futures aggregate trade stream:
  - `<symbol>@aggTrade`
- Aggressor-side mapping:
  - If maker flag `m` is present (`m == true` means buyer is maker):
    - `side="sell"` when `m==true` (seller aggressed)
    - `side="buy"` when `m==false` (buyer aggressed)
  - If maker flag is absent/unparseable, emit `side=null` (still emit the event; do not fabricate).

## Architectural Context (Why trades-only is insufficient)

`composer` Evidence Observers v1 requires features:

- `price` (latest / aligned price)
- `vwap` (windowed VWAP)
- `atr_z` (normalized volatility from candles)
- `cvd` (trade-side cumulative delta)
- `open_interest` (derivatives positioning proxy)

Trades alone can support `price`, `vwap`, and `cvd` (if trade aggressor side is available), but **cannot** provide:

- stable OHLC candles for ATR/ATR_z without local bucketing (forbidden in `market_data`)
- open interest (spot) at all; and even for futures it is not in spot trade stream payloads

Therefore, `market_data` must ingest additional Binance channels beyond spot trades.

## Source Choice (Spot vs USD‑M Futures)

Because `open_interest` is required for Evidence Observers v1 confidence/flow features, v1 uses **USD‑M futures only** (see Locked Decisions).

## Required Canonical Coverage (for composer v1)

Minimum coverage to support Evidence Observers v1 without violating `market_data` rules:

1. `TradeTick` (WS)
2. `Candle` at `interval_ms == 180000` (WS kline `3m`)
3. `OpenInterest` (REST poll)

Recommended additive coverage (for future snapshots / broader feature sets):

4. `BookTop` (WS)
5. `BookDelta` (WS)
6. `FundingRate` (WS, futures)
7. `MarkPrice` (WS, futures)
8. `IndexPrice` (WS, futures)
9. `LiquidationPrint` (WS, futures)

## Binance Public API Mapping (Normative)

This section maps Binance public transports to canonical `RawMarketEvent` emission.

### 1) `TradeTick` (WS)

**Binance stream**

- USD‑M futures (locked): `<symbol>@aggTrade`

**Canonical event**

- `event_type`: `TradeTick`
- `channel`: `trades`
- `exchange_ts_ms`: trade time from payload (`T` for both trade/aggTrade payloads)
- `normalized`:
  - `price` ← `p`
  - `quantity` ← `q`
  - `side`:
    - If payload provides aggressor/maker flag (`m` = buyer is maker), map as:
      - `side="sell"` when `m==true` (seller aggressed)
      - `side="buy"` when `m==false` (buyer aggressed)
    - Otherwise emit `side=null`
- Optional receipts:
  - `source_event_id` ← aggregate trade id (`a`) when present

### 2) `Candle` (WS kline)

**Binance stream**

- USD‑M futures (locked): `<symbol>@kline_3m`

**Canonical event**

- `event_type`: `Candle`
- `channel`: `candle_3m`
- `exchange_ts_ms`: kline close time (`k.T`) (preferred) or event time (`E`) if `k.T` absent
- `normalized`:
  - `open` ← `k.o`
  - `high` ← `k.h`
  - `low` ← `k.l`
  - `close` ← `k.c`
  - `volume` ← `k.v`
  - `interval_ms` ← `180000` (from interval string `k.i == "3m"`)
  - `is_final` ← `k.x`

### 3) `BookTop` (WS bookTicker)

**Binance stream**

- USD‑M futures: `<symbol>@bookTicker`

**Canonical event**

- `event_type`: `BookTop`
- `channel`: `book_top`
- `exchange_ts_ms`: event time (`E`) when present; else `null`
- `normalized`:
  - `best_bid_price` ← bid price (`b`)
  - `best_bid_quantity` ← bid qty (`B`)
  - `best_ask_price` ← ask price (`a`)
  - `best_ask_quantity` ← ask qty (`A`)

### 4) `BookDelta` (WS depth)

**Binance stream**

- USD‑M futures: `<symbol>@depth@100ms`

**Canonical event**

- `event_type`: `BookDelta`
- `channel`: `book_delta`
- `exchange_ts_ms`: event time (`E`) when present; else `null`
- `normalized`:
  - `bids` ← `b` (array of `[price, qty]`)
  - `asks` ← `a` (array of `[price, qty]`)
- Optional receipts:
  - `source_seq`: use the final update id (`u`) when present (for replay/debug only; no local sequencing semantics)

### 5–7) `MarkPrice`, `IndexPrice`, `FundingRate` (WS mark price)

**Binance stream**

- USD‑M futures: `<symbol>@markPrice@1s`

**Canonical events**

From each mark-price frame, emit up to three canonical events (each with identical `raw_payload`):

1. `event_type="MarkPrice"`, `normalized={"mark_price": ...}`
2. `event_type="IndexPrice"`, `normalized={"index_price": ...}`
3. `event_type="FundingRate"`, `normalized={"funding_rate": ...}`

Common:

- `channel`: `mark_price` (for all three)
- `exchange_ts_ms`: event time (`E`) when present; else `null`

This avoids overloading a single event_type with unrelated optional keys and preserves the canonical `event_type` split defined in `market_data` v1.

### 8) `LiquidationPrint` (WS forceOrder)

**Binance stream**

- USD‑M futures: `<symbol>@forceOrder`

**Canonical event**

- `event_type`: `LiquidationPrint`
- `channel`: `liquidation`
- `exchange_ts_ms`: order time (`o.T`) when present; else `null`
- `normalized`:
  - `price` ← `o.p`
  - `quantity` ← `o.q`
  - `side` ← `o.S` mapped to `buy|sell` (lowercased), else `null`

### 9) `OpenInterest` (REST poll)

**Binance endpoint**

- USD‑M futures REST: `GET /fapi/v1/openInterest?symbol=<SYMBOL>`

**Canonical event**

- `event_type`: `OpenInterest`
- `channel`: `open_interest`
- `exchange_ts_ms`: source-provided timestamp field if present (e.g., `time`), else `null`
- `normalized`:
  - `open_interest` ← `openInterest`
- `raw_payload`:
  - the exact response body bytes as received over HTTP (no re-serialization)

Polling cadence (locked for v1):

- Poll every `10s` (`poll_interval_ms == 10_000`).
- Poll jitter is forbidden; schedule must be deterministic from config.

## Implementation-Time Confirmations (Unavoidable but Non-Architectural)

These are *verification items* to avoid implementing against the wrong Binance payload shape; they do not reopen any design decisions.

- Confirm futures `aggTrade` payload keys used by the mapper (`p`, `q`, `m`, `T`, `a`) match current Binance public docs.
- Confirm futures `kline_3m` payload keys used by the mapper (`k.o/h/l/c/v`, `k.i`, `k.x`, `k.T`) match current Binance public docs.
- Confirm futures `bookTicker` payload keys used by the mapper (`b`, `B`, `a`, `A`, optional `E`) match current Binance public docs.
- Confirm futures `depth@100ms` payload keys used by the mapper (`b`, `a`, optional `E`, `u`) match current Binance public docs.
- Confirm futures `markPrice@1s` payload keys used by the mapper contain:
  - mark price, index price, and funding rate fields suitable for emitting `MarkPrice`/`IndexPrice`/`FundingRate`.
- Confirm `GET /fapi/v1/openInterest` response contains `openInterest` and whether a source timestamp field is present (`time`); if absent, emit `exchange_ts_ms=null` (allowed by contract).

## End-to-End Dataflow (Required)

1. Binance adapters (WS and REST pollers) emit `RawMarketEvent` via `IngestionPipeline`.
2. Events are published to the runtime bus (`Raw Event Bus`) and appended into `orchestrator.RawInputBuffer`.
3. Orchestrator selects deterministic cuts by `(symbol, ingest_seq range)`.
4. Composer consumes the cut and computes features:
   - `cvd` from `TradeTick.side/quantity`
   - `vwap` from `TradeTick.price/quantity`
   - `atr/atr_z` from `Candle` series (3m)
   - `open_interest` from `OpenInterest` series
5. Composer emits embedded engine evidence per `Planning/composer_to_regime_engine/spec.md` and `Planning/composer/evidence_observers_v1/spec.md`.

`market_data` is not responsible for cut selection, window sizing, or feature computation.

## Non-Goals / Guardrails

- Do not synthesize candles from trades.
- Do not infer liquidation intensity (that is composer/engine work).
- Do not align timestamps to 3m boundaries; only normalize units to ms and forward source timestamps.
- Do not “fill” missing fields by copying from other channels; missingness is allowed downstream.
