# AGENTS — consumers/dashboards implementation

This file applies **only** to the `consumers/dashboards` layer. It is not a project-wide policy and must not be copied upward.

`consumers/dashboards` is a *presentation + observation* layer. Treat it as a read-only window. If logic feels authoritative or stateful, it is probably wrong.

---

## 1. Scope Lock

This implementation is constrained by:

* `Planning/consumers/dashboards/spec.md`
* `Planning/consumers/dashboards/tasks.md`

These documents are authoritative. This layer:

* **MUST** render a read-only view of system state via the Dashboard View Model (DVM)
* **MUST NOT** influence orchestration, gating, regime, or analysis behavior
* **MUST NOT** emit control signals, decisions, or feedback upstream

If a change is not explicitly allowed by the spec, do not implement it.

---

## 2. Design Posture

* **Deterministic**: same inputs → same DVM snapshot
* **Read-only**: no side effects beyond rendering
* **Contract-first**: DVM is the only renderer input
* **Failure-isolated**: dashboard failure never affects upstream layers

Think: *instrument panel, not flight controls*.

---

## 3. Hard Invariants (Do Not Violate)

* DVM snapshots are immutable once produced
* Renderers consume **only** DVM snapshots (no upstream schemas)
* Upstream inputs are treated as at-least-once and may be duplicated or out of order
* Deterministic ordering rules defined in the DVM contract are always honored
* Missing or optional sections must never crash a renderer

Violating any of the above is a bug.

---

## 4. Forbidden Behaviors

Do **not** implement:

* Any upstream writes, acknowledgements, or control-plane actions
* Regime, signal, confidence, or analytical computation
* Thresholding, scoring, ranking, or inference beyond render-only derivations allowed by the spec
* Hidden state that alters rendered meaning over time
* Renderer dependence on upstream event schemas or internal analysis objects

If it changes system behavior, it does **not** belong here.

---

## 5. Implementation Order (Strict)

Follow `tasks.md` phases exactly:

1. **Phase 0 — DVM Contract** (freeze first)
2. **Phase 1 — DVM Builder**
3. **Phase 2 — Renderer Interface**
4. **Phase 3 — TUI Renderer (v1)**
5. **Phase 4 — Observability & Isolation**
6. **Phase 5 — Determinism & Compatibility**
7. **Phase 6 — Readiness Gate**

Do not skip ahead. Do not partially implement later phases.

---

## 6. Builder Rules

The DVM builder:

* Consumes upstream events only to construct the DVM snapshot
* Tolerates duplicates and out-of-order delivery without crashing
* Maintains only the minimal prior-snapshot state explicitly permitted by the spec (e.g., for render-only hysteresis summaries)
* Produces **full** DVM snapshots only (no partial/delta outputs in v1)

The builder observes; it never decides.

---

## 7. Error Handling Policy

* Upstream ingest issues → surfaced in DVM telemetry and system status
* Builder failures → degrade rendering, never upstream behavior
* Renderer failures → isolated; builder continues producing DVM snapshots

Errors must be visible to humans. Silence is failure.

---

## 8. Dependency Rules

Allowed:

* DVM schema and builder utilities
* Upstream event contracts **for the builder only**
* Presentation/runtime libraries for TUI or web rendering

Forbidden:

* Imports from analysis_engine internals
* Imports from orchestration control-plane interfaces
* Renderer access to raw upstream event streams or logs

This layer depends downward only.

---

## 9. Testing Expectations

Tests must prove:

* DVM schema compliance and required sections
* Deterministic ordering of all arrays
* Stable DVM output from a fixed input event log + config
* Renderer tolerance of missing optional fields and unknown future fields

Do not test analytical correctness — none exists here.

---

## 10. Change Discipline

* Additive changes only within a fixed `dvm_schema_version`
* Any breaking change requires a version bump and renderer review
* New render-only derivations must be explicitly allowed by the spec

If unsure: stop and update the spec first.

---

## 11. Mental Model

If someone asks:

> “Can dashboards affect what the system does?”

The correct answer is:

> “No. They show you what the system already decided.”
