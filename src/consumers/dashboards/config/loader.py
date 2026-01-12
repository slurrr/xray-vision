from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from importlib import resources

from consumers.dashboards.config.schema import DashboardConfig, validate_config

_ROOT_KEYS = {"refresh_cadence_ms", "default_time_window_ms", "enabled_views"}


def load_default_config() -> DashboardConfig:
    payload = _load_default_payload()
    config = _parse_config(payload)
    validate_config(config)
    return config


def _load_default_payload() -> Mapping[str, object]:
    text = (
        resources.files("consumers.dashboards.config")
        .joinpath("default.yaml")
        .read_text(encoding="utf-8")
    )
    yaml = importlib.import_module("yaml")
    data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise ValueError("dashboards default config must be a mapping")
    return data


def _parse_config(payload: Mapping[str, object]) -> DashboardConfig:
    _reject_unknown(payload, _ROOT_KEYS, "dashboards config")
    refresh_cadence_ms = payload.get("refresh_cadence_ms")
    default_time_window_ms = payload.get("default_time_window_ms")
    enabled_views = payload.get("enabled_views")
    if not isinstance(refresh_cadence_ms, int):
        raise ValueError("refresh_cadence_ms must be an int")
    if not isinstance(default_time_window_ms, int):
        raise ValueError("default_time_window_ms must be an int")
    if not isinstance(enabled_views, Sequence) or isinstance(enabled_views, (str, bytes)):
        raise ValueError("enabled_views must be a list")
    return DashboardConfig(
        refresh_cadence_ms=refresh_cadence_ms,
        default_time_window_ms=default_time_window_ms,
        enabled_views=[str(item) for item in enabled_views],
    )


def _reject_unknown(payload: Mapping[str, object], allowed: set[str], label: str) -> None:
    unknown = set(payload.keys()) - allowed
    if unknown:
        unknown_list = ", ".join(sorted(str(item) for item in unknown))
        raise ValueError(f"unknown {label} keys: {unknown_list}")
