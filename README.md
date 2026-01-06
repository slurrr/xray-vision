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

## Regime Engine

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
```

Minimal usage (hysteresis wrapper):

```python
from regime_engine.engine import run_with_hysteresis
from regime_engine.hysteresis import HysteresisConfig, HysteresisStore

store = HysteresisStore(states={})
decision = run_with_hysteresis(snapshot, store, HysteresisConfig())
```
