from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from composer.contracts.evidence_opinion import EvidenceOpinion

SCHEMA_NAME: Final[str] = "evidence_snapshot"
SCHEMA_VERSION: Final[str] = "1"


@dataclass(frozen=True)
class EvidenceSnapshot:
    schema: str
    schema_version: str
    symbol: str
    engine_timestamp_ms: int
    opinions: Sequence[EvidenceOpinion]
