# Contract — `EvidenceOpinion` v1

## Purpose

`EvidenceOpinion` is a single, stateless, advisory opinion emitted by an evidence observer in `composer`.

Evidence opinions:

- interpret features (not raw payloads)
- may disagree with each other
- are not authoritative truth
- are inputs to Regime Engine belief update (outside `composer`)

---

## Required Fields

- `type`: string
  - Stable evidence/opinion code (e.g., `flow_pressure`, `participation_expansion`).
  - Codes must be deterministic and stable across runs for explainability and replay.
- `direction`: string enum
  - One of: `UP`, `DOWN`, `NEUTRAL`
  - Semantics: direction of the opinion’s pressure / implication under that observer’s lens.
- `strength`: number
  - Range: `0.0` to `1.0` inclusive
  - Semantics: magnitude of the opinion under that observer’s scale (observer-local; not truth).
- `confidence`: number
  - Range: `0.0` to `1.0` inclusive
  - Semantics: observer’s confidence in its own opinion, based only on feature availability/quality (not belief).
- `source`: string
  - Stable identifier of the emitting observer (for explainability), e.g. `classical_regime_observer_v1`.

All numeric values must be finite (no `NaN`, no infinities).

---

## Determinism Requirements

- An opinion must be a pure, deterministic function of the input `FeatureSnapshot` and observer configuration.
- Observers must be stateless: no cross-run memory, no wall-clock reads, no randomness.

---

## Additive Evolution Rules

Additive changes allowed within v1:

- add new `type` codes and new observer `source` ids
- add optional fields (if needed later for explainability)

Breaking changes require explicit versioning.

