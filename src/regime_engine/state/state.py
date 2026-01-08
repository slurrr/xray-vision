from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from regime_engine.contracts.regimes import Regime

SCHEMA_NAME = "regime_state"
SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class RegimeState:
    schema: str
    schema_version: str
    symbol: str
    engine_timestamp_ms: int   # transitional; will move out once state is persistent
    belief_by_regime: Mapping[Regime, float]
    anchor_regime: Regime
