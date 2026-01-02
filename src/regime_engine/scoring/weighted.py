from __future__ import annotations

from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.scoring.types import VetoedScores


def apply_weights(
    vetoed: VetoedScores,
    *,
    weights: dict[Regime, float],
) -> list[RegimeScore]:
    weighted = []
    for score in vetoed.scores:
        weight = weights.get(score.regime, 1.0)
        weighted.append(
            RegimeScore(
                regime=score.regime,
                score=score.score * weight,
                contributors=list(score.contributors),
            )
        )
    return weighted
