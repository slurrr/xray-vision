from __future__ import annotations

from dataclasses import dataclass

from regime_engine.contracts.regimes import RegimeScore
from regime_engine.veto.types import VetoResult


@dataclass(frozen=True)
class UnweightedScores:
    scores: list[RegimeScore]


@dataclass(frozen=True)
class VetoedScores:
    scores: list[RegimeScore]
    vetoes: list[VetoResult]
