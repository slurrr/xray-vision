## RFC — Regime-Agnostic Evidence to Matrix-Assigned Regimes (Migration Plan)

### Scope
This document defines a phased migration plan that reconciles:
1) the currently implemented evidence → belief pipeline in this repository,
2) the intended architecture where the Evidence×Regime Matrix is the sole assigner of regime meaning, and
3) frozen constraints: belief math remains unchanged; the legacy path remains runnable throughout.

This is a planning artifact only. It describes contracts and data flows conceptually and does not prescribe code edits.

---

## 1) Current State (Factual)

### Evidence “species” in this repo (distinct, non-interchangeable)

**Composer evidence (regime-agnostic)**
- `src/composer/contracts/evidence_opinion.py:EvidenceOpinion`
  - Fields: `type`, `direction`, `strength`, `confidence`, `source`
  - No regime field.
- `src/composer/contracts/evidence_snapshot.py:EvidenceSnapshot`
  - Fields: `schema`, `schema_version`, `symbol`, `engine_timestamp_ms`, `opinions: Sequence[composer EvidenceOpinion]`
- Produced by:
  - `src/composer/evidence/compute.py:compute_evidence_snapshot` (using `src/composer/evidence/observers.py:OBSERVERS_V1`)
- Exposed by:
  - `src/composer/composer.py:compose` returning `(FeatureSnapshot, composer.contracts.EvidenceSnapshot)`
- **Not** used by the Regime Engine belief ingress path today.

**Regime Engine evidence (regime-labelled)**
- `src/regime_engine/state/evidence.py:EvidenceOpinion`
  - Fields: `regime: Regime`, `strength`, `confidence`, `source`
  - Regime is required.
- `src/regime_engine/state/evidence.py:EvidenceSnapshot`
  - Fields: `symbol`, `engine_timestamp_ms`, `opinions: Sequence[regime_engine EvidenceOpinion]`
- Consumed by belief update:
  - `src/regime_engine/state/update.py:update_belief`

### Where regime meaning is assigned today (explicit)
Regime meaning is assigned upstream (before belief) by Composer’s “engine evidence” observers:
- `src/composer/engine_evidence/observers.py:ClassicalRegimeObserver.emit`
- `src/composer/engine_evidence/observers.py:FlowPressureObserver.emit`
- `src/composer/engine_evidence/observers.py:VolatilityContextObserver.emit`

Each of these emits **Regime Engine** `EvidenceOpinion(regime=...)` directly (not composer/contracts EvidenceOpinion).

### What feeds belief today (call path)

**Snapshot assembly and evidence embedding**
- Runtime invokes:
  - `src/composer/engine_evidence/compute.py:compute_engine_evidence_snapshot` → returns `regime_engine.state.evidence.EvidenceSnapshot` (regime-labelled opinions)
  - `src/composer/legacy_snapshot/builder.py:build_legacy_snapshot` → embeds evidence into `RegimeInputSnapshot`
  - Embedding occurs in `src/composer/engine_evidence/embedding.py:embed_engine_evidence`
    - Embedded key: `composer_evidence_snapshot_v1` (stored under `snapshot.market.structure_levels[...]`)

**Regime Engine extraction and belief update**
- Regime Engine reads embedded evidence from snapshot:
  - `src/regime_engine/state/embedded_evidence.py:extract_embedded_evidence`
  - It parses opinions with required `regime` values and constructs a `regime_engine.state.evidence.EvidenceSnapshot`.
- Belief update consumes that `EvidenceSnapshot`:
  - `src/regime_engine/state/update.py:update_belief`
  - Selection rule: choose one opinion by ordering `(-strength, -confidence, regime_order)` and set belief one-hot for the selected regime.

### Current matrix layer behavior (as implemented)
- The matrix layer currently consumes **Regime Engine evidence**:
  - `src/regime_engine/matrix/types.py:MatrixInterpreter.interpret(self, evidence: EvidenceSnapshot) -> RegimeInfluenceSet`
  - This `EvidenceSnapshot` is the regime-labelled species from `src/regime_engine/state/evidence.py`.
- The pipeline always runs matrix compute/bridge/diff (even in legacy mode):
  - `src/regime_engine/pipeline.py:142-168` (mode log, interpreter selection, compute influences, bridge, diff)
- Belief routing is gated:
  - Only in `matrix_enabled` does `src/regime_engine/pipeline.py:169-180` allow `matrix_evidence` to feed `update_belief`.
- As a consequence, the matrix currently operates on evidence that already has a `regime` assigned upstream.

---

## 2) Target State (Precise Definition)

### Architectural intent (authoritative for target)
- Belief remains the system’s source of truth (unchanged belief math and invariants).
- The matrix is the **sole** assigner of regime meaning during interpretation:
  - No upstream component assigns `Regime` labels as part of evidence generation.
  - Upstream emits regime-neutral evidence signals only.

### Target evidence species and responsibilities

**Composer evidence (regime-neutral) remains regime-neutral**
- Composer emits `composer.contracts.EvidenceSnapshot` containing `composer.contracts.EvidenceOpinion` with `type` + `direction` + `strength` + `confidence` + `source`.
- This species is used as the upstream evidence transport into the engine boundary.

**Matrix interpreter assigns regimes**
- Matrix consumes regime-neutral evidence signals and produces regime-labelled influences:
  - Input: regime-neutral evidence (composer species, or an engine-local equivalent representation of the same regime-neutral fields).
  - Output: `RegimeInfluenceSet` (regime-labelled) suitable for bridging into Regime Engine evidence for belief consumption.

