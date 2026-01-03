from __future__ import annotations

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.hysteresis.decision import HysteresisDecision, HysteresisTransition
from regime_engine.hysteresis.rules import HysteresisError, apply_hysteresis
from regime_engine.hysteresis.state import HysteresisConfig, HysteresisState, HysteresisStore


def process_output(
    output: RegimeOutput,
    *,
    store: HysteresisStore,
    config: HysteresisConfig | None = None,
) -> HysteresisDecision:
    active_config = config or HysteresisConfig()
    state = store.state_for(output.symbol)
    decision, next_state = apply_hysteresis(output, state=state, config=active_config)
    store.update(output.symbol, next_state)
    return decision


__all__ = [
    "HysteresisConfig",
    "HysteresisDecision",
    "HysteresisError",
    "HysteresisState",
    "HysteresisStore",
    "HysteresisTransition",
    "apply_hysteresis",
    "process_output",
]
