from __future__ import annotations

import math
from typing import Final

from regime_engine.contracts.regimes import Regime
from regime_engine.state.state import RegimeState

_BELIEF_TOLERANCE: Final[float] = 1e-9


def _is_finite(value: float) -> bool:
    return math.isfinite(value)


def assert_belief_invariants(state: RegimeState) -> None:
    beliefs = state.belief_by_regime
    assert beliefs, "belief_by_regime must not be empty"
    assert state.anchor_regime in beliefs, "anchor_regime must be present in belief_by_regime"

    total = 0.0
    for regime, value in beliefs.items():
        assert isinstance(regime, Regime), "belief keys must be Regime"
        assert _is_finite(value), "belief values must be finite"
        assert 0.0 <= value <= 1.0, "belief values must be within [0, 1]"
        total += value

    assert abs(total - 1.0) <= _BELIEF_TOLERANCE, "belief must sum to 1"
