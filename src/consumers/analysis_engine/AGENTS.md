# AGENTS — consumers/analysis_engine implementation

This file applies **only** to the `consumers/analysis_engine` layer. It is not a project-wide policy and must not be copied upward.

`analysis_engine` is an *analysis orchestration* layer. Treat it as a deterministic, gated analysis runner. If logic leaks upstream or downstream, it is wrong.

---

## 1. Scope Lock

This implementation is constrained by:

* `Planning/consumers/analysis_engine/spec.md`
* `Planning/consumers/analysis_engine/tasks.md`

These documents are authoritative. This layer:

* **MUST** consume `state_gate_event` v1 only
* **MUST** execute analysis modules *only when the gate is OPEN*
* **MUST** emit versioned `analysis_engine_event` artifacts
* **MUST NOT** infer regimes, override gating, or execute trades

If a change is not explicitly allowed by the spec, do not implement it.

---

## 2. Design Posture

* **Deterministic**: same inputs + config → same artifacts
* **Gated**: no analysis unless explicitly permitted
* **Composable**: modules are pluggable, core is stable
* **Observable**: every run, artifact, and failure is explicit

Think: *analysis assembly line, not a decision maker*.

---

## 3. Hard Invariants (Do Not Violate)

* Regime Engine outputs are authoritative inputs only
* `state_gate` decisions are never re-interpreted
* Stage order is fixed: signals → detectors → rules → outputs
* Artifact envelopes are immutable once emitted
* Module execution order is deterministic
* `run_id` is the idempotency key

Violating any of the above is a bug.

---

## 4. Forbidden Behaviors

Do **not** implement:

* Regime, hysteresis, or gating logic
* Trade signals, sizing, or execution directives
* Downstream UI, alerting, or notification logic
* Implicit state, hidden memory, or wall-clock dependence
* Cross-module side effects or feedback coupling

If it influences permission or execution, it does **not** belong here.

---

## 5. Implementation Order (Strict)

Follow `tasks.md` phases exactly:

1. **Phase 0 — Contracts** (freeze first)
2. **Phase 1 — Engine shell**
3. **Phase 2 — Registry & plugins**
4. **Phase 3 — Execution planning**
5. **Phase 4 — Configuration**
6. **Phase 5 — Module execution harness**
7. **Phase 6 — Output interfaces**
8. **Phase 7 — Observability & health**
9. **Phase 8 — Determinism & replay tests**
10. **Phase 9 — Readiness gate**

Do not skip ahead. Do not partially implement later phases.

---

## 6. Module Rules

Each module:

* Declares a stable `module_id` and `module_kind`
* Declares explicit artifact dependencies
* Is deterministic and side-effect free (except outputs)
* May maintain state **only** via an explicit, versioned state contract
* Emits artifacts only through the engine

Modules may differ in logic, **never** in contract discipline.

---

## 7. Error Handling Policy

* Module exceptions → `ModuleFailed` event
* Missing dependencies → deterministic module failure
* Partial failures → run completes with `PARTIAL` status
* Engine-level failures → `AnalysisRunFailed`

Failures must be visible, attributable, and replay-safe. Silence is failure.

---

## 8. Dependency Rules

Allowed:

* `state_gate_event` v1 contract
* Regime Engine output payloads as immutable data
* Pure computation libraries
* Delivery primitives for output modules

Forbidden:

* Imports from `market_data`
* Direct vendor or raw market payloads
* Dashboard, alerting, or execution systems
* Any upstream feedback into gating or regime logic

This layer consumes truth; it does not create it.

---

## 9. Testing Expectations

Tests must prove:

* Deterministic execution ordering
* Idempotent handling of duplicate `run_id`
* Correct gating behavior (OPEN vs CLOSED)
* Failure isolation and `PARTIAL` runs
* Stable artifact emission envelopes

Snapshot tests must target contracts, not internal logic.

---

## 10. Change Discipline

* Additive changes only unless `schema_version` is bumped
* New artifact kinds or event types require spec updates
* Module payload changes require `artifact_schema_version` bumps
* Breaking changes require downstream review before merge

If unsure: stop and update the spec first.

---

## 11. Mental Model

If someone asks:

> “Does analysis_engine decide what to trade?”

The correct answer is:

> “No. It emits analysis artifacts when it is explicitly allowed to run.”
