# AGENTS — composer implementation

This file applies **only** to the `composer` layer. It is not a project-wide policy and must not be copied upward.

`composer` is a *deterministic assembly* layer. Treat it as a mechanical transformer from raw receipts to engine-ready inputs. If logic feels inferential or stateful, it is probably wrong.

---

## 1. Scope Lock

This implementation is constrained by:

* `Planning/composer/spec.md`
* `Planning/composer/tasks.md`
* `Planning/composer/composer_belief_planning_doc.md` (architecture intent)

These documents are authoritative for this layer. This layer:

* **MUST** compute numeric, descriptive features deterministically
* **MUST** construct stateless, advisory evidence opinions deterministically
* **MUST** emit immutable snapshots suitable for replay
* **MUST NOT** perform inference, belief updates, hysteresis, or gating

If a change is not explicitly allowed by the spec, do not implement it.

---

## 2. Design Posture

* **Deterministic**: same inputs + config → same outputs
* **Replayable**: outputs are reconstructible from the raw cut + config alone
* **Stateless**: no hidden cross-run memory; no wall-clock dependence
* **Explicit**: missing data is represented explicitly (no silent defaults)

Think: *snapshot assembly, not market interpretation*.

---

## 3. Hard Invariants (Do Not Violate)

* Composer never mutates or reinterprets `RawMarketEvent.raw_payload`.
* Feature computation is numeric and descriptive only (no labels, no regime truth).
* Evidence construction is stateless and advisory only.
* Composer outputs are immutable and versioned (additive evolution only).
* Ordering is deterministic (stable feature key ordering, stable opinion list ordering).
* No wall-clock reads, randomness, or global mutable state may influence outputs.

Violating any of the above is a bug.

---

## 4. Forbidden Behaviors

Do **not** implement:

* Inference, classification-as-truth, belief updates, or belief persistence
* Hysteresis or any “transition stability” wrappers
* Any gating / allow-deny decisions for downstream execution
* Downstream coupling (behavior changes based on orchestrator/consumer outcomes)
* Data correction: smoothing, de-duplication, gap filling, alignment, or “fixing”
* Semantic timestamp alignment or completeness inference

If downstream needs it, it does **not** belong here.

---

## 5. Implementation Order (Strict)

Follow `Planning/composer/tasks.md` phases exactly:

1. **Phase 0 — Contracts** (freeze first)
2. **Phase 1 — Package scaffolding**
3. **Phase 2 — Feature computation scaffolding**
4. **Phase 3 — Evidence construction scaffolding**
5. **Phase 4 — Determinism & replay tests**
6. **Phase 5 — Readiness gate**

Do not skip ahead. Do not partially implement later phases.

---

## 6. Dependency Rules

Allowed:

* `market_data` contract types (`RawMarketEvent`) as input shape only
* Pure math/array utilities that do not embed market semantics
* Local Composer contracts (`FeatureSnapshot`, `EvidenceSnapshot`, `EvidenceOpinion`)

Forbidden:

* Imports from `orchestrator` or any `consumers/*`
* Any Regime Engine internals (only future integration may use public APIs; composer itself does not invoke the engine)
* Strategy/analytics/trading utilities

This layer assembles inputs; it does not run the engine and it does not interpret outputs.

---

## 7. Testing Expectations

Tests must prove:

* Replay equivalence: same raw cut + config → identical snapshots
* Deterministic ordering of features and opinions
* Evidence observers are stateless (no cross-call memory)
* No wall-clock dependence (timestamps are explicit inputs)

No tests for regime “correctness” belong here — inference is not in this layer.

