# composer_to_regime_engine — spec (migration-only)

## Purpose & Scope

This subsystem defines the **migration-only integration boundary** between `composer` and the `regime_engine`.

Goal:

- Wire Composer-produced **belief-first evidence** into the Regime Engine’s canonical `EvidenceSnapshot` path for belief update (as established by `Planning/regime_engine/spec.md` Phase 1 addendum), while preserving legacy snapshot-driven invocation.

Non-goals (explicitly out of scope for this subsystem/phase):

- Dashboards changes
- Belief persistence (prior belief injection, stores, replay state)
- Any belief math changes (update rules, smoothing, hysteresis semantics)
- Snapshot removal or contract changes to `RegimeInputSnapshot`
- Downstream consumer changes

This integration is **additive** and must preserve existing engine behavior for legacy snapshot-driven invocations when no composer evidence is present.

## Architectural Rules (Non-Negotiable)

- **Belief is the only authority.** Labels are projections.
- **Composer never infers and is non-authoritative.**
- **Composer is the snapshot builder (migration-only authorization).**
- **During migration, Composer may emit multiple shaped outputs for the same `(symbol, engine_timestamp_ms)`**, including:
  - legacy `RegimeInputSnapshot` (snapshot-shaped inputs), and
  - belief-first `EvidenceSnapshot` (canonical evidence input to belief update).
- **Hysteresis never touches labels.**
- **No downstream layer computes regime logic.**
- **No belief math changes:** the belief updater semantics and invariants remain unchanged.
- **No persistence:** no prior-belief stores, no cross-run memory, no trend/delta computation.
- **Orchestrator remains a pure router:** no shaping and no inference.
- **Regime Engine selects execution path solely based on which inputs are present.**

## Current State (Legacy)

- `orchestrator` invokes the engine via `regime_engine.engine.run(snapshot: RegimeInputSnapshot) -> RegimeOutput`.
- The engine currently constructs its own evidence internally (classical resolution evidence) and updates belief.
- Composer exists and can emit evidence, but it is not wired into the engine.

## Integration Model (Authoritative)

### 1) Embedded Evidence Contract Reference (No Schema Changes)

The embedded composer evidence payload MUST conform to the existing, frozen evidence contracts already defined in the system.

This subsystem defines **transport and validation rules only**. It does not define a new evidence schema or schema version.

Authoritative contract reference for the embedded payload:

- `regime_engine.state.evidence.EvidenceSnapshot` v1 (engine-owned canonical evidence)
- `regime_engine.state.evidence.EvidenceOpinion` v1 entries within `EvidenceSnapshot`

These are the concrete implementation types for the canonical evidence model described in `Planning/regime_engine/spec.md` (Phase 1 addendum). This subsystem defines only how that existing evidence is transported and validated.

Composer must not emit regime truth. Opinions are advisory inputs to belief update.

### 2) Composer Dual-Shape Output (Migration-Only)

Composer is authorized (during migration) to produce multiple shaped outputs for the same `(symbol, engine_timestamp_ms)`:

- A legacy snapshot-shaped output that supports existing engine invocation (`RegimeInputSnapshot` shape).
- A belief-first evidence output (`EvidenceSnapshot`) for the same run.

Orchestrator remains a pure router. It forwards inputs and does not interpret or reshape them.

This integration must occur behind the existing public entrypoint:

- `regime_engine.engine.run(snapshot: RegimeInputSnapshot) -> RegimeOutput`

No new Regime Engine public APIs are introduced for evidence-only invocation in this phase.

### 2.1) Legacy Snapshot Assembly (Migration Note: Option A then fallback to Option B)

This note defines a deterministic, migration-only approach for how Composer may produce a legacy `RegimeInputSnapshot` suitable for `regime_engine.engine.run(snapshot)` while embedding composer evidence.

This note does not introduce new contracts and does not change the public Composer API (`composer.compose(...)` remains unchanged).

**Inputs**

- `raw_events`: the deterministic raw event cut for a single `(symbol, engine_timestamp_ms)` run
- `symbol`
- `engine_timestamp_ms`

**Output**

