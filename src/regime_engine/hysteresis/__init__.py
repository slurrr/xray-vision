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
    anchor_for_candidate = (
        prev_state.anchor_regime if prev_state is not None else regime_state.anchor_regime
    )
    candidate = select_candidate(
        regime_state.belief_by_regime,
        anchor_for_candidate,
        active_config.allowed_regimes,
    )
    b_anchor = regime_state.belief_by_regime.get(anchor_for_candidate, 0.0)
    b_candidate = (
        regime_state.belief_by_regime.get(candidate, 0.0) if candidate is not None else None
    )
    lead_over_anchor = b_candidate - b_anchor if b_candidate is not None else None
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
    decision = "SWITCH" if committed else "HOLD"
    reason_code = _select_reason_code(next_state.reason_codes)
    get_observability().log_hysteresis_decision(
        symbol=next_state.symbol,
        engine_timestamp_ms=next_state.engine_timestamp_ms,
        prior_anchor_regime=prev_state.anchor_regime if prev_state is not None else None,
        candidate_regime=candidate,
        selected_regime=next_state.anchor_regime,
        decision=decision,
        window_size=active_config.window_updates,
        confirmation_count=next_state.progress_current,
        threshold=active_config.commit_threshold,
        belief_margin=lead_over_anchor,
        reason_code=reason_code,
    )
    return next_state


def _select_reason_code(reason_codes: tuple[str, ...]) -> str:
    for code in reason_codes:
        if code.startswith("COMMIT_SWITCH:"):
            return code
    for code in reason_codes:
        if code == "COMMIT_BLOCKED_THRESHOLD":
            return code
    for code in reason_codes:
        if code.startswith("GATE_FAIL_"):
            return code
    return reason_codes[0] if reason_codes else "NONE"


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
