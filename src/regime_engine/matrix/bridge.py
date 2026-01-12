from __future__ import annotations

import math
from collections.abc import Sequence

from regime_engine.matrix.types import RegimeInfluence, RegimeInfluenceSet
from regime_engine.state.evidence import EvidenceOpinion, EvidenceSnapshot


def influences_to_evidence_snapshot(
    influence_set: RegimeInfluenceSet,
) -> EvidenceSnapshot:
    opinions: list[EvidenceOpinion] = []
    for influence in influence_set.influences:
        _validate_influence(influence)
        opinions.append(
            EvidenceOpinion(
                regime=influence.regime,
                strength=influence.strength,
                confidence=influence.confidence,
                source=influence.source,
            )
        )
    ordered = tuple(_order_opinions(opinions))
    return EvidenceSnapshot(
        symbol=influence_set.symbol,
        engine_timestamp_ms=influence_set.engine_timestamp_ms,
        opinions=ordered,
    )


def _validate_influence(influence: RegimeInfluence) -> None:
    if not _is_bounded_unit(influence.strength):
        raise ValueError("influence strength out of bounds")
    if not _is_bounded_unit(influence.confidence):
        raise ValueError("influence confidence out of bounds")


def _is_bounded_unit(value: float) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    if not math.isfinite(value):
        return False
    return 0.0 <= float(value) <= 1.0


def _order_opinions(opinions: Sequence[EvidenceOpinion]) -> list[EvidenceOpinion]:
    return sorted(
        opinions,
        key=lambda opinion: (
            opinion.regime.value,
            opinion.source,
            -opinion.confidence,
            -opinion.strength,
        ),
    )
