from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

REGIME_OPINION: Final[str] = "REGIME_OPINION"
FLOW_PRESSURE_OPINION: Final[str] = "FLOW_PRESSURE_OPINION"
VOLATILITY_REGIME_OPINION: Final[str] = "VOLATILITY_REGIME_OPINION"


@dataclass(frozen=True)
class EvidenceObserverDefinition:
    observer_id: str
    source_id: str
    may_emit: Sequence[str]


EVIDENCE_OBSERVERS_V1: Sequence[EvidenceObserverDefinition] = (
    EvidenceObserverDefinition(
        observer_id="classical_regime_v1",
        source_id="composer.classical",
        may_emit=(REGIME_OPINION,),
    ),
    EvidenceObserverDefinition(
        observer_id="flow_pressure_v1",
        source_id="composer.flow",
        may_emit=(FLOW_PRESSURE_OPINION,),
    ),
    EvidenceObserverDefinition(
        observer_id="volatility_context_v1",
        source_id="composer.volatility",
        may_emit=(VOLATILITY_REGIME_OPINION,),
    ),
)
