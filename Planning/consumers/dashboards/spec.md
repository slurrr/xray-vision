# consumers/dashboards — spec

## Purpose & Scope

`consumers/dashboards` is the pure presentation layer for the system. It renders a read-only view of system status and latest analytical outputs for humans.

Why it exists:

- Provide operational visibility into upstream behavior without adding coupling.
- Make it safe to replace or rewrite UI implementations without touching analysis logic.

Guarantees to upstream and downstream:

- **Upstream**: dashboards are observers only; they never influence orchestration, gating, or analysis behavior (no feedback loops).
- **Downstream (renderers)**: renderers consume only the stable Dashboard View Model (DVM) contract; they do not depend on upstream domain objects or event schemas.

Layer boundary rule:

- The only supported input to any renderer is the DVM. Any consumption of upstream event streams is confined to an internal DVM builder and must not leak into renderer interfaces.

Dashboards must never:

- Mutate configuration, state, or runtime control-plane decisions.
- Emit signals, rules, pattern detections, or any analytical conclusions.
- Depend on analysis_engine internals beyond its published contracts.

---

## Dashboard View Model (DVM)

### Definition & intent

The Dashboard View Model (DVM) is a **render-agnostic, immutable snapshot** of the system’s current visible state.

The DVM is the contract. Renderers are replaceable; the DVM is not.

### Design principles

- **Snapshot-based**: each DVM instance is a complete, self-contained representation suitable for rendering without additional upstream reads.
- **Immutable**: once produced, a DVM snapshot is not mutated.
- **Render-agnostic**: contains no layout concepts (no colors, coordinates, widgets).
- **Domain-decoupled**: contains only primitives and plain structures (strings/numbers/bools/arrays/maps). No upstream dataclass/enum instances.
- **Deterministic construction**: given the same upstream event stream and the same DVM builder configuration, the same DVM snapshot must be produced.

### Versioning & backward compatibility

- DVM snapshots carry a fixed `dvm_schema` and `dvm_schema_version`.
- Backward-compatible changes are additive only:
  - adding optional fields,
  - adding optional sections,
  - adding new list items (with stable identifiers).
- Breaking changes require a `dvm_schema_version` increment and renderer review.

---

## Inputs & Outputs (Contracts)

### Inputs (DVM builder)

The dashboards layer may include a DVM builder that consumes upstream events to build the latest DVM snapshot. The DVM builder may consume:

- `orchestrator_event` v1 (for run cadence/health context)
- `state_gate_event` v1 (for gate status and regime payload visibility)
- `analysis_engine_event` v1 (for analysis artifact summaries)

The DVM builder must treat all upstream inputs as at-least-once and tolerate duplicates and out-of-order delivery without crashing.

### Output responsibilities (render-only)

Renderers output presentation only (TUI in v1; browser/web UI in future). Renderers:

- consume DVM snapshots (and only DVM snapshots),
- render to a target surface,
- may support local navigation (scroll, filter view) but must not write upstream.

### Prohibited dependencies

- Renderers must not import or depend on:
  - `regime_engine` types,
  - `orchestrator_event` / `state_gate_event` / `analysis_engine_event` schemas,
  - any analysis module registry or internal analysis_engine state.
- Renderers must not reach into raw logs or buffers.

---

## DVM Structure

### DVM envelope (required)

- `dvm_schema`: string, fixed value `dashboard_view_model`
- `dvm_schema_version`: string, fixed value `1`
- `as_of_ts_ms`: int (local time when the snapshot was produced)
- `source_run_id`: string | null (most recent run_id reflected in the snapshot, if any)
- `source_engine_timestamp_ms`: int | null (most recent engine timestamp reflected, if any)

### Required sections (v1)

**1) System**

- `system.status`: string (`OK` | `DEGRADED` | `UNKNOWN`)
- `system.components`: array of:
  - `component_id`: string (`orchestrator` | `state_gate` | `analysis_engine` | `dashboards`)
  - `status`: string (`OK` | `DEGRADED` | `UNKNOWN`)
  - `details`: array of strings (stable, non-sensitive)
  - `last_update_ts_ms`: int | null

