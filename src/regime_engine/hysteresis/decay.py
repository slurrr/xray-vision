from __future__ import annotations


def apply_confidence_decay(
    confidence: float,
    *,
    candidate_count: int,
    decay_factor: float,
    min_confidence_floor: float,
) -> float:
    decayed = confidence * (decay_factor**candidate_count)
    return max(decayed, min_confidence_floor)
