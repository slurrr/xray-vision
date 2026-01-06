# AGENTS — market_data implementation

This file applies **only** to the `market_data` layer. It is not a project‑wide policy and must not be copied upward.

`market_data` is a *transport + normalization* layer. Treat it as a dumb, auditable pipe. If logic feels clever, it is probably wrong.

---

## 1. Scope Lock

This implementation is constrained by:

* `Planning/market_data/spec.md`
* `Planning/market_data/tasks.md`

These documents are authoritative. This layer:

* **MUST** emit raw, immutable events
* **MUST NOT** compute indicators, aggregates, alignments, regimes, or opinions
* **MUST NOT** infer, fix, smooth, dedupe, or enrich data

If a change is not explicitly allowed by the spec, do not implement it.

---

## 2. Design Posture

* **Deterministic**: same input → same output
* **Stateless**: no hidden memory affecting emission
* **Additive only**: no destructive transforms
* **Observable**: every failure is explicit

Think: *shipping receipts, not conclusions*.

---

## 3. Hard Invariants (Do Not Violate)

* `raw_payload` is preserved byte‑for‑byte
* `recv_ts_ms` is assigned exactly once, at receipt
* `exchange_ts_ms` is source‑provided only (unit‑normalized to ms)
* `normalized` fields are direct mappings only
* Decode / schema failures emit `DecodeFailure` (never silent drop)
* Delivery is **at‑least‑once**; duplicates are allowed

Violating any of the above is a bug.

---

## 4. Forbidden Behaviors

Do **not** implement:

* Candle construction or rebucketing
* Timestamp alignment or windowing
* Missing‑data inference or gap filling
* Value correction, smoothing, filtering, or de‑duplication
* Regime, signal, confidence, or trading logic
* Downstream feedback or adaptive emission

If downstream needs it, it does **not** belong here.

---

## 5. Implementation Order (Strict)

Follow `tasks.md` phases exactly:

1. **Phase 0 — Contracts** (freeze first)
2. **Phase 1 — Adapter framework**
3. **Phase 2 — Canonical event coverage**
4. **Phase 3 — Observability**
5. **Phase 4 — Determinism & safety**
6. **Phase 5 — Readiness gate**

Do not skip ahead. Do not partially implement later phases.

---

## 6. Adapter Rules

Each adapter:

* Owns exactly one `(source_id, channel)` stream
* Emits events through the common ingestion pipeline
* Has bounded, deterministic retry/backoff
* Fails fast on sustained backpressure

Adapters may differ in transport, **never** in semantics.

---

## 7. Error Handling Policy

* Transport errors → logged + retried per config
* Decode / structural errors → `DecodeFailure` event
* Sink backpressure exceeded → stop the affected adapter

Errors must be observable and attributable. Silence is failure.

---

## 8. Dependency Rules

Allowed:

* Transport clients (REST / WS)
* Parsing / serialization libs
* Local `RawMarketEvent` contract

Forbidden:

* Imports from downstream layers
* Regime engine logic or helpers
* Strategy, analytics, or trading utilities

This layer stands alone.

---

## 9. Testing Expectations

Tests must prove:

* Envelope fields are always present
* Required `normalized` keys exist per `event_type`
* `raw_payload` is unchanged
* Malformed inputs emit `DecodeFailure`
* Serialization is stable and immutable

No snapshot tests of derived values — there are none.

---

## 10. Change Discipline

* Additive changes only unless `schema_version` is bumped
* New `event_type` requires explicit spec update
* Breaking changes require downstream review before merge

If unsure: stop and update the spec first.

---

## 11. Mental Model

If someone asks:

> “Can market_data tell me *what’s happening*?”

The correct answer is:

> “No. It tells you *what arrived*.”
