from __future__ import annotations

from dataclasses import dataclass
from typing import List

from regime_engine.contracts.regimes import Regime


@dataclass(frozen=True)
class RegimeOutput:
    symbol: str
    timestamp: int

    regime: Regime
    confidence: float

    drivers: List[str]
    invalidations: List[str]

    permissions: List[str]
