from __future__ import annotations

from regime_engine.matrix.types import MatrixInterpreter, RegimeInfluence, RegimeInfluenceSet
from regime_engine.state.evidence import EvidenceOpinion, EvidenceSnapshot


class ShadowMatrixInterpreter(MatrixInterpreter):
    def interpret(self, evidence: EvidenceSnapshot) -> RegimeInfluenceSet:
        influences = tuple(_from_opinion(opinion) for opinion in evidence.opinions)
        return RegimeInfluenceSet(
            symbol=evidence.symbol,
            engine_timestamp_ms=evidence.engine_timestamp_ms,
            influences=influences,
        )


def _from_opinion(opinion: EvidenceOpinion) -> RegimeInfluence:
    return RegimeInfluence(
        regime=opinion.regime,
        strength=opinion.strength,
        confidence=opinion.confidence,
        source=opinion.source,
    )
