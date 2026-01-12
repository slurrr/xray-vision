from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardConfig:
    refresh_cadence_ms: int
    default_time_window_ms: int
    enabled_views: Sequence[str]


def validate_config(config: DashboardConfig) -> None:
    if config.refresh_cadence_ms < 0:
        raise ValueError("refresh_cadence_ms must be >= 0")
    if config.default_time_window_ms < 0:
        raise ValueError("default_time_window_ms must be >= 0")
    for view in config.enabled_views:
        if not view:
            raise ValueError("enabled_views entries must be non-empty")
