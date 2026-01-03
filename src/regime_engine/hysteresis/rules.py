from __future__ import annotations

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.hysteresis.decay import apply_confidence_decay
from regime_engine.hysteresis.decision import HysteresisDecision, HysteresisTransition
from regime_engine.hysteresis.state import HysteresisConfig, HysteresisState


class HysteresisError(ValueError):
    pass


def apply_hysteresis(
    output: RegimeOutput,
    *,
    state: HysteresisState,
    config: HysteresisConfig,
) -> tuple[HysteresisDecision, HysteresisState]:
    last_timestamp = state.last_timestamp
    if last_timestamp is not None and output.timestamp <= last_timestamp:
        raise HysteresisError("Non-increasing timestamp for hysteresis input.")

    gap = (
        last_timestamp is not None
        and output.timestamp - last_timestamp > config.update_interval_ms
    )
    if gap:
        next_state = HysteresisState(
            stable_output=output,
            candidate_regime=None,
            candidate_count=0,
            last_timestamp=output.timestamp,
        )
        transition = HysteresisTransition(
            stable_regime=output.regime,
            candidate_regime=None,
            candidate_count=0,
            transition_active=False,
            flipped=False,
            reset_due_to_gap=True,
        )
        decision = HysteresisDecision(
            selected_output=output,
            effective_confidence=output.confidence,
            transition=transition,
        )
        return decision, next_state

    if state.stable_output is None:
        next_state = HysteresisState(
            stable_output=output,
            candidate_regime=None,
            candidate_count=0,
            last_timestamp=output.timestamp,
        )
        transition = HysteresisTransition(
            stable_regime=output.regime,
            candidate_regime=None,
            candidate_count=0,
            transition_active=False,
            flipped=False,
            reset_due_to_gap=False,
        )
        decision = HysteresisDecision(
            selected_output=output,
            effective_confidence=output.confidence,
            transition=transition,
        )
        return decision, next_state

    stable_output = state.stable_output

    if output.regime == stable_output.regime:
        next_state = HysteresisState(
            stable_output=output,
            candidate_regime=None,
            candidate_count=0,
            last_timestamp=output.timestamp,
        )
        transition = HysteresisTransition(
            stable_regime=output.regime,
            candidate_regime=None,
            candidate_count=0,
            transition_active=False,
            flipped=False,
            reset_due_to_gap=False,
        )
        decision = HysteresisDecision(
            selected_output=output,
            effective_confidence=output.confidence,
            transition=transition,
        )
        return decision, next_state

    candidate_regime = output.regime
    if state.candidate_regime != candidate_regime:
        candidate_count = 1
    else:
        candidate_count = state.candidate_count + 1

    flip_ready = (
        candidate_count >= config.min_persistence_updates
        and output.confidence >= config.min_confidence_for_flip
    )

    if flip_ready:
        next_state = HysteresisState(
            stable_output=output,
            candidate_regime=None,
            candidate_count=0,
            last_timestamp=output.timestamp,
        )
        transition = HysteresisTransition(
            stable_regime=output.regime,
            candidate_regime=None,
            candidate_count=0,
            transition_active=False,
            flipped=True,
            reset_due_to_gap=False,
        )
        decision = HysteresisDecision(
            selected_output=output,
            effective_confidence=output.confidence,
            transition=transition,
        )
        return decision, next_state

    effective_confidence = apply_confidence_decay(
        stable_output.confidence,
        candidate_count=candidate_count,
        decay_factor=config.decay_factor,
        min_confidence_floor=config.min_confidence_floor,
    )

    next_state = HysteresisState(
        stable_output=stable_output,
        candidate_regime=candidate_regime,
        candidate_count=candidate_count,
        last_timestamp=output.timestamp,
    )
    transition = HysteresisTransition(
        stable_regime=stable_output.regime,
        candidate_regime=candidate_regime,
        candidate_count=candidate_count,
        transition_active=True,
        flipped=False,
        reset_due_to_gap=False,
    )
    decision = HysteresisDecision(
        selected_output=stable_output,
        effective_confidence=effective_confidence,
        transition=transition,
    )
    return decision, next_state
