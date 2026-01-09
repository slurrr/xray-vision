# market_data — Binance channel coverage v1 tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order; do not begin later phases until earlier phases are complete and reviewed.

This plan is constrained by:

- `Planning/market_data/spec.md`
- `Planning/market_data/binance_channel_coverage_v1/spec.md`
- `src/market_data/AGENTS.md`

## Phase 0 — Freeze (Coverage + Endpoint Confirmation)

1. Confirm the minimal composer v1 needs from `Planning/composer/evidence_observers_v1/spec.md` are still:
   - `price`, `vwap`, `atr_z`, `cvd`, `open_interest`
2. Confirm the locked decisions in `Planning/market_data/binance_channel_coverage_v1/spec.md` are accepted for v1:
   - USD‑M futures only (`fstream` WS, `fapi` REST)
   - perpetual USDT symbols only
   - kline interval fixed to `3m` (`180000ms`)
   - open interest via REST `GET /fapi/v1/openInterest` with `poll_interval_ms == 10_000`
   - trade stream fixed to `<symbol>@aggTrade`
3. Freeze the canonical event coverage target for Binance v1:
   - Required: `TradeTick`, `Candle(3m)`, `OpenInterest`
   - Recommended additive: `BookTop`, `BookDelta`, `FundingRate`, `MarkPrice`, `IndexPrice`, `LiquidationPrint`
4. Verify the payload key sets and endpoints listed under “Implementation-Time Confirmations” in the spec against current Binance public docs before writing code (verification only; do not change decisions).

## Phase 1 — Adapter/Config Design (No Behavior Changes Yet)

6. Decide whether to keep `src/market_data/adapters/binance/adapter.py` as:
   - multiple adapter classes in one module (one adapter per canonical channel), or
   - split per-channel adapters into separate modules under `src/market_data/adapters/binance/`.
   Either is acceptable; the invariant is one `(source_id, channel)` stream per adapter.
7. Extend/replace `BinanceTradeAdapterConfig` with explicit per-channel configs, including:
   - `ws_url` / `rest_url`
   - `symbol` and source stream symbol formatting rules
   - timeouts + retry policy + poll cadence (for REST)
8. Define stable `StreamKey.channel` and `RawMarketEvent.channel` naming for Binance:
   - `trades`, `candle_3m`, `book_top`, `book_delta`, `mark_price`, `liquidation`, `open_interest`

## Phase 2 — WebSocket Channel Coverage

9. Implement `TradeTick` emission with:
   - strict `raw_payload` preservation
   - side mapping from maker/aggressor flag when available
   - `source_event_id` when present
   - `channel="trades"`
10. Implement `Candle` (3m) emission from kline stream with:
    - `interval_ms == 180000`
    - `is_final` mapping
    - `channel="candle_3m"`
11. Implement `BookTop` and `BookDelta` emission (if enabled in config).
12. Implement `MarkPrice` stream decoding and emit:
    - `MarkPrice`, `IndexPrice`, `FundingRate` as separate canonical events (shared raw payload)
13. Implement `LiquidationPrint` emission from force-order stream.

## Phase 3 — REST Pollers (Open Interest)

14. Implement an `OpenInterest` poller adapter that:
    - polls `GET /fapi/v1/openInterest?symbol=...` deterministically from config cadence
    - preserves raw response bytes as `raw_payload`
    - parses `openInterest` and optional source timestamp fields
    - emits canonical `OpenInterest` events with `channel="open_interest"`

## Phase 4 — Runtime Wiring (Subscription Coverage)

15. Update the runtime entrypoint to start all enabled Binance adapters for a symbol:
    - trades + candle_3m + open_interest (required)
    - plus optional channels as configured
16. Ensure each adapter stops (fail-fast) on sustained sink backpressure per `Planning/market_data/spec.md`.

## Phase 5 — Contract + Determinism Tests

17. Add per-channel decode tests proving:
    - required `normalized` keys exist for each `event_type`
    - malformed payloads emit `DecodeFailure` (never silent drop)
    - `raw_payload` is preserved unchanged
18. Add replay-safety tests for stable serialization and immutability invariants.