**2) Symbols**

- `symbols`: array of per-symbol snapshots (order deterministic, lexicographic by `symbol`)
- Each symbol snapshot includes:
  - `symbol`: string
  - `last_run_id`: string | null
  - `last_engine_timestamp_ms`: int | null
  - `gate`:
    - `status`: string (`OPEN` | `CLOSED` | `UNKNOWN`)
    - `reasons`: array of strings (copied from state_gate when available; deterministic ordering)
  - `regime_truth` (optional; raw truth output, render-only):
    - Intent: represent the Regime Engine truth output as observed, without hysteresis interpretation.
    - Source: `orchestrator_event.EngineRunCompleted.payload.regime_output` when available.
    - Fields:
      - `regime_name`: string
      - `confidence`: number
      - `drivers`: array of strings
      - `invalidations`: array of strings
      - `permissions`: array of strings
  - `hysteresis` (optional; decision state, render-only):
    - Intent: represent hysteresis transition state as observed, without converting it into “effective regime” fields.
    - Source: `orchestrator_event.HysteresisDecisionPublished.payload.hysteresis_decision` when available.
    - Fields:
      - `effective_confidence`: number
      - `transition`:
        - `stable_regime`: string | null
        - `candidate_regime`: string | null
        - `candidate_count`: int
        - `transition_active`: bool
        - `flipped`: bool
        - `reset_due_to_gap`: bool
      - `summary` (optional; derived, render-only):
        - Intent: a glanceable narration derived only from fields already present under `hysteresis` (and, for `confidence_trend`, comparison to the previous DVM snapshot for the same symbol).
        - Guardrail: `hysteresis.summary` must not introduce new thresholds, recompute hysteresis behavior, or evolve state; it is a label-compression of already-observed decision state.
        - Presence rule: renderers must tolerate its absence. The DVM builder may omit `summary` if it cannot populate it deterministically from the available DVM fields.
        - Schema:
          - `phase`: string (`STABLE` | `TRANSITIONING` | `FLIPPED` | `RESET`)
            - Derivation rule (no new logic): derived from `transition` booleans only:
              - if `reset_due_to_gap == true` → `RESET`
              - else if `flipped == true` → `FLIPPED`
              - else if `transition_active == true` → `TRANSITIONING`
              - else → `STABLE`
          - `anchor_regime`: string | null (copy of `transition.stable_regime`)
          - `candidate_regime`: string | null (copy of `transition.candidate_regime`)
          - `progress`:
            - `current`: int (copy of `transition.candidate_count`)
            - `required`: int (required persistence count)
              - Derivation rule (no inference, no new thresholds):
                - If `transition.flipped == true`, set `required = progress.current` (the observed persistence count at which a flip occurred).
                - Else if the previous DVM snapshot for the same symbol contains `hysteresis.summary.progress.required`, carry it forward unchanged.
                - Else omit `summary` (do not invent a value).
          - `confidence_trend`: string (`RISING` | `FALLING` | `FLAT`)
            - Derivation rule: compare current `hysteresis.effective_confidence` to the previous DVM snapshot’s `hysteresis.effective_confidence` for the same symbol:
              - greater → `RISING`
              - less → `FALLING`
              - equal → `FLAT`
            - If a previous value is unavailable, set `FLAT`.
          - `notes`: array of strings (optional; stable reason codes; deterministic ordering)
            - Allowed values (v1): `reset_due_to_gap`, `flipped`
            - Population rule: include `reset_due_to_gap` if `transition.reset_due_to_gap == true`; include `flipped` if `transition.flipped == true`; sort lexicographically.
  - `regime_effective` (optional; effective regime exposed downstream, render-only):
    - Intent: represent the single effective regime that downstream consumption should treat as current.
    - Source: `state_gate_event` authoritative payload when available:
      - in truth mode: `payload.regime_output`
      - in hysteresis mode: `payload.hysteresis_decision.selected_output`
    - Fields:
      - `regime_name`: string
      - `confidence`: number
        - Mapping rule (no computation):
          - truth mode: copy `payload.regime_output.confidence`
          - hysteresis mode: copy `payload.hysteresis_decision.effective_confidence`
      - `drivers`: array of strings
      - `invalidations`: array of strings
      - `permissions`: array of strings
      - `source`: string (`truth` | `hysteresis`)
  - `analysis`: (render-only; optional depth expansion):
    - Intent:
      - Provide human-readable summaries and references to analysis artifacts produced upstream.
      - Support renderer expansion/collapse for per-symbol inspection.
      - Enable situational awareness without encoding decisions or rankings.
    - Source:
      - Derived exclusively from `analysis_engine_event` payloads.
      - Dashboards must not synthesize or infer analytical conclusions.
    - Guardrails:
      - `analysis` must not introduce new signals, scores, thresholds, or opinions.
      - `analysis` must not restate or reinterpret regime or gating decisions.
      - `analysis.highlights` are summaries, not rankings or recommendations.
      - Absence of analysis data must be handled gracefully (`status = EMPTY`).
    - `status`: string (`EMPTY` | `PARTIAL` | `PRESENT`)
    - `highlights`: array of strings (stable, best-effort summaries; deterministic ordering rule defined below)
    - `artifacts`: array of artifact summaries (optional; may be truncated):
      - `artifact_kind`: string
      - `module_id`: string
      - `artifact_name`: string
      - `artifact_schema`: string
      - `artifact_schema_version`: string
      - `summary`: string (render-safe text; no sensitive data)
  - `metrics` (optional; render-agnostic comparison metrics):
    - Intent:
      - Provide flat, numeric, deterministic observables to support renderer-side
        sorting, grouping, and visual comparison.
      - Metrics exist solely to aid human attention allocation and carry no
        interpretation, thresholds, or trade intent.
    - Source:
      - Derived exclusively from `analysis_engine_event` payloads.
      - Dashboards must not compute, infer, or mutate metrics.
    - Population rules:
      - All fields are optional and may be omitted or null.
      - Metrics must be deterministic and derived solely from upstream inputs
        explicitly allowed by this spec.
      - Metrics must not encode labels, buckets, rankings beyond numeric rank,
        or trade logic.
    - Fields:
      - `atr_pct`: number | null
        - Definition: Average True Range expressed as a percentage of price.
      - `atr_rank`: number | null
        - Definition: Rank of the symbol’s ATR within the current symbol universe, where `1` represents the **most volatile** symbol and larger values represent progressively lower volatility.
      - `range_24h_pct`: number | null
        - Definition: High–low price range over the trailing 24h window, expressed as a percentage of price.
      - `range_session_pct`: number | null
        - Definition: High–low price range over the current trading session, expressed as a percentage of price.
      - `volume_24h`: number | null
        - Definition: Total traded volume over the trailing 24h window.
      - `volume_rank`: number | null
        - Definition: Rank of the symbol’s 24h volume within the current symbol universe (ordering convention is renderer-defined).
      - `relative_volume`: number | null
        - Definition: Ratio of current volume to a typical or baseline volume (exact baseline definition is builder-specific but must be deterministic).
      - `relative_strength`: number | null
        - Definition: Relative performance metric versus a reference universe or benchmark, expressed as a scalar suitable for cross-symbol comparison.

