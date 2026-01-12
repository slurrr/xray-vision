from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from regime_engine.contracts.regimes import Regime
from regime_engine.state.evidence import EvidenceSnapshot


@dataclass(frozen=True)
class RegimeInfluence:
    regime: Regime
    strength: float
    confidence: float
    source: str


@dataclass(frozen=True)
class RegimeInfluenceSet:
    symbol: str
    engine_timestamp_ms: int
    influences: Sequence[RegimeInfluence]


class MatrixInterpreter(Protocol):
    def interpret(self, evidence: EvidenceSnapshot) -> RegimeInfluenceSet: ...
