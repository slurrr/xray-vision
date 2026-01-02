# Regime Engine — Foundation Specificationasdf

---

## Freeze Declarations

## Phase 0 Freeze Declaration

Phase 0 (Data Contracts & Snapshot Builder) is declared frozen.

The following are now stable and breaking-change protected:

- RegimeInputSnapshot and all sub-snapshots
- Missing-data representation semantics
- Timestamp alignment rules
- Snapshot serialization format

Changes to Phase 0 contracts require explicit versioning and downstream review.

## Phase 1 Freeze Declaration

Phase 1 — Feature Library is declared frozen.

## Phase 2 Freeze Declaration

Phase 2 — Regime Taxonomy & Scoring is declared frozen.

## Phase 3 — Freeze Declaration

Phase 3 — Hard Veto Logic is declared frozen.

---

## 1. Purpose

The Regime Engine is the truth layer of the scanner.
It classifies why price is moving, determines what behaviors are allowed,
and exposes invalidations.

It does NOT:

- Generate trade signals
- Scan patterns
- Execute trades

All downstream layers depend on it.

---

## 2. Architectural Position

asdf
Market Feeds
→ Regime Engine
├─ Phase 0: Data contracts + snapshot builder
├─ Phase 1: Feature computation
├─ Phase 2: Regime scoring + vetoes
├─ Phase 3: Resolution + confidence + explainability
└─ Phase 4: Hysteresis + memory
→ State Gate (IGNORE / WATCH / ACT)
→ Pattern Scanner (3m)
→ Human Discretion

Hard rule: downstream components may not recompute regime logic.

---

## 3. Design Principles

- Deterministic
- Explainable
- Data-first
- Small, stable regime taxonomy
- Explicit uncertainty
- Extensible without refactor

---

## 4. Cadence & Timeframes

- Regime update cadence: 3m
- Feature baselines: 15m and 1h
- Hysteresis window: configurable (default 3 updates)

---

## 5. Canonical Input Contract

### 5.1 RegimeInputSnapshot

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class RegimeInputSnapshot:
    symbol: str
    timestamp: int  # ms, aligned to 3m close

    market: "MarketSnapshot"
    derivatives: "DerivativesSnapshot"
    flow: "FlowSnapshot"
    context: "ContextSnapshot"
```

Missing data must be explicit and propagated.

---

### 5.2 Sub-Snapshots

#### MarketSnapshot

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class MarketSnapshot:
    price: float
    vwap: float
    atr: float
    atr_z: float
    range_expansion: float
    structure_levels: dict
    acceptance_score: float
    sweep_score: float
```

#### DerivativesSnapshot

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class DerivativesSnapshot:
    open_interest: float
    oi_slope_short: float
    oi_slope_med: float
    oi_accel: float
    funding_rate: float
    funding_slope: float
    funding_z: float
    liquidation_intensity: Optional[float]
```

#### FlowSnapshot

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class FlowSnapshot:
    cvd: float
    cvd_slope: float
    cvd_efficiency: float
    aggressive_volume_ratio: float
```

#### ContextSnapshot

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ContextSnapshot:
    rs_vs_btc: float
    beta_to_btc: float
    alt_breadth: float
    btc_regime: Optional[str]
    eth_regime: Optional[str]
```

---

## 6. Feature Library

- Pure functions only
- No cross-feature coupling
- Rolling z-score normalization
- Unit-testable from frozen snapshots

Feature groups:

- Positioning / leverage
- Flow efficiency
- Volatility / range
- Acceptance vs rejection
- Context / breadth

---

## 7. Regime Taxonomy (Locked)

```python
from enum import Enum

class Regime(Enum):
    CHOP_BALANCED = "CHOP_BALANCED"
    CHOP_STOPHUNT = "CHOP_STOPHUNT"
    LIQUIDATION_UP = "LIQUIDATION_UP"
    LIQUIDATION_DOWN = "LIQUIDATION_DOWN"
    SQUEEZE_UP = "SQUEEZE_UP"
    SQUEEZE_DOWN = "SQUEEZE_DOWN"
    TREND_BUILD_UP = "TREND_BUILD_UP"
    TREND_BUILD_DOWN = "TREND_BUILD_DOWN"
    TREND_EXHAUSTION = "TREND_EXHAUSTION"
```

No additions without removals.

---

## 8. Scoring Model

```python
from dataclasses import dataclass
from typing import List

@dataclass
class RegimeScore:
    regime: Regime
    score: float
    contributors: List[str]
```

Rules:

- Weighted composite scoring
- Relative scores only
- No single feature dominance

---

## 9. Hard Veto Gates

Truth constraints applied before scoring.

Examples:

- High acceptance → forbid liquidation and chop
- OI contracting + ATR expanding → forbid trend build
- OI flat + ATR compressed → force CHOP_BALANCED

---

## 10. Resolution & Confidence

- Rank regimes by score after vetoes
- Select top regime

Confidence derived from:

- Score separation
- Pillar agreement
- Stability over time

Range: 0–1

---

## 11. Explainability (Mandatory)

```python
from dataclasses import dataclass
from typing import List

@dataclass
class RegimeOutput:
    symbol: str
    timestamp: int

    regime: Regime
    confidence: float

    drivers: List[str]
    invalidations: List[str]

    permissions: List[str]
```

Empty drivers or invalidations invalidate the output.

---

## 12. Hysteresis & Stability

- Regime flips only if:
  - New regime exceeds score threshold
  - Persists for N updates
- Confidence decays during transitions

---

## 13. Logging & Evaluation

Logging:

- JSONL per update
- All regime scores
- Selected regime
- Confidence
- Drivers
- Invalidations

Evaluation metrics:

- Regime persistence
- Flip frequency
- Forward return distributions
- Forward volatility distributions
- Strategy-conditional expectancy

---

## 14. Downstream Integration Contract

State Gate depends only on:

- regime
- confidence
- permissions

Pattern Scanner depends only on:

- State = ACT
- Regime permissions

No back-references allowed.

---

## 15. Definition of Done

- Runs standalone
- Produces stable regimes
- Explains itself clearly
- Wrong beats vague
- No downstream refactors required
