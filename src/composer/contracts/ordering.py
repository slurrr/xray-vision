from __future__ import annotations

from collections.abc import Iterable, Mapping

from composer.contracts.evidence_opinion import EvidenceOpinion


def ordered_feature_items(
    features: Mapping[str, float | None],
) -> list[tuple[str, float | None]]:
    return sorted(features.items(), key=lambda item: item[0])


def evidence_opinion_sort_key(opinion: EvidenceOpinion) -> tuple:
    return (
        opinion.type,
        opinion.source,
        opinion.direction,
        -opinion.strength,
        -opinion.confidence,
    )


def order_evidence_opinions(
    opinions: Iterable[EvidenceOpinion],
) -> list[EvidenceOpinion]:
    return sorted(opinions, key=evidence_opinion_sort_key)
