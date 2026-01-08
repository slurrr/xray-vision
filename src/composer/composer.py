from __future__ import annotations

from collections.abc import Iterable

from composer.contracts.evidence_snapshot import EvidenceSnapshot
from composer.contracts.feature_snapshot import FeatureSnapshot
from composer.evidence.compute import compute_evidence_snapshot
from composer.features.compute import compute_feature_snapshot
from market_data.contracts import RawMarketEvent


def compose(
    raw_events: Iterable[RawMarketEvent],
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> tuple[FeatureSnapshot, EvidenceSnapshot]:
    events = tuple(raw_events)
    feature_snapshot = compute_feature_snapshot(
        events,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
    )
    evidence_snapshot = compute_evidence_snapshot(feature_snapshot)
    return feature_snapshot, evidence_snapshot
