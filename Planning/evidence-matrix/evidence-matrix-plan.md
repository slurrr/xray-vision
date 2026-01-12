# Evidence × Regime Matrix — Phase 1 Implementation Plan (Shadow Mode)

## Purpose

Introduce a new **MatrixInterpreter** layer that runs in **shadow mode** (observability only) over the same `EvidenceSnapshot` that currently feeds belief update, without changing:

- any frozen contracts,
- any belief update behavior,
- any hysteresis behavior,
- any engine outputs (`RegimeOutput`, `HysteresisState`) or downstream gating behavior.

Target architecture (future, not activated in Phase 1):

`EvidenceSnapshot → MatrixInterpreter → RegimeInfluenceSet → Belief/Hysteresis (unchanged)`

Phase 1 constraint: **MatrixInterpreter must not participate in belief update or hysteresis.**

---

## Phase 1 Scope (Binding)

### In scope
- Additive, internal-only introduction of:
  - `MatrixInterpreter` (new)
  - `RegimeInfluenceSet` (new)
- Execute MatrixInterpreter in **shadow mode** on the engine’s actual evidence stream.
- Add observability (structured logs only) for matrix inputs/outputs and failure modes.
- Add deterministic, non-disruptive guards to keep the system runnable and observable.

### Out of scope (must not occur)
- Any change to frozen contracts under `src/**/contracts/`.
- Any change to `regime_engine.engine.run` / `run_with_hysteresis` signatures or behaviors.
- Any change to belief selection rules (`update_belief`) or hysteresis progression/commit logic.
- Any change to output schemas or semantics (`RegimeOutput`, `HysteresisState`, orchestrator/state_gate events).
- Designing or authoring the actual matrix semantics (no new thresholds for inference, no new regime logic).

---

## Ground Truth Dependencies (from audit)

### Evidence source used by belief update today
Inside `src/regime_engine/pipeline.py` the engine selects one `EvidenceSnapshot` per run:

- **Embedded canonical evidence** (preferred when present): extracted from
  `RegimeInputSnapshot.market.structure_levels["composer_evidence_snapshot_v1"]`
  via `src/regime_engine/state/embedded_evidence.py`.
- **Classical fallback evidence** (when embedded evidence absent): built from legacy resolution via
  `src/regime_engine/state/evidence.py:build_classical_evidence`.

Belief update consumes only `EvidenceSnapshot(symbol, engine_timestamp_ms, opinions)` and applies:

- deterministic single-opinion selection (`strength desc`, then `confidence desc`, then `Regime enum order`),
- belief invariants (`belief_by_regime` non-empty, sums to 1, bounded values),
- symbol match enforcement.

### Hysteresis dependency
Hysteresis consumes `RegimeState.belief_by_regime` and (separately) persists its own `HysteresisState` records.
Dashboards derive belief display from `HysteresisState.debug["belief_by_regime"]`.

Phase 1 must not change any of the above.

---

## Implementation Steps (Phase 1)

### 1) Add internal matrix types (no public contracts)

Create a new internal module under the Regime Engine (exact location may follow local conventions, but must remain non-contract):

- `src/regime_engine/matrix/types.py`
  - `RegimeInfluenceSet` (new, internal-only)
  - `MatrixInterpreter` protocol/ABC (new, internal-only)

Constraints:
- Do **not** add these under any `contracts/` package.
- Do **not** re-export them from the public Regime Engine API layer (`src/regime_engine/engine.py`).
- Use only deterministic fields and deterministic ordering; include `symbol` + `engine_timestamp_ms` for correlation.

### 2) Implement a shadow-only interpreter implementation

Add a concrete interpreter implementation:

- `src/regime_engine/matrix/interpreter.py`
  - Implements `MatrixInterpreter`.
  - Accepts `EvidenceSnapshot` as input.
  - Produces a `RegimeInfluenceSet` that is **diagnostic-only** in Phase 1.

