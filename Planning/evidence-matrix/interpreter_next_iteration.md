## Evidence Matrix — Next Interpreter Iteration Plan (Dual-Run Only)

### Objective
Implement a non-identity `MatrixInterpreter` (the “real interpreter”) while keeping the system’s belief + hysteresis behavior unchanged by running it in **`dual_run`** (compute + log + diff only; no belief routing).

### Current Repo State (facts)
- Interpreter is identity passthrough:
  - `src/regime_engine/matrix/interpreter.py:ShadowMatrixInterpreter`
  - It maps `EvidenceSnapshot.opinions` → `RegimeInfluenceSet.influences` 1:1.
- Matrix execution + bridge + diff run unconditionally:
  - `src/regime_engine/pipeline.py:124-148`
- Belief is only driven by matrix when `effective_mode == matrix_enabled`:
  - `src/regime_engine/pipeline.py:149-176`
- Routing mode/scope are env-driven:
  - `src/regime_engine/matrix/config.py:38-57`

### Non-Negotiable Constraints for This Iteration
- No change to belief update semantics (`src/regime_engine/state/update.py:update_belief`).
- No change to hysteresis semantics (`src/regime_engine/hysteresis/**`).
- No contract changes under `src/regime_engine/contracts/**`.
- Default runtime remains non-interfering (legacy-only belief routing unless explicitly enabled).
- Interpreter output must be deterministic and exception-contained (same guarantees as current shadow path).

---

## Work Plan

### Step 1 — Add a real interpreter implementation (still not wired into belief)
Create a new interpreter class that implements `MatrixInterpreter`:
- New class: `MatrixInterpreterV1` (name illustrative)
- Location: `src/regime_engine/matrix/` (e.g., `interpreter_v1.py`)
- Input: `EvidenceSnapshot`
- Output: `RegimeInfluenceSet`

Required properties:
- **Deterministic**: no wall-clock reads, randomness, or reliance on non-deterministic container ordering.
- **Bounded**: influence fields must remain within `[0.0, 1.0]` since the bridge enforces bounds (`src/regime_engine/matrix/bridge.py:_validate_influence`).
- **Total exception containment**: any interpreter exceptions must be caught by the existing wrapper in `src/regime_engine/pipeline.py:_compute_matrix_influences`.

### Step 2 — Introduce a matrix definition surface (minimal, non-authoritative)
Add a data-only “matrix definition” representation that the interpreter consumes.

Constraints for the definition surface:
- It must not depend on belief selection logic (no “pick winner”, no ranking as a proxy for belief).
- It may define only how evidence is translated into influences (interpretation layer).
- It must be deterministic and purely data-driven.

Initial matrix definition for this iteration:
- Provide the smallest possible matrix that is sufficient to exercise the interpreter path and yield non-empty outputs from typical evidence.
- Keep it explicitly “v1 / provisional / diagnostic” and run only in dual-run; do not enable belief routing from it in this iteration.

### Step 3 — Make interpreter selection explicit and reversible (no belief impact)
Keep the ability to run either:
- `ShadowMatrixInterpreter` (current identity passthrough), or
- `MatrixInterpreterV1` (new implementation)

Mechanism (repo-standard config-first):
- Extend the Regime Engine matrix routing config (loaded from `src/regime_engine/matrix/config/default.yaml` via `src/regime_engine/matrix/config/loader.py:load_matrix_routing_config`) with a new key, e.g. `interpreter: shadow|v1`.
- Extend `src/regime_engine/matrix/config/schema.py:MatrixRoutingConfig` accordingly and validate the value.
- Update `src/regime_engine/matrix/config/loader.py:_ROOT_KEYS` and parsing to include the new field from YAML (and optionally keep a legacy env override, consistent with the current loader pattern).
- Wiring point is `_MATRIX_INTERPRETER` selection in `src/regime_engine/pipeline.py` (currently hard-coded to `ShadowMatrixInterpreter()`).

### Step 4 — Operate strictly in `dual_run` to validate observability + diffs
Run by editing `src/regime_engine/matrix/config/default.yaml` (or using the existing env override escape hatch in `src/regime_engine/matrix/config/loader.py:_apply_env_overrides` if you are temporarily using env overrides):
- `mode: dual_run`
- `symbol_allowlist: ["BTCUSDT"]` (or a small scope)
- `interpreter: v1`

Expected behavior:
- Existing engine outputs (regime outputs + hysteresis) remain identical to legacy-only runs.
- Matrix logs show `mode`, `shadow`, `bridge`, `diff` events as before.
- Diffs may begin to show mismatches (that is allowed in dual-run; it’s the point), but must remain bounded/deterministic.

### Step 5 — Replay validation (prove non-interference)
Using the existing capture artifacts:
- Replay baseline with interpreter selection `shadow` (or legacy-only config).
- Replay candidate with interpreter selection `v1` but still `REGIME_ENGINE_MATRIX_MODE=dual_run`.
- Diff outputs using `tools/evidence_matrix_replay/diff.py` and require:
  - `regime_outputs.jsonl` identical
  - `hysteresis_states.jsonl` identical (modulo ignored fields already configured in diff tool)
  - `persistence_counts.json` identical

### Step 6 — Unit tests (interpreter + determinism contracts)
Add unit tests under `tests/` to assert:
- Interpreter produces deterministic outputs for a fixed `EvidenceSnapshot`.
- Interpreter output ordering is deterministic.
- Interpreter output values are within bounds expected by the bridge.
- Interpreter handles empty evidence without error.

Note: These tests validate interpreter behavior only; they must not change belief/hysteresis semantics.

---

## Deliverables
- New interpreter implementation (`MatrixInterpreterV1`) under `src/regime_engine/matrix/`.
- Data-only matrix definition representation under `src/regime_engine/matrix/` (file layout as needed).
- Interpreter selection toggle (env) and wiring change in `src/regime_engine/pipeline.py` to select implementation.
- Unit tests for determinism/bounds.
- Replay evidence showing `dual_run` remains non-interfering (diff `status: ok`).

---

## Stop Conditions (do not proceed to belief routing)
- Any change in `regime_outputs.jsonl` or `hysteresis_states.jsonl` under `dual_run`.
- Any non-determinism observed across repeated replays with identical inputs/config.
- Any interpreter/bridge/log construction exceptions escaping the existing containment wrappers.
