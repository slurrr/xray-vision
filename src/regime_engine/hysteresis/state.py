from __future__ import annotations

from dataclasses import dataclass

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime


@dataclass(frozen=True)
class HysteresisConfig:
    min_persistence_updates: int = 3
    min_confidence_for_flip: float = 0.6
    decay_factor: float = 0.85
    min_confidence_floor: float = 0.2
    update_interval_ms: int = 180_000


@dataclass(frozen=True)
class HysteresisState:
    stable_output: RegimeOutput | None = None
    candidate_regime: Regime | None = None
    candidate_count: int = 0
    last_timestamp: int | None = None


@dataclass
class HysteresisStore:
    states: dict[str, HysteresisState]

    def state_for(self, symbol: str) -> HysteresisState:
        return self.states.get(symbol, HysteresisState())

    def update(self, symbol: str, state: HysteresisState) -> None:
        self.states[symbol] = state
