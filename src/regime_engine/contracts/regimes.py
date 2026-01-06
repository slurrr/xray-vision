from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class RegimeScore:
    regime: Regime
    score: float
    contributors: list[str]
