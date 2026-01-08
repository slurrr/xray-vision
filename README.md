# xray-vision

Each top-level subsystem is governed by its own AGENTS.md, spec.md and tasks.md.
Rules are scoped to their directory tree.

## Market Data

The market_data layer acquires raw receipts, performs shape-level normalization,
and emits immutable `RawMarketEvent` v1 envelopes. It is a transport + normalization
pipe only.

What it does:

- Preserves `raw_payload` byte-for-byte alongside normalized fields
- Emits canonical `RawMarketEvent` v1 with deterministic envelopes
- Emits `DecodeFailure` instead of silent drops on malformed input

What it does not do:

- Construct candles, align timestamps, or infer gaps
- Smooth, filter, de-duplicate, or correct values
- Compute indicators, regimes, or signals

Non-goals:

- Aggregation or inference of market meaning
- Downstream coupling or feedback
- Local replay stores (handled downstream)

Phase discipline:

- Follow `Planning/market_data/tasks.md` strictly in order.
- Contracts come first. No adapter lifecycle or decode paths until Phase 0 is frozen.

Determinism requirements:

- `recv_ts_ms` assigned exactly once at receipt
- `raw_payload` is immutable
- Normalized fields are direct mappings only

Public entrypoints:

- `market_data.contracts.RawMarketEvent` (v1 contract)
- `market_data.pipeline.IngestionPipeline`
- `market_data.decoder.decode_and_ingest(...) -> RawMarketEvent`

Minimal usage (decode + emit):

```python
from market_data.contracts import RawMarketEvent
from market_data.config import BackpressureConfig
from market_data.decoder import decode_and_ingest
from market_data.observability import NullLogger, NullMetrics, Observability
from market_data.pipeline import IngestionPipeline


class RecordingSink:
    def __init__(self) -> None:
        self.events = []

    def write(self, event: RawMarketEvent, *, block: bool, timeout_ms: int | None) -> None:
        self.events.append(event)


pipeline = IngestionPipeline(
    sink=RecordingSink(),
    backpressure=BackpressureConfig(policy="block", max_pending=1, max_block_ms=50),
    observability=Observability(logger=NullLogger(), metrics=NullMetrics()),
)

event = decode_and_ingest(
    pipeline=pipeline,
    event_type="TradeTick",
    source_id="source",
    symbol="TEST",
    exchange_ts_ms=123,
    raw_payload=b'{"price": 1.0, "quantity": 2.0, "side": "buy"}',
    payload_content_type="application/json",
)
```

## Orchestrator

The orchestrator layer coordinates ingestion, buffering, scheduling, and engine
invocation into a deterministic, replayable sequence of runs and outputs.

What it does:

- Appends every `RawMarketEvent` into an append-only buffer
- Persists deterministic run metadata (`EngineRunRecord` v1)
- Selects snapshot inputs deterministically and invokes the Regime Engine
- Publishes `orchestrator_event` v1 outputs with per-symbol ordering

What it does not do:

- Compute indicators, features, regimes, or signals
- Infer completeness, align timestamps, or fill gaps
- Apply consumer-specific logic or feedback loops

Non-goals:

- Market interpretation or data correction
- Consumer orchestration beyond generic fan-out
- Modifying Regime Engine behavior

Phase discipline:

- Follow `Planning/orchestrator/tasks.md` strictly in order.
- Contracts come first. No buffering/scheduling/invocation until Phase 0 is frozen.

Determinism requirements:

- Append-only buffer with strictly increasing `ingest_seq`
- Deterministic `run_id` derivation
- Replay equivalence from buffer + run logs

Public entrypoints:

- `orchestrator.contracts.OrchestratorEvent` (v1 contract)
- `orchestrator.buffer.RawInputBuffer`
- `orchestrator.scheduler.Scheduler`
- `orchestrator.cuts.CutSelector`
- `orchestrator.publisher.OrchestratorEventPublisher`

Minimal usage (deterministic cut + publish):

```python
from market_data.contracts import RawMarketEvent
from orchestrator.buffer import RawInputBuffer
from orchestrator.cuts import CutSelector
from orchestrator.publisher import OrchestratorEventPublisher, build_engine_run_started
from orchestrator.sequencing import SymbolSequencer


class RecordingSink:
    def __init__(self) -> None:
        self.events = []

    def write(self, event) -> None:
        self.events.append(event)


buffer = RawInputBuffer(max_records=10)
buffer.append(
    RawMarketEvent(
        schema="raw_market_event",
        schema_version="1",
        event_type="TradeTick",
        source_id="source",
        symbol="TEST",
        exchange_ts_ms=None,
        recv_ts_ms=1,
        raw_payload=b"{}",
        normalized={"price": 1.0, "quantity": 1.0, "side": None},
    )
)

cut = CutSelector().next_cut(buffer=buffer, symbol="TEST", cut_end_ingest_seq=1, cut_kind="timer")
publisher = OrchestratorEventPublisher(sink=RecordingSink(), sequencer=SymbolSequencer())
publisher.publish(
    build_engine_run_started(
        run_id="run-1",
        symbol="TEST",
        engine_timestamp_ms=123,
        cut_start_ingest_seq=cut.cut_start_ingest_seq,
        cut_end_ingest_seq=cut.cut_end_ingest_seq,
        cut_kind=cut.cut_kind,
        engine_mode="truth",
    )
)
```

