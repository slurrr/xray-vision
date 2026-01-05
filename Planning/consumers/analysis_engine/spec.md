# consumers/analysis_engine — spec

## Purpose & Scope

`consumers/analysis_engine` is the analysis-only layer that converts **gated engine runs** into **analytical artifacts** (signals, detections, evaluations) and emits those artifacts downstream in a stable, extensible form.

Role in system flow:

- Upstream layers produce authoritative regime truth (`RegimeOutput` / `HysteresisDecision`) and a gating decision (`state_gate_event`).
- `analysis_engine` runs *only when the gate is open* and produces analysis artifacts for downstream consumers.

Naming note:

- This planning layer corresponds to the item previously referred to as `consumers/pattern_scanner` in the implementation order; only the name differs.

`analysis_engine` explicitly does not:

- Execute trades, size positions, place orders, or generate execution directives.
- Infer or recompute regime logic (Regime Engine is authoritative).
- Promote/demote state or override gating (state_gate is authoritative).
- Produce dashboards, alerts, notifications, or user-facing output.
- Persist raw market data or create a data lake; persistence is limited to replay/idempotency needs.

---

## Conceptual Decomposition

This layer is modular by construction. There are four module categories with strict boundaries:

### Signals (computation)

- Pure computations that transform the run context into named numeric/boolean/categorical outputs.
- Must be deterministic and side-effect free.

### Detectors (pattern detection)

- Deterministic detectors that consume run context + signal outputs and emit **detections** (pattern candidates).
- Must be deterministic and side-effect free.

### Rules (evaluation)

- Deterministic evaluators that consume run context + signals + detections and emit **evaluations** (scores, suppressions, labels).
- Must be deterministic and side-effect free.

### Outputs (emission)

- Emission modules that transform evaluations into downstream-facing emitted artifacts.
- Outputs may perform delivery I/O, but must not influence computation (no feedback into signals/detectors/rules and no upstream coupling).

#### Allowed interactions

- Signals may depend only on the run context.
- Detectors may depend on the run context + signals.
- Rules may depend on the run context + signals + detections.
- Outputs may depend on the run context + evaluations (and may include signals/detections for reporting only).

No cross-category cycles are allowed. These boundaries exist to ensure:

- deterministic replay (computation is isolated from I/O),
- zero-impact extensibility (adding/removing a module does not rewrite the engine), and
- stable contracts (downstream observes artifacts, not implementation details).

---

## Inputs & Outputs (Contracts)

### Inputs: `StateGateEvent` v1

`analysis_engine` consumes `state_gate_event` v1 as defined in `Planning/consumers/state_gate/spec.md`.

Upstream market observables are treated as already encapsulated by the authoritative engine payloads included in `state_gate_event`. This layer does not consume `RawMarketEvent` directly.

Consumed input event types (v1):

- `GateEvaluated`
- `StateReset` (reset context for downstream analysis state, if any is retained)
- `StateGateHalted` (stop processing; gate is not trustworthy)

Run selection rule:

- `analysis_engine` must process a run only when:
  - `event_type == GateEvaluated`, and
  - `gate_status == OPEN`.

When `gate_status == CLOSED`, `analysis_engine` must not emit analysis artifacts for that run.

### Run context (authoritative fields)

For each processed run, the run context is defined only by:

- `symbol`, `run_id`, `engine_timestamp_ms`
- `engine_mode` (`truth` | `hysteresis`) when present
- the authoritative engine payload included in the `state_gate_event`:
  - `payload.hysteresis_decision` when `engine_mode == hysteresis`, else
  - `payload.regime_output` when `engine_mode == truth`
- `gate_status` and `reasons` (as inputs to analysis, not as state to modify)

No other inputs are part of the v1 contract.

### Outputs: `AnalysisEngineEvent` v1

`analysis_engine` emits a single downstream stream of versioned, append-only events.

**Envelope (required)**

- `schema`: string, fixed value `analysis_engine_event`
- `schema_version`: string, fixed value `1`
- `event_type`: string, one of the types below
- `symbol`: string
- `run_id`: string
- `engine_timestamp_ms`: int

**Common metadata (optional, additive only)**

- `engine_mode`: string (`truth` | `hysteresis`)
- `source_gate_reasons`: array of strings (copied from state_gate, deterministic ordering)

**Event types**

- `AnalysisRunStarted`
- `AnalysisRunSkipped`
  - Emitted only for traceability when a `GateEvaluated` input is `CLOSED`; must not include artifacts.