**3) Health & Telemetry**

- `telemetry.ingest`:
  - `last_orchestrator_event_ts_ms`: int | null
  - `last_state_gate_event_ts_ms`: int | null
  - `last_analysis_engine_event_ts_ms`: int | null
- `telemetry.staleness`:
  - `is_stale`: bool
  - `stale_reasons`: array of strings (stable codes; deterministic ordering)

### Extension rules (non-breaking)

- New top-level sections must be optional.
- New fields inside existing required sections must be optional.
- Renderer compatibility rule: a renderer must ignore unknown fields and unknown optional sections.
- No single field or section may ambiguously represent both truth and effective regime outputs; use `regime_truth`, `hysteresis`, and `regime_effective` as distinct renderable sections.

### Deterministic ordering rules (v1)

- `symbols` ordered by `symbol` ascending.
- `system.components` ordered by `component_id` ascending.
- `analysis.highlights` ordered lexicographically.
- `analysis.artifacts` ordered by `(artifact_kind, module_id, artifact_name)` ascending.
- `hysteresis.summary.notes` ordered lexicographically (when present).

---

## Renderer Model

### Separation of concerns

- DVM builder: consumes upstream events and produces DVM snapshots.
- Renderer: consumes DVM snapshots and renders them.

No renderer may access upstream event streams directly.

