from __future__ import annotations

from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.resolution.ranking import rank_scores
from regime_engine.resolution.types import ConfidenceInputs, ResolutionResult
from regime_engine.scoring.types import UnweightedScores
from regime_engine.scoring.weighted import apply_weights
from regime_engine.veto import apply_vetoes


def resolve_regime(
    candidates: list[RegimeScore],
    snapshot: RegimeInputSnapshot,
    *,
    weights: dict[Regime, float],
) -> ResolutionResult:
    """Resolve regime with order: veto -> weight -> rank -> resolve."""
    vetoed = apply_vetoes(UnweightedScores(scores=list(candidates)), snapshot)
    weighted = apply_weights(vetoed, weights=weights)

    vetoed_regimes = {result.regime for result in vetoed.vetoes if result.vetoed}
    eligible = [score for score in weighted if score.regime not in vetoed_regimes]

    ranked = rank_scores(eligible)
    winner = ranked[0] if ranked else None
    runner_up = ranked[1] if len(ranked) > 1 else None

    if winner is None:
        confidence_inputs = ConfidenceInputs(
            top_score=None,
            runner_up_score=None,
            score_spread=None,
            contributor_overlap_count=None,
        )
    elif runner_up is None:
        confidence_inputs = ConfidenceInputs(
            top_score=winner.score,
            runner_up_score=None,
            score_spread=None,
            contributor_overlap_count=None,
        )
    else:
        overlap = set(winner.contributors).intersection(runner_up.contributors)
        confidence_inputs = ConfidenceInputs(
            top_score=winner.score,
            runner_up_score=runner_up.score,
            score_spread=winner.score - runner_up.score,
            contributor_overlap_count=len(overlap),
        )

    return ResolutionResult(
        winner=winner,
        runner_up=runner_up,
        ranked=ranked,
        vetoes=list(vetoed.vetoes),
        confidence_inputs=confidence_inputs,
    )
