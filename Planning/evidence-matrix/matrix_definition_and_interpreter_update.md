## Phase 2.5 — Add Matrix Definition (Data) and Apply It in Interpreter (Dual-Run Only)

### Goal
Add a concrete Evidence×Regime “matrix definition” (data) and update the selected matrix interpreter to apply it, while keeping belief + hysteresis behavior unchanged by operating in `dual_run`.

### Current State (repo facts)
- Matrix routing is config-first via `src/regime_engine/matrix/config/default.yaml` loaded by `src/regime_engine/matrix/config/loader.py:load_matrix_routing_config`.
- Interpreter selection is already supported via `MatrixInterpreterKind` in `src/regime_engine/matrix/config/schema.py` and `_select_matrix_interpreter(...)` in `src/regime_engine/pipeline.py`.
- A definition scaffold exists:
  - `src/regime_engine/matrix/definition_v1.py` (`MatrixDefinitionV1`, `MATRIX_DEFINITION_V1`)
- A non-shadow interpreter exists:
  - `src/regime_engine/matrix/interpreter_v1.py:MatrixInterpreterV1`
- In `dual_run`, matrix output is computed, bridged, and diffed, but belief routing remains legacy (`src/regime_engine/pipeline.py:120-176`).

### Constraints (must hold for this iteration)
- No changes to belief update semantics (`src/regime_engine/state/update.py:update_belief`).
- No changes to hysteresis semantics (`src/regime_engine/hysteresis/**`).
- No changes to contracts (`src/regime_engine/contracts/**`).
- Deterministic output (no wall-clock reads, randomness, or non-deterministic iteration).
- Total exception containment remains inside pipeline wrappers (`src/regime_engine/pipeline.py:_compute_matrix_influences`, `_bridge_matrix_influences`, and safe-log helpers).

---

## Plan

### 1) Define the “matrix definition” format (v1, minimal but extensible)
Create a data representation that is explicitly “Evidence × Regime”.

Minimal requirements for v1:
- Keyed by:
  - `evidence_source` (string; from `EvidenceOpinion.source`)
  - `regime` (string; `Regime.value`)
- Defines deterministic transforms that remain purely interpretive and bounded:
  - `strength_weight` (float in `[0, 1]`)
  - `confidence_weight` (float in `[0, 1]`)
  - optional `strength_cap` (float in `[0, 1]`, or `null`)
  - optional `confidence_cap` (float in `[0, 1]`, or `null`)

Non-goals for v1 (explicitly deferred):
- Any time-based decay across runs (would require state or explicit timestamp policy).
- Any belief-style selection/aggregation logic beyond per-opinion translation.

### 2) Store the matrix definition as a package resource (config-standard)
Add a YAML resource under the matrix module (mirrors other config loaders):
- New file: `src/regime_engine/matrix/definitions/v1.yaml` (or similar path under `src/regime_engine/matrix/`)

Add a loader module:
- New file: `src/regime_engine/matrix/definitions/loader_v1.py`
- Behavior:
  - Load YAML via `importlib.resources`
  - Validate shape strictly (reject unknown keys, reject invalid types, enforce bounds)
  - Build an in-memory immutable definition object (dataclasses / tuples / frozensets)

### 3) Map definition into `MatrixDefinitionV1` (or replace it with the loaded object)
Choose one of two minimal approaches:

Option A (least churn):
- Keep `src/regime_engine/matrix/definition_v1.py:MatrixDefinitionV1`, extend it to represent per-(source, regime) cells in addition to current per-source defaults.
- Replace `MATRIX_DEFINITION_V1` constant to be constructed from the YAML loader at import time.

Option B (cleaner separation):
- Introduce a new definition type (e.g., `MatrixDefinitionCellsV1`) under `src/regime_engine/matrix/definitions/`.
- Update `src/regime_engine/matrix/interpreter_v1.py:MatrixInterpreterV1` to depend on that type instead of `MatrixDefinitionV1`.

Either way, the definition object must be immutable and deterministic in iteration order (e.g., sort keys on load, store as tuples).

### 4) Update `MatrixInterpreterV1` to apply the matrix definition deterministically
Update `src/regime_engine/matrix/interpreter_v1.py:MatrixInterpreterV1` so each `EvidenceOpinion` is translated using a matrix cell:
- Locate cell for `(opinion.source, opinion.regime)`; if missing, fall back to per-source default; if missing, fall back to global defaults.
- Compute:
  - `strength = clamp_unit(opinion.strength * strength_weight)` then apply `strength_cap` if present
  - `confidence = clamp_unit(opinion.confidence * confidence_weight)` then apply `confidence_cap` if present
- Output `RegimeInfluence` must satisfy the bridge bounds (`src/regime_engine/matrix/bridge.py:_validate_influence`).
- Output ordering must remain explicitly deterministic (keep the current sort key already used in `MatrixInterpreterV1.interpret`).

Important: in this iteration, **do not fan-out** an opinion into multiple regimes. Keep it 1:1 regime-preserving translation so the interpreter stays purely translational and easy to audit.

### 5) Keep the system in dual-run (non-interfering)
Set matrix routing config to dual-run in `src/regime_engine/matrix/config/default.yaml`:
- `mode: dual_run`
- `interpreter: v1`
- `symbol_allowlist: ["BTCUSDT"]` (or smallest scope you want to observe)

Expectation:
- `regime_engine.matrix.shadow`, `.bridge`, `.diff` will reflect the new interpreter outputs.
- Belief/hysteresis outputs remain driven by legacy evidence because `effective_mode != matrix_enabled` (`src/regime_engine/pipeline.py:169-176`).

### 6) Validation (required)
Replay harness (binary non-interference):
- Use the existing capture directory.
- Replay baseline and candidate with the same capture inputs:
  - Both runs must keep matrix routing in `dual_run`.
  - Candidate uses the new YAML-backed matrix definition + `interpreter: v1`.
- Run `tools/evidence_matrix_replay/diff.py`:
  - Must return `{"status":"ok"}` (no changes in `regime_outputs.jsonl`, `hysteresis_states.jsonl`, `persistence_counts.json`).

Unit tests (interpreter-local):
- Add tests validating:
  - parser rejects invalid schema/types/out-of-bounds weights
  - interpreter output is deterministic and sorted
  - output values are always within `[0, 1]`
  - missing cell fallback behavior is deterministic

### 7) Observability check (additive-only)
Verify via logs that:
- `regime_engine.matrix.mode` shows `effective_mode: dual_run` for allowlisted symbols.
- `regime_engine.matrix.shadow` influence summaries reflect matrix-applied weights/caps.
- No existing non-matrix log events change shape/order.

---

## Stop Conditions
- Any replay diff mismatch while still in `dual_run`.
- Any non-deterministic interpreter output across repeated replays on the same capture.
- Any exception escaping matrix wrappers and affecting engine control flow.

