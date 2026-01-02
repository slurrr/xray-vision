from __future__ import annotations

from regime_engine.confidence.types import PillarAgreement
from regime_engine.contracts.regimes import RegimeScore


def contributor_to_pillar(contributor: str) -> str:
    prefix, _, _ = contributor.partition(".")
    return prefix or "unknown"


def contributors_to_pillars(contributors: list[str]) -> frozenset[str]:
    return frozenset(contributor_to_pillar(item) for item in contributors)


def compute_pillar_agreement(
    winner: RegimeScore,
    runner_up: RegimeScore | None,
) -> PillarAgreement:
    """Compute pillar overlap; 'unknown' is excluded from overlap/union ratios."""
    winner_pillars = contributors_to_pillars(winner.contributors)
    if runner_up is None:
        return PillarAgreement(
            winner_pillars=winner_pillars,
            runner_up_pillars=None,
            overlap_count=None,
            union_count=None,
            overlap_ratio=None,
        )

    runner_up_pillars = contributors_to_pillars(runner_up.contributors)
    overlap = set(winner_pillars).intersection(runner_up_pillars)
    union = set(winner_pillars).union(runner_up_pillars)

    overlap.discard("unknown")
    union.discard("unknown")

    overlap_count = len(overlap)
    union_count = len(union)
    overlap_ratio = overlap_count / union_count if union_count else 0.0

    return PillarAgreement(
        winner_pillars=winner_pillars,
        runner_up_pillars=runner_up_pillars,
        overlap_count=overlap_count,
        union_count=union_count,
        overlap_ratio=overlap_ratio,
    )
