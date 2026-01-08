from __future__ import annotations

from regime_engine.hysteresis.rules import (
    GateDecision,
    advance_hysteresis,
    evaluate_gate,
    select_candidate,
)
from regime_engine.hysteresis.state import HysteresisConfig, HysteresisState, HysteresisStore
from regime_engine.state.state import RegimeState


def process_state(
    regime_state: RegimeState,
    *,
    store: HysteresisStore,
    config: HysteresisConfig | None = None,
) -> HysteresisState:
    active_config = config or HysteresisConfig()
    prev_state = store.state_for(regime_state.symbol)
    next_state = advance_hysteresis(prev_state, regime_state, active_config)
    store.update(regime_state.symbol, next_state)
    return next_state


__all__ = [
    "GateDecision",
    "HysteresisConfig",
    "HysteresisState",
    "HysteresisStore",
    "advance_hysteresis",
    "evaluate_gate",
    "process_state",
    "select_candidate",
]