## Composer

The Composer layer deterministically assembles engine-ready inputs from raw market data cuts.  
It is the sole location where **feature computation** and **evidence construction** occur.

The Composer does **not** perform inference, belief updates, hysteresis, or gating.

What it does

- Consumes deterministic cuts of `RawMarketEvent` selected by the orchestrator
- Computes numeric, descriptive **features** (indicators, rolling statistics, structure measures)
- Constructs **evidence opinions** by interpreting features (stateless observers)
- Assembles immutable, replayable engine input snapshots
- Emits composed inputs suitable for Regime Engine invocation

What it does not do

- Update or store belief state
- Apply hysteresis or temporal inertia
- Classify regimes authoritatively
- Gate downstream execution
- Perform strategy, analysis, or pattern recognition
- Mutate or reinterpret raw payloads

Non-goals

- Inference or decision-making
- Learning, optimization, or parameter adaptation
- Consumer-specific logic
- Downstream feedback or control signals

Architectural role

The Composer exists to make belief-driven inference possible without violating system discipline.

Key principles:

- **Belief is not in the data** — it must be constructed
- **Features are numeric descriptions**, not meaning
- **Evidence is opinionated but stateless**
- **Inference lives downstream**

The Composer provides the boundary between:

- raw data ingestion (`market_data` / `orchestrator`)
- belief inference (`regime_engine`)

Computation classes

The Composer explicitly separates two computation types:

Feature computation

- Deterministic numeric calculations (e.g. indicators, slopes, z-scores)
- Window-bounded state only
- No interpretation or meaning
- Organized internally under a `features/` module

Evidence construction

- Stateless observers that interpret features
- Emit sparse, opinionated evidence (direction, strength, confidence)
- Includes classical or heuristic regime observers
- Organized internally under an `evidence/` module

Phase discipline

- Follow `Planning/composer/tasks.md` strictly in order
- Contracts are frozen before any feature or evidence logic is implemented
- Feature math precedes evidence construction
- No inference logic is permitted in this layer

Determinism requirements

- Identical raw inputs and cuts must produce identical composed outputs
- Feature computation must be pure and deterministic
- Evidence construction must be stateless
- All outputs must be suitable for replay equivalence

Public entrypoints

- `composer.contracts.FeatureSnapshot`
- `composer.contracts.EvidenceSnapshot`
- `composer.composer.compose(...) -> (FeatureSnapshot, EvidenceSnapshot)`

Minimal usage (conceptual)

````python
from composer.composer import compose

feature_snapshot, evidence_snapshot = compose(
    raw_events=cut_events,
    symbol="TEST",
    engine_timestamp_ms=180_000,
)
```
The orchestrator is responsible for invoking the Regime Engine with composed inputs;
the Composer does not perform invocation itself.


## Regime Engine

    > ⚠️ Architectural Clarification (Authoritative)
    >
    > The Regime Engine maintains a *single authoritative internal state* representing
    > belief over regimes (RegimeState).
    >
    > “Regime” labels exposed in outputs are *derived projections* of that belief
    > (e.g. dominant regime at the current timestep), not independently maintained truth.
    >
    > Any classical or heuristic regime classification logic is treated as *evidence*
    > (observer opinions) feeding belief updates, not as a parallel source of authority.
    >
    > Hysteresis applies to belief evolution, not to regime labels directly.

The Regime Engine is the truth layer of a crypto scanner. It classifies why price is
moving, determines allowed behaviors, and exposes invalidations. All downstream
layers depend on its outputs and may not recompute regime logic.

What it does:

- Deterministic regime classification from frozen inputs
- Emits immutable `RegimeOutput` with drivers, invalidations, and permissions
- Optional hysteresis wrapper for operational stability (separate from truth)

What it does not do:

- Generate trade signals
- Scan patterns
- Execute trades
- Recompute regime logic downstream

Non-goals:

- Pattern detection
- Trade signals
- Execution logic
- Strategy assumptions

Phase discipline:

- Follow `tasks.md` strictly in order.
- Contracts come first. Do not implement features/scoring/veto/hysteresis logic
  until Phase 0 contracts are complete and frozen.

Determinism requirements:

- Frozen dataclasses for snapshots and outputs
- Explicit missing data representation (never silent)
- Snapshot serialization suitable for replay

Public entrypoints:

- `regime_engine.engine.run(snapshot) -> RegimeOutput` (truth API)
- `regime_engine.engine.run_with_hysteresis(snapshot, state, config) -> HysteresisDecision`

Contracts are immutable. Changes require explicit versioning and downstream review.

Minimal usage (truth API):

```python
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.engine import run