**Belief consumes regime-labelled opinions (unchanged math)**
- Belief update continues to consume a `regime_engine.state.evidence.EvidenceSnapshot` (regime-labelled opinions).
- Belief selection/one-hot assignment remains unchanged.
- The change is upstream of belief: the origin of regime-labelled opinions becomes “matrix output” rather than “composer heuristics”.

### Legacy path must remain runnable
- At every phase, the system can run in a mode where the currently implemented (pre-matrix) regime-labelled evidence path still produces valid inputs and belief/hysteresis continue to operate.

---

## 3) Phased Migration Plan

### Phase A — Parallel Regime-Neutral Transport (Additive Ingress)

**Purpose**
Introduce a regime-neutral evidence transport into the engine boundary in parallel with the existing regime-labelled embedded evidence, without changing belief behavior.

**Contracts**
- No breaking contract changes.
- Introduce an additive embedded payload (a new structure-level key) carrying the composer evidence species (`composer.contracts.EvidenceSnapshot` content) for the same `(symbol, engine_timestamp_ms)`.
  - The existing embedded key `composer_evidence_snapshot_v1` remains unchanged and continues to exist.

**Behavior unchanged**
- Belief continues to consume the existing regime-labelled embedded evidence via `extract_embedded_evidence` and `update_belief` as today.
- Hysteresis behavior and persistence remain unchanged.
- Legacy mode remains the default runnable mode.

**New data flows introduced (conceptual)**
- In addition to embedding `composer_evidence_snapshot_v1` (regime-labelled), snapshots also carry:
  - a regime-neutral evidence payload (composer species: `type`, `direction`, `strength`, `confidence`, `source`).
- Regime Engine gains the ability to read/parse this regime-neutral payload for observation only (not used for belief in this phase).

**Readiness signal**
- The regime-neutral payload is present, parseable, and deterministically aligned to `(symbol, engine_timestamp_ms)` alongside the existing payload.

---

### Phase B — Matrix Interprets Regime-Neutral Evidence (Dual-Run, Non-Interfering)

**Purpose**
Make the matrix interpreter operate on regime-neutral evidence, while remaining non-interfering to belief by running in dual-run.

**Contracts**
- No breaking contract changes.
- Matrix may introduce engine-local definition/config artifacts (internal) to represent the Evidence×Regime mapping rules.
- Matrix interpreter input contract changes are internal to the matrix layer (not public engine contracts), but must not change external engine invocation APIs.

**Behavior unchanged**
- Belief input remains legacy regime-labelled evidence (same selection rules and invariants).
- Hysteresis remains defined over belief and remains unchanged.
- Legacy path remains runnable and remains the source of truth for belief in this phase.

**New data flows introduced (conceptual)**
- Matrix consumes the regime-neutral embedded evidence payload (from Phase A).
- Matrix outputs a `RegimeInfluenceSet` (regime-labelled) derived solely from the matrix definition (the first point in the system where regime meaning is assigned in this path).
- A bridge converts matrix influences into `regime_engine.state.evidence.EvidenceSnapshot` (regime-labelled) for comparability, logging, and diffing only.
- Dual-run diffs compare:
  - legacy-selected regime (from legacy regime-labelled evidence) vs
  - matrix-selected regime (from matrix-derived regime-labelled evidence)
  without changing belief execution.

**Readiness signal**
- Deterministic replay shows no changes in belief/hysteresis outputs under dual-run.
- Matrix-derived selection mismatches (if any) are observable and attributable, without impacting legacy behavior.

---

### Phase C — Controlled Cutover: Matrix Feeds Belief (Gated, Reversible)

**Purpose**
Route matrix-derived regime-labelled evidence into belief in a controlled, gated way while retaining the legacy regime-labelled path for rollback and continued runnability.

**Contracts**
- No breaking contract changes.
- Belief math and selection rules remain unchanged; only the provenance of the `EvidenceSnapshot` feeding belief changes under gated routing.

**Behavior unchanged**
- Belief update semantics (ordering/one-hot invariants) remain unchanged.
- Hysteresis progression and persistence semantics remain unchanged.

**New data flows introduced (conceptual)**
- In matrix-enabled mode (scoped/gated), belief consumes matrix-derived regime-labelled evidence produced from regime-neutral inputs.
- Legacy regime-labelled evidence remains available and runnable:
  - as fallback (fail-closed behavior),
  - as a dual-run comparator, and/or
  - as a rollback path to return to legacy belief routing without requiring a schema migration.

**Reversibility**
- Routing can be switched back to legacy evidence without clearing or migrating hysteresis persistence state (belief math unchanged; hysteresis continues over belief).

**Stability condition**
- The system remains runnable whether:
  - regime-neutral evidence is present (matrix path active), or
  - regime-neutral evidence is absent/unavailable (legacy path still produces regime-labelled evidence and can drive belief).

---

## Summary of the reconciliation
- Today: Composer “engine evidence” observers assign regimes upstream and embed regime-labelled evidence; belief consumes that directly.
- Target: Upstream provides regime-neutral evidence; the matrix assigns regime meaning and produces regime-labelled inputs for the unchanged belief update.
- Migration: Add regime-neutral transport in parallel (A), interpret it in dual-run (B), then gate matrix into belief with full rollback (C), while keeping legacy runnable throughout.

