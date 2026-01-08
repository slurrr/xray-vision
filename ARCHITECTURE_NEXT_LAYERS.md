# Regime Engine Integration — Post‑v1.0 Architecture

## Status

- **Regime Engine v1.0 is complete and frozen**
- Phases 0–9 are finalized
- Engine internals, contracts, and semantics **MUST NOT change**
- All interaction with the engine is via its **public API only**:

  ```text
  run(snapshot_inputs) -> RegimeOutput
  run_with_hysteresis(snapshot_inputs, state, config) -> HysteresisState
  ```

This document defines the architecture of all layers _around_ the Regime Engine.
It is authoritative for planning and implementation.

---

## Core Principles (Non‑Negotiable)

1. **Single Source of Truth**

   - The Regime Engine owns:

     - Snapshot building
     - Timestamp alignment
     - Missing‑data semantics
     - Snapshot validation
     - Regime truth
     - Explainability
     - Hysteresis
     - Evaluation

2. **Strict Separation of Concerns**

   - Market data layers fetch **raw data only**
   - No inference, regime logic, alignment, or validation outside the engine

3. **Determinism & Replay Safety**

   - All raw inputs are immutable and replayable
   - Engine outputs must be reproducible from raw logs

4. **No Feedback Loops (Shadow Mode)**

   - Engine outputs must not affect upstream data behavior

---

## High‑Level Layering

```
Market Data Adapters
        ↓
Raw Event Bus
        ↓
RawInputBuffer (append‑only, replayable)
        ↓
Orchestrator (cadence + delivery only)
        ↓
Regime Engine (public API)
        ↓
Output Sinks (shadow‑mode observers)
```

---

## 1. Market Data Layer (Inputs Only)

### Responsibilities

- Fetch raw data from exchanges or vendors (REST / WS)
- Decode transport formats (JSON, protobuf, etc.)
- Normalize **shape**, not meaning
- Preserve original payloads and timestamps

### Prohibited

- Feature computation
- Alignment or bucketing
- Missing‑data handling
- Validation or correction
- Any regime, trading, or strategy logic

### Adapter Definition

An adapter is a **dumb pipe with receipts**.

Each emitted event MUST include:

- `exchange_ts` — timestamp from source payload
- `recv_ts` — local receipt timestamp
- `source_id` — exchange / venue identifier
- `raw_payload` — untouched original payload
- `normalized_fields` — minimal field mapping only

### Canonical Raw Event Types (Examples)

- `TradeTick`
- `BookTop` / `BookDelta`
- `Candle`
- `FundingRate`
- `OpenInterest`
- `IndexPrice` / `MarkPrice`

Adapters do **not** decide if data is late, missing, invalid, or aligned.
They only report what was observed.

---

## 2. Feed Scheduling & Cadence

### Two Clocks

- **Wall clock** — process execution time
- **Exchange clock** — timestamps embedded in raw data

### Scheduler Responsibilities

- Maintain polling cadence / WS subscriptions
- Define **engine invocation cadence** (timer or boundary‑based)
- Trigger deterministic "snapshot cuts"

### Scheduler Prohibitions

- No candle bucketing
- No timestamp alignment
- No inference about completeness

The scheduler decides _when to call the engine_, not _what the data means_.

---

## 3. RawInputBuffer

### Purpose

- Act as a staging and replay layer between adapters and engine
- Preserve all observed raw data immutably

### Requirements

- Append‑only ingestion
- No in‑place mutation
- Retain:

  - `exchange_ts`
  - `recv_ts`
  - monotonic ingestion sequence

### Capabilities

- Materialize raw inputs for a given engine invocation cut
- Support deterministic replay from persisted logs

The buffer is **not a validator** and **not a snapshot builder**.

---

## 4. Orchestrator

### Responsibilities

- Trigger engine runs on a fixed cadence or boundary
- Assemble `snapshot_inputs` from RawInputBuffer
- Call engine **public API only**
- Persist outputs and minimal run metadata

### Invocation Modes

**Timer‑Driven**

- Run every `T` seconds
- Cut raw inputs mechanically

**Boundary‑Driven**

- Run on known time boundaries (e.g., 3m close + delay)
- No semantic alignment performed

### Prohibitions

- No feature computation
- No validation
- No trading or execution logic

---

## 5. Runtime Dataflow

```
Adapters
  → Raw Event Bus
    → RawInputBuffer
      → Orchestrator
        → RegimeEngine.run(...)
          → RegimeOutput / HysteresisState
            → Output Sinks
```

All data flows in one direction.

---

## 6. Output Sinks (Shadow Mode)

### Allowed