snapshot = RegimeInputSnapshot(
    symbol="TEST",
    timestamp=180_000,
    market=MarketSnapshot(
        price=1.0,
        vwap=1.0,
        atr=1.0,
        atr_z=0.0,
        range_expansion=0.0,
        structure_levels={},
        acceptance_score=0.0,
        sweep_score=0.0,
    ),
    derivatives=DerivativesSnapshot(
        open_interest=1.0,
        oi_slope_short=0.0,
        oi_slope_med=0.0,
        oi_accel=0.0,
        funding_rate=0.0,
        funding_slope=0.0,
        funding_z=0.0,
        liquidation_intensity=None,
    ),
    flow=FlowSnapshot(
        cvd=0.0,
        cvd_slope=0.0,
        cvd_efficiency=0.0,
        aggressive_volume_ratio=0.0,
    ),
    context=ContextSnapshot(
        rs_vs_btc=0.0,
        beta_to_btc=0.0,
        alt_breadth=0.0,
        btc_regime=None,
        eth_regime=None,
    ),
)

output = run(snapshot)
````

Minimal usage (hysteresis wrapper):

```python
from regime_engine.engine import run_with_hysteresis
from regime_engine.hysteresis import HysteresisConfig, HysteresisStore

store = HysteresisStore(states={})
decision = run_with_hysteresis(snapshot, store, HysteresisConfig())
```

## State Gate

The state_gate layer materializes a deterministic per-symbol gate over orchestrator outputs and publishes explicit `state_gate_event` v1 decisions.

What it does:

- Consumes `orchestrator_event` v1 (`EngineRunCompleted`, `EngineRunFailed`, `HysteresisDecisionPublished`)
- Assembles a single authoritative payload per `run_id` (hysteresis wins when present)
- Applies deterministic resets (`max_gap_ms`, hysteresis `reset_due_to_gap`) before evaluation
- Evaluates gate status with ordered rules (run failure → CLOSED/DEGRADED; denylisted invalidations → CLOSED/HOLD; transition hold when configured; else OPEN/READY)
- Persists append-only `StateGateStateRecord` v1 log and maintains a snapshot cache for restart/replay
- Emits `GateEvaluated`, `StateReset`, and `StateGateHalted` events with stable reason codes

What it does not do:

- Compute market features, indicators, signals, or regimes
- Apply consumer-specific routing, prioritization, or downstream coupling
- Alter or “fix” Regime Engine outputs or orchestrator metadata
- Make wall-clock-based gating decisions

Non-goals:

- Alerts, dashboards, or user-facing outputs beyond structured logs/metrics
- Strategy or execution logic
- Upstream feedback or data correction

Phase discipline:

- Follow `Planning/consumers/state_gate/tasks.md` in order; contracts are frozen first, gating logic and persistence follow, then observability/failure isolation and determinism tests.

Determinism requirements:

- Idempotent handling of duplicated `(run_id, input_event_type)` inputs
- Exactly one `GateEvaluated` per `(symbol, run_id)`
- Append-only state log; restart/replay must reproduce the same output sequence
- Fail-closed: persistence/publish/internal failures halt and never emit OPEN gates

Public entrypoints:

- `consumers.state_gate.StateGateProcessor` (ingest orchestrator events → state_gate events)
- `consumers.state_gate.StateGateConfig` / `OperationLimits` / `validate_config`
- `consumers.state_gate.StateGateStateStore` (append-only log + snapshots)
- Contracts in `consumers.state_gate.contracts` (`StateGateEvent`, `StateGateStateRecord`, reason/reset codes)

Minimal usage (consume + decide):

```python
from consumers.state_gate import StateGateConfig, OperationLimits, StateGateProcessor
from orchestrator.contracts import OrchestratorEvent


config = StateGateConfig(
    max_gap_ms=1000,
    denylisted_invalidations=["late_data"],
    block_during_transition=True,
    input_limits=OperationLimits(max_pending=10, max_block_ms=100, max_failures=3),
    persistence_limits=OperationLimits(max_pending=10, max_block_ms=100, max_failures=3),
    publish_limits=OperationLimits(max_pending=10, max_block_ms=100, max_failures=3),
)

processor = StateGateProcessor(config=config)

# given an orchestrator OrchestratorEvent named event
outputs = processor.consume(event)  # list of StateGateEvent (GateEvaluated/StateReset/StateGateHalted)
```

