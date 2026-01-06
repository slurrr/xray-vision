from __future__ import annotations

from dataclasses import dataclass

from regime_engine.contracts.regimes import Regime


@dataclass(frozen=True)
class RegimeOutput:
    symbol: str
    timestamp: int

    regime: Regime
    confidence: float

    drivers: list[str]
    invalidations: list[str]

    permissions: list[str]
