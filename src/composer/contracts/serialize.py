from __future__ import annotations

from collections.abc import Mapping

from composer.contracts.evidence_opinion import EvidenceOpinion
from composer.contracts.evidence_snapshot import EvidenceSnapshot
from composer.contracts.feature_snapshot import FeatureSnapshot
from composer.contracts.ordering import order_evidence_opinions, ordered_feature_items


def feature_snapshot_to_dict(snapshot: FeatureSnapshot) -> dict[str, object]:
    features = {key: value for key, value in ordered_feature_items(snapshot.features)}
    return {
        "schema": snapshot.schema,
        "schema_version": snapshot.schema_version,
        "symbol": snapshot.symbol,
        "engine_timestamp_ms": snapshot.engine_timestamp_ms,
        "features": features,
    }


def evidence_opinion_to_dict(opinion: EvidenceOpinion) -> Mapping[str, object]:
    return {
        "type": opinion.type,
        "direction": opinion.direction,
        "strength": opinion.strength,
        "confidence": opinion.confidence,
        "source": opinion.source,
    }


def evidence_snapshot_to_dict(snapshot: EvidenceSnapshot) -> dict[str, object]:
    opinions = [evidence_opinion_to_dict(op) for op in order_evidence_opinions(snapshot.opinions)]
    return {
        "schema": snapshot.schema,
        "schema_version": snapshot.schema_version,
        "symbol": snapshot.symbol,
        "engine_timestamp_ms": snapshot.engine_timestamp_ms,
        "opinions": opinions,
    }
