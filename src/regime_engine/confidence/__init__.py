from __future__ import annotations

from collections.abc import Callable

from regime_engine.confidence.pillars import compute_pillar_agreement
from regime_engine.confidence.types import (
    ConfidenceBreakdown,
    ConfidenceResult,
    PillarAgreement,
)
from regime_engine.resolution.types import ResolutionResult


def synthesize_confidence(
    resolution: ResolutionResult,
    *,
    spread_transform: Callable[[float], float],
    agreement_transform: Callable[[float], float],
    veto_penalty_transform: Callable[[bool], float],
) -> ConfidenceResult:
    winner = resolution.winner
    runner_up = resolution.runner_up

    if winner is None:
        pillar_agreement = PillarAgreement(
            winner_pillars=frozenset(),
            runner_up_pillars=None,
            overlap_count=None,
            union_count=None,
            overlap_ratio=None,
        )
        breakdown = ConfidenceBreakdown(
            score_spread=None,
            pillar_overlap_ratio=None,
            veto_present=any(v.vetoed for v in resolution.vetoes),
        )
        return ConfidenceResult(
            confidence=None,
            breakdown=breakdown,
            pillar_agreement=pillar_agreement,
        )

    pillar_agreement = compute_pillar_agreement(winner, runner_up)
    spread = resolution.confidence_inputs.score_spread
    overlap_ratio = pillar_agreement.overlap_ratio
    veto_present = any(v.vetoed for v in resolution.vetoes)

    spread_value = spread if spread is not None else 0.0
    overlap_value = overlap_ratio if overlap_ratio is not None else 0.0
    combined = agreement_transform(overlap_value) + spread_transform(spread_value)

    combined *= veto_penalty_transform(veto_present)

    breakdown = ConfidenceBreakdown(
        score_spread=spread,
        pillar_overlap_ratio=overlap_ratio,
        veto_present=veto_present,
    )

    return ConfidenceResult(
        confidence=combined,
        breakdown=breakdown,
        pillar_agreement=pillar_agreement,
    )
