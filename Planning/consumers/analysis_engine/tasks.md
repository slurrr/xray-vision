# consumers/analysis_engine — tasks

This task list is ordered and implementation-ready. Complete tasks strictly in order; do not begin later phases until earlier phases are complete and reviewed.

## Phase 0 — Contracts (Freeze First)

1. Define the `analysis_engine_event` v1 schema exactly as specified in `Planning/consumers/analysis_engine/spec.md`.
2. Define the stable `ArtifactEmitted` envelope fields and the allowed `artifact_kind` values for v1.
3. Define the module registry contract:
   - required module metadata (`module_id`, `module_kind`, `module_version`)
   - dependency declaration format (`(module_id, artifact_name)`)
   - module-owned schema versioning (`artifact_schema_version`, `config_schema_version`)
   - optional explicit state contract for stateful modules (`state_schema_id`, `state_schema_version`)
4. Define the run context contract (authoritative fields sourced from `state_gate_event` only) and confirm that no other inputs are part of v1.
5. Define the idempotency contract (`run_id` as the key) and the minimal persistence needed to enforce it.
6. Define the internal `AnalysisModuleStateRecord` v1 persistence contract for stateful modules (append-only, per-symbol, per-module).
7. Freeze contracts and document additive-only evolution rules.

## Phase 1 — Engine Shell (No Modules Yet)

7. Implement consumption of the `state_gate_event` v1 stream.
8. Implement strict gating:
   - process only `GateEvaluated` with `gate_status == OPEN`
   - optionally emit `AnalysisRunSkipped` for `gate_status == CLOSED` with no artifacts
   - stop processing when `StateGateHalted` is received for a symbol/run
9. Implement run lifecycle emission (`AnalysisRunStarted`, `AnalysisRunCompleted`, `AnalysisRunFailed`) keyed by `run_id`.
10. Implement idempotency persistence so duplicated `run_id` inputs do not re-emit artifacts.
11. Implement internal state persistence plumbing that can store and retrieve `AnalysisModuleStateRecord` entries, without exposing it as a downstream contract.

## Phase 2 — Registry & Plugin Registration

11. Implement the module registry as a core component with deterministic discovery at process start.
12. Implement module-kind interfaces (signals/detectors/rules/outputs) with:
    - deterministic inputs (run context + declared dependencies only)
    - deterministic outputs (artifacts with stable envelopes)
    - explicit prohibition of side effects in signals/detectors/rules
    - optional explicit state input/output for stateful modules (state read before execute; state append after success)
13. Implement dependency validation:
    - fail startup on missing dependencies among enabled modules
    - fail startup on dependency cycles

## Phase 3 — Execution Plan Builder (Deterministic Composition)

14. Implement deterministic plan construction from:
    - enabled module set
    - declared dependencies
    - fixed stage order (signals → detectors → rules → outputs)
15. Implement deterministic per-run execution ordering:
    - stage order fixed
    - within stage: dependency order then lexicographic `module_id`
    - artifact emission ordering: stage then `module_id` then `artifact_name`

## Phase 4 — Configuration System (Guardrailed)

16. Define and implement the analysis_engine configuration contract:
    - enabled module list (by `module_id`)
    - per-module config blobs validated against module schemas
    - optional per-symbol enablement without changing stage ordering
17. Enforce guardrails:
    - reject unknown keys
    - reject any config-driven DSL/expressions in v1
    - validate config at startup and fail fast deterministically on invalid configs

## Phase 5 — Module Execution Harness (Isolation + Results)

18. Implement artifact storage for a single run (in-memory run-scoped store) keyed by `(module_id, artifact_name)`.
19. Implement module failure containment:
    - on exception or invalid output, emit `ModuleFailed` and mark module artifacts absent
    - deterministically mark dependents as failed with `error_kind == missing_dependency`
    - complete the run as `PARTIAL` when possible
    - commit state updates only for successfully executed modules
20. Implement `AnalysisRunCompleted.status` computation (`SUCCESS`/`PARTIAL`/`FAILED`) exactly as specified.

## Phase 6 — Output Emission (Interfaces Only)

21. Implement output-module execution as the final stage, with explicit prohibition on influencing upstream computation.
22. Ensure all downstream-visible information is emitted via `analysis_engine_event` v1 (no side-channel outputs as contracts).

## Phase 7 — Observability & Health (Contract Enforcement)

23. Implement structured logging with the minimum required fields for runs, modules, and failures.
24. Implement the minimum metrics set from `Planning/consumers/analysis_engine/spec.md`.
25. Implement health/readiness indicators that reflect:
    - input stream consumption health
    - idempotency persistence availability
    - current module registry load success

## Phase 8 — Determinism & Replay Validation (Layer-Local)

26. Add contract-level tests that validate:
    - stable plan ordering from a fixed registry + config
    - idempotent handling of duplicated `run_id` inputs
    - stable artifact emission ordering
27. Add failure isolation tests that validate:
    - a failing module yields `ModuleFailed` and does not crash the process
    - dependents fail deterministically with `missing_dependency`
    - run status becomes `PARTIAL` when appropriate
28. Add replay tests that validate identical outputs from a fixed `state_gate_event` input log + configuration.

## Phase 9 — Readiness Gate

29. Produce a “contract freeze” note stating:
    - finalized `analysis_engine_event` v1 schema and event_type list
    - finalized module registry contract and dependency rules
    - configuration keys required to run for a single symbol
    - explicit non-goals compliance confirmation
