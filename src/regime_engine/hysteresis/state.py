from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from regime_engine.contracts.regimes import Regime

SCHEMA_NAME = "hysteresis_state"
SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class HysteresisConfig:
    window_updates: int = 3
    enter_threshold: float = 0.6
    commit_threshold: float = 0.6
    min_lead_over_anchor: float | None = None
    decay_step: int = 1
    allowed_regimes: Sequence[Regime] | None = None
    reset_max_gap_ms: int | None = None


@dataclass(frozen=True)
class HysteresisState:
    schema: str
    schema_version: str
    symbol: str
    engine_timestamp_ms: int
    anchor_regime: Regime
    candidate_regime: Regime | None
    progress_current: int
    progress_required: int
    last_commit_timestamp_ms: int | None
    reason_codes: tuple[str, ...]
    debug: Mapping[str, object] | None = None


@dataclass
class HysteresisStore:
    states: dict[str, HysteresisState]

    def state_for(self, symbol: str) -> HysteresisState | None:
        return self.states.get(symbol)

    def update(self, symbol: str, state: HysteresisState) -> None:
        self.states[symbol] = state
