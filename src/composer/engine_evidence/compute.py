from __future__ import annotations

from composer.contracts.feature_snapshot import FeatureSnapshot
from composer.engine_evidence.observers import OBSERVERS_V1
from composer.engine_evidence.ordering import order_engine_evidence_opinions
from composer.observability import get_observability
from regime_engine.state.evidence import EvidenceSnapshot


def compute_engine_evidence_snapshot(
    snapshot: FeatureSnapshot,
) -> EvidenceSnapshot:
    opinions = []
    for observer in OBSERVERS_V1:
        opinions.extend(observer.emit(snapshot))
    ordered = tuple(order_engine_evidence_opinions(opinions))
    regimes: list[str] = []
    seen: set[str] = set()
    for opinion in ordered:
        regime_value = opinion.regime.value
        if regime_value in seen:
            continue
        seen.add(regime_value)
        regimes.append(regime_value)
    get_observability().log_evidence_emitted(
        symbol=snapshot.symbol,
        engine_timestamp_ms=snapshot.engine_timestamp_ms,
        opinion_count=len(ordered),
        regimes=regimes,
    )
    return EvidenceSnapshot(
        symbol=snapshot.symbol,
        engine_timestamp_ms=snapshot.engine_timestamp_ms,
        opinions=ordered,
    )
