# Evidence Matrix Legacy Rollover — Phase A Implementation Plan

## Purpose
Introduce a **regime-neutral evidence transport** into the engine boundary in parallel with the existing regime-labelled embedded evidence, without changing belief or hysteresis behavior.

This phase corresponds to “Phase A — Parallel Regime-Neutral Transport (Additive Ingress)” in `Planning/evidence-matrix/legacy_rollover/regime_agnostic_evidence_migration_rfc.md`.

---

## Scope (Binding)

### In scope
- Add an **additional embedded payload** on the `RegimeInputSnapshot` that carries the *composer/contracts* evidence species:
  - `src/composer/contracts/evidence_snapshot.py:EvidenceSnapshot` with `src/composer/contracts/evidence_opinion.py:EvidenceOpinion`
- Add a **read-only parser** on the Regime Engine side that can extract and validate this regime-neutral payload for observability and replay validation.
- Keep legacy embedded evidence (`composer_evidence_snapshot_v1`) unchanged and still used for belief.

### Out of scope
- Any change to belief selection/math in `src/regime_engine/state/update.py:update_belief`.
- Any change to hysteresis rules/persistence.
- Any change to existing embedded evidence key name and semantics (`composer_evidence_snapshot_v1`).
- Any change that removes or disables the legacy path.

---

## Contracts and Schemas (Phase A)

### Contract changes
- None (no breaking changes).

### Additive data format introduced
- Introduce a new embedded payload key under `RegimeInputSnapshot.market.structure_levels` that contains the **composer evidence snapshot** (regime-neutral).
  - The payload schema is the *composer/contracts* evidence snapshot:
    - `schema`, `schema_version`, `symbol`, `engine_timestamp_ms`, `opinions[]`
    - Each opinion has `type`, `direction`, `strength`, `confidence`, `source`

Notes:
- This is an additive embedded payload alongside existing `composer_evidence_snapshot_v1`.
- The exact key name must be fixed and treated as a stable embedded payload identifier for Phase B/C consumption.

---

## Ground Truth (Current Call Paths)
- Regime-labelled evidence is currently computed and embedded by:
  - `src/composer/engine_evidence/compute.py:compute_engine_evidence_snapshot`
  - `src/composer/engine_evidence/embedding.py:embed_engine_evidence`
  - invoked from `src/composer/legacy_snapshot/builder.py:build_legacy_snapshot`
- Regime Engine reads that payload via:
  - `src/regime_engine/state/embedded_evidence.py:extract_embedded_evidence`
- Composer regime-neutral evidence exists but is not currently embedded:
  - `src/composer/evidence/compute.py:compute_evidence_snapshot`

---

## Implementation Steps (Phase A)

### 1) Produce composer/contracts evidence snapshot for the run
- Ensure a `composer.contracts.EvidenceSnapshot` is produced for each run using the existing composer evidence observers:
  - `src/composer/evidence/compute.py:compute_evidence_snapshot`
- Source inputs remain the already-computed `FeatureSnapshot` for the run (no new upstream requirements).

### 2) Embed the composer/contracts evidence snapshot into the engine snapshot
- Embed the regime-neutral payload into `RegimeInputSnapshot.market.structure_levels` under the new key.
- Preserve these invariants:
  - `symbol` and `engine_timestamp_ms` in the embedded payload match the enclosing `RegimeInputSnapshot`.
  - Embedding is additive and does not mutate/remove `composer_evidence_snapshot_v1`.

### 3) Add a Regime Engine extractor for the regime-neutral embedded payload (read-only)
- Add a Regime Engine-side parser that:
  - reads the new embedded key from `snapshot.market.structure_levels`
  - validates:
    - symbol/timestamp match
    - opinion fields present and within bounds (`strength/confidence` in `[0, 1]`)
    - deterministic ordering rules (if ordering is required for replay/log stability)
  - returns a typed, internal representation for observation only.

### 4) Observability (additive)
- Emit additive logs confirming:
  - whether regime-neutral payload is present for each run
  - counts and bounded summaries of the embedded regime-neutral opinions
- Ensure logs are correlated using `(symbol, engine_timestamp_ms)` and do not reorder or modify existing events.

---

## Validation Gates (Phase A)
- Deterministic replay equivalence:
  - With Phase A enabled, `tools/evidence_matrix_replay/diff.py` must still return `{"status":"ok"}` when comparing pre-Phase-A vs post-Phase-A outputs, since belief/hysteresis are unchanged.
- Payload alignment:
  - For every run where regime-neutral payload is present, it must be parseable and `(symbol, engine_timestamp_ms)`-aligned to the snapshot.

---

## Rollback / Reversibility (Phase A)
- Disabling Phase A means:
  - stop embedding the additional regime-neutral payload key
  - keep legacy embedded evidence unchanged and still driving belief
- No persisted state formats change in this phase.

---

## Hard Constraints / Red Lines
- Do not change `composer_evidence_snapshot_v1` content, validation, or selection precedence.
- Do not change what feeds `update_belief` (legacy evidence remains authoritative in Phase A).
- Do not introduce any regime assignment logic into this new regime-neutral payload; it must remain composer/contracts evidence (type+direction-based).

