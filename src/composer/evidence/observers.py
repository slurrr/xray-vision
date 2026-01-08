from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from composer.contracts.evidence_observers import (
    EVIDENCE_OBSERVERS_V1,
    FLOW_PRESSURE_OPINION,
    REGIME_OPINION,
    VOLATILITY_REGIME_OPINION,
)
from composer.contracts.evidence_opinion import EvidenceOpinion
from composer.contracts.feature_snapshot import FEATURE_KEYS_V1, FeatureSnapshot


@dataclass(frozen=True)
class EvidenceObserver:
    observer_id: str
    source_id: str
    opinion_type: str

    def emit(self, snapshot: FeatureSnapshot) -> Sequence[EvidenceOpinion]:
        raise NotImplementedError


def _availability_confidence(features: Mapping[str, float | None]) -> float:
    total = len(FEATURE_KEYS_V1)
    if total == 0:
        return 0.0
    available = sum(1 for key in FEATURE_KEYS_V1 if features.get(key) is not None)
    return available / total


def _emit_neutral(
    snapshot: FeatureSnapshot,
    *,
    opinion_type: str,
    source_id: str,
) -> Sequence[EvidenceOpinion]:
    confidence = _availability_confidence(snapshot.features)
    if confidence <= 0.0:
        return ()
    return (
        EvidenceOpinion(
            type=opinion_type,
            direction="NEUTRAL",
            strength=0.0,
            confidence=confidence,
            source=source_id,
        ),
    )


_OBSERVER_SOURCE_BY_ID = {
    definition.observer_id: definition.source_id for definition in EVIDENCE_OBSERVERS_V1
}


class ClassicalRegimeObserver(EvidenceObserver):
    def emit(self, snapshot: FeatureSnapshot) -> Sequence[EvidenceOpinion]:
        return _emit_neutral(
            snapshot,
            opinion_type=REGIME_OPINION,
            source_id=_OBSERVER_SOURCE_BY_ID[self.observer_id],
        )


class FlowPressureObserver(EvidenceObserver):
    def emit(self, snapshot: FeatureSnapshot) -> Sequence[EvidenceOpinion]:
        return _emit_neutral(
            snapshot,
            opinion_type=FLOW_PRESSURE_OPINION,
            source_id=_OBSERVER_SOURCE_BY_ID[self.observer_id],
        )


class VolatilityContextObserver(EvidenceObserver):
    def emit(self, snapshot: FeatureSnapshot) -> Sequence[EvidenceOpinion]:
        return _emit_neutral(
            snapshot,
            opinion_type=VOLATILITY_REGIME_OPINION,
            source_id=_OBSERVER_SOURCE_BY_ID[self.observer_id],
        )


OBSERVERS_V1: Sequence[EvidenceObserver] = (
    ClassicalRegimeObserver(
        observer_id="classical_regime_v1",
        source_id=_OBSERVER_SOURCE_BY_ID["classical_regime_v1"],
        opinion_type=REGIME_OPINION,
    ),
    FlowPressureObserver(
        observer_id="flow_pressure_v1",
        source_id=_OBSERVER_SOURCE_BY_ID["flow_pressure_v1"],
        opinion_type=FLOW_PRESSURE_OPINION,
    ),
    VolatilityContextObserver(
        observer_id="volatility_context_v1",
        source_id=_OBSERVER_SOURCE_BY_ID["volatility_context_v1"],
        opinion_type=VOLATILITY_REGIME_OPINION,
    ),
)