- `ArtifactEmitted`
- `ModuleFailed`
- `AnalysisRunCompleted`
- `AnalysisRunFailed`

#### `ArtifactEmitted` payload contract (v1)

Every emitted artifact must include:

- `artifact_kind`: string (`signal` | `detection` | `evaluation` | `output`)
- `module_id`: string (stable identifier of the producing module)
- `artifact_name`: string (stable within the module)
- `artifact_schema`: string (module-owned schema identifier)
- `artifact_schema_version`: string (module-owned, versioned)
- `payload`: JSON-serializable object, immutable content (module-owned)

The engine must treat artifact payloads as opaque; only the artifact envelope is a stable cross-module contract.

#### `ModuleFailed` payload contract (v1)

- `module_id`: string
- `module_kind`: string (`signal` | `detector` | `rule` | `output`)
- `error_kind`: string (stable category, non-sensitive)
- `error_detail`: string (brief, non-sensitive)

#### `AnalysisRunCompleted` / `AnalysisRunFailed` payload contract (v1)

- `status`: string (`SUCCESS` | `PARTIAL` | `FAILED`)
- `module_failures`: array of `module_id` (deterministic ordering)

### Versioning & stability

- `analysis_engine_event` v1 changes are additive only:
  - add optional fields,
  - add new `event_type` values,
  - add new `artifact_kind` values only with downstream review.
- Breaking changes require `schema_version` increment and explicit downstream review.
- Module-owned artifact schemas are versioned independently; changes to a module’s payload must bump `artifact_schema_version`.

---

## Plugin & Modularity Model

### Registry model

The engine maintains a registry of modules. Each registered module must declare:

- `module_id` (stable, unique)
- `module_kind` (`signal` | `detector` | `rule` | `output`)
- `module_version` (module-owned, versioned)
- `dependencies` (a list of required upstream artifacts, expressed only as `(module_id, artifact_name)` pairs)
- `config_schema_id` and `config_schema_version` (module-owned)
- whether it is stateful, and if so:
  - `state_schema_id` and `state_schema_version` (module-owned)
- whether it is enabled by default (default should be disabled unless explicitly required)

The registry is a core contract; adding/removing modules must not require changing the engine core.

### Discovery & enable/disable

- Discovery/registration mechanism is an implementation detail, but must be deterministic at process start.
- Configuration selects which registered modules are enabled for execution.
- A run executes using the enabled set only; disabled modules do not run and do not emit artifacts.

### Composition & dependency resolution

At startup, the engine must:

- validate that all enabled modules have their declared dependencies satisfied by other enabled modules, and
- build an execution plan with a deterministic order:
  - category order: signals → detectors → rules → outputs
  - within a category: dependency order, then lexicographic `module_id`

Dependency cycles are forbidden and must fail startup deterministically.

### Module state (optional, explicit)

Some modules may require per-symbol history (e.g., multi-run pattern context). This is permitted only under an explicit, replayable state contract:

- State is per `(symbol, module_id)` and is versioned by the module (`state_schema_id`, `state_schema_version`).
- State updates are append-only; no in-place mutation.
- A module’s state is part of the deterministic input to that module for the next run.

The engine must persist state updates as an internal `AnalysisModuleStateRecord` (v1) with:

- `symbol`, `module_id`, `run_id`, `engine_timestamp_ms`
- `state_schema_id`, `state_schema_version`
- `state_payload` (module-owned, JSON-serializable, immutable content)

State is internal to the layer; it is not a downstream contract unless explicitly emitted as an artifact by an output module.

### Hot add/remove safety (conceptual)

“Hot add/remove” in this context means **zero engine-core changes**:

- Adding a module: register it and enable it via config; no rewrites of engine stages or contracts.
- Removing a module: disable it via config; dependency validation prevents silent breakage.

No runtime hot-reload guarantees are made in v1.

---

## Execution Model

### Stage order (non-negotiable)

For each processed run:

1. Build immutable run context from the input `state_gate_event`.
2. Execute enabled signal modules and collect signal artifacts.
3. Execute enabled detector modules and collect detection artifacts.
4. Execute enabled rule modules and collect evaluation artifacts.
5. Execute enabled output modules to emit output artifacts (and any additional `analysis_engine_event` items).

### Determinism & replay

For a fixed input event stream and fixed configuration:

