from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EvidenceDirection = Literal["UP", "DOWN", "NEUTRAL"]


@dataclass(frozen=True)
class EvidenceOpinion:
    type: str
    direction: EvidenceDirection
    strength: float
    confidence: float
    source: str