- A legacy `regime_engine.contracts.snapshots.RegimeInputSnapshot` for `(symbol, engine_timestamp_ms)`, with embedded engine evidence under:
  - `market.structure_levels["composer_evidence_snapshot_v1"]` (only if at least one opinion is emitted; otherwise omit the key)

**Option A (Preferred): Pass-through `SnapshotInputs` if present**

If the raw cut contains a `RawMarketEvent` with:

- `event_type == "SnapshotInputs"`
- `event.symbol == symbol`
- `event.normalized["timestamp_ms"] == engine_timestamp_ms`

then Composer should:

1. Select the single eligible `SnapshotInputs` event with the highest deterministic precedence within the cut (e.g., last in cut order / highest cut-local sequence if available).
2. Convert its `normalized` payload into a `RegimeInputSnapshot` using the same field mapping and explicit-missing propagation semantics as orchestrator snapshot construction (missing sub-objects/fields become explicit missing values; no fabrication).
3. Embed engine evidence using the reserved carrier key rules in this spec (omit the key if zero opinions).

This option avoids inventing feature math for legacy fields and is the preferred migration behavior.

**Option B (Fallback): Synthesize a partial snapshot from `FeatureSnapshot` + explicit missingness**

If no eligible `SnapshotInputs` event exists in the cut, Composer may synthesize a legacy `RegimeInputSnapshot` deterministically using only:

- the computed `FeatureSnapshot` v1 values for the run, and
- explicit missingness for all other legacy snapshot fields.

Mapping rules (v1):

- `snapshot.symbol = symbol`
- `snapshot.timestamp = engine_timestamp_ms`
- `market.price = features["price"]` else explicit missing
- `market.vwap = features["vwap"]` else explicit missing
- `market.atr = features["atr"]` else explicit missing
- `market.atr_z = features["atr_z"]` else explicit missing
- `market.range_expansion = explicit missing`
- `market.acceptance_score = explicit missing`
- `market.sweep_score = explicit missing`
- `market.structure_levels = {}` then embed evidence per this spec
- `derivatives.open_interest = features["open_interest"]` else explicit missing
- all other `derivatives.*` fields = explicit missing
- `flow.cvd = features["cvd"]` else explicit missing
- all other `flow.*` fields = explicit missing
- all `context.*` numeric fields = explicit missing
- `context.btc_regime` and `context.eth_regime` remain `null` (do not infer)

No additional feature computation is performed in this fallback. The purpose is only to produce a well-formed legacy snapshot container with explicit missingness.

### 3) Evidence Carrier Clarification (Reserved Key)

`RegimeInputSnapshot.market.structure_levels` is an **opaque metadata bag**.

Carrier rule (reserved and frozen):

- `snapshot.market.structure_levels["composer_evidence_snapshot_v1"]`

This key, when present, contains a JSON-serializable object representing an embedded `EvidenceSnapshot` payload that conforms to the frozen contracts referenced above.

The Regime Engine must ignore `structure_levels` entirely except for reading this reserved key via the evidence adapter.

### 4) Engine Canonicalization (Validation + Deterministic Ordering Only)

When embedded composer evidence is present, the Regime Engine treats it as the canonical evidence input to belief update, subject to:

- validation (types, bounds, finiteness, symbol/timestamp consistency)
- deterministic ordering (mandatory sort rule; see below)

Engine canonicalization must not perform any regime interpretation beyond validating that `opinion.regime` is in the engine’s regime set.

Unknown regimes (values not in the engine’s regime set) are invalid and must be dropped deterministically.

### 5) Deterministic Opinion Ordering (Mandatory)

Canonical evidence opinions MUST be sorted deterministically using the frozen key:

- `(regime.value, source, -confidence, -strength)`

This ordering is mandatory and must be applied by the engine evidence adapter before belief update consumes the opinions.

### 6) Evidence Source Selection Inside `run(snapshot)` (Presence-Based)

The Regime Engine selects execution path solely based on which inputs are present:

- If `composer_evidence_snapshot_v1` is present in the snapshot, use it as the canonical evidence input for belief update (after validation/ordering).
- If it is absent, use the legacy internal evidence construction path.