- module execution order is deterministic,
- module inputs are deterministic (context + declared dependencies only),
- artifact emission ordering is deterministic (stable by stage then `module_id` then `artifact_name`),
- idempotency behavior is deterministic (see below).

Signals/detectors/rules must not perform network I/O or consult wall-clock time. Output modules may perform I/O but must not influence upstream computation.

### Idempotency

- `analysis_engine` must treat `run_id` as the idempotency key.
- If a run has already been fully processed, reprocessing the same `run_id` must not emit additional artifacts (except for explicitly allowed duplicate delivery semantics if implemented, but v1 should prefer at-most-once per `run_id`).
- Reprocessing the same `run_id` must not mutate module state.

### Failure isolation

- A failing module must not crash the entire process.
- On `ModuleFailed`, the engine must:
  - emit a `ModuleFailed` event, and
  - treat that module’s artifacts as absent for this run.
- Modules with unsatisfied dependencies for a run must not execute and must not emit artifacts; the engine must surface this deterministically via `ModuleFailed` with `error_kind == missing_dependency`.
- A run’s overall `status` is:
  - `SUCCESS` if no module failures occurred,
  - `PARTIAL` if one or more modules failed but the engine completed all remaining executable modules,
  - `FAILED` only if the engine cannot safely form a run context or cannot maintain idempotency/state persistence guarantees.

---

## Configuration Model

Configuration controls *composition*, not logic.

### Configurable

- Which modules are enabled (by `module_id`).
- Module configuration values constrained by each module’s declared config schema.
- Global guardrails:
  - per-symbol enablement (optional)
  - maximum enabled module counts (optional, to prevent unbounded fan-out)

### Code-defined (not configurable)

- Stage ordering and cross-category boundaries.
- Module dependency declarations.
- Artifact schema identifiers and versioning rules.
- Any interpretation of Regime Engine outputs beyond what is expressed as explicit module logic.

### Guardrails

- Unknown config keys must be rejected (no “best effort” parsing).
- Config must not allow arbitrary expressions, scripts, or rule DSLs in v1.
- All configuration must be validated at startup; invalid configs must fail fast and deterministically.

---

## Dependency Boundaries

### Allowed dependencies

- `state_gate_event` v1 contract (input schema only).
- Regime Engine output contracts as immutable payloads (`RegimeOutput`, `HysteresisDecision`).
- Deterministic, pure computation libraries for signals/detectors/rules.
- Output delivery primitives (logging, message publish) for output modules only.

### Forbidden coupling

- No dependency on dashboards, UI layers, alerting systems, or any execution/trading system.
- No upstream coupling: no imports from `market_data` and no direct consumption of raw vendor payloads.
- No regime inference: Regime Engine outputs are inputs, not hypotheses to reinterpret.
- No state authority: must not modify or supersede `state_gate` gating decisions.

---

## Invariants & Guarantees

- The four-stage decomposition (signals → detectors → rules → outputs) and one-way dependencies are invariant.
- The cross-module artifact envelope (`ArtifactEmitted` fields) is invariant within `analysis_engine_event` v1.
- Engine core remains stable under module churn: module adds/removals do not require changes to stage orchestration logic.
- Replay safety: for a fixed input stream + config, outputs are reproducible.
- Safety under partial failure: module failure yields `PARTIAL` runs; the engine does not emit artifacts claiming success for failed modules.

---

## Operational Behavior

### Observability (contractual)

**Structured logs (minimum fields)**

- `symbol`, `run_id`, `engine_timestamp_ms`, `event_type`
- For module execution: `module_id`, `module_kind`, `module_version`
- For failures: `error_kind`, `error_detail` (non-sensitive)

**Metrics (minimum set)**

- Run counts by `status` (`SUCCESS`/`PARTIAL`/`FAILED`)
- Artifact counts by `artifact_kind` and `module_id`
- Module failure counts by `module_id` and `error_kind`
- Processing latency per stage (signals/detectors/rules/outputs)
- Idempotency: duplicate run inputs ignored count

### Error containment

If a module fails, only that module (and dependents) are affected for that run. The engine continues processing independent modules and completes the run as `PARTIAL`.

---

## Non-Goals

- No trade/execution logic, no position sizing, no portfolio state.
- No alerts/notifications/UI.
- No persistence of historical analysis beyond what is required for idempotency and replay.
- No DSL-driven dynamic logic in v1; all logic lives in versioned modules.
