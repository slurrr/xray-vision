from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.state import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    HysteresisConfig,
    HysteresisState,
)
from regime_engine.state.state import RegimeState


@dataclass(frozen=True)
class GateDecision:
    eligible: bool
    reason_codes: tuple[str, ...]


def _regime_order(allowed_regimes: Sequence[Regime] | None) -> tuple[Regime, ...]:
    if allowed_regimes is None:
        return tuple(Regime)
    return tuple(allowed_regimes)


def _select_top_regime(
    belief_by_regime: Mapping[Regime, float],
    allowed_regimes: Sequence[Regime] | None,
) -> Regime | None:
    order = _regime_order(allowed_regimes)
    if not order:
        return None

    best_regime = None
    best_value = None
    for regime in order:
        value = belief_by_regime.get(regime)
        if value is None:
            continue
        if best_value is None or value > best_value:
            best_regime = regime
            best_value = value
    return best_regime


def select_candidate(
    belief_by_regime: Mapping[Regime, float],
    anchor_regime: Regime,
    allowed_regimes: Sequence[Regime] | None,
) -> Regime | None:
    top_regime = _select_top_regime(belief_by_regime, allowed_regimes)
    if top_regime is None or top_regime == anchor_regime:
        return None
    return top_regime


def evaluate_gate(
    belief_by_regime: Mapping[Regime, float],
    anchor_regime: Regime,
    candidate_regime: Regime | None,
    config: HysteresisConfig,
) -> GateDecision:
    if candidate_regime is None:
        return GateDecision(eligible=False, reason_codes=())

    b_anchor = belief_by_regime.get(anchor_regime, 0.0)
    b_candidate = belief_by_regime.get(candidate_regime, 0.0)
    lead = b_candidate - b_anchor

    reasons = []
    eligible = True
    if b_candidate < config.enter_threshold:
        reasons.append("GATE_FAIL_ENTER_THRESHOLD")
        eligible = False
    if config.min_lead_over_anchor is not None and lead < config.min_lead_over_anchor:
        reasons.append("GATE_FAIL_MIN_LEAD")
        eligible = False

    return GateDecision(eligible=eligible, reason_codes=tuple(reasons))


def advance_hysteresis(
    prev_state: HysteresisState | None,
    regime_state: RegimeState,
    config: HysteresisConfig,
) -> HysteresisState:
    reasons: list[str] = []

    if prev_state is None:
        anchor_regime = regime_state.anchor_regime
    else:
        anchor_regime = prev_state.anchor_regime
    progress_required = config.window_updates
    prev_candidate = prev_state.candidate_regime if prev_state is not None else None
    prev_progress = prev_state.progress_current if prev_state is not None else 0
    last_commit = prev_state.last_commit_timestamp_ms if prev_state is not None else None

    top_regime = _select_top_regime(
        regime_state.belief_by_regime,
        config.allowed_regimes,
    )
    if top_regime is None:
        reasons.append("CANDIDATE_NONE")
        candidate = None
    elif top_regime == anchor_regime:
        reasons.append("CANDIDATE_SAME_AS_ANCHOR")
        candidate = None
    else:
        candidate = top_regime
        reasons.append(f"CANDIDATE_SELECTED:{candidate.value}")

    gate_decision = evaluate_gate(
        regime_state.belief_by_regime,
        anchor_regime,
        candidate,
        config,
    )
    reasons.extend(gate_decision.reason_codes)

    progress = prev_progress
    candidate_regime = prev_candidate

    if gate_decision.eligible and candidate is not None:
        if candidate_regime == candidate:
            progress = min(prev_progress + 1, progress_required)
            reasons.append("PROGRESS_INC")
        else:
            candidate_regime = candidate
            progress = 1
            reasons.append("PROGRESS_RESET")
    else:
        if prev_progress > 0:
            progress = max(0, prev_progress - config.decay_step)
            reasons.append("PROGRESS_DECAY")
        else:
            progress = 0
            reasons.append("PROGRESS_RESET")
        if progress == 0:
            candidate_regime = None

    if candidate_regime is not None and progress >= progress_required:
        b_candidate = regime_state.belief_by_regime.get(candidate_regime, 0.0)
        if b_candidate >= config.commit_threshold:
            reasons.append(
                f"COMMIT_SWITCH:{anchor_regime.value}->{candidate_regime.value}"
            )
            anchor_regime = candidate_regime
            candidate_regime = None
            progress = 0
            last_commit = regime_state.engine_timestamp_ms
        else:
            reasons.append("COMMIT_BLOCKED_THRESHOLD")

    if progress < 0:
        progress = 0
    if progress > progress_required:
        progress = progress_required

    belief_debug = {
        "belief_by_regime": {
            regime.value: value
            for regime, value in regime_state.belief_by_regime.items()
        }
    }

    return HysteresisState(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=regime_state.symbol,
        engine_timestamp_ms=regime_state.engine_timestamp_ms,
        anchor_regime=anchor_regime,
        candidate_regime=candidate_regime,
        progress_current=progress,
        progress_required=progress_required,
        last_commit_timestamp_ms=last_commit,
        reason_codes=tuple(reasons),
        debug=belief_debug,
    )