### Renderer expectations

**TUI renderer (v1)**

- Renders the latest DVM snapshot.
- Supports local navigation only (scrolling, selecting symbol panels).
- Must remain functional under partial data (missing sections).

**Browser / web UI (future)**

- Must render the same DVM snapshot schema.
- Must not introduce upstream coupling or require schema changes for UI framework concerns.

Renderer prohibitions:

- No control-plane actions (start/stop, enable/disable modules, change thresholds).
- No alerting or notification emission.

---

## Update & Refresh Semantics

### Snapshot vs streaming

The DVM is snapshot-based. Renderers update by consuming complete snapshots.

The internal DVM builder may process streaming inputs, but must output complete DVM snapshots.

### Frequency & staleness

- Snapshot publish frequency is configurable but must not affect upstream behavior.
- If upstream updates stop or the builder cannot keep up, the DVM must surface staleness via `telemetry.staleness` rather than attempting remediation upstream.

### Partial updates

Partial updates are not a v1 contract. If a transport uses deltas internally, deltas must be applied before producing a full DVM snapshot.

---

## Dependency Boundaries

### Allowed dependencies

- Upstream event contracts (`orchestrator_event`, `state_gate_event`, `analysis_engine_event`) for the DVM builder only.
- Presentation/runtime libraries for rendering targets (TUI/web) as an implementation detail.

### Explicitly forbidden coupling

- No dependency on analysis_engine internal module code, internal state stores, or registry internals.
- No dependency on orchestration control-plane interfaces.
- No upstream writes or acknowledgements used as a correctness mechanism.

---

## Invariants & Guarantees

- Dashboards are read-only observers.
- DVM is the only renderer input contract; renderers do not consume upstream domain objects or event schemas.
- Determinism: for a fixed input event log + fixed builder config, DVM snapshots are reproducible.
- Failure isolation: dashboard failures must not affect upstream correctness or liveness.

---

## Operational Behavior

### Observability (contractual)

**Structured logs (minimum fields)**

- `dvm_schema_version`, `as_of_ts_ms`, `source_run_id`, `source_engine_timestamp_ms`
- For builder ingest: `input_schema`, `input_event_type`
- For failures: `error_kind`, `error_detail` (non-sensitive)

**Metrics (minimum set)**

- DVM snapshots produced count
- Snapshot production latency
- Renderer frame/update rate (best-effort)
- Builder lag indicators (e.g., last seen upstream timestamps)
- Failure counts by component (builder vs renderer)

### Degraded-mode expectations

- If the DVM builder cannot ingest upstream events, it must continue rendering the last known DVM snapshot and mark `system.status == DEGRADED` and `telemetry.staleness.is_stale == true`.
- If a renderer fails, the builder continues producing DVM snapshots; rendering is allowed to restart independently.

---

## Non-Goals

- No alerts, paging, or notifications.
- No control plane (no start/stop controls, no config mutation, no module toggles).
- No business logic, analysis, gating, or orchestration changes.
- No persistence beyond what is required to avoid duplicate rendering artifacts and to support DVM determinism tests.