Shadow-mode constraints:
- No regime logic may be introduced that affects downstream computation; the interpreter output is not consumed by belief or hysteresis.
- The interpreter must be deterministic and side-effect-free (no network, no randomness, no wall-clock).
- If interpreter computation fails, it must not fail the engine run; the failure is observable only (see Step 4).

### 3) Execute MatrixInterpreter in the engine pipeline (shadow only)

Insert a shadow invocation at the single choke point where the engine has selected the effective `EvidenceSnapshot` for belief:

- File: `src/regime_engine/pipeline.py`
- Location: within `run_pipeline_with_state`, after evidence selection (embedded vs classical) and before `initialize_state` / `update_belief`.

Operational constraints:
- The engine must continue to call `update_belief(prior_state, evidence)` exactly as today.
- The engine must continue to call hysteresis (`process_state`) exactly as today.
- No engine outputs or logs currently emitted may be removed or reordered in a way that changes observable sequences; Phase 1 adds new log events only.

### 4) Add matrix shadow observability (structured logging only)

Add a new observability hook for matrix shadow execution:

- Preferred: extend `src/regime_engine/observability.py` with a new method on `Observability`, e.g. `log_matrix_shadow(...)`.

Minimum log fields (must be derivable without new contracts):
- `symbol`, `engine_timestamp_ms`
- evidence origin: `"embedded"` vs `"classical"` (as observed in `run_pipeline_with_state`)
- `opinion_count`
- per-opinion summary (bounded): `source`, `regime`, `strength`, `confidence` (exactly what exists in `EvidenceOpinion`)
- interpreter status: `"ok"` / `"error"`
- on error: exception type + message (string), and a stable error_code

Safety constraints:
- Logs must not include non-deterministic content (no timestamps beyond the existing `engine_timestamp_ms`).
- Payload sizes must be bounded; if logging all opinions is too large, log a capped list plus counts.

### 5) Preserve runnability: exception containment and correlation

Matrix shadow execution must satisfy:
- It never raises past the pipeline boundary; failures are logged and the pipeline proceeds unchanged.
- It correlates with existing observability (`regime_engine.run.start`, belief aggregation logs, hysteresis logs) using the same `(symbol, engine_timestamp_ms)` pair.

### 6) Verification gates (Phase 1 non-regression)

Add a Phase 1 verification checklist (tests or equivalence checks) that confirms:
- `RegimeOutput` is byte-for-byte identical for the same input snapshots before vs after matrix shadow introduction.
- `HysteresisState` is identical for the same `(symbol, engine_timestamp_ms)` sequences and same stored prior state.
- Belief invariants remain satisfied at every step.
- Snapshot serialization/replay remains compatible (matrix does not affect `RegimeInputSnapshot` JSONL encoding).

Implementation notes for verification (must not change runtime behavior):
- Prefer unit tests around `run_pipeline_with_state` and `run_with_hysteresis` using existing snapshot fixtures/patterns.
- Ensure no new logging breaks existing structured logger assumptions (Null logger must still work).

### 7) Tooling gates

After implementation:
- `ruff check .` must pass.
- `pyright` must pass.

---

## Shadow Mode Definition (Phase 1)

“Shadow mode” means:
- MatrixInterpreter runs on the same `EvidenceSnapshot` that is used for belief update.
- Its output (`RegimeInfluenceSet`) is **not** fed into belief update or hysteresis.
- The only externally visible change is additional structured log events.

---

## Explicit Red Lines (Phase 1)

The following must remain unchanged:
- Embedded evidence key name: `"composer_evidence_snapshot_v1"`.
- Evidence selection rules for belief update (`update_belief` selection and invariant checks).
- Hysteresis progression, commit behavior, and persistence schema/version.
- Explainability validation requirements and the contents of `RegimeOutput.{drivers, invalidations, permissions}` as currently derived.
- Downstream gating that uses `RegimeOutput.invalidations` (state_gate) and dashboards’ use of `HysteresisState.debug["belief_by_regime"]`.