## Analysis Engine

The analysis_engine layer runs gated analyses over `state_gate_event` inputs and emits deterministic `analysis_engine_event` v1 artifacts.

What it does:

- Consumes `state_gate_event` v1 and runs only when `gate_status == OPEN`
- Emits lifecycle events (`AnalysisRunStarted`, `AnalysisRunCompleted`, `AnalysisRunSkipped`, `AnalysisRunFailed`) and module outcomes (`ArtifactEmitted`, `ModuleFailed`)
- Executes registered modules in fixed stages (signals → detectors → rules → outputs) with dependency ordering and lexicographic ties
- Applies idempotency by `run_id` and persists optional module state via `AnalysisModuleStateRecord` v1 (append-only)
- Provides observable logs/metrics and health/readiness reporting

What it does not do:

- Infer regimes, alter gating, or execute trading/alerting logic
- Import upstream `market_data` or feed back into gating/engine
- Use wall-clock/randomness in computation stages (outputs may perform I/O but never affect computation)

Non-goals:

- Strategy/execution directives, sizing, or alerts/UI
- DSL-driven logic; configuration only enables modules and validates schemas
- Persistence beyond idempotency/state replay needs

Phase discipline:

- Follow `Planning/consumers/analysis_engine/tasks.md` in order; contracts freeze first, then shell, registry/plan, config guardrails, execution harness, outputs, observability, determinism tests, readiness note.

Determinism requirements:

- Idempotent handling of duplicate `run_id`; skip reprocessing
- Fixed stage and dependency order; artifact emission ordered by stage → module_id → artifact_name
- Module failures isolated to `PARTIAL` runs; missing deps yield deterministic `ModuleFailed`
- Replay-safe outputs from fixed input stream + config; module state appended only on successful modules

Public entrypoints:

- `consumers.analysis_engine.AnalysisEngine` (ingest `state_gate_event` → `analysis_engine_event`)
- `consumers.analysis_engine.AnalysisEngineConfig` / `ModuleConfig` / `SymbolConfig` / `validate_config`
- Registry and module helpers in `consumers.analysis_engine.registry` and `consumers.analysis_engine.modules`
- Contracts in `consumers.analysis_engine.contracts` (`AnalysisEngineEvent`, `ModuleDefinition`, `AnalysisModuleStateRecord`)

Minimal usage (gated run handling):

```python
from consumers.analysis_engine import AnalysisEngine, AnalysisEngineConfig, ModuleRegistry

registry = ModuleRegistry(modules=[])  # populate with AnalysisModule instances
config = AnalysisEngineConfig(enabled_modules=[], module_configs=[])
engine = AnalysisEngine(registry=registry, config=config)

# given a state_gate_event named event
outputs = engine.consume(event)  # list of AnalysisEngineEvent (lifecycle, artifacts, failures)
```

## Dashboards

The dashboards layer renders a read-only view of system state using the Dashboard View Model (DVM) and a TUI renderer.

What it does:

- Consumes orchestrator, state_gate, and analysis_engine events to build full DVM snapshots
- Renders immutable DVM snapshots via a TUI renderer
- Surfaces ingest failures and staleness in system/telemetry sections

What it does not do:

- Influence upstream behavior or emit control signals
- Interpret regimes, apply scoring, or generate analysis logic
- Depend on upstream schemas within the renderer (DVM only)

Non-goals:

- Alerting/notification systems
- Bi-directional control or feedback
- Partial/delta snapshot rendering (v1 produces full snapshots only)

Phase discipline:

- Follow `Planning/consumers/dashboards/tasks.md` in order; DVM contract first, builder next, renderer after.

Determinism requirements:

- DVM snapshots are immutable once produced
- Arrays are deterministically ordered by contract rules
- Missing optional sections never crash rendering

Public entrypoints:

- `consumers.dashboards.DashboardBuilder` (ingest events → DVM snapshots)
- `consumers.dashboards.TuiRenderer` (render DVM snapshots)
- Contracts in `consumers.dashboards.contracts` (`DashboardViewModel` and DVM sections)

Minimal usage (builder + TUI):

```python
from consumers.dashboards import DashboardBuilder, TuiRenderer

builder = DashboardBuilder()
renderer = TuiRenderer()
renderer.start()

# ingest upstream events into builder, then:
snapshot = builder.build_snapshot()
renderer.render(snapshot)
```
