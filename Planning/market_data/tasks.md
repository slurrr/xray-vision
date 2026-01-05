# market_data — tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order; do not begin later phases until earlier phases are complete and reviewed.

## Phase 0 — Contracts (Freeze First)

1. Create the `RawMarketEvent` v1 contract exactly as specified in `Planning/market_data/spec.md`.
2. Define the authoritative list of `event_type` values supported in v1 and their required `normalized` keys.
3. Define the minimal sink interface (“Raw Event Bus” writer) that `market_data` targets, including:
   - at-least-once delivery expectation
   - backpressure signaling behavior (block vs fail)
4. Define the configuration contract for `market_data` inputs:
   - `source_id` registry
   - symbol mapping rules (source-native → canonical `symbol`)
   - enabled channels per source
   - operational limits (timeouts, retry bounds, backpressure limits)
5. Document versioning rules and an explicit process for proposing breaking changes (schema_version increment + downstream review).

## Phase 1 — Adapter Framework (Acquisition + Delivery)

6. Define an adapter lifecycle model (start/run/stop) and a per-source/per-stream supervision model.
7. Implement a common ingestion pipeline that every adapter uses:
   - receipt timestamping (`recv_ts_ms`)
   - raw payload preservation (`raw_payload`)
   - structural validation for the declared `event_type`
   - emission to the sink with explicit failure handling
8. Implement deterministic retry/backoff behavior per adapter/stream from configuration.
9. Implement backpressure handling per the spec (no silent drops; fail-fast once limits are exceeded).

## Phase 2 — Canonical Event Coverage

10. Implement support for emitting each required canonical event type for v1 (as applicable per source):
    - `TradeTick`, `BookTop` and/or `BookDelta`, `Candle`, `FundingRate`, `OpenInterest`, `MarkPrice`, `IndexPrice`
11. Implement optional `SnapshotInputs` emission only for sources that provide those values directly (no local computation).
12. Implement `DecodeFailure` emission paths for:
    - undecodable payloads
    - schema/required-field mismatches
    - parse failures for required normalized keys

## Phase 3 — Observability (Contract Enforcement)

13. Implement structured logging with the required minimum fields for:
    - successful event emission (at a sampled rate if needed)
    - decode failures
    - transport state changes (connect/disconnect/retry/fail)
14. Implement the minimum metrics set from the spec, including:
    - per-event counts
    - decode failure counts
    - connection state + reconnect counters
    - exchange-to-receipt lag distribution
    - sink backpressure time/count

## Phase 4 — Determinism & Safety Checks (Layer-Local)

15. Add contract-level tests that validate:
    - envelope required fields are always present
    - required `normalized` keys exist for each `event_type`
    - `raw_payload` is preserved unchanged
    - `DecodeFailure` is emitted instead of silent drops on malformed inputs
16. Add replay safety checks for emitted events (immutability + stable serialization).
17. Verify the layer does not depend on downstream packages and does not import `regime_engine` for anything other than referencing the frozen field names in documentation/tests.

## Phase 5 — Readiness Gate

18. Produce a short “contract freeze” note stating:
    - the finalized `RawMarketEvent` v1 schema
    - the supported `event_type` list
    - configuration keys required to run a single source for a single symbol
19. Confirm scope compliance against `Planning/market_data/spec.md` Non-Goals before proceeding to the next layer.
