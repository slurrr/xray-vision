from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

SCHEMA_NAME: Final[str] = "feature_snapshot"
SCHEMA_VERSION: Final[str] = "1"

FEATURE_KEYS_V1: Sequence[str] = (
    "price",
    "vwap",
    "atr",
    "atr_z",
    "cvd",
    "open_interest",
)


@dataclass(frozen=True)
class FeatureSnapshot:
    schema: str
    schema_version: str
    symbol: str
    engine_timestamp_ms: int
    features: Mapping[str, float | None]
