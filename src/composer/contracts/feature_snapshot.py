from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

SCHEMA_NAME: Final[str] = "feature_snapshot"
SCHEMA_VERSION: Final[str] = "1"

FEATURE_KEYS_V1_CANONICAL: Sequence[str] = (
    "price_last",
    "vwap_3m",
    "atr_14",
    "atr_z_50",
    "cvd_3m",
    "aggressive_volume_ratio_3m",
    "open_interest_latest",
)

FEATURE_KEY_ALIASES: Mapping[str, str] = {
    "price": "price_last",
    "vwap": "vwap_3m",
    "atr": "atr_14",
    "atr_z": "atr_z_50",
    "cvd": "cvd_3m",
    "open_interest": "open_interest_latest",
}

FEATURE_KEYS_V1: Sequence[str] = FEATURE_KEYS_V1_CANONICAL


def feature_value(
    features: Mapping[str, float | None],
    key: str,
) -> float | None:
    value = features.get(key)
    if value is not None:
        return value
    canonical = FEATURE_KEY_ALIASES.get(key)
    if canonical is not None:
        value = features.get(canonical)
        if value is not None:
            return value
    for alias, canonical_key in FEATURE_KEY_ALIASES.items():
        if canonical_key != key:
            continue
        value = features.get(alias)
        if value is not None:
            return value
    return None


@dataclass(frozen=True)
class FeatureSnapshot:
    schema: str
    schema_version: str
    symbol: str
    engine_timestamp_ms: int
    features: Mapping[str, float | None]
