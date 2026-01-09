# AGENTS.md — Regime Engine Canonical Rules

This file defines **mandatory constraints** for all non-human contributors
(e.g., Codex, automation, scripted refactors).

These rules exist to prevent architectural drift.

---

## Project Identity

This repository implements the **Regime Engine** for xray-vision.

The Regime Engine is the **truth layer** of the system.
It explains _why_ price is moving and what behaviors are allowed.

It does NOT:

- Generate trade signals
- Scan patterns
- Execute trades
- Perform strategy logic

Downstream systems may **not** recompute regime logic.

> Architectural Clarification (Authoritative)
>
> The Regime Engine’s single source of truth is **RegimeState** (belief).
>
> Regime labels emitted by the engine are **derived projections** of belief,
> not independently authoritative truth.
>
> Any classical or heuristic regime classification logic is treated as
> **evidence** that updates belief, not as a parallel source of authority.

EvidenceSnapshot is the sole ingress for upstream signals, including Composer.
All opinions are treated uniformly as belief evidence.

Hysteresis is defined exclusively over belief (RegimeState) and produces
HysteresisState as the sole authoritative output; legacy decision-based
hysteresis is deprecated.

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

Phase status (Authoritative):

- Phases 0–3 (belief refoundation): **Frozen**
- Phase 4 (belief-first hysteresis & memory): **Authorized**
- Phases 5–9: **Frozen**

Agents may modify the Regime Engine **only** to implement Phase 4
as specified in the canonical belief-first architecture.
All other phases are locked.

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

---

## Development Environment (Invariant)

- This project uses a local virtual environment located at `.venv/`.
- All Python execution, testing, and tooling must run inside this environment.
- The package must be installed in editable mode before running tests:
  - `pip install -e .`
- Do not assume system Python is usable.
- Do not invoke `python`, `pip`, or test runners outside the active `.venv`.
- Do not modify Python version constraints unless explicitly instructed.

If imports fail, the correct fix is to activate `.venv` and ensure the editable install,
not to modify sys.path or test files.
