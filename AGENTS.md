# AGENTS.md — Regime Engine Canonical Rules

This file defines **mandatory constraints** for all non-human contributors
(e.g., Codex, automation, scripted refactors).

These rules exist to prevent architectural drift.

---

## Project Identity

This repository implements the **Regime Engine** for xray-vision.

The Regime Engine is the **truth layer** of the system.
It explains *why* price is moving and what behaviors are allowed.

It does NOT:
- Generate trade signals
- Scan patterns
- Execute trades
- Perform strategy logic

Downstream systems may **not** recompute regime logic.

---

## Source of Truth

- `spec.md` defines the canonical system truth:
  - Regime taxonomy
  - Input/output contracts
  - Scoring principles
  - Explainability requirements
- If code or tasks conflict with `spec.md`, the spec wins.

---

## Architectural Boundaries

- `engine.py` is the **public, stable API**
  - Downstream code depends only on this
  - Breaking changes are forbidden without explicit approval

- `pipeline.py` is **internal**
  - Implementation may change freely
  - Must not leak downstream

- `contracts/` contains **frozen dataclasses**
  - Changes here are breaking changes
  - No business logic is allowed in contracts

---

## Phase Discipline (Mandatory)

Development proceeds strictly in order:

1. Contracts & snapshot builder  
2. Feature computation  
3. Regime scoring  
4. Hard vetoes  
5. Resolution & confidence  
6. Explainability  
7. Hysteresis & memory  
8. Logging, replay, evaluation  
9. Integration readiness  

Later phases may **not** be partially implemented early.

If a phase is incomplete, stop.

Phase 0 contracts are frozen. Agents must not modify snapshot contracts,
missing-data semantics, alignment rules, or serialization format.

---

## Determinism & Explainability

- All regime inputs are frozen dataclasses
- Missing data must be explicit and propagated
- Regime outputs must include:
  - drivers
  - invalidations
  - permissions
- Empty explainability fields invalidate the output

Snapshot replay and JSONL logging are mandatory.

Wrong is acceptable. Vague is not.

---

## Change Discipline

- Regime taxonomy is locked
- Additions require removals
- Downstream refactors are not allowed
- Convenience changes that weaken constraints are forbidden
