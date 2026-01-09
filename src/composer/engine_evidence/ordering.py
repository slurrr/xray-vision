from __future__ import annotations

from collections.abc import Iterable

from regime_engine.state.evidence import EvidenceOpinion


def order_engine_evidence_opinions(
    opinions: Iterable[EvidenceOpinion],
) -> list[EvidenceOpinion]:
    return sorted(
        opinions,
        key=lambda opinion: (
            opinion.regime.value,
            opinion.source,
            -opinion.confidence,
            -opinion.strength,
        ),
    )