The engine must not “merge” composer evidence with legacy evidence in this phase (no aggregation policy changes). Evidence is single-source per run by the above rule.

### 7) Zero-Opinion Handling + Explainability (No Hard-Fail)

If composer evidence is present but results in zero canonical opinions after validation:

- The engine must not hard-fail the run.
- Belief remains the stateless prior (uniform) for that run.
- Projection proceeds deterministically from uniform belief.

Explainability must include the deterministic sentinel driver:

- `DRIVER_NO_CANONICAL_EVIDENCE`

This behavior must be deterministic and replay-safe.

## Determinism Requirements

- Validation and ordering must be deterministic for identical evidence inputs.
- No wall-clock reads or randomness may affect evidence handling.
- The mandatory sort key for opinions is frozen by this spec.

## Explainability Requirements (Composer Evidence Path)

When composer evidence is selected as the evidence source, outputs must still satisfy Regime Engine explainability requirements. Drivers/invalidations must be derived deterministically from the selected evidence input (e.g., opinion `source` identifiers, and stable validation-failure codes).

## Failure Modes & Handling

The composer evidence path must not hard-fail on “no opinions” (see Zero Opinions Handling).

Validation failures must be explicit and deterministic:

- Invalid opinion fields (non-finite numbers, out-of-range bounds) → drop deterministically and record an invalidation code.
- Unknown regime identifiers → drop deterministically and record an invalidation code.
- Symbol/timestamp mismatch between embedded evidence and snapshot → treat embedded evidence as invalid (drop all embedded opinions) and proceed with zero opinions behavior.

## Phased Plan (This Subsystem Only)

### Phase 0 — Freeze Boundary + Carrier (Migration-Only)

Scope:

- Freeze the regime-addressed evidence contract used at the composer→engine boundary.
- Freeze the legacy snapshot carrier location (`market.structure_levels["composer_evidence_snapshot_v1"]`).
- Freeze deterministic validation/drop rules for invalid opinions and unknown regimes.
 - Freeze the mandatory deterministic opinion ordering key.

Entry conditions:

- `Planning/regime_engine/spec.md` Phase 1 addendum is accepted (canonical EvidenceSnapshot is sole belief-update input).

Exit conditions:

- Carrier format and validation rules are specified.
- Deterministic ordering rules are specified.

Failure modes:

- Any requirement for engine-side regime mapping (forbidden).

### Phase 1 — Engine Consumption Behind `run(snapshot)`

Scope:

- Teach the engine pipeline invoked by `run(snapshot)` to:
  - detect embedded composer evidence at the frozen carrier location,
  - validate + deterministically order it,
  - use it as canonical evidence input to belief update for that run.
- Preserve legacy behavior when embedded composer evidence is absent.
- Ensure zero-opinion behavior is non-failing and deterministic (uniform belief).

Constraints:

- No belief math changes.
- No persistence.
- No changes to frozen `contracts/` payloads.

Exit conditions:

- Composer evidence can be consumed via the existing `run(snapshot)` API without any new public APIs.
- Legacy snapshot-driven behavior remains unchanged when embedded composer evidence is absent.

Failure modes:

- Explainability validation failures on the composer evidence path (must be addressed deterministically).
- Non-deterministic ordering or validation behavior.

### Phase 2 — Composer Evidence Compliance

Scope:

- Ensure Composer emits regime-addressed evidence opinions compatible with the engine canonical evidence model.
- Ensure Composer embeds the evidence snapshot into the frozen carrier location in legacy snapshot outputs.
- Ensure deterministic ordering and bounds.

Constraints:

- Composer remains non-authoritative (opinions are advisory only).

Exit conditions:

- Composer evidence is accepted by engine validation/ordering without any engine-side regime mapping.

Failure modes:

- Composer emits unknown/invalid regimes or unstable ordering that causes non-determinism.

### Stop & Evaluate

After Phase 2, stop and explicitly choose the next active subsystem (e.g., orchestrator wiring, dashboard exposure, or persistence boundary activation).
