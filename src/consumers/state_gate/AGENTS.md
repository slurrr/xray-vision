# AGENTS — consumers/state_gate implementation

This file applies **only** to the `consumers/state_gate` layer. It is not a project‑wide policy and must not be copied upward.

`state_gate` is a *deterministic gating + state materialization* layer. Treat it as a strict interpreter of orchestrator outputs. If logic feels discretionary, it is wrong.

---

## 1. Scope Lock

This implementation is constrained by:

* `Planning/consumers/state_gate/spec.md`
* `Planning/consumers/state_gate/tasks.md`

These documents are authoritative. This layer:

* **MUST** emit explicit, versioned gating decisions
* **MUST** maintain replayable per‑symbol state derived only from orchestrator outputs
* **MUST NOT** generate signals, patterns, alerts, or user‑facing conclusions
* **MUST NOT** reinterpret, modify, or “correct” Regime Engine outputs

If a change is not explicitly allowed by the spec, do not implement it.

---

## 2. Design Posture

* **Deterministic**: same input stream + config → same state and outputs
* **Replayable**: all decisions derivable from persisted inputs and config
* **Explicit**: gate open/closed is always stated, never implied
* **Fail‑closed**: uncertainty closes the gate

Think: *traffic light controller, not a driver*.

---

## 3. Hard Invariants (Do Not Violate)

* Gate decisions are binary: `OPEN` or `CLOSED`
* Exactly one `GateEvaluated` is emitted per `(symbol, run_id)`
* State transitions are append‑only and persisted before emission
* Regime outputs and hysteresis decisions are treated as authoritative facts
* Idempotent handling of duplicated inputs is mandatory
* Delivery is **at‑least‑once**; duplicates are allowed

Violating any of the above is a bug.

---

## 4. Forbidden Behaviors

Do **not** implement:

* Market feature computation or regime inference
* Pattern, signal, confidence, or strategy logic
* Consumer‑specific branching or prioritization
* Heuristic interpretation of regime meaning
* Wall‑clock‑based decisions or timeouts
* Downstream feedback or adaptive behavior

If downstream needs it, it does **not** belong here.

---

## 5. Implementation Order (Strict)

Follow `tasks.md` phases exactly:

1. **Phase 0 — Contracts** (freeze first)
2. **Phase 1 — Input consumption & run assembly**
3. **Phase 2 — State machine**
4. **Phase 3 — Gating evaluation**
5. **Phase 4 — Persistence & replay safety**
6. **Phase 5 — Observability & health**
7. **Phase 6 — Failure isolation**
8. **Phase 7 — Determinism tests**
9. **Phase 8 — Readiness gate**

Do not skip ahead. Do not partially implement later phases.

---

## 6. Adapter Rules

Each logical input stream:

* Consumes `orchestrator_event` v1 only
* Assembles inputs deterministically per `run_id`
* Produces at most one gating decision per run
* Applies per‑symbol ordering safeguards

Differences in upstream timing or duplication must not change semantics.

---

## 7. Error Handling Policy

* Upstream run failures → gate `CLOSED`, state `DEGRADED`
* Persistence failure → transition to `HALTED`
* Output backpressure beyond limits → transition to `HALTED`
* Internal inconsistency → emit `StateGateHalted`

Errors must be observable and must never result in an `OPEN` gate.

---

## 8. Dependency Rules

Allowed:

* `orchestrator_event` v1 input contracts
* Regime Engine output contracts (`RegimeOutput`, `HysteresisDecision`)
* Local persistence primitives (log + snapshot cache)

Forbidden:

* Imports from downstream consumers
* Imports from `market_data` or vendor payloads
* Regime logic, indicators, or strategy helpers

This layer interprets, it does not decide.

---

## 9. Testing Expectations

Tests must prove:

* Exactly‑once `GateEvaluated` per `(symbol, run_id)`
* Deterministic state transitions for promotion, demotion, and reset
* Idempotent handling of duplicated inputs
* Replay produces identical outputs
* Failures never emit `OPEN` gates

No tests for market meaning — there is none here.

---

## 10. Change Discipline

* Additive changes only unless `schema_version` is bumped
* New gating rules require explicit spec updates
* State model changes require downstream review before merge

If unsure: stop and update the spec first.

---

## 11. Mental Model

If someone asks:

> “Can state_gate tell me *what to do*?”

The correct answer is:

> “No. It tells you *whether you are allowed to act*.”
