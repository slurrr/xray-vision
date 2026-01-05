# xray-vision

Each top-level subsystem is governed by its own AGENTS.md, spec.md and tasks.md.
Rules are scoped to their directory tree.

## Maket Data

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
