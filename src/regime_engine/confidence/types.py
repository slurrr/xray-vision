from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PillarAgreement:
    winner_pillars: frozenset[str]
    runner_up_pillars: frozenset[str] | None
    overlap_count: int | None
    union_count: int | None
    overlap_ratio: float | None


@dataclass(frozen=True)
class ConfidenceBreakdown:
    score_spread: float | None
    pillar_overlap_ratio: float | None
    veto_present: bool


@dataclass(frozen=True)
class ConfidenceResult:
    """
    Final confidence synthesis result.

    Invariant: confidence is None iff no winner exists; otherwise it is a real number.
    """

    confidence: float | None
    breakdown: ConfidenceBreakdown
    pillar_agreement: PillarAgreement
