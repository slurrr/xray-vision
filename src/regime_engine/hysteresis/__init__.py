from __future__ import annotations

from regime_engine.hysteresis.rules import (
    GateDecision,
    advance_hysteresis,
    evaluate_gate,
    select_candidate,
)
from regime_engine.hysteresis.state import HysteresisConfig, HysteresisState, HysteresisStore
from regime_engine.observability import get_observability
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
    prev_anchor = prev_state.anchor_regime.value if prev_state is not None else None
    committed = prev_anchor is not None and prev_anchor != next_state.anchor_regime.value
    get_observability().log_hysteresis_transition(
        symbol=next_state.symbol,
        engine_timestamp_ms=next_state.engine_timestamp_ms,
        anchor_prev=prev_state.anchor_regime if prev_state is not None else None,
        anchor_next=next_state.anchor_regime,
        candidate_regime=next_state.candidate_regime,
        progress_current=next_state.progress_current,
        progress_required=next_state.progress_required,
        committed=committed,
        reason_codes=next_state.reason_codes,
    )
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
