from __future__ import annotations

from dataclasses import dataclass

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime


@dataclass(frozen=True)
class HysteresisTransition:
    stable_regime: Regime | None
    candidate_regime: Regime | None
    candidate_count: int
    transition_active: bool
    flipped: bool
    reset_due_to_gap: bool


@dataclass(frozen=True)
class HysteresisDecision:
    selected_output: RegimeOutput
    effective_confidence: float
    transition: HysteresisTransition