- Append‑only logs
- Dashboards / visualizers
- Metrics (latency, missing data rates)
- Non‑trading alerts ("regime changed", "validation failed")

### Prohibited

- Trade execution
- Strategy evaluation
- Upstream feedback

---

## 7. Guardrails

### Code‑Level

- Separate packages or repos:

  - `market_data/`
  - `orchestrator/`
  - `regime_engine/` (frozen dependency)
  - `consumers/`

### Interface‑Level

- Engine inputs: `snapshot_inputs` only
- Engine outputs: `RegimeOutput` / `HysteresisState` only

### Behavioral

- Raw data is immutable
- No derived fields outside engine
- No hidden state in adapters

### Testing

- Replay determinism tests
- Adapter contract tests
- Orchestrator cadence stability tests

---

## 8. Shadow‑Mode Plan

### Phase 0 — Single Symbol

- One venue, one symbol
- Persist raw events and engine outputs

### Phase 1 — Replay Verification

- Re‑run engine from raw logs
- Outputs must match original runs

### Phase 2 — Scale Breadth

- Add symbols and venues incrementally
- Measure quality, do not fix it upstream

### Phase 3 — Observer Alerts

- Notify on regime changes, missing data, hysteresis flips
- Still no execution or strategy logic

---

## Mental Model

- **Adapters**: collect receipts
- **Buffer**: store receipts
- **Orchestrator**: choose when to hand receipts to the engine
- **Engine**: decide what receipts mean
- **Consumers**: observe verdicts, never steer the process

---

## Scope Control

This document is intentionally limited to:

- Correctness
- Boundaries
- Long‑term safety

Execution, trading, and strategy layers are **explicitly out of scope**.

---

## 9. Composer (Deterministic Input Assembly)

### Purpose

The Composer layer deterministically assembles **engine-ready inputs** from raw market events
selected by the Orchestrator.

It exists to make downstream inference possible **without violating the Regime Engine’s
single-source-of-truth guarantees**.

The Composer performs **no inference, no belief updates, and no hysteresis**.

---

### Responsibilities

- Consume deterministic raw input cuts selected by the Orchestrator
- Perform **pure, deterministic feature computation** (numeric descriptions only)
- Construct **stateless evidence opinions** derived from features
- Assemble immutable, replayable engine input snapshots
- Guarantee replay equivalence from identical raw inputs

---

### Explicit Non-Responsibilities

The Composer MUST NOT:

- Maintain belief, regime state, or hysteresis
- Authoritatively classify regimes
- Apply validation, vetoes, or permissions
- Gate downstream execution
- Perform strategy, pattern detection, or analysis logic
- Mutate or reinterpret raw payloads
- Introduce feedback loops upstream

---

### Architectural Position

  Market Data Adapters
  ↓
  Raw Event Bus
  ↓
  RawInputBuffer (conceptual dataflow stage)
  ↓
  Orchestrator (cut selection only)
  ↓
  Composer (feature + evidence assembly)
  ↓
  Regime Engine (belief + hysteresis)
  ↓
  Output Sinks / Consumers

The Composer is the **only layer where numeric feature computation is permitted
outside the Regime Engine**, and only in service of assembling inference inputs.

---

### Computation Classes

The Composer explicitly separates two deterministic computation classes:

#### Feature Computation

- Numeric, descriptive calculations only
  - indicators
  - rolling statistics
  - slopes, ratios, z-scores
- Window-bounded state permitted
- No interpretation or meaning
- No regime logic

Features describe *what was observed*, not *what it means*.

#### Evidence Construction

- Stateless observers that interpret features
- Emit sparse, opinionated evidence
  - direction
  - strength
  - confidence
- Includes classical or heuristic regime observers
- Evidence is advisory input to the Regime Engine, never truth

---

### Determinism & Replay Requirements

- Identical raw inputs and cut boundaries MUST produce identical composed outputs
- Feature computation MUST be pure and deterministic
- Evidence construction MUST be stateless
- Composer outputs MUST be replay-safe from raw logs alone

---

### Interface Contract

The Composer emits immutable inputs suitable for Regime Engine invocation:

- Feature snapshots (dense, numeric)
- Evidence snapshots (sparse, opinionated)

The Orchestrator remains responsible for invoking the Regime Engine using these
composed inputs; the Composer never performs invocation itself.

---

### Mental Model

- **Market Data**: collect receipts
- **Orchestrator**: store receipts and choose *when* to evaluate
- **Composer**: assemble *what* to evaluate
- **Regime Engine**: decide *what it means*
- **Consumers**: observe outcomes, never steer inference


---
