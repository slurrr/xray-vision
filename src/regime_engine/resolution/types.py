from __future__ import annotations

from dataclasses import dataclass

from regime_engine.contracts.regimes import RegimeScore
from regime_engine.veto.types import VetoResult


@dataclass(frozen=True)
class ConfidenceInputs:
    """
    Derived inputs used later for confidence calibration.

    Invariants:
    - top_score is None when no eligible (non-vetoed) scores exist.
    - runner_up_score is None when fewer than two eligible scores exist.
    - score_spread and contributor_overlap_count are None unless both top and runner-up exist.
    """

    top_score: float | None
    runner_up_score: float | None
    score_spread: float | None
    contributor_overlap_count: int | None


@dataclass(frozen=True)
class ResolutionResult:
    winner: RegimeScore | None
    runner_up: RegimeScore | None
    ranked: list[RegimeScore]
    vetoes: list[VetoResult]
    confidence_inputs: ConfidenceInputs
