from __future__ import annotations

from composer.contracts.evidence_snapshot import SCHEMA_NAME, SCHEMA_VERSION, EvidenceSnapshot
from composer.contracts.feature_snapshot import FeatureSnapshot
from composer.contracts.ordering import order_evidence_opinions
from composer.evidence.observers import OBSERVERS_V1


def compute_evidence_snapshot(snapshot: FeatureSnapshot) -> EvidenceSnapshot:
    opinions = []
    for observer in OBSERVERS_V1:
        opinions.extend(observer.emit(snapshot))
    ordered = tuple(order_evidence_opinions(opinions))
    return EvidenceSnapshot(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=snapshot.symbol,
        engine_timestamp_ms=snapshot.engine_timestamp_ms,
        opinions=ordered,
    )
