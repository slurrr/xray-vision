# Phase 6 — Dashboard Exposure (Read-Only) tasks

This task list is ordered and implementation-ready for Phase 6 only.

Dashboards remain passive observability only.

## Phase 6 Tasks

1. Confirm current dashboards wiring inputs:
   - `orchestrator_event` v1 (truth + hysteresis)
   - `state_gate_event` v1 (gate + effective regime)
   - `analysis_engine_event` v1 (artifacts)
2. Add DVM contract fields (additive-only) for belief display:
   - `symbols[].belief.anchor_regime`
   - `symbols[].belief.distribution[]` with deterministic ordering `(mass desc, regime_name asc)`
   - `symbols[].belief.trend.status` and `symbols[].belief.trend.anchor_mass_delta`
3. Implement builder mapping for belief input:
   - read `belief_by_regime` from `HysteresisState.debug["belief_by_regime"]` when present
   - omit belief section when absent
4. Implement render-only derivations in the builder:
   - compute `anchor_regime` as deterministic argmax over the belief distribution (tie-break by Regime enum order)
   - compute `trend` using only the immediately prior observed belief snapshot (no thresholds; `UNKNOWN` when unavailable)
5. Update renderer(s) to display:
   - belief distribution (by regime)
   - anchor regime
   - belief trend (status + delta when available)
6. Add determinism/compatibility tests:
   - stable DVM belief ordering
   - stable trend outputs for a fixed, time-ordered belief input log
   - graceful behavior when belief input is missing (belief omitted)
7. Validate Phase 6 completion criteria against a fixed replay log (builder output deterministic; renderer tolerant).

## External Dependency (Blocking Prerequisite)

8. Ensure upstream provides belief state in the dashboards input stream without contract changes:
   - populate `HysteresisState.debug["belief_by_regime"]` deterministically per run

Dashboards cannot display belief distribution or trend until this prerequisite exists.
