from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from regime_engine.confidence.types import ConfidenceResult
from regime_engine.contracts.regimes import Regime
from regime_engine.resolution.types import ResolutionResult


@dataclass(frozen=True)
class EvidenceOpinion:
    regime: Regime
    strength: float
    confidence: float
    source: str


@dataclass(frozen=True)
class EvidenceSnapshot:
    symbol: str
    engine_timestamp_ms: int
    opinions: Sequence[EvidenceOpinion]


def build_classical_evidence(
    resolution: ResolutionResult,
    confidence: ConfidenceResult,
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> EvidenceSnapshot:
    winner = resolution.winner
    if winner is None:
        return EvidenceSnapshot(symbol=symbol, engine_timestamp_ms=engine_timestamp_ms, opinions=())

    confidence_value = confidence.confidence if confidence.confidence is not None else 0.0
    opinion = EvidenceOpinion(
        regime=winner.regime,
        strength=1.0,
        confidence=confidence_value,
        source="classical_resolution_v1",
    )
    return EvidenceSnapshot(
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        opinions=(opinion,),
    )
