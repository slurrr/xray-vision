# AGENTS — orchestrator implementation

This file applies **only** to the `orchestrator` layer. It is not a project-wide policy and must not be copied upward.

`orchestrator` is a *coordination + scheduling* layer. Treat it as a deterministic conductor. If logic feels clever or interpretive, it is probably wrong.

---

## 1. Scope Lock

This implementation is constrained by:

* `Planning/orchestrator/spec.md`
* `Planning/orchestrator/tasks.md`

These documents are authoritative. This layer:

* **MUST** turn an unbounded stream of raw receipts into a deterministic, replayable sequence of engine runs and outputs
* **MUST** persist append-only input and run metadata sufficient for replay
* **MUST NOT** compute indicators, features, regimes, patterns, or opinions
* **MUST NOT** infer completeness, align market meaning, gap fill, or “fix” data

If a change is not explicitly allowed by the spec, do not implement it.

---

## 2. Design Posture

* **Deterministic**: same inputs + config → same run plan, cuts, run_ids, and emitted events
* **Replayable**: decisions are reconstructible from persisted logs (inputs + run records)
* **Mechanically correct**: scheduling/cuts are procedural, not semantic
* **Observable**: every failure and retry is explicit

Think: *coordination receipts, not conclusions*.

---

## 3. Hard Invariants (Do Not Violate)

* Buffered raw inputs are stored append-only and **unaltered**
* `ingest_seq` is strictly increasing within the buffer
* Run planning and cut selection are deterministic and replayable from persisted records
* Snapshot selection follows the spec’s deterministic rule exactly (no heuristics)
* Engine invocation uses **public Regime Engine APIs only**
* Outputs are **at-least-once**; duplicates are allowed

Violating any of the above is a bug.

---

## 4. Forbidden Behaviors

Do **not** implement:

* Any feature/indicator computation
* Timestamp alignment, completeness inference, gap filling, or window semantics
* Regime/pattern/signal/confidence logic (beyond invoking the engine)
* Consumer-specific routing rules or behavior changes based on consumer outcomes
* Feedback loops (consumer acks/latency must not change orchestration decisions beyond generic backpressure)

If downstream needs it, it does **not** belong here.

---

## 5. Implementation Order (Strict)

Follow `tasks.md` phases exactly:

1. **Phase 0 — Contracts** (freeze first)
2. **Phase 1 — Data-plane: Input Subscription + Buffering**
3. **Phase 2 — Control-plane: Lifecycle + Scheduling**
4. **Phase 3 — Data-plane: Cut Selection + Engine Invocation**
5. **Phase 4 — Data-plane: Output Publishing (Fan-out)**
6. **Phase 5 — Failure Handling + Backpressure (Domain-Explicit)**
7. **Phase 6 — Control-plane: Observability (Contract Enforcement)**
8. **Phase 7 — Determinism & Replay Validation (Layer-Local)**
9. **Phase 8 — Readiness Gate**

Do not skip ahead. Do not partially implement later phases.

---

## 6. Scheduler Rules

The scheduler:

* Supports exactly two modes: `timer` and `boundary`
* Persists an `EngineRunRecord` for each planned run before attempting execution
* Enforces per-symbol sequential execution (no overlap; monotonic `engine_timestamp_ms`)
* Defines cuts deterministically (no “data looks complete” logic)
* Treats `raw_payload` as opaque; only contract-level envelope/normalized keys may be used

Scheduling decides *when to run*, never *what it means*.

---

## 7. Error Handling Policy

* Ingestion errors → logged + retried per config (bounded, deterministic)
* Buffer append failure → fail-fast to not-ready/degraded (never silent drop)
* If `SnapshotInputs` are missing, orchestrator may proceed using composer-assembled snapshot per spec. Emit `EngineRunFailed` only if neither `SnapshotInputs` nor composer fallback snapshot is available.
* Engine failures → bounded retries, then `EngineRunFailed`, then continue
* Publish failures → bounded retries, then halt/pause scheduling (no silent drop)

Errors must be observable and attributable. Silence is failure.

---

## 8. Dependency Rules

Allowed:

* `market_data` contract types (input schema only)
* Regime Engine public API + frozen payload contracts (`RegimeOutput`, `HysteresisState`)
* Append-only storage primitives (file/local DB/etc.)
* Messaging/broker clients for input subscription and output publishing

Forbidden:

* Imports from consumers
* Regime/pattern logic or helpers beyond the public engine API
* Strategy/analytics/trading utilities
* Vendor payload interpretation beyond the `RawMarketEvent` contract

This layer coordinates; it does not compute.

---

## 9. Testing Expectations

Tests must prove:

* Stable deterministic `run_id` derivation
* Deterministic cut selection from a fixed buffered input log
* Per-symbol ordering guarantees for published outputs
* Replay equivalence from persisted `RawInputBufferRecord` + `EngineRunRecord` logs
* Buffered input events are stored unchanged (immutability)

No tests that assume “market meaning” correctness — this layer does not know meaning.

---

## 10. Change Discipline

* Additive changes only unless schema versions are bumped
* New output `event_type` requires explicit spec update
* Any behavior change must be justified in terms of determinism/replay impact
* Breaking changes require downstream review before merge

If unsure: stop and update the spec first.

---

## 11. Mental Model

If someone asks:

> “Can orchestrator tell me *what’s happening*?”

The correct answer is:

> “No. It tells you *what ran, when it ran, what it used, and what it emitted*.”
