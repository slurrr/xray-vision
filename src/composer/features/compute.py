from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from types import MappingProxyType

from composer.contracts.feature_snapshot import (
    FEATURE_KEYS_V1,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    FeatureSnapshot,
)
from composer.contracts.ordering import ordered_feature_items
from market_data.contracts import RawMarketEvent


def _latest_numeric_value(
    raw_events: Iterable[RawMarketEvent],
    *,
    symbol: str,
    key: str,
) -> float | None:
    latest: float | None = None
    for event in raw_events:
        if event.symbol != symbol:
            continue
        value = event.normalized.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and math.isfinite(value):
            latest = float(value)
    return latest


def compute_feature_snapshot(
    raw_events: Iterable[RawMarketEvent],
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> FeatureSnapshot:
    events = tuple(raw_events)
    features: Mapping[str, float | None] = {
        key: _latest_numeric_value(events, symbol=symbol, key=key)
        for key in FEATURE_KEYS_V1
    }
    ordered_features = {key: value for key, value in ordered_feature_items(features)}
    return FeatureSnapshot(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        features=MappingProxyType(ordered_features),
    )
