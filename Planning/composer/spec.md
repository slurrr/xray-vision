# composer — spec (Phase 0 contract freeze)

## Architectural Inversion (Authoritative)

This subsystem exists to support a system-wide architectural shift:

FROM:
- Regime classified as truth
- Belief implemented as a hysteresis wrapper around regime output

TO:
- Regime represented as belief (RegimeState)
- Hysteresis as inertia on belief mass
- Regime labels exposed only as projections of belief

This inversion is intentional, foundational, and non-negotiable.
All Composer responsibilities exist solely to support this model.

## Purpose & Scope

`composer` is the deterministic assembly layer that transforms **raw market receipts** into **engine-ready inference inputs**.

It exists because:

- Raw payloads cannot carry belief inputs.
- Feature math cannot live in ingestion (`market_data`).
- Inference (belief update + hysteresis) must remain exclusively inside the Regime Engine.

`composer` must never perform inference. It computes **features** (numeric descriptions) and constructs **evidence** (stateless opinions) and emits immutable snapshots.

This spec defines only interface semantics and contracts. It intentionally does not prescribe implementation details.

---

## Core Responsibilities

### 1) Feature Computation (Numeric, Descriptive)

Given a deterministic cut of `RawMarketEvent` inputs, `composer` computes a dense set of numeric features such as:

- indicators
- slopes / z-scores
- rolling statistics
- ratios
- structure measurements

Feature computation properties:

- deterministic
- numeric
- window-bounded computation is allowed, but **must be fully derivable from the provided cut**
- no interpretation, no classification, no regime truth

### 2) Evidence Construction (Opinionated, Stateless, Advisory)

From the computed `FeatureSnapshot`, `composer` constructs a sparse set of evidence opinions:

- opinions have `type`, `direction`, `strength`, `confidence`, and `source`
- each opinion is deterministic and stateless
- opinions may disagree; no opinion is authoritative truth

Evidence properties:

- deterministic
- stateless (no cross-run memory)
- advisory input to the Regime Engine belief updater

### 3) Snapshot Assembly (Immutable, Replayable)

`composer` emits:

- `FeatureSnapshot` v1 (dense numeric features)
- `EvidenceSnapshot` v1 (sparse evidence opinions)

Both snapshots are immutable and replay-safe.

---

## Explicit Non-Goals (Prohibited)

`composer` MUST NOT:

- perform inference, belief updates, or maintain belief state
- implement hysteresis, transition stability, or any belief inertia
- gate downstream execution or emit allow/deny decisions
- invoke the Regime Engine (no `run(...)` calls from composer)
- align timestamps for market meaning, infer completeness, gap-fill, or “fix” data
- smooth/filter/deduplicate/correct values beyond required parsing of normalized fields
- depend on orchestrator or consumer internals or behavior (no downstream coupling)

---

## Inputs & Outputs (Contracts)

### Inputs

`composer` consumes a deterministic **cut** of raw receipts (selected upstream; cut selection is not a composer concern):

- `raw_events`: an ordered sequence of `market_data.contracts.RawMarketEvent` that pertain to the target `(symbol, engine_timestamp_ms)` invocation.
- `symbol`: canonical instrument identifier.
- `engine_timestamp_ms`: the engine-time timestamp for which snapshots are being assembled.

Contract assumptions:

- input delivery is at-least-once upstream; duplicates may be present in `raw_events`
- `RawMarketEvent.raw_payload` is treated as opaque and never mutated or reinterpreted
- only contract-level envelope and `normalized` fields are used

### Outputs

`composer` outputs two immutable, versioned snapshots:

1. `FeatureSnapshot` v1
2. `EvidenceSnapshot` v1 (containing `EvidenceOpinion` v1 entries)

The authoritative contract definitions for these types are:

- `Planning/composer/contracts/feature_snapshot.md`
- `Planning/composer/contracts/evidence_opinion.md`
- `Planning/composer/contracts/evidence_snapshot.md`

### External (Additive) Contract: `RegimeState` v1

`RegimeState` is the authoritative belief state used by the Regime Engine. It is included here only as an additive cross-layer contract referenced by the architecture plan; `composer` does not own or mutate it.

- Definition: `Planning/composer/contracts/regime_state.md`

---

## Determinism & Replay Semantics

`composer` is replay-safe if and only if:

- for identical `(raw_events, symbol, engine_timestamp_ms)` inputs and identical composer configuration, it produces identical `FeatureSnapshot` and `EvidenceSnapshot` outputs (byte-for-byte stable serialization if serialized)
- feature sets and opinion lists are deterministically ordered (no hash-order dependence)
- no wall-clock reads, randomness, or implicit global state can influence outputs

Missingness must be represented explicitly (e.g., `None`/null values) rather than silently defaulting or skipping features/opinions.

---

## Versioning & Stability

- `FeatureSnapshot` v1 and `EvidenceSnapshot` v1 are additive-only:
  - adding optional fields is allowed
  - adding new feature keys / new opinion types is allowed
- breaking changes require a schema-version increment and explicit downstream review

---

## Dependency Boundaries

Allowed dependencies:

- `market_data` contract types (`RawMarketEvent`) as input shape only
- composer-local contract types (`FeatureSnapshot`, `EvidenceSnapshot`, `EvidenceOpinion`)
- pure, deterministic math utilities

Forbidden dependencies:

- `orchestrator` implementation internals (composer is not wired yet)
- any `consumers/*` packages
- Regime Engine internals or non-public APIs

---

## Public Entrypoints (Interface Semantics)

The public API of `composer` is a single composition entrypoint:

- `composer.compose(...) -> (FeatureSnapshot, EvidenceSnapshot)`

Semantics:

- the function is pure with respect to its inputs and configuration
- it may compute window-bounded features only from the provided `raw_events`
- it must never call the Regime Engine
