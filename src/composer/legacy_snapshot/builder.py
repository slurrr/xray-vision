from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import fields
from typing import Any

from composer.contracts.feature_snapshot import FeatureSnapshot, feature_value
from composer.engine_evidence.embedding import embed_engine_evidence
from market_data.contracts import RawMarketEvent
from regime_engine.contracts.snapshots import (
    MISSING,
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.state.evidence import EvidenceSnapshot


def build_legacy_snapshot(
    raw_events: Iterable[RawMarketEvent],
    *,
    symbol: str,
    engine_timestamp_ms: int,
    feature_snapshot: FeatureSnapshot,
    evidence_snapshot: EvidenceSnapshot,
) -> RegimeInputSnapshot:
    events = tuple(raw_events)
    snapshot_event = _select_snapshot_event(
        events,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
    )
    if snapshot_event is not None:
        legacy_snapshot = _build_from_snapshot_event(
            snapshot_event,
            symbol=symbol,
            engine_timestamp_ms=engine_timestamp_ms,
        )
    else:
        legacy_snapshot = _build_from_features(
            feature_snapshot,
            symbol=symbol,
            engine_timestamp_ms=engine_timestamp_ms,
        )
    return embed_engine_evidence(legacy_snapshot, evidence_snapshot)


def _select_snapshot_event(
    raw_events: Iterable[RawMarketEvent],
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> RawMarketEvent | None:
    selected: RawMarketEvent | None = None
    for event in raw_events:
        if event.event_type != "SnapshotInputs":
            continue
        if event.symbol != symbol:
            continue
        timestamp = event.normalized.get("timestamp_ms")
        if timestamp != engine_timestamp_ms:
            continue
        selected = event
    return selected


def _build_from_snapshot_event(
    snapshot_event: RawMarketEvent,
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> RegimeInputSnapshot:
    normalized = snapshot_event.normalized
    market = _build_dataclass(MarketSnapshot, normalized.get("market"))
    derivatives = _build_dataclass(DerivativesSnapshot, normalized.get("derivatives"))
    flow = _build_dataclass(FlowSnapshot, normalized.get("flow"))
    context = _build_dataclass(ContextSnapshot, normalized.get("context"))
    return RegimeInputSnapshot(
        symbol=symbol,
        timestamp=engine_timestamp_ms,
        market=market,
        derivatives=derivatives,
        flow=flow,
        context=context,
    )


def _build_from_features(
    feature_snapshot: FeatureSnapshot,
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> RegimeInputSnapshot:
    features = feature_snapshot.features
    market = MarketSnapshot(
        price=_feature_or_missing(features, "price_last"),
        vwap=_feature_or_missing(features, "vwap_3m"),
        atr=_feature_or_missing(features, "atr_14"),
        atr_z=_feature_or_missing(features, "atr_z_50"),
        range_expansion=MISSING,
        structure_levels={},
        acceptance_score=MISSING,
        sweep_score=MISSING,
    )
    derivatives = DerivativesSnapshot(
        open_interest=_feature_or_missing(features, "open_interest_latest"),
        oi_slope_short=MISSING,
        oi_slope_med=MISSING,
        oi_accel=MISSING,
        funding_rate=MISSING,
        funding_slope=MISSING,
        funding_z=MISSING,
        liquidation_intensity=MISSING,
    )
    flow = FlowSnapshot(
        cvd=_feature_or_missing(features, "cvd_3m"),
        cvd_slope=MISSING,
        cvd_efficiency=MISSING,
        aggressive_volume_ratio=MISSING,
    )
    context = ContextSnapshot(
        rs_vs_btc=MISSING,
        beta_to_btc=MISSING,
        alt_breadth=MISSING,
        btc_regime=None,
        eth_regime=None,
    )
    return RegimeInputSnapshot(
        symbol=symbol,
        timestamp=engine_timestamp_ms,
        market=market,
        derivatives=derivatives,
        flow=flow,
        context=context,
    )


def _feature_or_missing(
    features: Mapping[str, float | None],
    key: str,
) -> float | Any:
    value = feature_value(features, key)
    if value is None:
        return MISSING
    return value


def _build_dataclass(cls: type, payload: Any) -> Any:
    values: dict[str, Any] = {}
    mapping: Mapping[str, Any] | None = payload if isinstance(payload, Mapping) else None
    for field in fields(cls):
        if mapping is None or field.name not in mapping:
            values[field.name] = MISSING
        else:
            values[field.name] = mapping[field.name]
    return cls(**values)
