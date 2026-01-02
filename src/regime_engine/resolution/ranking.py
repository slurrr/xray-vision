from __future__ import annotations

from regime_engine.contracts.regimes import Regime, RegimeScore


def rank_scores(scores: list[RegimeScore]) -> list[RegimeScore]:
    """Rank scores deterministically: score desc, then Regime enum order."""
    order = {regime: index for index, regime in enumerate(Regime)}
    return sorted(
        scores,
        key=lambda score: (-score.score, order.get(score.regime, len(order))),
    )
