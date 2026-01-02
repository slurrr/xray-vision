from __future__ import annotations

from dataclasses import dataclass

from regime_engine.contracts.regimes import Regime


@dataclass(frozen=True)
class VetoResult:
    regime: Regime
    vetoed: bool
    reasons: list[str]
