# Phase 6 — Dashboard Exposure (Read-Only)

This document is a Phase 6 addendum for `consumers/dashboards`.
It does not replace `Planning/consumers/dashboards/spec.md`; it narrows scope to the Phase 6 deliverable.

## Purpose & Scope

Expose belief state to humans via dashboards in a **read-only**, deterministic, replay-safe way.

Required display elements (read-only):

- Belief distribution (by regime)
- Anchor regime
- Belief trend (derived, render-only)

This phase is strictly observational. Dashboards remain passive.

## Hard Constraints (Non-Negotiable)

- No computation that creates or modifies belief in dashboards.
- No control, mutation, acknowledgements, or feedback upstream.
- No new belief math.
- Deterministic and replay-safe views only.
- Additive changes only unless versioned.
- No persistence beyond what already exists (dashboard builder may hold minimal in-memory prior state for render-only trend).
- No engine or composer changes unless strictly required to expose *existing* state.

## Current Wiring Audit (As-Is)

Dashboards currently ingest:

- `orchestrator_event` v1
  - `EngineRunCompleted.payload.regime_output` → DVM `regime_truth`
  - `HysteresisStatePublished.payload.hysteresis_state` → DVM `hysteresis` (transition/progress)
- `state_gate_event` v1
  - gate status and (when available) `regime_effective`
- `analysis_engine_event` v1
  - analysis summaries and artifacts

What is already complete:

- Gate status display
- Regime truth display (from `RegimeOutput`)
- Hysteresis transition summary display (from `HysteresisState`)
- Effective regime display (from `state_gate_event` when available)

What is not currently possible:

- Belief distribution: no belief state is present in any ingested upstream payload.
- Belief trend: no time-ordered belief snapshots exist in the dashboard input stream.

## Data Requirements & Sources (Phase 6)

### Required upstream data

To render belief distribution and trend without dashboard-side belief computation, the dashboard input stream must include belief state.

Minimum required belief payload per `(symbol, engine_timestamp_ms)`:

- `belief_by_regime`: mapping `Regime.value -> float` for all regimes, summing to 1 (within tolerance).

### Authorized source (minimal exposure; no contract changes)

Use the existing `HysteresisState.debug` field as the carrier for belief state:

- `hysteresis_state.debug["belief_by_regime"]` = mapping `str -> float`

This requires an upstream change to populate `debug` (exposing existing engine state), but does not change frozen contract schemas.

If `debug` or `belief_by_regime` is absent, dashboards must omit belief sections (or mark them as unavailable).

### Anchor regime source

The DVM may derive the displayed anchor regime as a render-only projection from the belief distribution:

- `anchor_regime = argmax(belief_by_regime)` with deterministic tie-break by `Regime` enum order.

This is display-only and must not influence any upstream behavior.

### Trend source

Belief trend is derived render-only using only:

- the current belief snapshot for a symbol, and
- the immediately prior belief snapshot observed by the dashboard builder for that symbol (in-memory only).

No smoothing, memory windows, or persistence is introduced.

If there is no prior snapshot available (first observation after start/reset), trend is `UNKNOWN`.

## DVM Additions (Additive-Only)

Add an optional belief section to the per-symbol DVM snapshot.

### Symbol section additions (optional)

`symbols[].belief` (optional object)

- `anchor_regime`: string (regime value)
- `distribution`: array of `{ regime_name: string, mass: number }`
  - Ordering rule (deterministic): sort by `(mass desc, regime_name asc)`.
- `trend` (optional object):
  - `status`: string enum `RISING | FALLING | FLAT | UNKNOWN`
  - `anchor_mass_delta`: number | null

### Trend computation (render-only; deterministic)

Let:

- `p0` = prior mass for `anchor_regime` (from prior snapshot), if available
- `p1` = current mass for `anchor_regime`
- `delta = p1 - p0`

Then:

- If no prior snapshot or missing prior mass: `status = UNKNOWN`, `anchor_mass_delta = null`
- Else if `delta > 0`: `status = RISING`
- Else if `delta < 0`: `status = FALLING`
- Else: `status = FLAT`

No thresholds are applied in Phase 6.

## Renderer Rules (Read-Only)

Renderers must:

- Consume only the DVM (no upstream contracts).
- Render belief distribution, anchor, and trend when present.
- Tolerate missing optional fields and unknown future fields (ignore unknowns).

## Completion Criteria (Phase 6)

Phase 6 is complete when:

- DVM includes the optional `belief` section per above.
- Dashboard builder populates `belief` when upstream belief payload is present.
- Renderer displays belief distribution, anchor regime, and trend read-only.
- Outputs are deterministic for a fixed input event log.

## Explicit Non-Goals

- No interactivity (controls, toggles, actions).
- No charting polish beyond correctness.
- No dashboard-side inference of belief from regime labels, evidence, or drivers.
- No persistence beyond existing mechanisms (no new stores).
